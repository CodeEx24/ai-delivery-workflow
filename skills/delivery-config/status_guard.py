#!/usr/bin/env python3
"""Status guard: a Claude Code hook that stops agents moving tracker tickets the wrong way.

Agents read the status guide, but a guide is advice. This hook checks every Jira transition an
agent makes through an Atlassian MCP connector, before it happens:

  1. A status a person owns (movedBy "person", for example DONE STAGING) is refused, unless a
     person said so and a one-time permit was written for that ticket and status.
  2. No skipping: an agent moves a ticket one status forward at a time, or back to In Progress or
     To Do. In Review straight to DONE STAGING is refused. So is In Progress to Testing (Staging).
  3. The guard must know where the ticket is. It learns from the agent's own reads
     (getTransitionsForJiraIssue, getJiraIssue, searchJiraIssuesUsingJql), so a move without a
     fresh read of the ticket is refused with the reason, and the agent reads and retries.

Commands:
  status_guard.py hook                        read the hook event on stdin (PreToolUse / PostToolUse)
  status_guard.py permit KEY "Status" --said "<the person's words>"
                                              allow one agent move a person asked for (30 minutes)
  status_guard.py install --repo <path>       register the hook in <repo>/.claude/settings.json
  status_guard.py show                        print what the guard knows

People can always move tickets in the tracker itself. The guard only checks agent tool calls.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import config as cfg  # noqa: E402  (same folder: one source for stages and defaults)

STATE_PATH = Path(os.environ.get("DELIVERY_GUARD_STATE") or Path.home() / ".claude" / "delivery-status-guard.json")
FRESH_SECONDS = 15 * 60
PERMIT_SECONDS = 30 * 60
KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]+-\d+$")
TRANSITION_TOOL = re.compile(r"^mcp__.*atlassian.*__transitionJiraIssue$", re.I)
READ_TOOLS = re.compile(r"^mcp__.*atlassian.*__(getTransitionsForJiraIssue|getJiraIssue|searchJiraIssuesUsingJql)$", re.I)
BACK_STAGES = ("todo", "inProgress")
HOOK_COMMAND = (
    "f=\"$HOME/.claude/skills/delivery-config/status_guard.py\"; "
    "if [ ! -f \"$f\" ]; then echo 'Ticket status guard is missing: update the AI delivery workflow kit "
    "(git pull, then run the installer).' >&2; exit 2; fi; "
    "if python3 -c '' >/dev/null 2>&1; then exec python3 \"$f\" hook; else exec python \"$f\" hook; fi"
)
PRE_MATCHER = "mcp__.*[Aa]tlassian.*__transitionJiraIssue"
POST_MATCHER = "mcp__.*[Aa]tlassian.*__(getTransitionsForJiraIssue|getJiraIssue|searchJiraIssuesUsingJql|transitionJiraIssue)"


# ---------- state ----------

def load_state():
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("transitions", {})
            data.setdefault("current", {})
            data.setdefault("ids", {})
            data.setdefault("permits", [])
            return data
    except (OSError, ValueError):
        pass
    return {"transitions": {}, "current": {}, "ids": {}, "permits": []}


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_PATH)


# ---------- reading tool results ----------

def walk(value, depth=0):
    """Every dict inside a tool result, including JSON carried in text blocks."""
    if depth > 12:
        return
    if isinstance(value, str):
        text = value.strip()
        if text[:1] in "{[":
            try:
                yield from walk(json.loads(text), depth + 1)
            except ValueError:
                pass
        return
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child, depth + 1)


def issue_key(state, raw):
    raw = str(raw or "").strip()
    return raw if KEY_RE.match(raw) else state["ids"].get(raw, raw)


def target_name(state, key, tool_input):
    tid = str((tool_input.get("transition") or {}).get("id") or "")
    if not tid:
        return None
    project = key.split("-")[0] if key else ""
    return state["transitions"].get(key, {}).get(tid) or state["transitions"].get(f"project:{project}", {}).get(tid)


def learn(state, tool, tool_input, response):
    now = time.time()
    if tool.endswith("getTransitionsForJiraIssue"):
        key = issue_key(state, tool_input.get("issueIdOrKey"))
        found = {}
        for d in walk(response):
            to = d.get("to")
            if "id" in d and isinstance(to, dict) and to.get("name"):
                found[str(d["id"])] = to["name"]
        if found and key:
            state["transitions"][key] = found
            project = key.split("-")[0]
            state["transitions"].setdefault(f"project:{project}", {}).update(found)
        return
    if tool.endswith("transitionJiraIssue"):
        key = issue_key(state, tool_input.get("issueIdOrKey"))
        target = target_name(state, key, tool_input)
        text = json.dumps(response)[:2000].lower() if response is not None else ""
        if target and "error" not in text:
            state["current"][key] = {"status": target, "at": now}
        return
    for d in walk(response):
        key, fields = d.get("key"), d.get("fields")
        if isinstance(key, str) and KEY_RE.match(key) and isinstance(fields, dict):
            status = fields.get("status")
            if isinstance(status, dict) and status.get("name"):
                state["current"][key] = {"status": status["name"], "at": now}
            if d.get("id"):
                state["ids"][str(d["id"])] = key


# ---------- project rules ----------

def ticket_keys(root):
    try:
        data = json.loads((root / ".engineering" / "config.json").read_text(encoding="utf-8-sig"))
        return [str(k) for k in data.get("ticketKeys", [])]
    except (OSError, ValueError, AttributeError):
        return []


def find_project(cwd, project):
    """The repo whose delivery config owns this project key: cwd's repo first, then its subfolders."""
    candidates = []
    start = Path(os.environ.get("CLAUDE_PROJECT_DIR") or cwd or ".").resolve()
    for folder in [start, *start.parents]:
        if (folder / cfg.CONFIG_PATH).exists():
            candidates.append(folder)
            break
    try:
        for child in sorted(start.iterdir()):
            if child.is_dir() and (child / cfg.CONFIG_PATH).exists():
                candidates.append(child)
    except OSError:
        pass
    for root in candidates:
        if project in ticket_keys(root):
            return root
    return candidates[0] if len(candidates) == 1 else None


