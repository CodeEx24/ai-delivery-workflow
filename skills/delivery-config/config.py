#!/usr/bin/env python3
"""Read and change a project's delivery settings (docs/workflow/delivery.config.json).

  python config.py --repo . show [--json]
  python config.py --repo . set key=value [key=value ...]
  python config.py --repo . reset key [key ...] | --all

Only values that differ from the defaults are stored. Standard library only.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

CONFIG_PATH = Path("docs") / "workflow" / "delivery.config.json"
SCHEMA = "delivery-config/1"
MERGE_RULES = ("Bash(gh pr merge:*)", "Bash(gh pr merge *)", "Bash(gh pr merge)")

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
}


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


def parse_value(key, raw):
    require_known(key)
    _, kind, low, high, _ = SETTINGS[key]
    text = str(raw).strip()
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
    path = root / CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"schema": SCHEMA}
    body.update({k: stored[k] for k in SETTINGS if k in stored and stored[k] != SETTINGS[k][0]})
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
    values = {k: stored.get(k, spec[0]) for k, spec in SETTINGS.items()}
    permission = merge_permission(root)
    warnings = []
    values["effectiveMergePath"] = values["mergePath"]
    if values["mergePath"] == "agent" and permission != "allow":
        values["effectiveMergePath"] = "owner"
        warnings.append(
            f"mergePath is agent, but '{MERGE_RULES[0]}' is not allowed (found: {permission}), "
            "so you still merge. Add it to permissions.allow in .claude/settings.json "
            "and remove it from ask and deny."
        )
    return values, stored, permission, warnings


def show(root, as_json):
    values, stored, permission, warnings = effective(root)
    if as_json:
        print(json.dumps({"schema": SCHEMA, "file": CONFIG_PATH.as_posix(), "values": values,
                          "mergePermission": permission, "warnings": warnings}, indent=2))
        return
    print(f"Delivery settings: {root / CONFIG_PATH}")
    print(f"{'setting':<23}{'value':<10}{'source':<9}what it controls")
    for key, spec in SETTINGS.items():
        value = values[key]
        shown = ("on" if value else "off") if isinstance(value, bool) else str(value)
        print(f"{key:<23}{shown:<10}{'project' if key in stored else 'default':<9}{spec[4]}")
    print(f"\nWho merges right now: {values['effectiveMergePath']}")
    for warning in warnings:
        print(f"WARNING: {warning}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Delivery settings for one project")
    parser.add_argument("--repo", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    show_cmd = sub.add_parser("show")
    show_cmd.add_argument("--json", action="store_true")
    set_cmd = sub.add_parser("set")
    set_cmd.add_argument("pairs", nargs="+", metavar="key=value")
    reset_cmd = sub.add_parser("reset")
    reset_cmd.add_argument("keys", nargs="*")
    reset_cmd.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)

    try:
        root = repo_root(args.repo)
        if args.command == "show":
            show(root, args.json)
        elif args.command == "set":
            stored = load(root)
            changes = {}
            for pair in args.pairs:
                if "=" not in pair:
                    raise ConfigError(f"'{pair}' is not key=value")
                key, raw = pair.split("=", 1)
                changes[key.strip()] = parse_value(key.strip(), raw)
            stored.update(changes)
            save(root, stored)
            show(root, False)
        else:
            if not args.all and not args.keys:
                raise ConfigError("name the settings to reset, or use --all")
            for key in args.keys:
                require_known(key)
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
