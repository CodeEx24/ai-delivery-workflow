#!/usr/bin/env python3
"""Route /deliver from a folder that holds several repos to the right project.

  python workspace.py --from . route --keys ABC[,XYZ] [--args "--mine"] [--json]
  python workspace.py --from . list [--json]
  python workspace.py --from . map --key ABC --repo <folder>
  python workspace.py --from . unmap --key ABC

Mappings are personal and live in ~/.claude/delivery.workspaces.json, so the workspace folder gets
no new files. This script reads repos and changes none of them. Exit codes: 0 ok, 2 error.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = "delivery-workspaces/1"
KEY_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")
README_KEY = re.compile(r"\bKey:\s*`([A-Z][A-Z0-9]{1,9})`")
VALUE_RE = re.compile(r"^[A-Za-z0-9._/,-]{1,120}$")
FLAGS_WITH_VALUE = {"--only", "--cap", "--base", "--engine", "--pause", "--resume"}
FLAGS = FLAGS_WITH_VALUE | {"--mine", "--dry-run", "--status", "--board", "--now"}
ONE_SHOT = {"--dry-run", "--status", "--board", "--pause"}
REFS = ("origin/HEAD", "origin/staging", "origin/develop", "origin/main", "origin/master")
SKIP = {"node_modules", "dist", "build", "vendor", "venv"}
CONFIG_FILE = "docs/workflow/delivery.config.json"
LOCK_FRESH = timedelta(minutes=45)


class WorkspaceError(Exception):
    pass


def git(repo, *args):
    try:
        done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def store_path():
    override = os.environ.get("DELIVERY_WORKSPACES")
    return Path(override) if override else Path.home() / ".claude" / "delivery.workspaces.json"


def load_store():
    path = store_path()
    if not path.exists():
        return {"schema": SCHEMA, "workspaces": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise WorkspaceError(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("workspaces"), dict):
        raise WorkspaceError(f"{path} has an unexpected format")
    return data


def save_store(data):
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".tmp")
    partial.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(partial, path)


def workspace_id(root):
    return root.resolve().as_posix()


def is_repo(path):
    return (path / ".git").exists()


def find_repos(root):
    found = []
    try:
        children = sorted(p for p in root.iterdir() if p.is_dir())
    except OSError as exc:
        raise WorkspaceError(f"cannot read {root}: {exc}") from exc
    for child in children:
        if child.name.startswith(".") or child.name in SKIP:
            continue
        if is_repo(child):
            found.append(child)
            continue
        try:
            found += sorted(p for p in child.iterdir() if p.is_dir() and not p.name.startswith(".") and is_repo(p))
        except OSError:
            continue
    return found


def read_project_file(repo, relative):
    path = repo / relative
    if path.is_file():
        try:
            return path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            pass
    for ref in REFS:
        text = git(repo, "show", f"{ref}:{relative}")
        if text is not None:
            return text
    return None


def repo_keys(repo):
    """The workflow doc names a repo's own key. Standards ticket keys are only a fallback."""
    text = read_project_file(repo, "docs/workflow/README.md")
    match = README_KEY.search(text or "")
    if match:
        return [match.group(1)]
    raw = read_project_file(repo, ".engineering/config.json")
    try:
        keys = json.loads(raw).get("ticketKeys", []) if raw else []
    except (ValueError, AttributeError):
        return []
    return [k for k in keys if isinstance(k, str) and KEY_RE.match(k)] if isinstance(keys, list) else []


def relative(root, path):
    return path.resolve().relative_to(root.resolve()).as_posix()


def clean_args(raw):
    tokens = (raw or "").split()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token not in FLAGS:
            raise WorkspaceError(f"unsupported /deliver option from a workspace: {token}")
        if token in FLAGS_WITH_VALUE and index + 1 < len(tokens) and not tokens[index + 1].startswith("-"):
            index += 1
            if not VALUE_RE.match(tokens[index]):
                raise WorkspaceError(f"invalid value for {token}")
        elif token in ("--only", "--cap", "--base", "--engine"):
            raise WorkspaceError(f"{token} needs a value")
        index += 1
    return tokens


def prompt_for(key, tokens):
    command = " ".join(["/deliver", key, *tokens])
    return command if ONE_SHOT & set(tokens) else f"/loop {command}"