def project_guide(root):
    if root is None:
        return {}
    try:
        return cfg.status_guide(cfg.load_status_entries(root))
    except Exception:  # an unreadable config falls back to the default rules
        return {}


def stage_of(guide, status):
    name = str(status or "").strip().lower()
    return next((s for s, g in guide.items() if g["status"].strip().lower() == name), None)


def default_person_only(status):
    """No project mapping: treat any 'done' status as a person's call."""
    return "done" in str(status).lower()


# ---------- permits ----------

def take_permit(state, key, status):
    now = time.time()
    state["permits"] = [p for p in state["permits"] if p.get("expires", 0) > now]
    for p in state["permits"]:
        if p["key"] == key and p["status"].strip().lower() == str(status).strip().lower():
            state["permits"].remove(p)
            return p
    return None


# ---------- decisions ----------

def decide(state, tool_input, cwd):
    """None to allow, or the reason to refuse."""
    key = issue_key(state, tool_input.get("issueIdOrKey"))
    project = key.split("-")[0] if KEY_RE.match(key) else ""
    target = target_name(state, key, tool_input)
    if not target:
        return (f"The status guard does not know where transition "
                f"{(tool_input.get('transition') or {}).get('id')} goes for {key}. Call "
                f"getTransitionsForJiraIssue for {key} first, then retry the same move.")
    if take_permit(state, key, target):
        return None
    current = state["current"].get(key)
    fresh = bool(current) and time.time() - current.get("at", 0) < FRESH_SECONDS

    guide = project_guide(find_project(cwd, project))
    to_stage = stage_of(guide, target)
    if guide and to_stage is None:
        return (f"'{target}' is not in this project's status mapping (docs/workflow/delivery.config.json). "
                f"Leave {key} where it is and ask the owner.")
    person_only = guide[to_stage]["movedBy"] == "person" if to_stage else default_person_only(target)
    if person_only:
        when = guide[to_stage]["when"] if to_stage else "a person decides this move"
        return (f"Only a person moves a ticket to '{target}' ({when}). Leave {key} where it is and tell the "
                f"owner it is ready for them. If the owner explicitly asks you to make this move, run: "
                f"python \"$HOME/.claude/skills/delivery-config/status_guard.py\" permit {key} \"{target}\" "
                f"--said \"<their words>\", then retry.")
    if not fresh:
        return (f"Read {key} first (getJiraIssue) so the status guard knows its current status, then retry. "
                f"Tickets move one status at a time.")
    from_stage = stage_of(guide, current["status"])
    if not guide or to_stage in BACK_STAGES or from_stage is None or from_stage == to_stage:
        return None
    order = [s for s in cfg.STAGES if s in guide]
    step = order.index(to_stage) - order.index(from_stage)
    if step == 1:
        return None
    if step < 0:
        return (f"{key} would move back from '{current['status']}' to '{target}'. Agents only send a ticket "
                f"back to In Progress or To Do. Ask the owner.")
    nxt = guide[order[order.index(from_stage) + 1]]["status"]
    return (f"{key} is in '{current['status']}'. Moving it to '{target}' skips '{nxt}'. Move it one status "
            f"at a time: '{nxt}' first, and only if that move belongs to this step of the workflow "
            f"(see `statuses guide`). If it does not, leave the ticket and tell the owner.")


