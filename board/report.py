#!/usr/bin/env python3
"""Change report: one self-contained HTML page per ticket, never committed.

Shows what a ticket changed and how it was proven: every changed file grouped by area
(frontend, backend & logic, database, tests, config, docs), the functions / components /
tables touched in each with a plain-language explanation and a link to the file, the acceptance
criteria, every test and review round, and the device tester's step-by-step screenshots for
failed and passing runs.

  python report.py --job <worktree>/.delivery/jobs/<KEY> [--archive <main checkout>] [--open]
  python board.py report --repo <main checkout> --ticket <KEY> [--open]   # same, finds the job

Inputs (all optional except job.json):
  <job>/job.json          ticket, title, type, risk, branch, base_branch, worktree, pr, acceptance
  <job>/changes.json      the explainer's explanations (schema delivery-changes/1, see
                          skills/deliver/references/change-report.md)
  <job>/walkthrough.md    fallback for the summary, "Try it" steps and the Mermaid diagram
  <job>/round-N/*.md      verdict first lines; round-N/screenshots/*.png the device steps
  git diff base...branch  in the worktree: the changed files and the functions touched in them

Writes <job>/report.html (images by relative path). With --archive, also copies the page and
its screenshots to <main>/.delivery/reports/<KEY>/ so the report outlives the job folder,
which merge-ticket deletes. Both places are under .delivery/, which is gitignored.

Standard library only. Python 3.10+.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

AREAS = [
    ("frontend", "Frontend", "Screens, components, styles and client code"),
    ("backend", "Backend & logic", "Server code, API routes, actions and shared logic"),
    ("database", "Database", "Migrations, schema, policies and SQL"),
    ("tests", "Tests", "Unit, integration and end-to-end tests"),
    ("config", "Config & tooling", "Build, CI, dependencies and settings"),
    ("docs", "Docs", "Guides, ticket records and other documentation"),
    ("other", "Other", "Everything else"),
]
AREA_KEYS = {a[0] for a in AREAS}

# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def inline_md(v) -> str:
    """Escape, then render the bits of Markdown agents use in one-liners: **bold** and `code`."""
    s = esc(v)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"`([^`]+)`", r"<code class='mono'>\1</code>", s)


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def git(cwd: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def classify(path: str) -> str:
    p = path.replace("\\", "/").lower()
    name = p.rsplit("/", 1)[-1]
    ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    if (re.search(r"(^|/)(migrations?|supabase|prisma|drizzle|db|database|schema)(/|$)", p)
            or ext in {".sql", ".prisma"}):
        return "database"
    if (re.search(r"(^|/)(tests?|__tests__|e2e|playwright|cypress|maestro|spec)(/|$)", p)
            or re.search(r"\.(test|spec|e2e)\.", name)):
        return "tests"
    if ext in {".md", ".mdx", ".rst", ".txt"} or p.startswith("docs/"):
        return "docs"
    if (p.startswith(".github/") or p.startswith(".claude/") or name in {
            "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb",
            "tsconfig.json", "dockerfile", "makefile", ".gitignore", ".env.example",
            "requirements.txt", "pyproject.toml", "go.mod", "go.sum", "cargo.toml"}
            or re.search(r"\.config\.(js|ts|mjs|cjs|json)$", name) or ext in {".yml", ".yaml", ".toml"}):
        return "config"
    if (re.search(r"(^|/)(api|server|actions?|functions|edge-functions|routes|services|workers?|jobs|cron)(/|$)", p)
            or name in {"route.ts", "route.js", "middleware.ts", "middleware.js"}
            or re.search(r"\.server\.(ts|js|tsx)$", name)):
        return "backend"
    if (ext in {".tsx", ".jsx", ".vue", ".svelte", ".css", ".scss", ".sass", ".less", ".html", ".astro"}
            or re.search(r"(^|/)(components|pages|app|views|screens|hooks|styles|public|ui)(/|$)", p)):
        return "frontend"
    if ext in {".ts", ".js", ".mjs", ".cjs", ".py", ".go", ".rb", ".php", ".java", ".kt", ".cs", ".rs"}:
        return "backend"
    return "other"


# Definitions we can spot in added / removed diff lines, per language family.
DEF_PATTERNS = [
    (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)"), "function"),
    (re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*(?::[^=]+)?=>"), "function"),
    (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)"), "class"),
    (re.compile(r"^\s*(?:export\s+)?(?:interface|type)\s+([A-Za-z_$][\w$]*)"), "type"),
    (re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)"), "function"),
    (re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)"), "function"),
    (re.compile(r"(?i)^\s*create\s+(?:or\s+replace\s+)?(table|view|function|policy|index|trigger|type)\s+(?:if\s+not\s+exists\s+)?([\w.\"]+)"), "sql"),
    (re.compile(r"(?i)^\s*alter\s+table\s+(?:if\s+exists\s+)?([\w.\"]+)"), "table"),
    (re.compile(r"(?i)^\s*drop\s+(table|view|function|policy|index|trigger)\s+(?:if\s+exists\s+)?([\w.\"]+)"), "sql-drop"),
    (re.compile(r"^\s*(?:describe|it|test)\(\s*['\"`]([^'\"`]{1,80})"), "test"),
]
HUNK_CONTEXT = re.compile(
    r"(?:function\s*\*?\s*|class\s+|def\s+|func\s+(?:\([^)]*\)\s*)?|(?:const|let|var)\s+)([A-Za-z_$][\w$]*)")


def defs_in(line: str) -> list[tuple[str, str]]:
    for rx, kind in DEF_PATTERNS:
        m = rx.search(line)
        if not m:
            continue
        if kind in ("sql", "sql-drop"):
            return [(m.group(2).strip('"'), m.group(1).lower())]
        if kind == "table":
            return [(m.group(1).strip('"'), "table")]
        name = m.group(1)
        if kind == "function" and name[:1].isupper():
            kind = "component"
        return [(name, kind)]
    return []


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------

def git_changes(worktree: Path, base: str) -> tuple[str | None, list[dict]]:
    """Files changed on the branch vs its base, with +/- counts, symbols and a capped diff."""
    ref = None
    for cand in (f"origin/{base}", base):
        if git(worktree, "rev-parse", "--verify", "--quiet", cand) is not None:
            ref = cand
            break
    if ref is None:
        return None, []
    rng = f"{ref}...HEAD"
    files: dict[str, dict] = {}
    for line in (git(worktree, "diff", "--name-status", "-M", rng) or "").splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0][:1]
        path = parts[-1]
        files[path] = {"path": path, "status": status, "from": parts[1] if status == "R" else None,
                       "added": 0, "removed": 0, "binary": False, "symbols": {}}
    for line in (git(worktree, "diff", "--numstat", "-M", rng) or "").splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        path = parts[-1]
        if "=>" in path:  # rename shown as a/{x => y}/b
            path = re.sub(r"\{[^{}]*=> ([^{}]*)\}", r"\1", path).replace("//", "/")
            path = path.split(" => ")[-1]
        f = files.get(path)
        if f is None:
            continue
        if parts[0] == "-":
            f["binary"] = True
        else:
            f["added"], f["removed"] = int(parts[0]), int(parts[1])
    diff = git(worktree, "diff", "-M", "-U3", rng) or ""
    current = None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/(.*) b/(.*)$", line)
            current = files.get(m.group(2)) if m else None
            continue
        if current is None:
            continue
        if line.startswith(("index ", "--- ", "+++ ", "similarity ", "rename ", "new file", "deleted file")):
            continue
        syms = current["symbols"]
        if line.startswith("@@"):
            m = HUNK_CONTEXT.search(line.split("@@", 2)[-1])
            if m:
                syms.setdefault(m.group(1), {"kind": "function", "plus": False, "minus": False})
        elif line.startswith("+"):
            for name, kind in defs_in(line[1:]):
                syms.setdefault(name, {"kind": kind, "plus": False, "minus": False})["plus"] = True
        elif line.startswith("-"):
            for name, kind in defs_in(line[1:]):
                syms.setdefault(name, {"kind": kind, "plus": False, "minus": False})["minus"] = True
    out = []
    for f in files.values():
        syms = []
        for name, s in f["symbols"].items():
            if f["status"] == "A":
                change = "added"
            elif f["status"] == "D":
                change = "removed"
            else:
                change = ("added" if s["plus"] and not s["minus"]
                          else "removed" if s["minus"] and not s["plus"] else "modified")
            syms.append({"name": name, "kind": s["kind"], "change": change, "what": ""})
        f["symbols"] = syms[:40]
        out.append(f)
    out.sort(key=lambda f: natural_key(f["path"]))
    return ref, out


def parse_walkthrough(text: str) -> dict:
    out: dict = {"summary": [], "try": [], "mermaid": None, "functions": {}}
    m = re.search(r"```mermaid\s*\n(.*?)```", text, re.S)
    if m:
        out["mermaid"] = m.group(1).strip()
    for sec in re.split(r"^##\s+", text, flags=re.M):
        head, _, body = sec.partition("\n")
        h = head.strip().lower()
        if h.startswith("what this pr does"):
            out["summary"] = [re.sub(r"^\s*[-*]\s+", "", l).strip() for l in body.splitlines() if re.match(r"\s*[-*]\s+", l)]
        elif h.startswith("try it"):
            out["try"] = [re.sub(r"^\s*\d+[.)]\s+", "", l).strip() for l in body.splitlines() if re.match(r"\s*\d+[.)]\s+", l)]
        elif h.startswith("key functions"):
            for l in body.splitlines():
                cells = [c.strip().strip("`") for c in l.strip().strip("|").split("|")]
                if len(cells) >= 3 and cells[0] and not set(cells[0]) <= set("-: ") and cells[0].lower() != "function":
                    out["functions"][cells[0].split("(")[0].strip()] = {"file": cells[1], "what": cells[2]}
    return out


SHOT = re.compile(r"(?i)(?:^|[-_])(AC\d+)(?:[-_](before|after))?(?:[-_]step[-_]?(\d+))?")
FAIL_MARK = re.compile(r"(?i)(?:^|[-_])(fail|failed|error|broken)(?:[-_.]|$)")
PASS_MARK = re.compile(r"(?i)(?:^|[-_])(pass|passed|ok|success)(?:[-_.]|$)")


def collect_rounds(job_dir: Path) -> list[dict]:
    rounds = []
    for rdir in sorted((p for p in job_dir.glob("round-*") if p.is_dir()), key=lambda p: natural_key(p.name)):
        verdicts = {}
        for md in sorted(rdir.glob("*.md")):
            first = read_text(md).strip().splitlines()[:1]
            verdicts[md.stem] = first[0].strip() if first else ""
        shots = []
        for img in sorted((p for p in rdir.rglob("*") if p.suffix.lower() in IMAGE_EXT and p.is_file()),
                          key=lambda p: natural_key(p.name)):
            stem = img.stem
            ac = re.search(r"(?i)(?:^|[-_])(AC\d+)(?=[-_]|$)", stem)
            phase = re.search(r"(?i)(?:^|[-_])(before|after)(?=[-_]|$)", stem)
            step = re.search(r"(?i)(?:^|[-_])step[-_]?(\d+)(?=[-_]|$)", stem)
            # What is left after removing the key, AC, phase, step and pass/fail marks: the step's caption.
            caption = stem[ac.end():] if ac else stem
            caption = re.sub(r"(?i)(^|[-_])(before|after|step[-_]?\d+|fail|failed|error|broken|pass|passed|ok|success)(?=[-_]|$)", r"\1", caption)
            caption = re.sub(r"[-_]+", " ", caption).strip()
            shots.append({
                "rel": img.relative_to(job_dir).as_posix(),
                "name": img.name,
                "ac": ac.group(1).upper() if ac else "Other",
                "phase": phase.group(1).lower() if phase else None,
                "step": int(step.group(1)) if step else None,
                "caption": caption,
                "fail": bool(FAIL_MARK.search(stem)),
                "pass": bool(PASS_MARK.search(stem)),
            })
        rounds.append({"name": rdir.name, "n": int(re.sub(r"\D", "", rdir.name) or 0),
                       "verdicts": verdicts, "shots": shots})
    return rounds


def parse_ac_tables(job_dir: Path, rounds: list[dict]) -> list[dict]:
    """Per-AC results from the testers' markdown tables (| AC | Criterion | Status/Result | ...).

    Used when job.json has no acceptance table. The latest round wins for each AC and source.
    """
    acs: dict[str, dict] = {}
    for r in rounds:
        for source in ("test-functional", "test-device"):
            text = read_text(job_dir / r["name"] / f"{source}.md")
            header = None
            for line in text.splitlines():
                if not line.strip().startswith("|"):
                    header = None if not line.strip() else header
                    continue
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if cells and cells[0].upper() == "AC":
                    header = [c.lower() for c in cells]
                    continue
                if header is None or set("".join(cells)) <= set("-: "):
                    continue
                if not re.match(r"(?i)^(AC\d+|E\d+)", cells[0]):
                    continue
                col = lambda *names: next((i for i, h in enumerate(header) if any(n in h for n in names)), None)
                ci, si = col("criterion"), col("status", "result")
                ei = col("what i saw", "evidence", "test")
                for ac in re.split(r"\s*,\s*", cells[0]):
                    a = acs.setdefault(ac.upper(), {"id": ac.upper(), "text": "", "results": {}, "evidence": ""})
                    if ci is not None and ci < len(cells) and cells[ci] not in ("-", ""):
                        a["text"] = cells[ci]
                    if si is not None and si < len(cells):
                        a["results"][source] = cells[si]
                    if ei is not None and ei < len(cells) and cells[ei] not in ("-", ""):
                        a["evidence"] = cells[ei][:300]
    return sorted(acs.values(), key=lambda a: natural_key(a["id"]))


def result_cls(text: str) -> str:
    t = (text or "").lower()
    if re.search(r"\b(fail|failed|changes|not met|not_met|blocked)\b", t):
        return "fail"
    if re.search(r"\b(pass|passed|met|ok)\b", t):
        return "pass"
    return "warn" if t else ""


def verdict_word(line: str) -> str:
    m = re.search(r"\b(PASS|CHANGES|BLOCKED|FAIL|APPROVE|ESCALATE|NOT RUN)\b", line or "", re.I)
    return m.group(1).upper() if m else ""


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

CSS = """
:root{--bg:#f7f7f5;--panel:#fff;--ink:#1d1d1b;--muted:#6b6b66;--line:#e4e3de;--accent:#3d6bd8;
--pass:#1f8a4c;--pass-bg:#e5f4ea;--fail:#c2362f;--fail-bg:#fbe7e5;--warn:#9a6a00;--warn-bg:#fdf2d6;
--add:#1f8a4c;--del:#c2362f;--code:#f1f0ec;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#121316;--panel:#1b1d21;--ink:#e8e8e6;
--muted:#9a9b98;--line:#2c2f35;--accent:#7ea2ff;--pass:#5ad08a;--pass-bg:#173523;--fail:#ff7a70;--fail-bg:#3b1d1b;
--warn:#f0c04c;--warn-bg:#3a2f12;--add:#5ad08a;--del:#ff7a70;--code:#23262b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:28px 16px 80px}
h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:36px 0 12px}h3{font-size:15px;margin:0}
a{color:var(--accent)}.muted{color:var(--muted)}.mono{font-family:var(--mono);font-size:13px}
.meta{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 0}
.chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);background:var(--panel);
border-radius:999px;padding:2px 10px;font-size:12.5px;font-family:var(--mono);color:var(--ink);text-decoration:none}
.chip.pass{background:var(--pass-bg);color:var(--pass);border-color:transparent}
.chip.fail{background:var(--fail-bg);color:var(--fail);border-color:transparent}
.chip.warn{background:var(--warn-bg);color:var(--warn);border-color:transparent}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.stat b{display:block;font-size:22px}.stat span{color:var(--muted);font-size:13px}
ul.tight,ol.tight{margin:6px 0;padding-left:20px}
.area{margin-top:18px}.area-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px;margin-bottom:8px}
.file{border:1px solid var(--line);border-radius:10px;background:var(--panel);margin:8px 0;overflow:hidden}
.file-head{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 14px}
.file-head .path{font-family:var(--mono);font-size:13.5px;font-weight:600;word-break:break-all}
.st{font-family:var(--mono);font-size:11px;padding:1px 6px;border-radius:4px;background:var(--code)}
.st.A{color:var(--add)}.st.D{color:var(--del)}.add{color:var(--add)}.del{color:var(--del)}
.file-head .links{margin-left:auto;font-size:13px}.file-body{padding:0 14px 12px}.what{margin:2px 0 8px}
table{border-collapse:collapse;width:100%;font-size:13.5px}th,td{text-align:left;padding:6px 8px;
border-top:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-weight:600;font-size:12px}
.tbl-wrap{overflow-x:auto}
.round{margin:14px 0}.round-head{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:8px}
.ac-group{margin:10px 0 16px}.ac-group h3{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:8px}
.shots{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px}
figure{margin:0;border:2px solid var(--line);border-radius:10px;overflow:hidden;background:var(--panel)}
figure.fail{border-color:var(--fail)}figure.pass{border-color:var(--pass)}
figure img{display:block;width:100%;height:150px;object-fit:cover;object-position:top;cursor:zoom-in;background:var(--code)}
figcaption{padding:6px 8px;font-size:12px;font-family:var(--mono);display:flex;gap:6px;justify-content:space-between}
figure.fail figcaption span:last-child{color:var(--fail)}figure.pass figcaption span:last-child{color:var(--pass)}
#lb{position:fixed;inset:0;background:rgba(0,0,0,.85);display:none;align-items:center;justify-content:center;padding:16px;z-index:9}
#lb.on{display:flex}#lb img{max-width:100%;max-height:92vh;border-radius:8px}
#lb p{position:fixed;bottom:12px;left:0;right:0;text-align:center;color:#fff;font-family:var(--mono);font-size:13px;margin:0}
.empty{color:var(--muted);font-style:italic}
"""

JS = """
const lb=document.getElementById('lb'),li=lb.querySelector('img'),lp=lb.querySelector('p');
document.addEventListener('click',e=>{const i=e.target.closest('figure img');
 if(i){li.src=i.src;lp.textContent=i.alt;lb.classList.add('on');return}
 if(e.target.closest('#lb'))lb.classList.remove('on')});