def base_branch(repo, tokens):
    script = Path(__file__).resolve().parents[1] / "delivery-config" / "config.py"
    args = [sys.executable, "-B", str(script), "--repo", str(repo), "branch", "--json"]
    if "--base" in tokens:
        args[-1:-1] = ["--base", tokens[tokens.index("--base") + 1]]
    try:
        done = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=60, check=False)
        return json.loads(done.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {"error": "could not resolve the base branch"}


def orchestrator_running(repo):
    try:
        data = json.loads((repo / ".delivery" / "orchestrator.json").read_text(encoding="utf-8-sig"))
        beat = datetime.fromisoformat(str(data["lock"]["heartbeatAt"]).replace("Z", "+00:00"))
    except (OSError, ValueError, KeyError, TypeError):
        return False
    if beat.tzinfo is None:
        beat = beat.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - beat < LOCK_FRESH


def inspect(root, repo, key, tokens):
    branch = (git(repo, "branch", "--show-current") or "").strip()
    status = git(repo, "status", "--porcelain")
    changed = [] if status is None else [line for line in status.splitlines() if not line.endswith(CONFIG_FILE)]
    state = base_branch(repo, tokens)
    row = {"key": key, "status": "found", "repo": relative(root, repo), "path": repo.resolve().as_posix(),
           "branch": branch, "base": state.get("base"), "release": state.get("release"),
           "recommendedBase": state.get("recommended"), "baseCandidates": state.get("candidates", []),
           "uncommittedFiles": len(changed), "prompt": prompt_for(key, tokens),
           "launch": ["orca", "agent", "launch", "--agent", "claude", "--worktree", f"path:{repo.resolve().as_posix()}",
                      "--prompt", prompt_for(key, tokens), "--json"],
           "manual": f'cd "{repo.resolve()}"; claude "{prompt_for(key, tokens)}"'}
    if status is None or "error" in state:
        row.update(action="blocked", reason=state.get("error", "git status failed"))
    elif orchestrator_running(repo):
        row.update(action="already-running", reason="a recent /deliver session holds this repo's lock")
    elif state.get("needsChoice"):
        row.update(action="choose-base", reason=state.get("reason"))
    elif state.get("requiresConfirmation"):
        row.update(action="confirm-base", reason=state.get("reason"))
    elif changed:
        row.update(action="blocked", reason=f"{len(changed)} uncommitted file(s) in the main checkout")
    elif branch != state.get("base"):
        row.update(action="switch-branch", reason=f"the checkout is on '{branch or 'detached HEAD'}', not '{state.get('base')}'")
    else:
        row.update(action="launch", reason=None)
    return row


def mapped(root, key, saved):
    value = saved.get(key)
    if not value:
        return None
    path = root / value
    return path if is_repo(path) else None


def route(root, keys, raw_args):
    inside = git(root, "rev-parse", "--show-toplevel")
    if inside:
        return {"mode": "repo", "path": inside.strip(), "projects": []}
    tokens = clean_args(raw_args)
    saved = load_store()["workspaces"].get(workspace_id(root), {})
    repos = find_repos(root)
    if not repos:
        raise WorkspaceError("no Git repos were found in this folder or one level below it")
    known = {repo: repo_keys(repo) for repo in repos}
    projects = []
    for key in keys:
        target = mapped(root, key, saved)
        matches = [target] if target else [repo for repo, names in known.items() if key in names]
        if len(matches) == 1:
            projects.append(inspect(root, matches[0], key, tokens))
        else:
            options = matches or repos
            projects.append({"key": key, "status": "ambiguous" if matches else "unknown", "action": "choose-repo",
                             "reason": f"{len(matches)} repos declare {key}" if matches else f"no repo declares {key}",
                             "candidates": [relative(root, repo) for repo in options]})
    return {"mode": "workspace", "workspace": workspace_id(root), "projects": projects}


def list_projects(root):
    saved = load_store()["workspaces"].get(workspace_id(root), {})
    rows = []
    for repo in find_repos(root):
        name = relative(root, repo)
        pinned = [k for k, v in saved.items() if v == name]
        rows.append({"repo": name, "keys": sorted(set(pinned) | set(repo_keys(repo))), "saved": pinned})
    return {"workspace": workspace_id(root), "repos": rows}


def set_mapping(root, key, repo_name):
    if not KEY_RE.match(key):
        raise WorkspaceError("--key is not a project key")
    path = (root / repo_name).resolve()
    try:
        name = path.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise WorkspaceError("--repo must be inside this workspace") from exc
    if not is_repo(path):
        raise WorkspaceError(f"{repo_name} is not a Git repo")
    data = load_store()
    data["workspaces"].setdefault(workspace_id(root), {})[key] = name
    save_store(data)
    return {"ok": True, "key": key, "repo": name}


def remove_mapping(root, key):
    data = load_store()
    removed = data["workspaces"].get(workspace_id(root), {}).pop(key, None)
    save_store(data)
    return {"ok": True, "key": key, "removed": removed}


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Route /deliver from a multi-repo folder")
    parser.add_argument("--from", dest="start", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    route_cmd = sub.add_parser("route")
    route_cmd.add_argument("--keys", required=True)
    route_cmd.add_argument("--args", default="")
    sub.add_parser("list")
    map_cmd = sub.add_parser("map")
    map_cmd.add_argument("--key", required=True)
    map_cmd.add_argument("--repo", required=True)
    unmap_cmd = sub.add_parser("unmap")
    unmap_cmd.add_argument("--key", required=True)
    for command in (route_cmd, sub.choices["list"], map_cmd, unmap_cmd):
        command.add_argument("--json", action="store_true")
    raw = list(sys.argv[1:] if argv is None else argv)
    if "--args" in raw and raw.index("--args") + 1 < len(raw):  # the value itself starts with dashes
        at = raw.index("--args")
        raw[at:at + 2] = [f"--args={raw[at + 1]}"]
    args = parser.parse_args(raw)
    root = Path(args.start).resolve()
    try:
        if args.command == "route":
            keys = [k.strip().upper() for k in args.keys.split(",") if k.strip()]
            if not keys or not all(KEY_RE.match(k) for k in keys):
                raise WorkspaceError("--keys must be project keys, such as ABC or ABC,XYZ")
            body = route(root, list(dict.fromkeys(keys)), args.args)
        elif args.command == "list":
            body = list_projects(root)
        elif args.command == "map":
            body = set_mapping(root, args.key.upper(), args.repo)
        else:
            body = remove_mapping(root, args.key.upper())
    except WorkspaceError as exc:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(body, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
