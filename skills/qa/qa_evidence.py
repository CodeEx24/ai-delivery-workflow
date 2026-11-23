#!/usr/bin/env python3
"""Check QA evidence, bug handoffs and retest results.

  python qa_evidence.py scan --run DIR [--repo .] [--json]
  python qa_evidence.py evidence --run DIR --uploaded FILE [--repo .] [--json]
  python qa_evidence.py handoff --bug FILE [--repo .] [--json]
  python qa_evidence.py retest --prior FILE --current FILE [--tested-sha SHA] [--out FILE] [--json]

Findings name the file, line and kind. They never include the matched text.
Exit codes: 0 ok or passed, 1 findings, incomplete or failed, 2 error, 3 retest blocked.
Standard library only.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path

TEXT_SUFFIXES = {".md", ".json", ".txt", ".log", ".har", ".csv", ".html", ".xml", ".yaml", ".yml"}
VISUAL_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".webm", ".mp4"}
SAFE_EMAIL = re.compile(
    r"@(?:[\w-]+\.)*(?:example\.(?:com|org|net)|example|invalid|test|localhost)$", re.I
)
NOT_REDACTED = r"(?!\[?redacted|\*{3}|<)"
PATTERNS = (
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("authorization header",
     re.compile(r"\b(?:proxy-)?authorization[\"']?\s*[:=]\s*[\"']?" + NOT_REDACTED + r"\S+", re.I)),
    ("cookie", re.compile(r"\b(?:set-)?cookie[\"']?\s*[:=]\s*[\"']?" + NOT_REDACTED + r"[^\s\"';=]+=", re.I)),
    ("bearer token", re.compile(r"\bbearer\s+" + NOT_REDACTED + r"[a-z0-9._~+/=-]{12,}", re.I)),
    ("jwt", re.compile(r"\beyJ[\w-]{6,}\.[\w-]{6,}\.[\w-]{6,}")),
    ("access key", re.compile(r"\b(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abprs]-[\w-]{10,}|sk-[\w-]{20,})\b")),
    ("credential assignment",
     re.compile(r"\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token)"
                r"[\"']?\s*[:=]\s*[\"']?(?!\[?redacted|<|null\b|none\b|true\b|false\b|\*+)"
                r"[^\s\"',}]{4,}", re.I)),
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
CARD_RE = re.compile(r"\b(?:\d{4}[ -]?){3}\d{1,7}\b")
RUN_ID_RE = re.compile(r"\b\d{8}-\d{6}\b")
ID_RE = re.compile(r"^[A-Za-z0-9-]{1,40}$")
STATUSES = ("planned", "passed", "failed", "blocked")

HANDOFF_SECTIONS = {
    "Source": ("Source ticket", "QA run"),
    "Environment": ("Environment", "URL", "Deployed SHA", "Browser", "Viewport", "Account role"),
    "Preconditions and test data": (),
    "Reproduction steps": (),
    "Failing scenarios": ("Scenario", "Acceptance criteria"),
    "Console and network": (),
    "Suspected area (hypothesis)": (),
    "Regression risk": (),
    "Commands": ("Reproduce", "Retest"),
    "Evidence": ("Evidence status",),
}


class EvidenceError(Exception):
    pass


def luhn(digits):
    total = 0
    for index, char in enumerate(reversed(digits)):
        number = int(char)
        if index % 2:
            number = number * 2 - 9 if number > 4 else number * 2
        total += number
    return total % 10 == 0


def known_secrets(repo):
    """Values of the project's QA secrets, kept only in memory to compare against evidence."""
    if not repo:
        return {}
    path = Path(__file__).resolve().parents[1] / "qa-config" / "qa_config.py"
    if not path.is_file():
        return {}
    spec = importlib.util.spec_from_file_location("qa_config_for_evidence", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        root = module.repo_root(repo)
        secrets = module.secrets_path(root)
    except module.QaError:
        return {}
    values = {}
    if secrets is not None:
        for line in secrets.read_bytes().decode("utf-8-sig", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.removeprefix("export ").partition("=")
            value = value.strip().strip("\"'")
            if len(value) >= 6:
                values[value] = name.strip()
    return values


def scan_text(text, label, secrets):
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        kinds = {kind for kind, pattern in PATTERNS if pattern.search(line)}
        for value, name in secrets.items():
            if value in line:
                kinds.add(f"value of {name}")
        for match in EMAIL_RE.findall(line):
            if not SAFE_EMAIL.search(match):
                kinds.add("email address")
        if not RUN_ID_RE.search(line):
            for match in CARD_RE.finditer(line):
                digits = re.sub(r"\D", "", match.group())
                if 13 <= len(digits) <= 19 and luhn(digits):
                    kinds.add("payment card number")
        findings += [{"file": label, "line": number, "kind": kind} for kind in sorted(kinds)]
    return findings


def scan_run(run, repo):
    if not run.is_dir():
        raise EvidenceError("--run is not a folder")
    secrets = known_secrets(repo)
    findings, visual, unscannable = [], [], []
    for path in sorted(p for p in run.rglob("*") if p.is_file()):
        label = path.relative_to(run).as_posix()
        suffix = path.suffix.lower()
        if suffix in VISUAL_SUFFIXES:
            visual.append(label)
        elif suffix in TEXT_SUFFIXES:
            text = path.read_bytes().decode("utf-8", errors="replace")
            findings += scan_text(text, label, secrets)
        else:
            unscannable.append(label)
    return {"ok": not findings and not unscannable, "findings": findings,
            "unscannable": unscannable, "needsVisualReview": visual}


def inventory(run):
    required = [name for name in ("report.md", "scenarios.json") if (run / name).is_file()]
    shots = sorted(p.relative_to(run).as_posix() for p in (run / "screenshots").glob("*")
                   if p.is_file()) if (run / "screenshots").is_dir() else []
    logs = sorted(p.relative_to(run).as_posix() for p in (run / "logs").rglob("*")
                  if p.is_file()) if (run / "logs").is_dir() else []
    return required, shots, logs


def check_evidence(run, uploaded_file, repo):
    scan = scan_run(run, repo)
    required, shots, logs = inventory(run)
    try:
        uploaded = {line.strip().replace("\\", "/").rsplit("/", 1)[-1]
                    for line in uploaded_file.read_text(encoding="utf-8-sig").splitlines()
                    if line.strip()}
    except OSError:
        raise EvidenceError("cannot read --uploaded")
    expected = required + shots + logs
    missing = [name for name in expected if name.rsplit("/", 1)[-1] not in uploaded]
    for name in ("report.md", "scenarios.json"):
        if name not in required:
            missing.append(f"{name} (not in the run folder)")
    if not shots:
        missing.append("step screenshots (none in the run folder)")
    if not logs:
        missing.append("sanitized logs (none in the run folder)")
    complete = not missing and scan["ok"]
    return {"status": "complete" if complete else "Evidence incomplete",
            "label": None if complete else "qa:evidence-missing", "missing": missing,
            "screenshotsInOrder": shots, "unsafe": scan["findings"],
            "unscannable": scan["unscannable"], "needsVisualReview": scan["needsVisualReview"]}


def section_body(text, heading):
    match = re.search(rf"^###\s+{re.escape(heading)}\s*$", text, re.M)
    if not match:
        return None
    rest = text[match.end():]
    end = re.search(r"^#{2,3}\s", rest, re.M)
    return (rest[:end.start()] if end else rest).strip()


def check_handoff(path, repo):
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        raise EvidenceError("cannot read --bug")
    problems = []
    if not re.search(r"^##\s+Engineering handoff\s*$", text, re.M):
        problems.append("missing '## Engineering handoff'")
    for heading, labels in HANDOFF_SECTIONS.items():
        body = section_body(text, heading)
        if not body:
            problems.append(f"missing or empty section: {heading}")
            continue
        for label in labels:
            if label.lower() not in body.lower():
                problems.append(f"{heading}: missing {label}")
    steps = section_body(text, "Reproduction steps") or ""
    rows = [r for r in steps.splitlines() if re.match(r"^\|\s*\d+\s*\|", r)]
    if not rows:
        problems.append("Reproduction steps: needs numbered table rows")
    for row in rows:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) < 5 or not all(cells):
            problems.append(f"Reproduction step {cells[0]}: needs action, screenshot, expected, actual")
        elif not re.search(r"\.(png|jpe?g|webp)\b", cells[2], re.I) and "no screenshot" not in cells[2].lower():
            problems.append(f"Reproduction step {cells[0]}: needs a screenshot filename")
    evidence = section_body(text, "Evidence") or ""
    if re.search(r"evidence incomplete", evidence, re.I):
        if not re.search(r"^\s*[-*]?\s*Missing:\s*\S", evidence, re.I | re.M):
            problems.append("Evidence: 'Evidence incomplete' must list what is Missing")
        if "qa:evidence-missing" not in text:
            problems.append("Evidence: 'Evidence incomplete' needs the qa:evidence-missing label")
    elif not re.search(r"evidence status:\s*\**\s*complete", evidence, re.I):
        problems.append("Evidence: status must be complete or Evidence incomplete")
    unsafe = scan_text(text, path.name, known_secrets(repo))
    return {"ok": not problems and not unsafe, "problems": problems, "unsafe": unsafe}


def load_scenarios(path, label):
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise EvidenceError(f"{label} is not readable JSON")
    rows = data.get("scenarios") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise EvidenceError(f"{label} has no scenarios list")
    out = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not ID_RE.fullmatch(row["id"]):
            raise EvidenceError(f"{label} has a scenario with an invalid id")
        if row["id"] in out:
            raise EvidenceError(f"{label} repeats scenario {row['id']}")
        if row.get("status") not in STATUSES:
            raise EvidenceError(f"{label}: scenario {row['id']} has an invalid status")
        out[row["id"]] = row
    return out


def has_proof(row):
    return bool(row.get("screenshots") or row.get("logs"))


def compare(prior, current, tested_sha=None):
    groups = {"previouslyFailedNowPassing": [], "stillFailing": [], "newlyFailing": [],
              "notRun": [], "stillPassing": [], "newPassing": []}
    required_gap = []
    for sid in list(prior) + [s for s in current if s not in prior]:
        before, after = prior.get(sid), current.get(sid)
        was_failed = bool(before) and before["status"] == "failed"
        source = before if before else after
        required = was_failed or source.get("required", True) is not False
        state = (after or {}).get("status")
        if state == "passed" and not has_proof(after):
            state = "unproven"
        if state == "passed":
            key = "previouslyFailedNowPassing" if was_failed else "stillPassing" if before else "newPassing"
            groups[key].append(sid)
        elif state == "failed":
            groups["stillFailing" if was_failed else "newlyFailing"].append(sid)
        else:
            groups["notRun"].append(sid)
            if required:
                required_gap.append(sid)
    if not prior:
        result, reason = "BLOCKED", "the prior run has no scenarios"
    elif groups["newlyFailing"] or groups["stillFailing"]:
        result, reason = "FAILED", "a scenario failed"
    elif required_gap:
        result, reason = "BLOCKED", "required scenarios were not run or have no proof"
    elif not tested_sha:
        result, reason = "BLOCKED", "the tested commit was not recorded"
    elif groups["notRun"]:
        result, reason = "PASSED WITH NOTES", "optional scenarios were not run"
    else:
        result, reason = "PASSED", "every scenario passed with proof"
    return {"result": result, "reason": reason, "testedSha": tested_sha, **groups,
            "requiredNotRun": required_gap,
            "counts": {key: len(value) for key, value in groups.items()}}


def write_json(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(body, handle, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "error: invalid arguments. Run with --help for usage.\n")


def build_parser():
    parser = SafeParser(description="QA evidence, handoff and retest checks")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("--run", required=True, type=Path)
    evidence = sub.add_parser("evidence")
    evidence.add_argument("--run", required=True, type=Path)
    evidence.add_argument("--uploaded", required=True, type=Path)
    handoff = sub.add_parser("handoff")
    handoff.add_argument("--bug", required=True, type=Path)
    retest = sub.add_parser("retest")
    retest.add_argument("--prior", required=True, type=Path)
    retest.add_argument("--current", required=True, type=Path)
    retest.add_argument("--tested-sha")
    retest.add_argument("--out", type=Path)
    for cmd in (scan, evidence, handoff):
        cmd.add_argument("--repo")
    for cmd in (scan, evidence, handoff, retest):
        cmd.add_argument("--json", action="store_true")
    return parser


def print_summary(body):
    for key, value in body.items():
        if value not in ([], None):
            print(f"{key}: {json.dumps(value)}")


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        if args.command == "scan":
            body = scan_run(args.run, args.repo)
            code = 0 if body["ok"] else 1
        elif args.command == "evidence":
            body = check_evidence(args.run, args.uploaded, args.repo)
            code = 0 if body["status"] == "complete" else 1
        elif args.command == "handoff":
            body = check_handoff(args.bug, args.repo)
            code = 0 if body["ok"] else 1
        else:
            if args.tested_sha and not re.fullmatch(r"[0-9a-fA-F]{7,40}", args.tested_sha):
                raise EvidenceError("--tested-sha must be a commit SHA")
            body = compare(load_scenarios(args.prior, "--prior"),
                           load_scenarios(args.current, "--current"), args.tested_sha)
            if args.out:
                write_json(args.out, body)
            code = {"FAILED": 1, "BLOCKED": 3}.get(body["result"], 0)
    except EvidenceError as exc:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(body, indent=2))
    else:
        print_summary(body)
    return code


if __name__ == "__main__":
    sys.exit(main())
