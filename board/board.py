#!/usr/bin/env python3
"""Delivery board: a live, local dashboard for the AI delivery workflow.

Reads the delivery loop's state files (never writes them) and serves one page that shows
waves, every ticket's step, blockers and owner questions. Answers typed on the page are
dropped into .delivery/inbox/ for the orchestrator to pick up on its next cycle.

Standard library only. Python 3.10+. Works on Windows, macOS and Linux.

  python board.py serve  --repo <main checkout> [--port 8765] [--open]
  python board.py status --repo <main checkout>            # print the aggregated JSON
  python board.py event  --repo <main checkout> --kind stage --ticket ABC-27 --text "gate r2 PASS"
  python board.py inbox  --repo <main checkout> [--take]   # list (or consume) board answers
  python board.py stop   --repo <main checkout>
  python board.py pause  --repo <main checkout> [--ticket KEY] [--now] [--reason "..."]
  python board.py resume --repo <main checkout> [--ticket KEY]
  python board.py serve  --demo                             # sample data, no project needed
  python board.py report --repo <main checkout> --ticket ABC-27 [--open]   # HTML change report

Files read (schemas: skills/deliver/references/state-files.md and board.md):
  .delivery/orchestrator.json        orchestrator state (tickets, questions, lanes, backlog)
  .delivery/wave-plan.json           plan-waves output (proposed or applied)
  .delivery/events.jsonl             activity feed (orchestrator appends via `board.py event`)
  <worktree>/.delivery/jobs/<KEY>/   each ticket's job.json and round files
Files written:
  .delivery/board.json               where the board runs (pid, port, url) - board only
  .delivery/inbox/*.json             answers and feedback from the page - board only
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
INDEX = HERE / "index.html"
DEFAULT_PORT = 8765
TEXT_TYPES = {".md": "text/markdown", ".json": "application/json", ".log": "text/plain", ".txt": "text/plain"}
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
MAX_FILES_PER_JOB = 400
EVENT_TAIL = 300
ANSWERABLE_KINDS = ("decision", "spec-approval", "escalation", "action", "needs-info")
# The change report is a static page: inline styles and script, Mermaid from jsDelivr, local images.
REPORT_CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
              "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; connect-src 'self'; "
              "frame-ancestors 'none'")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_json(path: Path, problems: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as err:
        problems.append(f"{path.name}: {err}")
        return None


def write_json_atomic(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def first_line(path: Path) -> str | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return fh.readline().strip()
    except OSError:
        return None


def iso_from_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).astimezone().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

class Worktrees:
    """`git worktree list` is cheap but not free; cache it for a few seconds."""

    def __init__(self, repo: Path):
        self.repo = repo
        self._at = 0.0
        self._paths: list[Path] = []

    def paths(self) -> list[Path]:
        if time.time() - self._at < 10:
            return self._paths
        paths: list[Path] = []
        try:
            out = subprocess.run(
                ["git", "-C", str(self.repo), "worktree", "list", "--porcelain"],
                capture_output=True, text=True, timeout=5,
            ).stdout
            paths = [Path(line[9:].strip()) for line in out.splitlines() if line.startswith("worktree ")]
        except (OSError, subprocess.SubprocessError):
            pass
        self._paths, self._at = paths, time.time()
        return paths


def scan_job_folder(folder: Path) -> dict:
    """List a job folder's files with first lines (verdicts) and the latest change time."""
    files = []
    latest = 0.0
    try:
        entries = sorted(folder.rglob("*"))
    except OSError:
        entries = []
    for p in entries:
        if len(files) >= MAX_FILES_PER_JOB:
            break
        if not p.is_file() or p.name.endswith(".tmp"):
            continue
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        latest = max(latest, mtime)
        suffix = p.suffix.lower()
        if suffix in TEXT_TYPES or suffix in IMAGE_TYPES:
            files.append({
                "path": p.relative_to(folder).as_posix(),
                "kind": "image" if suffix in IMAGE_TYPES else "text",
                "first": first_line(p) if suffix == ".md" else None,
                "mtime": iso_from_ts(mtime),
            })
    return {"files": files, "lastActivity": iso_from_ts(latest) if latest else None}


