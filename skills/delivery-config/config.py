#!/usr/bin/env python3
"""Read and change delivery settings for a project and for this machine.

  python config.py --repo . show [--json]
  python config.py --repo . set [--me] key=value [key=value ...]
  python config.py --repo . reset [--me] key [key ...] | --all
  python config.py --repo . branch [--base BRANCH] [--json]
  python config.py --repo . statuses show | suggest --from FILE [--save] | check --from FILE
                                   | set stage=Status ... | reset [stage ...|--all] | target --event EVENT

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
    return {k: parse_value(k, v) for k, v in data.items() if k not in ("schema", "statuses")}


def save(root, stored):
    body = {"schema": SCHEMA}
    body.update({k: stored[k] for k in SETTINGS if k in stored and stored[k] != SETTINGS[k][0]})
    # Keep the statuses block exactly as written (names or guide objects), after validating it.
    if load_status_entries(root):
        body["statuses"] = read_config_json(root)["statuses"]
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
                          "machine": specs, "mergePermission": permission, "statuses": load_statuses(root),
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
    mapping = load_statuses(root)
    print("\nTICKET STATUSES (team, see: /delivery-config statuses)")
    for stage in STAGES:
        print(f"  {stage:<19}{mapping.get(stage, 'not used')}")
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


# Ticket statuses: each project maps its own tracker statuses to these stages.
STAGES = ("todo", "inProgress", "inReview", "testingStaging", "doneStaging", "testingProduction", "done")
STAGE_TEXT = {
    "todo": "Ready to start",
    "inProgress": "Being built or fixed",
    "inReview": "PR is open",
    "testingStaging": "Merged; QA checks it on staging (or the only testing step)",
    "doneStaging": "Passed on staging, waiting for release",
    "testingProduction": "Released; being checked in production",
    "done": "Finished",
}
# Each event moves a ticket to the first stage the project has, in this order.
EVENTS = {
    "start": ("inProgress",),
    "prOpened": ("inReview",),
    "merged": ("testingStaging", "doneStaging", "done"),
    "qaPassed": ("doneStaging", "done"),
    "released": ("testingProduction", "done"),
    "verified": ("done",),
    "qaFailed": ("inProgress", "todo"),
    "ciFailed": ("inProgress", "todo"),
}
PERSON_EVENTS = ("qaPassed", "verified")
# Who may move a ticket INTO each stage, and when. A project can override any of these per stage.
MOVERS = ("agent", "person", "any")
DEFAULT_MOVED_BY = {
    "todo": "any",
    "inProgress": "agent",
    "inReview": "agent",
    "testingStaging": "agent",
    "doneStaging": "person",
    "testingProduction": "any",
    "done": "any",
}
DEFAULT_WHEN = {
    "todo": "Only when QA fails and the project has no in-progress status",
    "inProgress": "When work on the ticket starts, or when QA fails and it goes back for a fix",
    "inReview": "When the PR is opened",
    "testingStaging": "After the PR is merged and the deploy to staging is green. Then stop: a tester moves it on",
    "doneStaging": "Only a tester, after QA passes on staging",
    "testingProduction": "After the release to production",
    "done": "When the work is finished: after the production check, or after the merge if the project has no testing step",
}
GUIDE_TEXT_MAX = 300
CANCELLED = ("cancel", "won t", "wont", "reject", "duplicate", "invalid", "abandon")
TODO_NAMES = ("to do", "todo", "ready", "ready for dev", "ready for development", "selected for development",
              "open", "backlog")
CATEGORY = {"new": "new", "to do": "new", "todo": "new", "backlog": "new", "unstarted": "new", "triage": "new",
            "indeterminate": "indeterminate", "in progress": "indeterminate", "started": "indeterminate",
            "done": "done", "completed": "done", "complete": "done", "closed": "done",
            "canceled": "canceled", "cancelled": "canceled"}


def clean_status(name):
    text = str(name).strip()
    if not text or len(text) > 80 or any(ord(ch) < 32 for ch in text):
        raise ConfigError("a status name must be 1 to 80 printable characters")
    return text


def read_config_json(root):
    path = root / CONFIG_PATH
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"cannot read {CONFIG_PATH}: {exc}")
    if not isinstance(data, dict):
        raise ConfigError(f"{CONFIG_PATH} must be a JSON object")
    return data


def clean_guide_text(stage, key, value):
    if not isinstance(value, str) or not value.strip() or len(value) > GUIDE_TEXT_MAX:
        raise ConfigError(f"statuses.{stage}.{key} must be text of 1 to {GUIDE_TEXT_MAX} characters")
    return value.strip()


def parse_status_entry(stage, entry):
    """A stage maps to a status name, or to {name, meaning?, movedBy?, when?}."""
    if isinstance(entry, str):
        return {"name": clean_status(entry)}
    if not isinstance(entry, dict) or "name" not in entry:
        raise ConfigError(f"statuses.{stage} must be a status name or an object with a name")
    unknown = set(entry) - {"name", "meaning", "movedBy", "when"}
    if unknown:
        raise ConfigError(f"statuses.{stage} has unknown keys: {', '.join(sorted(unknown))}")
    parsed = {"name": clean_status(entry["name"])}
    for key in ("meaning", "when"):
        if key in entry:
            parsed[key] = clean_guide_text(stage, key, entry[key])
    if "movedBy" in entry:
        if entry["movedBy"] not in MOVERS:
            raise ConfigError(f"statuses.{stage}.movedBy must be one of: {', '.join(MOVERS)}")
        parsed["movedBy"] = entry["movedBy"]
    return parsed


def load_status_entries(root):
    raw = read_config_json(root).get("statuses")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError("statuses must be an object of stage: status name")
    found = {}
    for stage, entry in raw.items():
        if stage not in STAGES:
            raise ConfigError(f"unknown stage '{stage}'. Stages: {', '.join(STAGES)}")
        found[stage] = parse_status_entry(stage, entry)
    return found


def load_statuses(root):
    return {stage: entry["name"] for stage, entry in load_status_entries(root).items()}


def status_guide(entries):
    """Every mapped stage with its meaning, who may move a ticket into it, and when."""
    return {
        stage: {
            "status": entries[stage]["name"],
            "meaning": entries[stage].get("meaning", STAGE_TEXT[stage]),
            "movedBy": entries[stage].get("movedBy", DEFAULT_MOVED_BY[stage]),
            "when": entries[stage].get("when", DEFAULT_WHEN[stage]),
        }
        for stage in STAGES
        if stage in entries
    }


def save_statuses(root, mapping):
    """Save stage: name pairs. A stage already written as an object keeps its guide text."""
    data = read_config_json(root) or {"schema": SCHEMA}
    data.setdefault("schema", SCHEMA)
    old = data.get("statuses") if isinstance(data.get("statuses"), dict) else {}
    if mapping:
        out = {}
        for stage in STAGES:
            if stage not in mapping:
                continue
            previous = old.get(stage)
            out[stage] = {**previous, "name": mapping[stage]} if isinstance(previous, dict) else mapping[stage]
        data["statuses"] = out
    else:
        data.pop("statuses", None)
    write_json(root / CONFIG_PATH, data)


def status_allowed(entries, target, actor):
    """May this actor move a ticket into `target` (a stage key or a tracker status name)?"""
    guide = status_guide(entries)
    stage = target if target in guide else next(
        (s for s, g in guide.items() if g["status"].lower() == str(target).strip().lower()), None)
    body = {"target": target, "actor": actor, "stage": stage, "status": None, "movedBy": None,
            "allowed": False, "reason": None}
    if not guide:
        body["reason"] = "this project has no status mapping yet. Run /delivery-config statuses"
        return body
    if stage is None:
        body["reason"] = (f"'{target}' is not in this project's status mapping. Leave the ticket where it is "
                          "and ask the owner")
        return body
    g = guide[stage]
    body.update(status=g["status"], movedBy=g["movedBy"], when=g["when"])
    if actor == "agent" and g["movedBy"] == "person":
        body["reason"] = f"only a person moves a ticket to '{g['status']}': {g['when']}"
        return body
    body["allowed"] = True
    return body


def norm(name):
    return re.sub(r"[^a-z0-9]+", " ", str(name).lower()).strip()


def read_tracker_statuses(path):
    """Accept [{name, category}], ["name"], or Jira's transitions response as-is."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}")
    if isinstance(data, dict) and isinstance(data.get("transitions"), list):
        data = [{"name": (t.get("to") or {}).get("name") or t.get("name"),
                 "category": ((t.get("to") or {}).get("statusCategory") or {}).get("key")}
                for t in data["transitions"] if isinstance(t, dict)]
    if isinstance(data, dict) and isinstance(data.get("statuses"), list):
        data = data["statuses"]
    if not isinstance(data, list):
        raise ConfigError("the status list must be a JSON list")
    found, seen = [], set()
    for item in data:
        name = item.get("name") if isinstance(item, dict) else item
        category = item.get("category") if isinstance(item, dict) else None
        if not isinstance(name, str) or not name.strip():
            continue
        name = clean_status(name)
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        found.append((name, CATEGORY.get(norm(category), "") if category else ""))
    if not found:
        raise ConfigError("the status list is empty")
    return found


