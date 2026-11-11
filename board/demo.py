"""Sample project for `board.py serve --demo`: writes fresh state files with current timestamps.

The data shows every situation the board renders: an approved wave plan, tickets in build /
review, an owner question, a ready-to-merge PR, a critical bug, merged tickets and an activity
feed. It writes only into the directory it is given (a temp folder), never into a real project.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _t(minutes_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).astimezone().isoformat(timespec="seconds")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _json(path: Path, data) -> None:
    _write(path, json.dumps(data, indent=2) + "\n")


def build(root: Path) -> Path:
    d = root / ".delivery"
    gh = "https://github.com/acme/tasks"
    jira = "https://acme.atlassian.net/browse"

    _json(d / "wave-plan.json", {
        "schema": "wave-plan/1", "project": "ABC", "status": "applied",
        "generatedAt": _t(600), "approvedAt": _t(560), "approvedBy": "owner",
        "planDoc": "docs/waves/wave-plan.md", "cap": 3,
        "criticalPath": ["ABC-1", "ABC-3", "ABC-6", "ABC-9"],
        "startsFirst": ["ABC-1", "ABC-2"], "problems": [],
        "waves": [
            {"n": 1, "title": "Foundations: scaffold, auth, data model", "tickets": [
                {"key": "ABC-1", "title": "Scaffold app + CI", "type": "chore", "priority": "P0", "dependsOn": []},
                {"key": "ABC-2", "title": "Spike: choose sync engine", "type": "spike", "priority": "P1", "dependsOn": []},
                {"key": "ABC-3", "title": "Sign-in with email link", "type": "feature", "priority": "P0", "dependsOn": ["ABC-1"]},
            ]},
            {"n": 2, "title": "Core value: tasks and inbox", "tickets": [
                {"key": "ABC-4", "title": "Create and edit tasks", "type": "feature", "priority": "P0", "dependsOn": ["ABC-3"]},
                {"key": "ABC-5", "title": "Today and Inbox screens", "type": "feature", "priority": "P1", "dependsOn": ["ABC-4"]},
                {"key": "ABC-6", "title": "Offline sync", "type": "feature", "priority": "P0", "dependsOn": ["ABC-2", "ABC-3"]},
                {"key": "ABC-7", "title": "Crash when a task title is empty", "type": "bug", "priority": "Highest",
                 "dependsOn": ["ABC-4"], "critical": True},
            ]},
            {"n": 3, "title": "Retention: reminders and sharing", "tickets": [
                {"key": "ABC-8", "title": "Push reminders", "type": "feature", "priority": "P1", "dependsOn": ["ABC-5"]},
                {"key": "ABC-9", "title": "Share a list", "type": "feature", "priority": "P2", "dependsOn": ["ABC-6"]},
            ]},
        ],
    })

    _json(d / "orchestrator.json", {
        "schema": "deliver/1", "projectKey": "ABC", "flavor": "deliver", "mode": "loop",
        "tracker": {"kind": "jira", "projectUrl": "https://acme.atlassian.net/jira/software/projects/ABC"},
        "repo": {"nameWithOwner": "acme/tasks", "defaultBranch": "main"},
        "lock": {"holder": "loop-session", "acquiredAt": _t(240), "heartbeatAt": _t(3)},
        "policy": {"cap": 3, "mergePath": "owner", "maxRounds": 3, "deviceLaneEnabled": True},
        "setup": {"checkedAt": _t(240), "gaps": [
            {"item": "dev build registry", "severity": "degraded", "fix": "write docs/setup/dev-builds.md", "status": "open"}]},
        "waves": {"source": "labels:wave-N", "planDoc": "docs/waves/wave-plan.md",
                  "window": {"base": 2, "next": 3}, "planApprovedAt": _t(560)},
        "backlog": {"updatedAt": _t(3), "items": {
            "ABC-1": {"status": "done", "wave": 1}, "ABC-2": {"status": "done", "wave": 1},
            "ABC-3": {"status": "done", "wave": 1},
            "ABC-4": {"status": "in_progress", "wave": 2}, "ABC-5": {"status": "in_progress", "wave": 2},
            "ABC-6": {"status": "in_progress", "wave": 2}, "ABC-7": {"status": "in_progress", "wave": 2},
            "ABC-8": {"status": "blocked", "wave": 3, "blockedBy": ["ABC-5"]},
            "ABC-9": {"status": "blocked", "wave": 3, "blockedBy": ["ABC-6"]},
        }},
        "tickets": {
            "ABC-4": {"title": "Create and edit tasks", "url": f"{jira}/ABC-4", "wave": 2, "type": "Feature", "risk": "medium",
                      "stage": "reviewing", "round": 2, "holdsSlot": True, "waitingOn": None,
                      "branch": "feat/abc-004/tasks-crud", "pr": {"number": 41, "url": f"{gh}/pull/41"},
                      "routing": ["gate", "tester-functional", "tester-device", "reviewer-code", "reviewer-ui", "reviewer-ux"],
                      "dispatchedAt": _t(180), "stageSince": _t(9), "lastReportAt": _t(9)},
            "ABC-6": {"title": "Offline sync", "url": f"{jira}/ABC-6", "wave": 2, "type": "Feature", "risk": "high",
                      "stage": "awaiting_owner", "round": 0, "holdsSlot": False, "waitingOn": "owner",
                      "waitingSince": _t(25), "branch": "feat/abc-006/offline-sync",
                      "dispatchedAt": _t(70), "stageSince": _t(25), "lastReportAt": _t(25)},
            "ABC-7": {"title": "Crash when a task title is empty", "url": f"{jira}/ABC-7", "wave": 2, "type": "Bug",
                      "risk": "low", "critical": True, "stage": "dispatched", "round": 0, "holdsSlot": True,
                      "waitingOn": "worker", "branch": "fix/abc-007/empty-title",
                      "dispatchedAt": _t(14), "stageSince": _t(14), "lastReportAt": _t(2)},
            "ABC-5": {"title": "Today and Inbox screens", "url": f"{jira}/ABC-5", "wave": 2, "type": "Feature",
                      "risk": "medium", "stage": "awaiting_owner_merge", "round": 1, "holdsSlot": False,
                      "waitingOn": "owner", "waitingSince": _t(40), "branch": "feat/abc-005/today-inbox",
                      "pr": {"number": 39, "url": f"{gh}/pull/39"},
                      "dispatchedAt": _t(300), "stageSince": _t(40), "lastReportAt": _t(40)},
        },
        "gate": {"holder": None, "queue": []},
        "deviceLane": {"holder": "ABC-4", "grantedAt": _t(30), "queue": []},
        "mergeLock": {"holder": None, "awaitingOwnerMerge": ["ABC-5"]},
        "ownerQuestions": [
            {"id": "Q1", "key": "ABC-6", "kind": "decision", "askedAt": _t(25), "answeredAt": None, "answer": None,
             "question": "Conflict rule for offline edits: last write wins, or keep both and ask the user?",
             "options": ["A: Last write wins (simple, may lose an edit)", "B: Keep both and show a merge prompt"],
             "recommendation": "A: matches the spike's finding that conflicts are rare; revisit in wave 3"},
        ],
        "history": [
            {"key": "ABC-1", "title": "Scaffold app + CI", "pr": f"{gh}/pull/31", "mergedAt": _t(500), "rounds": 1, "cost": "$1.80"},
            {"key": "ABC-2", "title": "Spike: choose sync engine", "pr": f"{gh}/pull/33", "mergedAt": _t(420), "rounds": 1, "cost": "$0.90"},
            {"key": "ABC-3", "title": "Sign-in with email link", "pr": f"{gh}/pull/35", "mergedAt": _t(260), "rounds": 2, "cost": "$4.10"},
        ],
        "cycle": {"count": 14, "lastCycleAt": _t(3), "nextWakeAt": _t(-7), "lastDelaySec": 600},
    })

    j4 = d / "jobs" / "ABC-4"
    _json(j4 / "job.json", {
        "schema": "deliver-job/1", "ticket": "ABC-4", "title": "Create and edit tasks", "type": "feature", "risk": "medium",
        "stage": "reviewing", "round": 2, "branch": "feat/abc-004/tasks-crud", "base_branch": "main",
        "pr": {"number": 41, "url": f"{gh}/pull/41"}, "record": "docs/tickets/ABC-4.md",
        "roles": ["tester-functional", "tester-device", "reviewer-code", "reviewer-ui", "reviewer-ux"],
        "acceptance": [
            {"id": "AC1", "text": "A user can create a task with a title", "status": "met", "evidence": "tasks.create.test.ts"},
            {"id": "AC2", "text": "Editing a task saves within 1 second", "status": "met", "evidence": "AC2 screenshots"},
            {"id": "AC3", "text": "Deleting asks for confirmation", "status": "pending", "evidence": ""},
        ],
        "verdicts": {"round-1": {"checks": "PASS", "tester-functional": "PASS", "tester-device": "PASS",
                                 "reviewer-code": "CHANGES", "reviewer-ui": "PASS", "reviewer-ux": "CHANGES"}},
        "progress": {"step": 4, "phase": "Round 2 review", "current": "reviewer-ux reading screenshots"},
        "cost": "$3.40", "updated_at": _t(9),
    })
    _write(j4 / "plan.md", "# ABC-4 plan\n\n- [x] Task model\n- [x] Create form\n- [x] Edit form\n- [x] Delete with confirm\n")
    _write(j4 / "round-1" / "checks.md", "VERDICT: PASS\nCOMMIT: 1a2b3c4\n\n## Summary\n- lint, typecheck, 84 tests passed in 41s\n")
    _write(j4 / "round-1" / "review-code.md",
           "VERDICT: CHANGES\n\n## Summary\n- `saveTask` swallows the API error (src/tasks/api.ts:42)\n- Missing test for an empty title\n")
    _write(j4 / "round-1" / "review-ux.md", "VERDICT: CHANGES\n\n## Summary\n- Delete has no confirmation (AC3)\n")
    _write(j4 / "round-2" / "checks.md", "VERDICT: PASS\nCOMMIT: 5d6e7f8\n\n## Summary\n- lint, typecheck, 91 tests passed in 44s\n")
    _write(j4 / "round-2" / "test-functional.md",
           "VERDICT: PASS\n\n| AC | Test | Result |\n|---|---|---|\n| AC1 | create.test | pass |\n| AC3 | delete-confirm.test | pass |\n")
    _write(j4 / "round-2" / "test-device.md", "VERDICT: PASS\n\n## Summary\n- 3 criteria walked on the iOS simulator, 11 screenshots\n")
    _write(j4 / "round-2" / "review-code.md", "VERDICT: PASS\n\n## Summary\n- Error now surfaces as a toast; test added\n")

    j6 = d / "jobs" / "ABC-6"
    _json(j6 / "job.json", {
        "schema": "deliver-job/1", "ticket": "ABC-6", "title": "Offline sync", "type": "feature", "risk": "high",
        "stage": "awaiting_owner", "round": 0, "branch": "feat/abc-006/offline-sync", "record": "docs/tickets/ABC-6.md",
        "progress": {"step": 0, "phase": "Phase 3 · questions", "current": "waiting on Q1 (conflict rule)"},
        "updated_at": _t(25),
    })
    _write(j6 / "plan.md", "# ABC-6 plan (draft)\n\nBlocked on the conflict rule (Q1).\n")

    j7 = d / "jobs" / "ABC-7"
    _json(j7 / "job.json", {
        "schema": "deliver-job/1", "ticket": "ABC-7", "title": "Crash when a task title is empty", "type": "bug", "risk": "low",
        "stage": "building", "round": 0, "branch": "fix/abc-007/empty-title", "record": "docs/tickets/ABC-7.md",
        "progress": {"step": 1, "phase": "Phase 6 · build", "tasksDone": 2, "tasksTotal": 3,
                     "current": "Task 3: guard the save handler"},
        "updated_at": _t(2),
    })
    _write(j7 / "plan.md",
           "# ABC-7 plan\n\n- [x] Reproduce with a failing test\n- [x] Validate title in the form\n- [ ] Guard the save handler\n")

    j5 = d / "jobs" / "ABC-5"
    _json(j5 / "job.json", {
        "schema": "deliver-job/1", "ticket": "ABC-5", "title": "Today and Inbox screens", "type": "feature", "risk": "medium",
        "stage": "ready_to_merge", "round": 1, "branch": "feat/abc-005/today-inbox",
        "pr": {"number": 39, "url": f"{gh}/pull/39"}, "decision": "APPROVE",
        "verdicts": {"round-1": {"checks": "PASS", "tester-functional": "PASS", "tester-device": "PASS",
                                 "reviewer-code": "PASS", "reviewer-ui": "PASS", "reviewer-ux": "PASS"}},
        "cost": "$5.20", "updated_at": _t(40),
    })
    _write(j5 / "decision.md", "APPROVE\n\n## Summary\n- Every routed role passed in round 1\n- Walkthrough posted to the PR\n")

    events = [
        (500, "merge", "ABC-1", "merged → PR #31 (cleanup verified)"),
        (260, "merge", "ABC-3", "merged → PR #35 (2 rounds)"),
        (180, "dispatch", "ABC-4", "worker started in worktree abc-004-tasks-crud"),
        (70, "dispatch", "ABC-6", "worker started in worktree abc-006-offline-sync"),
        (55, "verdict", "ABC-4", "round 1: reviewer-code CHANGES, reviewer-ux CHANGES → FIX r1"),
        (40, "stage", "ABC-5", "APPROVE → ready-to-merge; waiting for your merge of PR #39"),
        (30, "gate", "ABC-4", "gate r2 PASS → TEST r2 (device lane granted)"),
        (25, "question", "ABC-6", "Q1 relayed: conflict rule for offline edits"),
        (14, "dispatch", "ABC-7", "critical bug jumps the queue; worker started"),
        (9, "stage", "ABC-4", "testers r2 PASS → REVIEW r2"),
        (3, "cycle", None, "cycle 14 · in flight 2/3 · next wake 600s"),
    ]
    _write(d / "events.jsonl", "".join(
        json.dumps({"ts": _t(m), "kind": k, "ticket": t, "text": x, "actor": "orchestrator"}) + "\n"
        for m, k, t, x in events))
    return root