def same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def job_folders(repo: Path, orch: dict | None, worktrees: Worktrees) -> dict[str, Path]:
    """Every job folder: orchestrator worktree paths first, then the main checkout and other worktrees."""
    folders: dict[str, Path] = {}
    for key, t in ((orch or {}).get("tickets") or {}).items():
        wt = (t or {}).get("worktreePath")
        if wt:
            folders[key] = Path(wt) / ".delivery" / "jobs" / key
    roots = [repo] + [p for p in worktrees.paths() if not same_path(p, repo)]
    for root in roots:
        jobs_dir = root / ".delivery" / "jobs"
        if not jobs_dir.is_dir():
            continue
        for child in jobs_dir.iterdir():
            if child.is_dir() and child.name not in folders:
                folders[child.name] = child
    return {k: v for k, v in folders.items() if v.is_dir()}


def collect_jobs(repo: Path, orch: dict | None, worktrees: Worktrees, problems: list[str]) -> dict[str, dict]:
    jobs = {}
    for key, folder in job_folders(repo, orch, worktrees).items():
        job = read_json(folder / "job.json", problems) or {}
        jobs[key] = {"folder": str(folder), "job": job, "hasReport": (folder / "report.html").is_file(),
                     **scan_job_folder(folder)}
    return jobs


def archived_reports(repo: Path) -> list[str]:
    """Tickets whose change report was archived to .delivery/reports/<KEY>/ (survives merge cleanup)."""
    root = repo / ".delivery" / "reports"
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if (p / "report.html").is_file())


def open_job_questions(repo: Path, orch: dict | None, worktrees: Worktrees) -> dict[str, dict]:
    """Open questions workers wrote into job.json, keyed by their id (`<KEY>-q<n>`)."""
    out: dict[str, dict] = {}
    for key, folder in job_folders(repo, orch, worktrees).items():
        job = read_json(folder / "job.json", []) or {}
        for i, q in enumerate(job.get("questions") or [], 1):
            if not isinstance(q, dict) or q.get("answeredAt") or q.get("answer"):
                continue
            qid = str(q.get("id") or f"{key}-q{i}")
            out[qid] = {**q, "id": qid, "key": key}
    return out


def tail_events(path: Path, problems: list[str]) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-EVENT_TAIL:]
    except FileNotFoundError:
        return []
    except OSError as err:
        problems.append(f"events.jsonl: {err}")
        return []
    events = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except ValueError:
            problems.append("events.jsonl has a line that is not JSON (skipped)")
    return events


def list_inbox(repo: Path) -> list[dict]:
    inbox = repo / ".delivery" / "inbox"
    out = []
    if inbox.is_dir():
        for p in sorted(inbox.glob("*.json")):
            try:
                out.append({"file": p.name, **json.loads(p.read_text(encoding="utf-8"))})
            except (OSError, ValueError):
                continue
    return out


def aggregate(repo: Path, worktrees: Worktrees) -> dict:
    problems: list[str] = []
    d = repo / ".delivery"
    orch = read_json(d / "orchestrator.json", problems)
    return {
        "schema": "delivery-board/1",
        "now": now_iso(),
        "repo": str(repo),
        "orchestrator": orch,
        "plan": read_json(d / "wave-plan.json", problems),
        "jobs": collect_jobs(repo, orch, worktrees, problems),
        "events": tail_events(d / "events.jsonl", problems),
        "inbox": list_inbox(repo),
        "reports": archived_reports(repo),
        "problems": problems,
    }


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

class Board:
    def __init__(self, repo: Path, port: int):
        self.repo = repo
        self.port = port
        self.token = secrets.token_urlsafe(24)  # in memory and in the served page only, never on disk
        self.worktrees = Worktrees(repo)
        self.lock = threading.Lock()

    def job_folder(self, key: str) -> Path | None:
        orch = read_json(self.repo / ".delivery" / "orchestrator.json", [])
        return job_folders(self.repo, orch, self.worktrees).get(key)