def has(text, *words):
    """Whole-word prefix match: 'stag' matches 'staging', but 'live' does not match 'delivered'."""
    tokens = text.split()
    return any((word in text) if " " in word else any(t.startswith(word) for t in tokens) for word in words)


def cancelled(name, category):
    return category == "canceled" or any(word in norm(name) for word in CANCELLED)


def suggest_statuses(statuses):
    pool = [(name, cat, norm(name)) for name, cat in statuses if not cancelled(name, cat)]
    mapping, how, taken = {}, {}, set()

    def testing(text):
        return has(text, "test", "qa", "uat", "verif", "validat")

    def staging(text):
        return has(text, "stag", "stg", "preprod", "pre prod")

    def production(text):
        return has(text, "prod", "live")

    def finished(text):
        return has(text, "done", "complete", "closed", "resolved", "released", "deployed", "merged", "shipped")

    def pick(stage, test, why, order=None):
        if stage in mapping:
            return
        hits = [row for row in pool if row[0] not in taken and test(row)]
        if order:
            hits.sort(key=order)
        if hits:
            mapping[stage], how[stage] = hits[0][0], why
            taken.add(hits[0][0])

    pick("testingProduction", lambda r: testing(r[2]) and production(r[2]), "name")
    pick("doneStaging", lambda r: finished(r[2]) and staging(r[2]), "name")
    pick("testingStaging", lambda r: testing(r[2]) and staging(r[2]), "name")
    pick("testingStaging", lambda r: testing(r[2]) and not production(r[2]) and r[1] != "done", "name (general testing step)")
    pick("inReview", lambda r: has(r[2], "review") or r[2] in ("pr", "pull request"), "name")
    pick("todo", lambda r: r[2] in TODO_NAMES, "name", order=lambda r: TODO_NAMES.index(r[2]))
    pick("inProgress", lambda r: has(r[2], "progress", "doing", "develop", "wip", "started", "implement", "building"), "name")
    pick("done", lambda r: r[1] == "done" and not staging(r[2]), "category", order=lambda r: r[2] != "done")
    pick("done", lambda r: finished(r[2]) and not staging(r[2]) and not testing(r[2]), "name")
    pick("todo", lambda r: r[1] == "new", "category")
    pick("inProgress", lambda r: r[1] == "indeterminate" and not testing(r[2]) and not has(r[2], "review"), "category")
    unmapped = [name for name, cat in statuses if name not in taken and not cancelled(name, cat)]
    return {"mapping": {s: mapping[s] for s in STAGES if s in mapping}, "matchedBy": how,
            "missingStages": [s for s in STAGES if s not in mapping], "unmappedStatuses": unmapped}


