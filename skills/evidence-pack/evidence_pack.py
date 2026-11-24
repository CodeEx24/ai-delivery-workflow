#!/usr/bin/env python3
"""Build a labeled evidence PDF for a test run, and an Evidence Index for a ticket.

  python evidence_pack.py build --scenarios FILE --ticket ABC-123 --stage DEV|QA|FIX|RETEST
      --round N --title "Ticket title" --out DIR --visual-reviewed
      [--before PRIOR_SCENARIOS] [--responds-to FILE_NAME] [--sha SHA] [--at ISO] [--repo .] [--json]
  python evidence_pack.py index --ticket ABC-123 --names FILE [--focus TEXT]
      [--format markdown|jira|text] [--json]
  python evidence_pack.py parse --name FILE_NAME [--json]

The tracker is not involved here: any tracker that keeps file names can drive the index.
Exit codes: 0 ok, 1 unsafe evidence, 2 error. Standard library plus a Chromium browser.
"""
import argparse
import base64
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

STAGES = ("DEV", "QA", "FIX", "RETEST")
RESULTS = ("PASSED", "NOTES", "FAILED", "BLOCKED")
KEY = r"[A-Z][A-Z0-9]{0,9}-[0-9]+"
KEY_RE = re.compile(rf"^{KEY}$")
NAME_RE = re.compile(rf"^(?P<ticket>{KEY})_(?P<stage>DEV|QA|FIX|RETEST)_R(?P<round>[1-9][0-9]*)_"
                     r"(?P<result>PASSED|NOTES|FAILED|BLOCKED)_(?P<slug>[a-z0-9-]+)_"
                     r"(?P<stamp>\d{8}-\d{4}Z)_(?P<sha>[0-9a-f]{7}|unknown)\.pdf$")
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
LABELS = {"PASSED": "PASSED", "NOTES": "PASSED WITH NOTES", "FAILED": "FAILED", "BLOCKED": "BLOCKED"}
ICONS = {"PASSED": "✅", "NOTES": "⚠️", "FAILED": "❌", "BLOCKED": "🚫"}
STAGE_NAMES = {"DEV": "Development test", "QA": "QA test", "FIX": "Fix verification", "RETEST": "QA retest"}
SIZE_WARNING = 10 * 1024 * 1024


class PackError(Exception):
    pass


class UnsafeEvidence(Exception):
    def __init__(self, body):
        super().__init__("unsafe evidence")
        self.body = body