def make_handler(board: Board):
    allowed_hosts = {f"127.0.0.1:{board.port}", f"localhost:{board.port}"}
    csp = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
           "script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")

    class Handler(BaseHTTPRequestHandler):
        server_version = "DeliveryBoard/1"

        def log_message(self, fmt, *args):  # keep the terminal quiet
            pass

        def _host_ok(self) -> bool:
            # Blocks DNS rebinding: only requests addressed to this local port are served.
            return self.headers.get("Host", "") in allowed_hosts

        def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data):
            self._send(status, json.dumps(data).encode("utf-8"), "application/json; charset=utf-8")

        def _error(self, status: int, msg: str):
            self._json(status, {"error": msg})

        # --- GET -----------------------------------------------------------
        def do_GET(self):
            if not self._host_ok():
                return self._error(HTTPStatus.FORBIDDEN, "host not allowed")
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                html = INDEX.read_text(encoding="utf-8").replace("__BOARD_TOKEN__", board.token)
                return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8",
                                  {"Content-Security-Policy": csp})
            if url.path == "/api/ping":
                return self._json(200, {"ok": True, "repo": str(board.repo)})
            if url.path == "/api/status":
                with board.lock:
                    data = aggregate(board.repo, board.worktrees)
                return self._json(200, data)
            if url.path == "/api/file":
                return self._file(parse_qs(url.query))
            if url.path.startswith("/report/"):
                return self._report(url.path[len("/report/"):])
            return self._error(HTTPStatus.NOT_FOUND, "not found")

        def _report(self, rest: str):
            # /report/<KEY>/            -> report.html
            # /report/<KEY>/<rel path>  -> a screenshot the report links to
            from urllib.parse import unquote
            key, _, rel = unquote(rest).partition("/")
            rel = rel or "report.html"
            roots = []
            folder = board.job_folder(key) if key else None
            if folder is not None and (folder / "report.html").is_file():
                roots.append(folder)
            archive = board.repo / ".delivery" / "reports" / key
            if key and (archive / "report.html").is_file():
                roots.append(archive)
            for root in roots:
                root = root.resolve()
                target = (root / rel).resolve()
                try:
                    inside = os.path.commonpath([str(root), str(target)]) == str(root)
                except ValueError:
                    inside = False
                suffix = target.suffix.lower()
                if not inside or not target.is_file():
                    continue
                if suffix == ".html" and target.name == "report.html":
                    return self._send(200, target.read_bytes(), "text/html; charset=utf-8",
                                      {"Content-Security-Policy": REPORT_CSP})
                if suffix in IMAGE_TYPES:
                    return self._send(200, target.read_bytes(), IMAGE_TYPES[suffix])
            return self._error(404, "no report for this ticket yet")

        def _file(self, q: dict):
            key = (q.get("ticket") or [""])[0]
            rel = (q.get("path") or [""])[0]
            if not key or not rel:
                return self._error(400, "ticket and path are required")
            folder = board.job_folder(key)
            if folder is None:
                return self._error(404, "unknown ticket")
            root = folder.resolve()
            target = (root / rel).resolve()
            try:
                inside = os.path.commonpath([str(root), str(target)]) == str(root)
            except ValueError:  # different drives on Windows
                inside = False
            suffix = target.suffix.lower()
            if not inside or not target.is_file() or (suffix not in TEXT_TYPES and suffix not in IMAGE_TYPES):
                return self._error(404, "file not available")
            if suffix in IMAGE_TYPES:
                return self._send(200, target.read_bytes(), IMAGE_TYPES[suffix])
            text = target.read_text(encoding="utf-8", errors="replace")
            return self._send(200, text.encode("utf-8"), "text/plain; charset=utf-8")

        # --- POST ----------------------------------------------------------
        def do_POST(self):
            if not self._host_ok():
                return self._error(HTTPStatus.FORBIDDEN, "host not allowed")
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).netloc not in allowed_hosts:
                return self._error(HTTPStatus.FORBIDDEN, "origin not allowed")
            if self.headers.get("X-Board-Token") != board.token:
                return self._error(HTTPStatus.FORBIDDEN, "bad token (reload the page)")
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > 16_384:
                return self._error(400, "body missing or too large")
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except ValueError:
                return self._error(400, "body is not JSON")
            if not isinstance(body, dict):
                return self._error(400, "body must be a JSON object")
            path = urlparse(self.path).path
            if path == "/api/answer":
                return self._answer(body)
            if path == "/api/feedback":
                return self._feedback(body)
            return self._error(404, "not found")

        def _answer(self, body: dict):
            qid = str(body.get("id", "")).strip()
            answer = str(body.get("answer", "")).strip()
            if not qid or not answer or len(answer) > 4000:
                return self._error(400, "id and answer are required")
            orch = read_json(board.repo / ".delivery" / "orchestrator.json", []) or {}
            open_q = {q.get("id"): q for q in orch.get("ownerQuestions") or [] if not q.get("answeredAt")}
            q = open_q.get(qid)
            if q is None:
                # A worker's question the orchestrator has not relayed yet (job.json.questions).
                jq = open_job_questions(board.repo, orch, board.worktrees).get(qid)
                if jq is None:
                    return self._error(409, f"{qid} is not an open question")
                return self._drop("answer", {"id": qid, "key": jq["key"], "answer": answer,
                                             "jobQuestion": qid})
            if q.get("kind") not in ANSWERABLE_KINDS:
                return self._error(409, f"{qid} ({q.get('kind')}) must be answered in the chat")
            return self._drop("answer", {"id": qid, "key": q.get("key"), "answer": answer})

        def _feedback(self, body: dict):
            key = str(body.get("key", "")).strip()
            text = str(body.get("text", "")).strip()
            if not key or not text or len(text) > 8000:
                return self._error(400, "key and text are required")
            return self._drop("feedback", {"key": key, "text": text})

        def _drop(self, kind: str, data: dict):
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            ident = "".join(c for c in str(data.get("id") or data.get("key")) if c.isalnum() or c in "-_")
            name = f"{kind}-{ident}-{stamp}.json"
            write_json_atomic(board.repo / ".delivery" / "inbox" / name,
                              {"kind": kind, "via": "board", "at": now_iso(), **data})
            return self._json(200, {"ok": True, "file": name})

    return Handler