def check_statuses(mapping, statuses):
    names = {name.lower() for name, _ in statuses}
    missing = [{"stage": s, "status": mapping[s]} for s in STAGES if s in mapping and mapping[s].lower() not in names]
    used = {v.lower() for v in mapping.values()}
    new = [name for name, cat in statuses if name.lower() not in used and not cancelled(name, cat)]
    return {"ok": not missing and bool(mapping), "configured": bool(mapping), "missing": missing, "unmapped": new}


def status_target(mapping, event, entries=None):
    if event not in EVENTS:
        raise ConfigError(f"unknown event '{event}'. Events: {', '.join(EVENTS)}")
    body = {"event": event, "stage": None, "status": None, "requiresPerson": event in PERSON_EVENTS,
            "needsSetup": not mapping, "reason": None}
    if not mapping:
        body["reason"] = "this project has no status mapping yet. Run /delivery-config statuses"
        return body
    guide = status_guide(entries if entries is not None else {s: {"name": n} for s, n in mapping.items()})
    for stage in EVENTS[event]:
        if stage in mapping:
            body.update(stage=stage, status=mapping[stage], when=guide[stage]["when"])
            if guide[stage]["movedBy"] == "person":
                body["requiresPerson"] = True
                body["reason"] = f"only a person moves a ticket to '{mapping[stage]}': {guide[stage]['when']}"
            return body
    body["reason"] = f"this project has no status for '{event}', so leave the ticket where it is"
    return body