document.addEventListener('keydown',e=>{if(e.key==='Escape')lb.classList.remove('on')});
"""


def chip(text: str, cls: str = "") -> str:
    return f'<span class="chip {cls}">{esc(text)}</span>'


def verdict_chip(label: str, line: str) -> str:
    w = verdict_word(line)
    cls = "pass" if w in ("PASS", "APPROVE") else "fail" if w in ("CHANGES", "FAIL", "BLOCKED", "ESCALATE") else ""
    return chip(f"{label}: {w or (line[:30] if line else '?')}", cls)



def build_html(job_dir: Path) -> tuple[str, list[str]]:
    job = read_json(job_dir / "job.json")
    changes = read_json(job_dir / "changes.json")
    walk = parse_walkthrough(read_text(job_dir / "walkthrough.md"))
    key = job.get("ticket") or job.get("key") or job_dir.name
    worktree = Path(job.get("worktree") or job_dir.parent.parent.parent)
    title = job.get("title") or ""
    if not title and job.get("record"):
        first = (read_text(worktree / job["record"]).lstrip().splitlines() or [""])[0]
        title = re.sub(r"^#\s*", "", first).strip()
        title = re.sub(r"^" + re.escape(key) + r"\s*[-—:·]\s*", "", title)
    base = job.get("base_branch") or ""
    if not base and worktree.is_dir():  # the repo's default branch (origin/HEAD), e.g. preview
        head = (git(worktree, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD") or "").strip()
        base = head.rsplit("/", 1)[-1] if head else ""
    base = base or "main"
    ref, files = git_changes(worktree, base) if worktree.is_dir() else (None, [])

    # Links to each file on the ticket branch, when the remote is GitHub.
    web_base = None
    remote = (git(worktree, "remote", "get-url", "origin") or "").strip() if worktree.is_dir() else ""
    gh = re.search(r"github\.com[:/]+([^/]+)/(.+?)(?:\.git)?$", remote)
    branch = job.get("branch") or ((git(worktree, "branch", "--show-current") or "").strip() if worktree.is_dir() else "")
    if gh and branch:
        web_base = f"https://github.com/{gh.group(1)}/{gh.group(2)}/blob/{quote(branch)}/"

    explained = changes.get("files") or {}
    # Files the explainer described but git did not list (e.g. the worktree is gone): keep them.
    listed = {f["path"] for f in files}
    for path, info in explained.items():
        if path not in listed:
            files.append({"path": path, "status": (info or {}).get("status", "M"), "from": None, "added": None,
                          "removed": None, "binary": False, "symbols": []})
    for f in files:
        info = explained.get(f["path"]) or {}
        f["area"] = info.get("area") if info.get("area") in AREA_KEYS else classify(f["path"])
        f["what"] = info.get("what") or ""
        given = info.get("symbols") or []
        if given:
            found = {s["name"]: s for s in f["symbols"]}
            merged = []
            for s in given:
                seen = found.pop(s.get("name"), {})
                merged.append({"name": s.get("name"), "kind": s.get("kind") or seen.get("kind", ""),
                               "change": s.get("change") or seen.get("change", "modified"),
                               "what": s.get("what") or ""})
            f["symbols"] = merged + list(found.values())
        for s in f["symbols"]:
            if not s.get("what") and s["name"] in walk["functions"]:
                s["what"] = walk["functions"][s["name"]]["what"]

    summary = changes.get("summary") or walk["summary"]
    try_steps = changes.get("howToTry") or walk["try"]
    notes = changes.get("notes") or []
    rounds = collect_rounds(job_dir)
    acceptance = job.get("acceptance") or []
    decision = job.get("decision") or verdict_word(read_text(job_dir / "decision.md").split("\n", 1)[0])
    pr = job.get("pr") or {}
    if not isinstance(pr, dict):  # some workers store just the URL or the number
        s = str(pr)
        num = re.search(r"(\d+)\s*$", s)
        pr = {"url": s if s.startswith("http") else None, "number": num.group(1) if num else s}
    acceptance = [a for a in acceptance if isinstance(a, dict)]

    images: list[str] = []
    parts: list[str] = []
    w = parts.append

    # header
    w(f"<header><p class='muted mono'>Change report · not committed · generated {esc(datetime.now().strftime('%Y-%m-%d %H:%M'))}</p>")
    w(f"<h1>{esc(key)}{' · ' + esc(title) if title else ''}</h1><div class='meta'>")
    for label in (job.get("type"), job.get("risk") and f"{job['risk']} risk"):
        if label:
            w(chip(label))
    if job.get("branch"):
        w(chip(f"{job['branch']} → {base}"))
    if decision:
        w(chip(f"decision: {decision}", "pass" if decision == "APPROVE" else "fail"))
    if pr.get("url"):
        w(f"<a class='chip' href='{esc(pr['url'])}'>PR #{esc(pr.get('number', ''))}</a>")
    if job.get("record"):
        w(chip(job["record"]))
    w("</div></header>")

    # summary + stats
    by_area: dict[str, list[dict]] = {}
    for f in files:
        by_area.setdefault(f["area"], []).append(f)
    plus = sum(f["added"] or 0 for f in files)
    minus = sum(f["removed"] or 0 for f in files)
    nsyms = sum(len(f["symbols"]) for f in files)
    w("<h2>Summary</h2><div class='panel'>")
    w("<ul class='tight'>" + "".join(f"<li>{inline_md(s)}</li>" for s in summary) + "</ul>" if summary
      else "<p class='empty'>No summary yet (the explainer writes it after APPROVE).</p>")
    w("</div><div class='stats' style='margin-top:10px'>")
    w(f"<div class='panel stat'><b>{len(files)}</b><span>files changed</span></div>")
    w(f"<div class='panel stat'><b>{nsyms}</b><span>functions and components touched</span></div>")
    for k, label, _ in AREAS:
        if by_area.get(k):
            w(f"<div class='panel stat'><b>{len(by_area[k])}</b><span>{esc(label)}</span></div>")
    w("</div>")
    if notes:
        w("<h2>Notes for the reviewer</h2><div class='panel'><ul class='tight'>"
          + "".join(f"<li>{inline_md(r)}</li>" for r in notes) + "</ul></div>")


    # changes by area
    w("<h2>What changed</h2>")
    if ref is None and not explained:
        w("<p class='empty'>No diff available: the worktree or the base branch could not be read.</p>")
    for k, label, blurb in AREAS:
        group = by_area.get(k) or []
        if not group:
            continue
        w(f"<section class='area'><div class='area-head'><h2 style='margin:0'>{esc(label)}</h2>"
          f"<span class='muted'>{esc(blurb)} · {len(group)} file{'s' if len(group) != 1 else ''}</span></div>")
        for f in group:
            status = {"A": "added", "M": "updated", "D": "deleted", "R": "renamed"}.get(f["status"], f["status"])
            links = []
            if web_base and f["status"] != "D":
                links.append(f"<a href='{esc(web_base + quote(f['path']))}' target='_blank' rel='noopener'>view on GitHub</a>")
            local = worktree / f["path"]
            if f["status"] != "D" and local.is_file():
                links.append(f"<a href='{esc(local.resolve().as_uri())}'>open file</a>")
            w(f"<div class='file'><div class='file-head'><span class='st {esc(f['status'])}'>{esc(status)}</span>"
              f"<span class='path'>{esc(f['path'])}</span>"
              + (f"<span class='muted mono'>from {esc(f['from'])}</span>" if f.get("from") else "")
              + (f"<span class='links'>{' · '.join(links)}</span>" if links else "") + "</div><div class='file-body'>")
            w(f"<p class='what'>{inline_md(f['what'])}</p>" if f["what"]
              else "<p class='what empty'>No explanation yet (the explainer adds it after APPROVE).</p>")
            if f["symbols"]:
                w("<div class='tbl-wrap'><table><tr><th>Function / component</th><th>Change</th><th>What changed</th></tr>")
                for s in f["symbols"]:
                    change = "updated" if s["change"] == "modified" else s["change"]
                    cls = "add" if change == "added" else "del" if change == "removed" else ""
                    w(f"<tr><td class='mono'>{esc(s['name'])}</td><td class='{cls}'>{esc(change)}</td>"
                      f"<td>{inline_md(s.get('what', ''))}</td></tr>")
                w("</table></div>")
            w("</div></div>")
        w("</section>")

    # acceptance
    w("<h2>Acceptance criteria</h2>")
    if acceptance:
        w("<div class='panel tbl-wrap'><table><tr><th>AC</th><th>Criterion</th><th>Status</th><th>Evidence</th></tr>")
        for a in acceptance:
            st = a.get("status", "")
            cls = "pass" if st == "met" else "fail" if st in ("not_met", "blocked") else "warn" if st == "partial" else ""
            w(f"<tr><td class='mono'>{esc(a.get('id'))}</td><td>{esc(a.get('text'))}</td>"
              f"<td>{chip(st or '?', cls)}</td><td class='mono'>{esc(a.get('evidence'))}</td></tr>")
        w("</table></div>")
    else:
        tables = parse_ac_tables(job_dir, rounds)
        if tables:
            sources = [s for s in ("test-functional", "test-device") if any(s in a["results"] for a in tables)]
            w("<div class='panel tbl-wrap'><table><tr><th>AC</th><th>Criterion</th>"
              + "".join(f"<th>{esc(s.replace('test-', '') + ' test')}</th>" for s in sources)
              + "<th>What the tester saw</th></tr>")
            for a in tables:
                w(f"<tr><td class='mono'>{esc(a['id'])}</td><td>{esc(a['text'])}</td>"
                  + "".join(f"<td>{chip(a['results'][s][:40], result_cls(a['results'][s])) if s in a['results'] else ''}</td>" for s in sources)
                  + f"<td>{esc(a['evidence'])}</td></tr>")
            w("</table><p class='muted' style='margin:8px 0 0'>From the testers' reports (latest round per criterion).</p></div>")
        else:
            w("<p class='empty'>No acceptance results yet.</p>")

    if try_steps:
        w("<h2>Try it yourself</h2><div class='panel'><ol class='tight'>"
          + "".join(f"<li>{inline_md(s)}</li>" for s in try_steps) + "</ol></div>")

    # rounds and screenshots
    w("<h2>Testing and review rounds</h2>")
    if not rounds:
        w("<p class='empty'>No rounds yet.</p>")
    for r in rounds:
        dev_w = verdict_word(r["verdicts"].get("test-device", ""))
        run_label = ("Passed run" if dev_w == "PASS" else "Failed run" if dev_w in ("CHANGES", "FAIL")
                     else "Blocked run" if dev_w == "BLOCKED" else "")
        w(f"<div class='round panel'><div class='round-head'><h3>Round {r['n']}</h3>")
        if run_label:
            w(chip(run_label, "pass" if dev_w == "PASS" else "fail"))
        for name, line in r["verdicts"].items():
            w(verdict_chip(name, line))
        w("</div>")
        if r["shots"]:
            # This round's per-AC device results, so an AC that did not pass is marked even when
            # the tester did not put -FAIL in a screenshot name.
            round_acs = {a["id"]: a["results"].get("test-device", "") for a in parse_ac_tables(job_dir, [r])}
            groups: dict[str, list[dict]] = {}
            for s in r["shots"]:
                groups.setdefault(s["ac"], []).append(s)
            for ac in sorted(groups, key=natural_key):
                shots = sorted(groups[ac], key=lambda s: (s["phase"] == "after", s["step"] or 0, natural_key(s["name"])))
                reported = result_cls(round_acs.get(ac, ""))
                marked = any(s["fail"] for s in shots)
                failed = marked or reported == "fail"
                status = ("FAIL" if failed else "PASS" if reported == "pass" or dev_w == "PASS"
                          else (round_acs.get(ac) or "")[:24])
                last_fails = failed and not marked  # no explicit mark: the final step is the evidence
                w(f"<div class='ac-group'><h3>{esc(ac)} {chip(status, 'pass' if status == 'PASS' else 'fail' if status == 'FAIL' else 'warn') if status else ''}"
                  f"<span class='muted' style='font-weight:400'>{len(shots)} step{'s' if len(shots) != 1 else ''}</span></h3><div class='shots'>")
                for s in shots:
                    images.append(s["rel"])
                    mark = ("fail" if s["fail"] or (last_fails and s is shots[-1])
                            else "pass" if (s["pass"] or (status == "PASS" and s is shots[-1])) else "")
                    bits = [s["phase"], f"step {s['step']}" if s["step"] else None, s["caption"]]
                    label = " · ".join(b for b in bits if b) or s["name"]
                    tail = "✗ failed here" if mark == "fail" else "✓ passed" if mark == "pass" else ""
                    w(f"<figure class='{mark}'><img loading='lazy' src='{esc(s['rel'])}' alt='{esc(s['name'])}'>"
                      f"<figcaption><span>{esc(label)}</span><span>{tail}</span></figcaption></figure>")
                w("</div></div>")
        elif "test-device" in r["verdicts"]:
            w("<p class='empty'>The device tester ran but left no screenshots in this round's folder.</p>")
        w("</div>")

    body = "\n".join(parts)
    page = (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(key)} change report</title><style>{CSS}</style></head><body><main>{body}</main>"
            f"<div id='lb'><img alt=''><p></p></div><script>{JS}</script></body></html>")
    return page, images


def write_report(job_dir: Path, archive_repo: Path | None = None) -> Path:
    job_dir = job_dir.resolve()
    if not (job_dir / "job.json").is_file():
        sys.exit(f"no job.json in {job_dir}")
    page, images = build_html(job_dir)
    out = job_dir / "report.html"
    out.write_text(page, encoding="utf-8")
    if archive_repo is None:
        return out
    key = read_json(job_dir / "job.json").get("ticket") or job_dir.name
    dest = archive_repo.resolve() / ".delivery" / "reports" / key
    dest.mkdir(parents=True, exist_ok=True)
    for rel in images:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(job_dir / rel, target)
        except OSError:
            pass
    (dest / "report.html").write_text(page, encoding="utf-8")
    return dest / "report.html"


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a ticket's HTML change report.")
    ap.add_argument("--job", required=True, help="the ticket's job folder (.delivery/jobs/<KEY>)")
    ap.add_argument("--archive", default=None, help="main checkout: also copy to .delivery/reports/<KEY>/")
    ap.add_argument("--open", action="store_true", help="open the report in the browser")
    args = ap.parse_args()
    path = write_report(Path(args.job), Path(args.archive) if args.archive else None)
    print(path)
    if args.open:
        webbrowser.open(path.as_uri())


if __name__ == "__main__":
    main()