def serve(repo: Path, port: int, open_browser: bool) -> None:
    repo = repo.resolve()
    (repo / ".delivery").mkdir(parents=True, exist_ok=True)
    httpd = board = None
    for candidate in range(port, port + 20):
        board = Board(repo, candidate)
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", candidate), make_handler(board))
            break
        except OSError:
            continue
    if httpd is None or board is None:
        sys.exit(f"no free port in {port}-{port + 19}")
    url = f"http://127.0.0.1:{board.port}/"
    info_path = repo / ".delivery" / "board.json"
    write_json_atomic(info_path, {"pid": os.getpid(), "port": board.port, "url": url,
                                  "repo": str(repo), "startedAt": now_iso()})
    print(f"Delivery board: {url}  (repo {repo})", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if json.loads(info_path.read_text(encoding="utf-8")).get("pid") == os.getpid():
                info_path.unlink()
        except (OSError, ValueError):
            pass


# ---------------------------------------------------------------------------
# CLI helpers for the orchestrator
# ---------------------------------------------------------------------------

def cmd_event(repo: Path, kind: str, ticket: str | None, text: str, actor: str) -> None:
    path = repo / ".delivery" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"ts": now_iso(), "kind": kind, "ticket": ticket or None, "text": text, "actor": actor})
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def cmd_control(repo: Path, action: str, ticket: str | None, now: bool, reason: str | None) -> None:
    """Ask the running orchestrator to pause or resume (applied at the start of its next cycle)."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    item = {"kind": "control", "action": action, "via": "board.py", "at": now_iso(),
            "ticket": ticket or None, "mode": "now" if now else "soft", "reason": reason or None}
    write_json_atomic(repo / ".delivery" / "inbox" / f"control-{action}-{stamp}.json", item)
    scope = ticket or "everything"
    mode = f" ({item['mode']})" if action == "pause" else ""
    print(f"{action} requested for {scope}{mode}; the orchestrator applies it on its next cycle. "
          f"For an immediate effect, type /deliver <KEY> --{action} in the orchestrator's chat.")


def cmd_inbox(repo: Path, take: bool) -> None:
    items = list_inbox(repo)
    if take and items:
        done = repo / ".delivery" / "inbox" / "done"
        done.mkdir(parents=True, exist_ok=True)
        for item in items:
            os.replace(repo / ".delivery" / "inbox" / item["file"], done / item["file"])
    print(json.dumps(items, indent=2))


def cmd_report(repo: Path, ticket: str, archive: bool, open_it: bool) -> None:
    sys.path.insert(0, str(HERE))
    import report  # noqa: E402  (sibling module)
    orch = read_json(repo / ".delivery" / "orchestrator.json", [])
    folder = job_folders(repo, orch, Worktrees(repo)).get(ticket)
    if folder is None:
        archived = repo / ".delivery" / "reports" / ticket / "report.html"
        if archived.is_file():
            print(f"{archived}  (job folder is gone; this is the archived copy)")
            if open_it:
                webbrowser.open(archived.resolve().as_uri())
            return
        sys.exit(f"no job folder for {ticket}")
    path = report.write_report(folder, repo if archive else None)
    print(path)
    if open_it:
        webbrowser.open(path.resolve().as_uri())


def cmd_stop(repo: Path) -> None:
    info_path = repo / ".delivery" / "board.json"
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("board not running (no .delivery/board.json)")
        return
    try:
        os.kill(int(info["pid"]), signal.SIGTERM)
        print(f"stopped board pid {info['pid']} ({info.get('url')})")
    except (OSError, KeyError, ValueError) as err:
        print(f"could not stop pid {info.get('pid')}: {err}")
    try:
        info_path.unlink()
    except OSError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Live delivery board for the AI delivery workflow.")
    sub = parser.add_subparsers(dest="cmd")

    def add_repo(p):
        p.add_argument("--repo", default=".", help="main checkout of the project (default: current dir)")

    p_serve = sub.add_parser("serve", help="serve the board (default)")
    add_repo(p_serve)
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_serve.add_argument("--open", action="store_true", help="open the browser")
    p_serve.add_argument("--demo", action="store_true", help="serve the bundled sample project")

    add_repo(sub.add_parser("status", help="print the aggregated JSON"))

    p_event = sub.add_parser("event", help="append one line to .delivery/events.jsonl")
    add_repo(p_event)
    p_event.add_argument("--kind", required=True,
                         help="cycle|dispatch|stage|gate|verdict|question|answer|merge|escalate|error|note")
    p_event.add_argument("--ticket", default=None)
    p_event.add_argument("--text", required=True)
    p_event.add_argument("--actor", default="orchestrator")

    p_inbox = sub.add_parser("inbox", help="list answers dropped by the board")
    add_repo(p_inbox)
    p_inbox.add_argument("--take", action="store_true", help="move them to inbox/done after printing")

    add_repo(sub.add_parser("stop", help="stop the running board"))

    for action in ("pause", "resume"):
        p_ctl = sub.add_parser(action, help=f"ask the running orchestrator to {action} (next cycle)")
        add_repo(p_ctl)
        p_ctl.add_argument("--ticket", default=None, help="only this ticket (default: everything)")
        if action == "pause":
            p_ctl.add_argument("--now", action="store_true", help="stop workers at once instead of after their step")
            p_ctl.add_argument("--reason", default=None)

    p_report = sub.add_parser("report", help="build a ticket's HTML change report (never committed)")
    add_repo(p_report)
    p_report.add_argument("--ticket", required=True)
    p_report.add_argument("--no-archive", action="store_true",
                          help="do not copy it to .delivery/reports/<KEY>/ in the main checkout")
    p_report.add_argument("--open", action="store_true", help="open the report in the browser")

    args = parser.parse_args(sys.argv[1:] or ["serve"])
    if args.cmd in (None, "serve"):
        repo = Path(getattr(args, "repo", "."))
        if getattr(args, "demo", False):
            import tempfile
            sys.path.insert(0, str(HERE))
            import demo  # noqa: E402  (sibling module, only needed for --demo)
            repo = demo.build(Path(tempfile.mkdtemp(prefix="delivery-board-demo-")))
        serve(repo, getattr(args, "port", DEFAULT_PORT), getattr(args, "open", False))
        return
    repo = Path(args.repo).resolve()
    if args.cmd == "status":
        print(json.dumps(aggregate(repo, Worktrees(repo)), indent=2))
    elif args.cmd == "event":
        cmd_event(repo, args.kind, args.ticket, args.text, args.actor)
    elif args.cmd == "inbox":
        cmd_inbox(repo, args.take)
    elif args.cmd == "stop":
        cmd_stop(repo)
    elif args.cmd in ("pause", "resume"):
        cmd_control(repo, args.cmd, args.ticket, getattr(args, "now", False), getattr(args, "reason", None))
    elif args.cmd == "report":
        cmd_report(repo, args.ticket, not args.no_archive, args.open)


if __name__ == "__main__":
    main()