def run_statuses(root, args):
    entries = load_status_entries(root)
    mapping = {stage: entry["name"] for stage, entry in entries.items()}
    if args.action == "guide":
        guide = status_guide(entries)
        if args.json:
            print(json.dumps({"guide": guide}, indent=2))
        elif not guide:
            print("No mapping yet. Read the tracker's statuses, then: /delivery-config statuses suggest")
        else:
            who = {"agent": "the workflow", "person": "a person only", "any": "the workflow or a person"}
            print(f"Ticket statuses in {root / CONFIG_PATH}\n")
            for stage, g in guide.items():
                print(f"{g['status']}  ({stage})\n  Means:    {g['meaning']}\n  Moved by: {who[g['movedBy']]}\n"
                      f"  When:     {g['when']}\n")
        return 0
    if args.action == "allowed":
        body = status_allowed(entries, args.to, args.actor)
        print(json.dumps(body, indent=2))
        return 0 if body["allowed"] else 1
    if args.action == "show":
        body = {"statuses": mapping, "stages": {s: STAGE_TEXT[s] for s in STAGES}, "guide": status_guide(entries),
                "events": {e: list(v) for e, v in EVENTS.items()}, "personEvents": list(PERSON_EVENTS)}
        if args.json:
            print(json.dumps(body, indent=2))
        else:
            print(f"Ticket statuses in {root / CONFIG_PATH}")
            for stage in STAGES:
                print(f"  {stage:<19}{mapping.get(stage, 'not used'):<24}{STAGE_TEXT[stage]}")
            if not mapping:
                print("No mapping yet. Read the tracker's statuses, then: /delivery-config statuses suggest")
        return 0
    if args.action in ("suggest", "check"):
        statuses = read_tracker_statuses(args.source)
        body = suggest_statuses(statuses) if args.action == "suggest" else check_statuses(mapping, statuses)
        if args.action == "suggest" and args.save:
            if not body["mapping"]:
                raise ConfigError("nothing could be matched, so nothing was saved")
            save_statuses(root, body["mapping"])
            body["saved"] = True
        print(json.dumps(body, indent=2))
        return 0 if args.action == "suggest" or body["ok"] else 1
    if args.action == "set":
        for pair in args.pairs:
            if "=" not in pair:
                raise ConfigError(f"'{pair}' is not stage=Status")
            stage, name = (part.strip() for part in pair.split("=", 1))
            if stage not in STAGES:
                raise ConfigError(f"unknown stage '{stage}'. Stages: {', '.join(STAGES)}")
            mapping[stage] = clean_status(name)
        save_statuses(root, mapping)
    elif args.action == "reset":
        if not args.all and not args.stages:
            raise ConfigError("name the stages to reset, or use --all")
        for stage in args.stages:
            if stage not in STAGES:
                raise ConfigError(f"unknown stage '{stage}'")
            mapping.pop(stage, None)
        save_statuses(root, {} if args.all else mapping)
    elif args.action == "target":
        body = status_target(mapping, args.event, entries)
        print(json.dumps(body, indent=2))
        return 1 if body["needsSetup"] else 0
    print(json.dumps({"ok": True, "statuses": load_statuses(root)}, indent=2))
    return 0


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
    status_cmd = sub.add_parser("statuses")
    status_sub = status_cmd.add_subparsers(dest="action", required=True)
    status_show = status_sub.add_parser("show")
    status_show.add_argument("--json", action="store_true")
    for name in ("suggest", "check"):
        cmd = status_sub.add_parser(name)
        cmd.add_argument("--from", dest="source", required=True)
        if name == "suggest":
            cmd.add_argument("--save", action="store_true")
    status_set = status_sub.add_parser("set")
    status_set.add_argument("pairs", nargs="+", metavar="stage=Status")
    status_reset = status_sub.add_parser("reset")
    status_reset.add_argument("stages", nargs="*")
    status_reset.add_argument("--all", action="store_true")
    status_target_cmd = status_sub.add_parser("target")
    status_target_cmd.add_argument("--event", required=True)
    status_guide_cmd = status_sub.add_parser("guide")
    status_guide_cmd.add_argument("--json", action="store_true")
    status_allowed_cmd = status_sub.add_parser("allowed")
    status_allowed_cmd.add_argument("--to", required=True, help="tracker status name or stage key")
    status_allowed_cmd.add_argument("--actor", choices=("agent", "person"), default="agent")
    args = parser.parse_args(argv)

    try:
        root = repo_root(args.repo)
        if args.command == "statuses":
            return run_statuses(root, args)
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