def run_hook():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    tool = str(event.get("tool_name", ""))
    tool_input = event.get("tool_input") or {}
    if STATE_PATH.with_suffix(".debug").exists():  # touch this file to log raw events while checking a connector
        with STATE_PATH.with_suffix(".log").open("a", encoding="utf-8") as log:
            log.write(json.dumps(event)[:20000] + chr(10))
    phase = event.get("hook_event_name", "")
    state = load_state()
    if phase == "PostToolUse" and (READ_TOOLS.match(tool) or TRANSITION_TOOL.match(tool)):
        learn(state, tool, tool_input, event.get("tool_response"))
        save_state(state)
        return 0
    if phase == "PreToolUse" and TRANSITION_TOOL.match(tool):
        reason = decide(state, tool_input, event.get("cwd"))
        save_state(state)
        if reason:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Ticket status guard: {reason}",
            }}))
    return 0


# ---------- commands ----------

def cmd_permit(key, status, said):
    if not KEY_RE.match(key):
        raise SystemExit(f"'{key}' is not a ticket key like ABC-123")
    if not said or len(said.strip()) < 3:
        raise SystemExit("--said needs the person's own words asking for this move")
    state = load_state()
    state["permits"].append({"key": key, "status": status, "said": said.strip()[:300],
                             "at": time.time(), "expires": time.time() + PERMIT_SECONDS})
    save_state(state)
    print(json.dumps({"permit": key, "status": status, "validMinutes": PERMIT_SECONDS // 60,
                      "note": "One move. Quote the person's words in the ticket comment."}))


def hook_entry(matcher):
    return {"matcher": matcher, "hooks": [{"type": "command", "command": HOOK_COMMAND, "timeout": 15}]}


def cmd_install(repo):
    path = Path(repo).resolve() / ".claude" / "settings.json"
    data = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    hooks = data.setdefault("hooks", {})
    changed = False
    for phase, matcher in (("PreToolUse", PRE_MATCHER), ("PostToolUse", POST_MATCHER)):
        entries = hooks.setdefault(phase, [])
        mine = [e for e in entries if any("status_guard.py" in h.get("command", "") for h in e.get("hooks", []))]
        want = hook_entry(matcher)
        if mine != [want]:
            entries[:] = [e for e in entries if e not in mine] + [want]
            changed = True
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"settings": str(path), "changed": changed,
                      "next": "Commit .claude/settings.json so every checkout and worktree uses the guard"}))


def cmd_show():
    state = load_state()
    now = time.time()
    print(json.dumps({
        "state": str(STATE_PATH),
        "current": {k: {"status": v["status"], "ageMinutes": round((now - v["at"]) / 60)}
                    for k, v in sorted(state["current"].items())},
        "permits": [p for p in state["permits"] if p.get("expires", 0) > now],
        "knownTransitions": sorted(k for k in state["transitions"] if not k.startswith("project:")),
    }, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ticket status guard (Claude Code hook)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("hook")
    permit = sub.add_parser("permit")
    permit.add_argument("key")
    permit.add_argument("status")
    permit.add_argument("--said", required=True)
    install = sub.add_parser("install")
    install.add_argument("--repo", default=".")
    sub.add_parser("show")
    args = parser.parse_args(argv)
    if args.cmd == "hook":
        return run_hook()
    if args.cmd == "permit":
        return cmd_permit(args.key, args.status, args.said)
    if args.cmd == "install":
        return cmd_install(args.repo)
    return cmd_show()


if __name__ == "__main__":
    sys.exit(main() or 0)