def load_checks():
    path = Path(__file__).resolve().parents[1] / "qa" / "qa_evidence.py"
    if not path.is_file():
        raise PackError("the qa skill is missing, so evidence cannot be scanned. Reinstall the kit")
    spec = importlib.util.spec_from_file_location("qa_evidence_for_pack", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def slugify(text, limit=6):
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return "-".join(words[:limit]) or "untitled"


def short_sha(value):
    value = (value or "").strip().lower()
    return value[:7] if re.fullmatch(r"[0-9a-f]{7,40}", value) else "unknown"


def parse_time(value):
    if not value:
        return datetime.now(timezone.utc)
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PackError("--at must be an ISO date and time") from exc
    if moment.tzinfo is None:
        raise PackError("--at must include a time zone")
    return moment.astimezone(timezone.utc)


def file_name(ticket, stage, number, result, title, moment, sha):
    return (f"{ticket}_{stage}_R{number}_{result}_{slugify(title)}_"
            f"{moment.strftime('%Y%m%d-%H%MZ')}_{short_sha(sha)}.pdf")


def parse_name(name):
    match = NAME_RE.match((name or "").strip().replace("\\", "/").rsplit("/", 1)[-1])
    if not match:
        return None
    row = match.groupdict()
    row["round"] = int(row["round"])
    row["name"] = match.group(0)
    return row


def image_path(base, relative):
    if not isinstance(relative, str) or not relative:
        return None
    path = (base / relative).resolve()
    try:
        path.relative_to(base)
    except ValueError:
        return None
    return path if path.is_file() and path.suffix.lower() in IMAGE_TYPES else None


def data_uri(path):
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{IMAGE_TYPES[path.suffix.lower()]};base64,{payload}"


def text_of(value):
    return "" if value is None else str(value)


def steps_of(scenario):
    raw = scenario.get("steps") or []
    shots = [s for s in (scenario.get("screenshots") or []) if isinstance(s, str)]
    rows = []
    for index, step in enumerate(raw):
        item = step if isinstance(step, dict) else {"action": step}
        shot = item.get("screenshot") or (shots[index] if index < len(shots) else None)
        rows.append({"action": text_of(item.get("action")), "expected": text_of(item.get("expected")),
                     "actual": text_of(item.get("actual")), "screenshot": shot,
                     "status": text_of(item.get("status")).lower()})
    for shot in shots[len(raw):]:
        rows.append({"action": "Additional evidence", "expected": "", "actual": "", "screenshot": shot,
                     "status": ""})
    if rows:
        rows[-1]["expected"] = rows[-1]["expected"] or text_of(scenario.get("expected"))
        rows[-1]["actual"] = rows[-1]["actual"] or text_of(scenario.get("actual"))
    return rows


def failing_index(scenario, rows):
    if scenario.get("status") != "failed" or not rows:
        return None
    for index, row in enumerate(rows):
        if row["status"] == "failed" or "-FAIL" in text_of(row["screenshot"]):
            return index
    return len(rows) - 1


def has_proof(scenario, base):
    if any(image_path(base, shot) for shot in scenario.get("screenshots") or []):
        return True
    return any(image_path(base, row["screenshot"]) for row in steps_of(scenario)) or bool(scenario.get("logs"))


def overall(data, scenarios, base):
    """The result comes from the scenarios, so a report cannot claim more than they show."""
    if not scenarios:
        return "BLOCKED", []
    if any(s.get("status") == "failed" for s in scenarios):
        return "FAILED", []
    not_run, optional = [], []
    for scenario in scenarios:
        passed = scenario.get("status") == "passed" and has_proof(scenario, base)
        if not passed:
            (not_run if scenario.get("required", True) else optional).append(text_of(scenario.get("id")))
    if not_run:
        return "BLOCKED", not_run
    if optional or "NOTES" in text_of(data.get("result")).upper():
        return "NOTES", optional
    return "PASSED", []


def flows_of(scenarios):
    flows = {}
    for scenario in scenarios:
        name = text_of(scenario.get("flow")).strip() or f"{text_of(scenario.get('ac')) or 'General'} Flow"
        flows.setdefault(name, []).append(scenario)
    return flows


def flow_status(items):
    states = [s.get("status") for s in items]
    if "failed" in states:
        return "FAILED"
    return "PASSED" if all(state == "passed" for state in states) else "BLOCKED"


CSS = """
@page { size: A4; margin: 16mm 15mm 17mm;
  @bottom-left { content: "Internal test evidence"; font: 8pt 'Segoe UI', Arial, sans-serif; color: #66727e; }
  @bottom-right { content: "Page " counter(page) " of " counter(pages); font: 8pt 'Segoe UI', Arial, sans-serif; color: #66727e; } }
* { box-sizing: border-box; }
body { margin: 0; color: #17212b; font: 10pt/1.45 'Segoe UI', Arial, sans-serif; }
a { color: inherit; text-decoration: none; }
h1 { margin: 6mm 0 1mm; font-size: 23pt; line-height: 1.15; }
h2 { margin: 0 0 3mm; font-size: 16pt; }
h3 { margin: 5mm 0 2mm; font-size: 11.5pt; }
code { font: 8.6pt Consolas, monospace; overflow-wrap: anywhere; }
.band { padding: 8mm; color: #fff; border-radius: 2mm; background: #245b73; }
.band.FAILED { background: #a92f24; } .band.BLOCKED { background: #5d6470; } .band.NOTES { background: #9a5b08; }
.band .eyebrow { font-size: 9pt; font-weight: 600; letter-spacing: .08em; }
.band .result { margin-top: 3mm; font-size: 13pt; font-weight: 700; }
table { width: 100%; border-collapse: collapse; margin: 3mm 0; font-size: 9pt; }
th { padding: 1.6mm 2mm; color: #fff; text-align: left; background: #2b3945; }
td { padding: 1.6mm 2mm; vertical-align: top; border-bottom: .3mm solid #dfe4e9; overflow-wrap: anywhere; }
.facts td:first-child { width: 36mm; color: #5b6875; font-weight: 600; }
.badge { display: inline-block; padding: .3mm 2mm; border-radius: 3mm; font-size: 8pt; font-weight: 700; white-space: nowrap; }
.PASSED { color: #116b41; background: #e5f5ec; } .FAILED { color: #a92f24; background: #fdeaea; }
.BLOCKED { color: #4d5560; background: #eceef1; } .NOTES { color: #8a5207; background: #fdf1dc; }
.band.PASSED, .band.FAILED, .band.BLOCKED, .band.NOTES { color: #fff; }
.flow { break-before: page; }
.flow-head { display: flex; justify-content: space-between; align-items: center; padding-bottom: 2mm;
  margin-bottom: 3mm; border-bottom: .7mm solid #245b73; }
.flow-head h2 { margin: 0; }
.scenario-meta { margin: 0 0 2mm; color: #5b6875; font-size: 8.8pt; }
.step { break-inside: avoid; margin: 0 0 4mm; padding: 3mm; border: .3mm solid #d9e0e6; border-radius: 1.5mm; }
.step.fail { border: .6mm solid #c0392b; background: #fff7f6; }
.step-title { display: flex; justify-content: space-between; gap: 3mm; font-weight: 700; }
.pair { display: grid; grid-template-columns: 1fr 1fr; gap: 2mm 5mm; margin: 1.5mm 0; font-size: 9pt; }
.pair b { color: #5b6875; }
img { display: block; max-width: 100%; max-height: 78mm; margin: 2mm auto 0; border: .25mm solid #cfd7de; }
.missing { padding: 3mm; color: #a92f24; text-align: center; border: .3mm dashed #c0392b; font-size: 9pt; }
.compare { break-inside: avoid; display: grid; grid-template-columns: 1fr 1fr; gap: 4mm; margin: 0 0 4mm; padding: 3mm;
  background: #f4f7f9; border-radius: 1.5mm; }
.compare h4 { margin: 0; font-size: 9pt; } .compare img { max-height: 62mm; }
"""


def esc(value):
    return html.escape(text_of(value), quote=True)


def badge(result):
    return f'<span class="badge {result}">{LABELS[result]}</span>'


def status_key(status):
    return {"passed": "PASSED", "failed": "FAILED"}.get(status, "BLOCKED")


def picture(base, relative, alt):
    path = image_path(base, relative)
    if path:
        return f'<img src="{data_uri(path)}" alt="{esc(alt)}">'
    return '<div class="missing">No screenshot for this step</div>'


def render_step(base, scenario, row, number, fail_at):
    failed = fail_at == number - 1
    if failed:
        state = "FAILED"
    elif scenario.get("status") == "failed" and fail_at is not None and number - 1 > fail_at:
        state = "BLOCKED"
    elif scenario.get("status") == "failed":
        state = "PASSED"
    else:
        state = status_key(scenario.get("status"))
    pair = ""
    if row["expected"] or row["actual"]:
        pair = (f'<div class="pair"><div><b>Expected:</b> {esc(row["expected"]) or "Not recorded"}</div>'
                f'<div><b>Actual:</b> {esc(row["actual"]) or "Not recorded"}</div></div>')
    return (f'<div class="step{" fail" if failed else ""}"><div class="step-title">'
            f'<span>Step {number}: {esc(row["action"])}</span>{badge(state)}</div>{pair}'
            f'{picture(base, row["screenshot"], row["action"])}</div>')


def render_compare(base, prior_base, prior, rows):
    prior_rows = steps_of(prior)
    index = failing_index(prior, prior_rows)
    if index is None or not rows:
        return ""
    after = rows[min(index, len(rows) - 1)]
    return (f'<div class="compare"><div><h4>Before: failed at step {index + 1}</h4>'
            f'{picture(prior_base, prior_rows[index]["screenshot"], "Before")}</div>'
            f'<div><h4>After: same step</h4>{picture(base, after["screenshot"], "After")}</div></div>')


def render(meta, data, scenarios, base, prior_base, prior):
    flows = flows_of(scenarios)
    rows = []
    first_failure = None
    sections = []
    for number, (name, items) in enumerate(flows.items(), 1):
        state = flow_status(items)
        step_total = sum(len(steps_of(s)) for s in items)
        note = f"{step_total} steps"
        body = []
        for scenario in items:
            steps = steps_of(scenario)
            fail_at = failing_index(scenario, steps)
            if fail_at is not None:
                note = f"{step_total} steps, failed at {esc(scenario.get('id'))} step {fail_at + 1}"
                first_failure = first_failure or f"{name}, {scenario.get('id')} step {fail_at + 1}"
            body.append(f'<h3>{esc(scenario.get("id"))} · {esc(text_of(scenario.get("type")).title())} '
                        f'{badge(status_key(scenario.get("status")))}</h3>'
                        f'<p class="scenario-meta">{esc(scenario.get("ac"))}'
                        f'{" · Preconditions: " + esc(scenario.get("preconditions")) if scenario.get("preconditions") else ""}</p>')
            before = prior.get(scenario.get("id"))
            if before and before.get("status") == "failed":
                body.append(render_compare(base, prior_base, before, steps))
            body += [render_step(base, scenario, row, i, fail_at) for i, row in enumerate(steps, 1)]
            if not steps:
                body.append('<div class="missing">No steps were recorded</div>')
        rows.append(f'<tr><td><a href="#flow-{number}"><b>{esc(name)}</b></a></td><td>{badge(state)}</td>'
                    f'<td>{note}</td></tr>')
        sections.append(f'<section class="flow" id="flow-{number}"><div class="flow-head"><h2>{esc(name)}</h2>'
                        f'{badge(state)}</div>{"".join(body)}</section>')
    facts = [("Ticket", meta["ticket"]), ("Stage", f'{STAGE_NAMES[meta["stage"]]}, round {meta["round"]}'),
             ("Tested at", meta["moment"].strftime("%Y-%m-%d %H:%M UTC")), ("Commit", meta["sha"]),
             ("Environment", data.get("environment")), ("URL", data.get("url")),
             ("Account role", data.get("role")), ("Browser", " / ".join(
                 text_of(x) for x in (data.get("browser"), data.get("viewport")) if x)),
             ("QA run", data.get("runId"))]
    if meta["responds_to"]:
        facts.append(("Responds to", meta["responds_to"]))
    fact_rows = "".join(f'<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>' for k, v in facts if v)
    passed = sum(1 for s in scenarios if s.get("status") == "passed")
    failed = sum(1 for s in scenarios if s.get("status") == "failed")
    other = len(scenarios) - passed - failed
    extra = f'<p><b>Not verified:</b> {esc(", ".join(meta["not_run"]))}</p>' if meta["not_run"] else ""
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" '
            f"content=\"default-src 'none'; img-src data:; style-src 'unsafe-inline'\">"
            f'<title>{esc(meta["name"])}</title><style>{CSS}</style></head><body>'
            f'<div class="band {meta["result"]}"><div class="eyebrow">TEST EVIDENCE · {esc(meta["ticket"])}</div>'
            f'<h1>{esc(meta["title"])}</h1><div class="result">{ICONS[meta["result"]]} {LABELS[meta["result"]]}</div></div>'
            f'<table class="facts">{fact_rows}</table><h3>Flows tested</h3>'
            f'<table><tr><th>Flow</th><th>Result</th><th>Steps</th></tr>{"".join(rows)}</table>'
            f'<p>{len(scenarios)} scenarios: {passed} passed, {failed} failed, {other} not verified.</p>{extra}'
            f'{"".join(sections)}</body></html>')
    return page, first_failure


