#!/usr/bin/env python3
"""Read and change delivery settings for a project and for this machine.

  python config.py --repo . show [--json]
  python config.py --repo . set [--me] key=value [key=value ...]
  python config.py --repo . reset [--me] key [key ...] | --all
  python config.py --repo . branch [--base BRANCH] [--json]

Team settings live in docs/workflow/delivery.config.json and are committed.
Personal settings (--me) live in ~/.claude/delivery.machine.json and win over the project's.
Only values that differ from the defaults are stored for a project. Standard library only.
branch exits 0 when resolved, 1 when a person must choose, 2 on error, 3 when a target needs a yes.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

CONFIG_PATH = Path("docs") / "workflow" / "delivery.config.json"
STANDARDS_PATH = Path(".engineering") / "config.json"
STANDARDS_KEYS = {"baseBranch": "baseBranch", "releaseBranch": "productionBranch"}
SCHEMA = "delivery-config/1"
MACHINE_SCHEMA = "delivery-machine-config/1"
MERGE_RULES = ("Bash(gh pr merge:*)", "Bash(gh pr merge *)", "Bash(gh pr merge)")
BRANCH_RE = re.compile(r"^(?!-)(?!.*\.\.)(?!.*//)(?!.*\.lock$)[A-Za-z0-9._/-]{1,100}(?<![./])$")
LONG_LIVED = ("staging", "develop", "development", "dev", "next")

# key: (default, type or choices, minimum, maximum, what it controls)
SETTINGS = {
    "cap": (2, int, 1, 10, "Tickets (worker agents) in flight at once"),
    "maxRounds": (3, int, 1, 6, "Fix-and-review rounds before a ticket escalates to you"),
    "loopMinutes": ("auto", "auto-or-int", 1, 60, "Minutes between loop wake-ups; auto paces by activity"),
    "idleReleaseMin": (60, int, 5, 1440, "Minutes a worker waits on you before it is released"),
    "autoAcceptRecommended": (False, bool, None, None, "Accept the recommended option on routine questions"),
    "mergePath": ("owner", ("owner", "agent"), None, None, "Who merges an approved PR"),
    "mergeStrategy": ("squash", ("squash", "merge", "rebase"), None, None, "How PRs are merged"),
    "workerMayPush": (True, bool, None, None, "Workers push ticket branches and open draft PRs"),
    "deviceLane": (True, bool, None, None, "Run the browser or device tester"),
    "engine": ("orca", ("orca", "subagents"), None, None, "How workers run"),
    "diskWarnGb": (15, int, 1, 1000, "Warn when free disk falls below this many GB"),
    "baseBranch": (None, "branch", None, None, "Branch tickets start from and PRs target"),
    "releaseBranch": (None, "branch", None, None, "Production branch; unset means the repo default"),
}

# Settings about one computer. Everything else is a team rule and cannot be set personally.
MACHINE_KEYS = ("cap", "loopMinutes", "idleReleaseMin", "engine", "diskWarnGb")


class ConfigError(Exception):
    pass


def repo_root(start):
    try:
        out = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(out.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        raise ConfigError(f"{start} is not inside a git repository")


def require_known(key):
    if key not in SETTINGS:
        raise ConfigError(f"unknown setting '{key}'. Known: {', '.join(SETTINGS)}")


def require_machine_key(key):
    require_known(key)
    if key not in MACHINE_KEYS:
        raise ConfigError(
            f"{key} is a team rule and cannot be set with --me. "
            f"Personal settings: {', '.join(MACHINE_KEYS)}"
        )


def parse_value(key, raw):
    require_known(key)
    _, kind, low, high, _ = SETTINGS[key]
    text = str(raw).strip()
    if kind == "branch":
        if not BRANCH_RE.match(text):
            raise ConfigError(f"{key} is not a valid branch name")
        return text
    if kind is bool:
        lowered = text.lower()
        if lowered in ("true", "yes", "on"):
            return True
        if lowered in ("false", "no", "off"):
            return False
        raise ConfigError(f"{key} must be on or off")
    if isinstance(kind, tuple):
        if text.lower() not in kind:
            raise ConfigError(f"{key} must be one of: {', '.join(kind)}")
        return text.lower()
    if kind == "auto-or-int" and text.lower() == "auto":
        return "auto"
    try:
        number = int(text)
    except ValueError:
        hint = "auto or a whole number" if kind == "auto-or-int" else "a whole number"
        raise ConfigError(f"{key} must be {hint}")
    if not low <= number <= high:
        raise ConfigError(f"{key} must be between {low} and {high}")
    return number


def allowed_values(key):
    _, kind, low, high, _ = SETTINGS[key]
    if kind == "branch":
        return "branch name"
    if kind is bool:
        return "on, off"
    if isinstance(kind, tuple):
        return ", ".join(kind)
    if kind == "auto-or-int":
        return f"auto, {low}-{high}"
    return f"{low}-{high}"


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


def load(root):
    path = root / CONFIG_PATH
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"cannot read {CONFIG_PATH}: {exc}")
    if not isinstance(data, dict):
        raise ConfigError(f"{CONFIG_PATH} must be a JSON object")
    return {k: parse_value(k, v) for k, v in data.items() if k != "schema"}


def save(root, stored):
    body = {"schema": SCHEMA}
    body.update({k: stored[k] for k in SETTINGS if k in stored and stored[k] != SETTINGS[k][0]})
    write_json(root / CONFIG_PATH, body)


def machine_path():
    override = os.environ.get("DELIVERY_MACHINE_CONFIG")
    return Path(override) if override else Path.home() / ".claude" / "delivery.machine.json"


def load_machine():
    """Return (values, warnings). A bad personal file never stops delivery or widens a team rule."""
    path = machine_path()
    if not path.exists():
        return {}, []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return {}, [f"ignored your machine settings, cannot read {path}: {exc}"]
    if not isinstance(data, dict):
        return {}, [f"ignored your machine settings, {path} must be a JSON object"]
    values, warnings = {}, []
    for key, raw in data.items():
        if key == "schema":
            continue
        if key not in MACHINE_KEYS:
            warnings.append(f"ignored '{key}' in your machine settings: it is not a personal setting")
            continue
        try:
            values[key] = parse_value(key, raw)
        except ConfigError as exc:
            warnings.append(f"ignored your machine setting: {exc}")
    return values, warnings


def save_machine(values):
    path = machine_path()
    if not values:
        if path.exists():
            path.unlink()
        return
    body = {"schema": MACHINE_SCHEMA}
    body.update({k: values[k] for k in MACHINE_KEYS if k in values})
    write_json(path, body)


def total_ram_gb():
    try:
        if os.name == "nt":
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(MemoryStatus)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return None
            total = status.ullTotalPhys
        else:
            total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        return round(total / 1024 ** 3)
    except (AttributeError, OSError, ValueError):
        return None


def machine_specs():
    cpus = os.cpu_count()
    ram = total_ram_gb()
    suggested = None
    if cpus and ram:
        suggested = max(1, min(6, cpus // 4, ram // 8))
    return {"cpuThreads": cpus, "ramGb": ram, "suggestedCap": suggested}


def merge_permission(root):
    """Return 'allow', 'ask', 'deny' or 'none' for gh pr merge. Deny beats ask beats allow."""
    files = [
        root / ".claude" / "settings.local.json",
        root / ".claude" / "settings.json",
        Path.home() / ".claude" / "settings.json",
    ]
    found = set()
    for file in files:
        try:
            perms = json.loads(file.read_text(encoding="utf-8-sig")).get("permissions", {})
        except (OSError, ValueError, AttributeError):
            continue
        if not isinstance(perms, dict):
            continue
        for level in ("allow", "ask", "deny"):
            if any(rule in MERGE_RULES for rule in perms.get(level, [])):
                found.add(level)
    for level in ("deny", "ask", "allow"):
        if level in found:
            return level
    return "none"


def effective(root):
    stored = load(root)
    machine, warnings = load_machine()
    values, sources = {}, {}
    for key, spec in SETTINGS.items():
        if key in machine:
            values[key], sources[key] = machine[key], "me"
        elif key in stored:
            values[key], sources[key] = stored[key], "project"
        else:
            values[key], sources[key] = spec[0], "default"
    permission = merge_permission(root)
    values["effectiveMergePath"] = values["mergePath"]
    if values["mergePath"] == "agent" and permission != "allow":
        values["effectiveMergePath"] = "owner"
        warnings.append(
            f"mergePath is agent, but '{MERGE_RULES[0]}' is not allowed (found: {permission}), "
            "so you still merge. Add it to permissions.allow in .claude/settings.json "
            "and remove it from ask and deny."
        )
    return values, sources, permission, warnings


def print_rows(keys, values, sources):
    print(f"{'setting':<23}{'value':<10}{'source':<9}{'allowed':<22}what it controls")
    for key in keys:
        value = values[key]
        shown = ("on" if value else "off") if isinstance(value, bool) else str(value)
        shown = "not set" if value is None else shown
        print(f"{key:<23}{shown:<10}{sources[key]:<9}{allowed_values(key):<22}{SETTINGS[key][4]}")


def show(root, as_json):
    values, sources, permission, warnings = effective(root)
    specs = machine_specs()
    suggested = specs["suggestedCap"]
    if suggested and values["cap"] > suggested:
        warnings.append(
            f"cap {values['cap']} is above the {suggested} suggested for this computer. "
            "If it slows down, lower it with: /delivery-config --me cap=" + str(suggested)
        )
    if as_json:
        print(json.dumps({"schema": SCHEMA, "file": CONFIG_PATH.as_posix(),
                          "machineFile": str(machine_path()), "values": values, "sources": sources,
                          "machine": specs, "mergePermission": permission,
                          "warnings": warnings}, indent=2))
        return
    team_keys = [key for key in SETTINGS if key not in MACHINE_KEYS]
    cpu = specs["cpuThreads"] or "unknown"
    ram = f"{specs['ramGb']} GB" if specs["ramGb"] else "unknown"
    print(f"Team settings:     {root / CONFIG_PATH}")
    print(f"Your settings:     {machine_path()}")
    print(f"This computer:     {cpu} CPU threads, {ram} RAM, suggested cap: {suggested or 'unknown'}")
    print("\nYOUR MACHINE (only you, in every project)")
    print_rows(MACHINE_KEYS, values, sources)
    print("\nTEAM RULES (everyone on this project, commit the file)")
    print_rows(team_keys, values, sources)
    print(f"\nWho merges right now: {values['effectiveMergePath']}")
    print("\nHow to change")
    print("  Just for me:       /delivery-config --me cap=4")
    print("  Undo mine:         /delivery-config reset --me cap")
    print("  Undo all mine:     /delivery-config reset --me --all")
    print("  For the team:      /delivery-config maxRounds=4")
    print("  PR target branch:  /delivery-config baseBranch=staging")
    print("  Undo team value:   /delivery-config reset maxRounds")
    for warning in warnings:
        print(f"WARNING: {warning}")


def git_out(root, *args):
    try:
        done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def repo_branches(root):
    """Return (branches, default branch), from origin when it exists, else from local branches."""
    branches, default = [], None
    remote = git_out(root, "ls-remote", "--symref", "origin", "HEAD", "refs/heads/*") or ""
    for line in remote.splitlines():
        if line.startswith("ref: refs/heads/") and line.endswith("\tHEAD"):
            default = line[len("ref: refs/heads/"):-len("\tHEAD")]
        elif "\trefs/heads/" in line:
            branches.append(line.split("\trefs/heads/", 1)[1])
    if not branches:
        local = git_out(root, "for-each-ref", "--format=%(refname:short)", "refs/heads") or ""
        branches = [line.strip() for line in local.splitlines() if line.strip()]
    if default not in branches:
        default = next((name for name in ("main", "master") if name in branches), None)
        default = default or (branches[0] if branches else None)
    return branches, default


def merged_pr_targets(root):
    try:
        done = subprocess.run(["gh", "pr", "list", "--state", "merged", "--limit", "50", "--json", "baseRefName"],
                              cwd=str(root), capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=30, check=False)
        rows = json.loads(done.stdout) if done.returncode == 0 else []
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return Counter()
    return Counter(row.get("baseRefName") for row in rows if isinstance(row, dict))


def branch_candidates(branches, default):
    names = [name for name in LONG_LIVED if name in branches]
    if default and default not in names:
        names.append(default)
    return names


def recommend_branch(branches, default, counts):
    names = branch_candidates(branches, default)
    used = [name for name in names if counts.get(name)]
    if used:
        return max(used, key=lambda name: (counts[name], name != default))
    return names[0] if names else None


def load_standards(root):
    """Branch values from the standards kit, so both tools share one answer."""
    text = None
    try:
        text = (root / STANDARDS_PATH).read_text(encoding="utf-8-sig")
    except OSError:
        # The checkout may be on an old branch, so also read the shared branches.
        for ref in ("origin/staging", "origin/develop", "origin/HEAD", "origin/main", "origin/master"):
            text = git_out(root, "show", f"{ref}:{STANDARDS_PATH.as_posix()}")
            if text:
                break
    try:
        data = json.loads(text) if text else {}
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    found = {}
    for key, name in STANDARDS_KEYS.items():
        value = data.get(name)
        if isinstance(value, str) and BRANCH_RE.match(value):
            found[key] = value
    return found


def sync_standards(root, changes):
    """Keep .engineering/config.json in step, so PR checks accept the saved target."""
    path = root / STANDARDS_PATH
    wanted = {STANDARDS_KEYS[k]: v for k, v in changes.items() if k in STANDARDS_KEYS}
    if not wanted or not path.exists():
        return
    text = path.read_bytes().decode("utf-8-sig")
    for name, value in wanted.items():
        pattern = rf'("{name}"\s*:\s*)"[^"]*"'
        if re.search(pattern, text):
            text = re.sub(pattern, lambda m: f'{m.group(1)}"{value}"', text, count=1)
        else:
            text = text.replace("{", f'{{\n  "{name}": "{value}",', 1)
    json.loads(text)
    path.write_bytes(text.encode("utf-8"))


def branch_state(root, override=None):
    stored = {**load_standards(root), **load(root)}
    own = load(root)
    branches, default = repo_branches(root)
    if not branches:
        raise ConfigError("this repository has no branches yet. Make a first commit, then run this again")
    release = stored.get("releaseBranch") or default
    configured = stored.get("baseBranch")
    counts = merged_pr_targets(root)
    recommended = recommend_branch(branches, default, counts)
    body = {"base": None, "release": release, "default": default, "source": None, "needsChoice": False,
            "requiresConfirmation": False, "recommended": recommended, "reason": None,
            "candidates": [{"branch": name, "mergedPrs": counts.get(name, 0), "production": name == release}
                           for name in branch_candidates(branches, default)],
            "saveCommand": f"/delivery-config baseBranch={recommended}", "warnings": []}
    if release not in branches:
        body["warnings"].append(f"releaseBranch '{release}' does not exist")
    standards = load_standards(root)
    for key in STANDARDS_KEYS:
        if key in own and key in standards and own[key] != standards[key]:
            body["warnings"].append(f"{key} is {own[key]} here but {standards[key]} in {STANDARDS_PATH.as_posix()}. "
                                    f"Run /delivery-config {key}={own[key]} to align them")
    if override:
        value = parse_value("baseBranch", override)
        if value not in branches:
            raise ConfigError(f"branch '{value}' does not exist")
        body.update(base=value, source="run")
        separate = (configured and configured != release) or any(n != release for n in branch_candidates(branches, default))
        if value == release and separate:
            body["requiresConfirmation"] = True
            body["reason"] = f"'{value}' is the production branch and this repo has a separate integration branch"
    elif configured and configured in branches:
        body.update(base=configured, source="project" if "baseBranch" in own else "standards")
    elif configured:
        body.update(needsChoice=True, reason=f"the saved base branch '{configured}' no longer exists")
    else:
        body.update(needsChoice=True, reason="this repo has no saved base branch")
    return body


def show_branch(root, override, as_json):
    body = branch_state(root, override)
    if as_json:
        print(json.dumps(body, indent=2))
    elif body["needsChoice"]:
        print(f"Choose a base branch: {body['reason']}.")
        for row in body["candidates"]:
            mark = " (Recommended)" if row["branch"] == body["recommended"] else ""
            note = ", production" if row["production"] else ""
            print(f"  {row['branch']}{mark}: {row['mergedPrs']} recent merged PRs{note}")
        print(f"Save it with: {body['saveCommand']}")
    else:
        print(f"Base branch: {body['base']} ({body['source']})  Release branch: {body['release']}")
        if body["requiresConfirmation"]:
            print(f"Needs a yes: {body['reason']}")
    if not as_json:
        for warning in body["warnings"]:
            print(f"WARNING: {warning}")
    return 1 if body["needsChoice"] else 3 if body["requiresConfirmation"] else 0


def check_branches_exist(root, changes):
    wanted = {k: v for k, v in changes.items() if k in ("baseBranch", "releaseBranch")}
    if wanted:
        branches, _ = repo_branches(root)
        for key, value in wanted.items():
            if branches and value not in branches:
                raise ConfigError(f"{key}: branch '{value}' does not exist. Branches: {', '.join(branches[:20])}")


def parse_pairs(pairs):
    changes = {}
    for pair in pairs:
        if "=" not in pair:
            raise ConfigError(f"'{pair}' is not key=value")
        key, raw = pair.split("=", 1)
        changes[key.strip()] = parse_value(key.strip(), raw)
    return changes


def main(argv=None):
    parser = argparse.ArgumentParser(description="Delivery settings for a project and this machine")
    parser.add_argument("--repo", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    show_cmd = sub.add_parser("show")
    show_cmd.add_argument("--json", action="store_true")
    set_cmd = sub.add_parser("set")
    set_cmd.add_argument("--me", action="store_true", help="only this computer")
    set_cmd.add_argument("pairs", nargs="+", metavar="key=value")
    reset_cmd = sub.add_parser("reset")
    reset_cmd.add_argument("--me", action="store_true", help="only this computer")
    reset_cmd.add_argument("keys", nargs="*")
    reset_cmd.add_argument("--all", action="store_true")
    branch_cmd = sub.add_parser("branch")
    branch_cmd.add_argument("--base")
    branch_cmd.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        root = repo_root(args.repo)
        if args.command == "branch":
            return show_branch(root, args.base, args.json)
        if args.command == "show":
            show(root, args.json)
        elif args.command == "set":
            changes = parse_pairs(args.pairs)
            if args.me:
                for key in changes:
                    require_machine_key(key)
            else:
                check_branches_exist(root, changes)
            if args.me:
                machine, _ = load_machine()
                machine.update(changes)
                save_machine(machine)
            else:
                stored = load(root)
                stored.update(changes)
                save(root, stored)
                sync_standards(root, changes)
            show(root, False)
        else:
            if not args.all and not args.keys:
                raise ConfigError("name the settings to reset, or use --all")
            for key in args.keys:
                require_machine_key(key) if args.me else require_known(key)
            if args.me:
                machine, _ = load_machine()
                machine = {} if args.all else {k: v for k, v in machine.items() if k not in args.keys}
                save_machine(machine)
            else:
                stored = {} if args.all else load(root)
                for key in args.keys:
                    stored.pop(key, None)
                save(root, stored)
            show(root, False)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