def find_browser():
    configured = os.environ.get("EVIDENCE_BROWSER")
    if configured and Path(configured).is_file():
        return configured
    for name in ("chrome", "google-chrome", "chromium", "chromium-browser", "msedge", "microsoft-edge"):
        found = shutil.which(name)
        if found:
            return found
    roots = [os.environ.get(k) for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
    candidates = [Path(r) / p for r in roots if r for p in
                  ("Google/Chrome/Application/chrome.exe", "Microsoft/Edge/Application/msedge.exe")]
    candidates += [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                   Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")]
    return next((str(p) for p in candidates if p.is_file()), None)


def to_pdf(page, target):
    with tempfile.TemporaryDirectory(prefix="evidence-pack-") as folder:
        source = Path(folder) / "evidence.html"
        source.write_text(page, encoding="utf-8")
        partial = Path(folder) / "evidence.pdf"
        browser = find_browser()
        if browser:
            command = [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--disable-extensions",
                       "--no-pdf-header-footer", "--host-resolver-rules=MAP * ~NOTFOUND",
                       f"--user-data-dir={Path(folder) / 'profile'}", f"--print-to-pdf={partial}", source.as_uri()]
        else:
            npx = shutil.which("npx")
            if not npx:
                raise PackError("no Chrome, Edge, Chromium or Playwright found to create the PDF")
            command = [npx, "--no-install", "playwright", "pdf", source.as_uri(), str(partial)]
        try:
            done = subprocess.run(command, capture_output=True, timeout=180, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PackError("the browser could not create the PDF") from exc
        if not partial.is_file() or partial.read_bytes()[:5] != b"%PDF-":
            raise PackError(f"the browser did not create a PDF (exit {done.returncode})")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("xb") as handle:
                handle.write(partial.read_bytes())
        except FileExistsError as exc:
            raise PackError(f"refusing to overwrite {target.name}") from exc


def load_json(path, label):
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise PackError(f"cannot read {label}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("scenarios"), list):
        raise PackError(f"{label} has no scenarios list")
    if not all(isinstance(s, dict) for s in data["scenarios"]):
        raise PackError(f"{label} has an invalid scenario")
    return data


def build(args):
    if not KEY_RE.match(args.ticket) or args.round < 1:
        raise PackError("--ticket or --round is not valid")
    if args.responds_to and not parse_name(args.responds_to):
        raise PackError("--responds-to must be an evidence PDF name")
    data = load_json(args.scenarios, "--scenarios")
    scenarios = data["scenarios"]
    base = args.scenarios.resolve().parent

    checks = load_checks()
    secrets = checks.known_secrets(args.repo)
    findings = checks.scan_text(args.scenarios.read_text(encoding="utf-8-sig"), args.scenarios.name, secrets)
    findings += checks.scan_text(args.title, "--title", secrets)
    if findings:
        raise UnsafeEvidence({"ok": False, "error": "redact these before building", "findings": findings})
    images = sorted({text_of(r["screenshot"]) for s in scenarios for r in steps_of(s) if image_path(base, r["screenshot"])})
    if images and not args.visual_reviewed:
        raise UnsafeEvidence({"ok": False, "error": "open and review each image, then pass --visual-reviewed",
                              "needsVisualReview": images})

    prior, prior_base = {}, base
    if args.before:
        before = load_json(args.before, "--before")
        prior_base = args.before.resolve().parent
        prior = {s.get("id"): s for s in before["scenarios"]}

    result, not_run = overall(data, scenarios, base)
    moment = parse_time(args.at or data.get("date"))
    sha = args.sha or data.get("testedSha") or data.get("deployedSha")
    name = file_name(args.ticket, args.stage, args.round, result, args.title, moment, sha)
    target = args.out / name
    if target.exists():
        raise PackError(f"refusing to overwrite {name}")
    meta = {"name": name, "ticket": args.ticket, "stage": args.stage, "round": args.round, "title": args.title,
            "result": result, "moment": moment, "sha": short_sha(sha), "responds_to": args.responds_to,
            "not_run": not_run}
    page, first_failure = render(meta, data, scenarios, base, prior_base, prior)
    to_pdf(page, target)
    size = target.stat().st_size
    body = {"ok": True, "file": str(target), "name": name, "result": result, "flows": list(flows_of(scenarios)),
            "firstFailure": first_failure, "notRun": not_run, "bytes": size}
    if size > SIZE_WARNING:
        body["warning"] = "the PDF is over 10 MB, so check the tracker's upload limit"
    return body


def index(args):
    if not KEY_RE.match(args.ticket):
        raise PackError("--ticket is not valid")
    try:
        names = args.names.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise PackError("cannot read --names") from exc
    rows = {}
    for line in names:
        row = parse_name(line)
        if row and row["ticket"] == args.ticket:
            rows[row["name"]] = row
    order = sorted(rows.values(), key=lambda r: (r["stamp"], STAGES.index(r["stage"]), r["round"]))
    newest = order[-1] if order else None
    tests = [r for r in order if r["stage"] in ("QA", "RETEST")]
    open_failure = tests[-1] if tests and tests[-1]["result"] in ("FAILED", "BLOCKED") else None
    return {"ok": True, "ticket": args.ticket, "checkFirst": newest["name"] if newest else None,
            "openFailure": open_failure["name"] if open_failure else None,
            "documents": [r["name"] for r in order], "body": render_index(args, order, newest, open_failure)}


def nice_time(stamp):
    return datetime.strptime(stamp, "%Y%m%d-%H%MZ").strftime("%Y-%m-%d %H:%M UTC")


def render_index(args, order, newest, open_failure):
    title = f"📁 Evidence Index · {args.ticket}"
    if not newest:
        return f"{title}\nNo evidence documents yet."
    focus = f" ({args.focus})" if args.focus else ""
    lines = [title, f"▶ Check first: {newest['name']}{focus}"]
    if open_failure and open_failure["name"] != newest["name"]:
        lines.append(f"Open QA failure: {open_failure['name']}")
    cells = [(f"{r['stage']} R{r['round']}", f"{ICONS[r['result']]} {LABELS[r['result']]}", nice_time(r["stamp"]),
              r["sha"], r["name"]) for r in order]
    heads = ("Stage", "Result", "Time", "Commit", "Document")
    lines.append("")
    if args.format == "jira":
        lines.append("||" + "||".join(heads) + "||")
        lines += ["|" + "|".join(cell) + "|" for cell in cells]
    elif args.format == "text":
        lines.append(" · ".join(heads))
        lines += [" · ".join(cell) for cell in cells]
    else:
        lines += ["| " + " | ".join(heads) + " |", "|---|---|---|---|---|"]
        lines += ["| " + " | ".join(f"`{c}`" if i == 4 else c for i, c in enumerate(cell)) + " |" for cell in cells]
    return "\n".join(lines)


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "error: invalid arguments. Run with --help for usage.\n")


def build_parser():
    parser = SafeParser(description="Evidence PDF and index")
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("build")
    make.add_argument("--scenarios", required=True, type=Path)
    make.add_argument("--ticket", required=True)
    make.add_argument("--stage", required=True, choices=STAGES)
    make.add_argument("--round", required=True, type=int)
    make.add_argument("--title", required=True)
    make.add_argument("--out", required=True, type=Path)
    make.add_argument("--visual-reviewed", action="store_true")
    make.add_argument("--before", type=Path)
    make.add_argument("--responds-to")
    make.add_argument("--sha")
    make.add_argument("--at")
    make.add_argument("--repo")
    listing = sub.add_parser("index")
    listing.add_argument("--ticket", required=True)
    listing.add_argument("--names", required=True, type=Path)
    listing.add_argument("--focus")
    listing.add_argument("--format", choices=("markdown", "jira", "text"), default="markdown")
    parsed = sub.add_parser("parse")
    parsed.add_argument("--name", required=True)
    for command in (make, listing, parsed):
        command.add_argument("--json", action="store_true")
    return parser


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    code = 0
    try:
        if args.command == "build":
            body = build(args)
        elif args.command == "index":
            body = index(args)
        else:
            body = parse_name(args.name)
            if body is None:
                raise PackError("not an evidence PDF name")
    except UnsafeEvidence as exc:
        body, code = exc.body, 1
    except PackError as exc:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(body, indent=2, ensure_ascii=False))
    elif args.command == "index":
        print(body["body"])
    else:
        print(body.get("file") or body.get("name") or json.dumps(body, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
