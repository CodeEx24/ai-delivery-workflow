# State files and messages

**This file is the single source of truth** for the delivery loop's state: the `job.json` and
`orchestrator.json` schemas, the stage names, the job folder layout and the messages. The
workflow file, `implement-ticket`, `verify-ticket`, `merge-ticket` and the loop's agents all
point here; none defines its own variant. Everything the loop needs to resume lives in two
kinds of gitignored files. **One writer per file:** the orchestrator writes
`orchestrator.json`; the ticket's worker (the session running `implement-ticket`) writes
`job.json`. Subagents never write `job.json`: they report in their own file and the worker
copies what matters into it. The orchestrator writes only *other* files inside a job folder
(the gate's `round-N/checks.md`).

```
<main checkout>/.delivery/
├─ orchestrator.json            orchestrator state (this file's main schema)
├─ orchestrator.log.md          optional: one line per cycle (time, actions, next wake)
├─ events.jsonl                 activity feed for the live board (orchestrator appends; board.md)
├─ wave-plan.json               machine-readable wave plan (plan-waves writes; board.md)
├─ board.json                   where the live board runs: pid, port, url (board writes)
├─ inbox/*.json                 answers / feedback typed on the board (board writes, orchestrator consumes → inbox/done/)
└─ briefs/<KEY>-<n>.md          the brief each worker was started with (kept until cleanup)

<ticket worktree>/.delivery/jobs/<KEY>-<n>/    deleted at cleanup (merge-ticket step 7)
├─ plan.md                      task plan (implement-ticket phase 5)
├─ job.json                     stage file (worker writes)
├─ round-N/checks.md            gate result (orchestrator writes; first line VERDICT: PASS|FAIL)
├─ round-N/test-functional.md   tester-functional   first line VERDICT: PASS|CHANGES
├─ round-N/test-device.md       tester-device       first line VERDICT: PASS|CHANGES|BLOCKED
├─ round-N/review-code.md  review-security.md  review-ui.md  review-ux.md
│                               reviewers, one per routed role, first line VERDICT: PASS|CHANGES
├─ round-N/screenshots/         <KEY>-<n>-AC1-step-01.png … (tester-device; never committed)
├─ decision.md                  approver; first line APPROVE | ESCALATE
├─ walkthrough.md               explainer; posted into the PR description
├─ changes.json                 explainer; per-file and per-function explanations (change-report.md)
└─ report.html                  the owner's change report (board.py report; never committed)

<main checkout>/.delivery/reports/<KEY>/       archived change report + its screenshots; kept after cleanup
```

`<KEY>-<n>` is the full ticket key (`ABC-27`); where this skill writes `<KEY>` for a ticket it
means the same full key. With GitHub Issues the key is `GH-<n>` (issue `#12` → `GH-12`) in
folders, branches (`feat/gh-012/<slug>`), worktree names and state files; `#12` in human text, and
PR bodies say `Closes #12`. Standalone runs (no `/deliver`) use the same folder in whatever
checkout the builder works in. Write JSON atomically: write `<file>.tmp`, then rename over
the original. Timestamps are ISO 8601 with offset.

## `orchestrator.json` (schema 1)

```json
{
  "schema": "deliver/1",
  "projectKey": "ABC",
  "flavor": "deliver | factory",
  "mode": "loop | plain | watcher",
  "tracker": {
    "kind": "jira | linear | github | local",
    "backlogFile": "docs/tickets/backlog.md (only when kind = local)",
    "site": "acme.atlassian.net",
    "cloudId": "…",
    "projectUrl": "https://acme.atlassian.net/jira/software/projects/ABC",
    "statuses": { "todo": "To Do", "inProgress": "In Progress", "review": "In Review", "done": "Done" },
    "needsHumanLabel": "needs-human",
    "readyToMergeLabel": "ready-to-merge",
    "readyRule": "label:ready | none",
    "criticalBugRule": "type = Bug and (label severity:critical or priority in (Highest, Blocker))",
    "typeMap": { "Story": "Feature", "Bug": "Bug", "Task": "Chore", "Spike": "Spike" }
  },
  "repo": {
    "nameWithOwner": "owner/repo",
    "defaultBranch": "main",
    "mainCheckout": "/path/to/main-checkout",
    "orcaRepoId": "…",
    "checksScript": "scripts/workflow/checks.sh",
    "costScript": "scripts/workflow/cost | null",
    "isNative": true
  },
  "orca": { "runId": "run_…", "watcherHandle": null, "engine": "orca | subagents" },
  "lock": {
    "holder": "plain-session | loop-session | watcher:<handle>",
    "acquiredAt": "…",
    "heartbeatAt": "…"
  },
  "policy": {
    "cap": 2,
    "capSource": "machine | docs/workflow/delivery.config.json | docs/workflow/README.md | default (2) | --cap",
    "mergePath": "owner (default) | agent (only if the merge command is allowed for agents)",
    "autoAcceptRecommended": false,
    "loopMinutes": "auto | 1-60",
    "idleReleaseMin": 60,
    "mergeStrategy": "squash | merge | rebase",
    "workerMayPush": true,
    "maxRounds": 3,
    "workerAgent": "claude",
    "workerModel": null,
    "gateConcurrency": 1,
    "deviceLaneEnabled": true,
    "diskWarnGb": 15,
    "scope": { "mode": "mine | specific | all | null", "keys": ["ABC-42"], "confirmedAt": "…", "source": "prompt | flag | file" },
    "mine": { "enabled": false, "keys": ["ABC-42"], "refreshedAt": "…", "idleSince": null },
    "approvedAt": "…"
  },
  "setup": {
    "checkedAt": "…",
    "gaps": [
      { "item": "dev build registry", "severity": "blocking | degraded | info",
        "fix": "write docs/setup/dev-builds.md (guide: docs/actions/dev-build-registry.md)",
        "status": "open | accepted | fixed" }
    ]
  },
  "import": {
    "source": "docs/spec.md | https://… | null (key mode)",
    "file": ".delivery/import-2026-11-08.md",
    "approvedAt": "… | null"
  },
  "waves": {
    "source": "labels:wave-N | backlog:Wave",
    "planDoc": "docs/waves/wave-plan.md",
    "window": { "base": 2, "next": 3 },
    "planApprovedAt": "… | null"
  },
  "backlog": {
    "updatedAt": "…",
    "items": {
      "ABC-35": { "status": "done | in_progress | ready | blocked | todo | needs_owner", "wave": 3,
                  "title": "…", "type": "Feature", "url": "https://…", "blockedBy": ["ABC-30"] }
    }
  },
  "tickets": {
    "ABC-27": {
      "title": "Today and Inbox screens",
      "url": "https://…/browse/ABC-27",
      "wave": 2, "type": "Feature", "risk": "medium", "critical": false,
      "stage": "reviewing",
      "round": 1,
      "holdsSlot": true,
      "waitingOn": null,
      "waitingSince": null,
      "branch": "feat/abc-027/today-inbox",
      "worktreeId": "<repoId>::<path>",
      "worktreePath": "/path/to/worktrees/abc-027-today-inbox",
      "taskId": "task_…",
      "dispatchId": "dsp_…",
      "agentId": "… (subagent engine only)",
      "pr": { "number": 31, "url": "https://github.com/owner/repo/pull/31" },
      "ownedPaths": ["src/features/tasks/**", "src/app/(tabs)/today.tsx"],
      "hotspots": ["package.json"],
      "routing": ["gate", "tester-functional", "tester-device", "reviewer-code", "reviewer-ui", "reviewer-ux"],
      "pendingRoles": ["reviewer-ux"],
      "dispatchedAt": "…", "stageSince": "…", "lastReportAt": "…",
      "notes": "device test r1 waited behind ABC-30"
    }
  },
  "pause": { "active": false, "scope": "all | tickets", "tickets": [], "mode": "soft | now",
             "since": "…", "by": "owner (chat) | owner (board.py)", "reason": null },
  "gate": { "holder": "ABC-27 | null", "round": 1, "startedAt": "…", "bgTaskId": "…", "queue": ["ABC-31"] },
  "deviceLane": { "holder": "ABC-30 | null", "grantedAt": "…", "queue": ["ABC-27"] },
  "mergeLock": { "holder": "ABC-25 | null", "startedAt": "…", "awaitingOwnerMerge": ["ABC-24"] },
  "ownerQuestions": [
    { "id": "Q3", "key": "ABC-30", "messageId": "msg_…", "kind": "decision | spec-approval | escalation | action | setup",
      "question": "…", "options": ["A …", "B …"], "recommendation": "A — because …",
      "askedAt": "…", "answeredAt": null, "answer": null }
  ],
  "history": [
    { "key": "ABC-25", "pr": "https://github.com/owner/repo/pull/29", "mergedAt": "…", "mergeSha": "abc1234",
      "rounds": 2, "cost": "$4.12 | null", "cleanedAt": "…", "leftovers": [] }
  ],
  "cycle": { "count": 12, "lastCycleAt": "…", "nextWakeAt": "…", "lastDelaySec": 600, "lastSummary": "…" }
}
```

Rules:

- `holdsSlot` is true for stages `dispatched`, `gating`, `gate_failed`, `testing`,
  `device_wait`, `reviewing`, `approving` and `merging`; false for `queued`,
  `awaiting_owner`, `escalated`, `blocked`, `awaiting_owner_merge`, `paused`, `merged`, `cleaned`.
- `paused` (owner paused it, `pause.md`): the ticket also carries `pausedFrom` (the stage to
  return to) and `pausedAt`. `pause` is `null` or `active: false` when nothing is paused.
  In-flight count = tickets with `holdsSlot: true`. It must never exceed `policy.cap`.
- `waitingOn`: `null | "owner" | "gate" | "device-lane" | "merge-lock" | "worker"`;
  `waitingSince` is set when `waitingOn` becomes `"owner"`. After `policy.idleReleaseMin`
  (default 60) waiting on the owner, the worker is released (`worker-release`); `send` or a
  resume brief brings it back (cycle.md 3a).
- Labels: `needs-human` only for real escalations (ESCALATE, round limit, owner action);
  `ready-to-merge` while an approved PR waits for the owner's merge (`awaiting_owner_merge`).
- A ticket leaves `tickets` only after cleanup is verified; it then gets a `history` row.
- `ownerQuestions` ids are short and stable for the run (`Q1`, `Q2` …) so the owner can
  answer "Q3: B" in chat or on the live board. `kind` may also be `needs-info` (a question
  /factory posted on a GitHub issue).
- `backlog` is rewritten every cycle from the wave-status block (or /factory's queue): every open
  ticket of the window and later waves. It feeds the live board's Waves strip (`board.md`).

### Lock

One orchestrator per project. On start and every cycle, compare `lock`:

- No lock, or `heartbeatAt` older than `2 × cycle.lastDelaySec + 10 min` → take it.
- Held by someone else and fresh → **do not cycle**. Report who holds it and since when;
  offer `--status`, or `--takeover` if the owner knows that session is gone.
- `--takeover` → take it, note the previous holder in `cycle.lastSummary`, `run-use` the Run.

## `job.json` (schema `deliver-job/1`, worker-owned)

The one stage file for every ticket, with or without `/deliver`. `implement-ticket` writes it at
hand-off; the worker keeps it current at every stage change; the agents, `verify-ticket` and
`merge-ticket` read it. Fields the orchestrator decides (routed roles, device lane) arrive in
its stage instruction and the worker copies them in. Without an orchestrator, whoever runs the
loop by hand sets them the same way.

```json
{
  "schema": "deliver-job/1",
  "ticket": "ABC-27",
  "title": "Today and Inbox screens",
  "type": "feature | bug | chore | spike",
  "risk": "low | medium | high",
  "stage": "built",
  "round": 1,
  "branch": "feat/abc-027/today-inbox",
  "base_branch": "main",
  "worktree": "/path/to/worktrees/abc-027-today-inbox",
  "dispatch": "dsp_… | null",
  "pr": { "number": 31, "url": "https://github.com/owner/repo/pull/31" },
  "record": "docs/tickets/ABC-27.md",
  "routing": { "ui_changed": true, "app_testable": true, "security_surface": false,
               "backend_schema": false, "needs_login": true },
  "roles": ["tester-functional", "tester-device", "reviewer-code", "reviewer-ui", "reviewer-ux"],
  "device_lane": { "granted": true, "round": 1, "granted_at": "…" },
  "acceptance": [ { "id": "AC1", "text": "verbatim criterion",
                    "status": "met | partial | not_met | blocked | pending",
                    "evidence": "test name / file:line / screenshot" } ],
  "verdicts": { "round-1": { "checks": "PASS", "tester-functional": "PASS",
                             "tester-device": "BLOCKED", "reviewer-code": "CHANGES" } },
  "blocked": [ { "ac": "AC3", "reason": "needs a physical device" } ],
  "decision": "APPROVE | ESCALATE | null",
  "escalation": "one specific question for the owner | null",
  "owner_actions": ["docs/actions/set-backend-secret.md"],
  "services": [ { "kind": "dev-server | simulator | local-backend", "port": 8082, "pid": 4242,
                  "name": "…", "started_by": "tester-device", "status": "running | stopped" } ],
  "cost": "$3.10 | null",
  "last_error": null,
  "progress": { "step": 1, "phase": "Phase 6 · build", "tasksDone": 2, "tasksTotal": 5,
                "current": "Task 3: guard the save handler", "updated_at": "…" },
  "questions": [ { "id": "ABC-27-q1", "kind": "decision", "q": "ABC-27: …?",
                   "options": ["A - …", "B - …"], "recommendation": "A - because …",
                   "askedAt": "…", "messageId": null, "answer": null, "answeredAt": null } ],
  "updated_at": "…"
}
```

`job.json` exists from the worker's **first minute** (implement-ticket writes it at intake with
`stage: "intake"`), not only at hand-off, so the live board shows a ticket as soon as it starts.
`progress` is for the board (step index: 0 intake · 1 build · 2 gate · 3 test · 4 review ·
5 approve · 6 merge · 7 done). `questions` holds every owner question the worker asked, one decision per entry
(`id` `<KEY>-q<n>`, `kind`, `q`, `options`, `recommendation`, `askedAt`, `messageId`, `answer`,
`answeredAt`, optional `notes`); full rules in implement-ticket's `references/owner-questions.md`.
Orca workers write it before their `ask`; subagent workers instead of an `ask`. The board shows
open entries even before the orchestrator relays them.

| Field | Who decides it | Read by |
|---|---|---|
| `ticket`, `title`, `type`, `risk`, `branch`, `base_branch`, `worktree`, `record` | Builder at intake (risk confirmed there) | Everyone |
| `pr` (number + URL) | Builder when the draft PR opens | Agents (`gh pr view <number>`), merge-ticket |
| `routing` flags | Builder, honestly: they decide who judges the work | Orchestrator (routing) |
| `roles` | Orchestrator (or the manual runner) from the routing table, per round; worker copies them in | Agents, approver (which files must exist) |
| `device_lane` | Orchestrator grants it in `TEST` / `DEVICE`; worker copies it in | tester-device / verify-ticket (never start without it) |
| `verdicts`, `acceptance`, `blocked` | Worker, from the round files' first lines and tables | Orchestrator, approver, merge-ticket |
| `services` | Worker, from tester-device's report (what it started and stopped) | Orchestrator (lane release), merge-ticket cleanup |
| `decision`, `escalation`, `owner_actions`, `cost` | Worker, from `decision.md`, owner guides and the cost script | Orchestrator, merge-ticket |
| `progress` | Worker, at each phase and plan task | The live board |
| `questions` | Worker, one entry per decision, before asking | Orchestrator → `ownerQuestions` (one each, `jobQuestion` link), the live board |

### Stage vocabulary

Worker-written (`job.json.stage`):

| Stage | Meaning |
|---|---|
| `intake` | Reading the ticket, exploring (implement-ticket phases 1–2) |
| `awaiting_owner` | An `ask` is pending (design question or record acceptance) |
| `building` | Implementing (phase 6 onward) |
| `built` | Draft PR open, local checks passed, waiting for the gate (round N) |
| `testing` | Running the testers of round N it was told to run |
| `tested` | Those testers have written their files (and committed their tests) |
| `reviewing` | Running the reviewers of round N on the round's final commit |
| `reviewed` | Every reviewer of round N has written its file |
| `fixing` | Addressing CHANGES or a failed gate |
| `approving` | Approver (and explainer on APPROVE) running |
| `ready_to_merge` | `decision.md` = APPROVE, walkthrough posted, branch pushed |
| `escalated` | ESCALATE, round limit, or blocked on the owner; `escalation` filled |
| `blocked` | Cannot proceed for a non-owner reason (blocker reopened, environment broken); `last_error` |
| `failed` | Gave up; `last_error` |

Orchestrator stages (in `orchestrator.json.tickets[*].stage`): `queued`, `dispatched`,
`gating`, `gate_failed`, `testing`, `device_wait`, `reviewing`, `approving`, `merging`,
`awaiting_owner`, `escalated`, `blocked`, `awaiting_owner_merge`, `merged`, `cleaned`. When both
files speak, the orchestrator stage is the more specific view of the same moment (e.g. job
`built` + orchestrator `gating`).

### Round order and verdict words

Every round runs in this order (workflow section 3, "Round order"):

1. **Gate** (orchestrator, script) → `round-N/checks.md`, `VERDICT: PASS|FAIL`. FAIL → `FIX`;
   nothing else runs.
2. **Testers** (`TEST r<N>`, plus `DEVICE r<N>` if the lane was busy): tester-functional and
   tester-device in parallel. Both may commit tests / E2E flows (`git pull --rebase`, then
   `git push`). tester-device writes `PASS`, `CHANGES` or `BLOCKED` (line 2 `Blocked: <reason>`).
3. **Reviewers** (`REVIEW r<N>`): code, security, ui, ux in parallel on the round's final
   commit (after the testers' commits); ui / ux read `round-N/screenshots/` and
   `test-device.md`. They run whatever the testers said, so one fix round covers everything.
4. Any `CHANGES` (tester or reviewer) → `FIX`. Otherwise the **approver** (`APPROVE`), then the
   **explainer** on APPROVE.

`BLOCKED` is not a code failure: it never triggers `FIX` and never resumes the builder by
itself. The approver ESCALATEs with one owner question (provide what is missing, or defer the
criterion), unless the ticket record already holds an owner deferral for every blocked AC.

## Messages between orchestrator and workers

All through Orca orchestration; subjects start with `[<KEY>-<n>]` so a batch is easy to sort.

**Worker → orchestrator**

| How | Subject | When |
|---|---|---|
| `ask --question` | `[ABC-27] OWNER: <question>` (with `--options`) | A design fork the brief and record don't settle |
| `ask --question` | `[ABC-27] SPEC-APPROVAL: <record path> — <one-line summary>` | Medium/high risk record ready for acceptance |
| `ask --question` | `[ABC-27] SCOPE: needs <path> outside owned paths — <why>` | Before touching anything not owned |
| `send --type status` | `[ABC-27] stage <stage> r<N>` | Optional, at stage changes (cheap progress signal) |
| `worker_done --outcome succeeded --phase <stage>` | report body | End of every instruction: `built`, `tested`, `reviewed`, `ready_to_merge`, `escalated` |
| `worker_done --outcome failed --phase <stage>` | report body with the error | `blocked` / `failed` |

**Orchestrator → worker** (`send --to dispatch:<id> --type dispatch`, or `reply --id` to an ask)

| Subject | Body says |
|---|---|
| `[ABC-27] TEST r<N>` | Gate PASS; testers to run (tester-functional; tester-device only if the lane is granted now) |
| `[ABC-27] DEVICE r<N>` | Lane granted later in the round: run tester-device only; release services after |
| `[ABC-27] REVIEW r<N>` | Every routed tester has written; reviewers to run on the final commit (with model hints) |
| `[ABC-27] FIX r<N>` | Gate, testers or reviewers asked for changes; files to read; then back to `built` r<N+1> |
| `[ABC-27] APPROVE` | Every routed role wrote PASS (tester-device may be BLOCKED); run approver, then explainer on APPROVE |
| `[ABC-27] RESUME` | Owner answered the escalation: the answer, and what to do next |
| `[ABC-27] RESYNC` | Re-sync with the default branch (conflict merge-ticket could not resolve) |
| `[ABC-27] STOP` | Owner asked to stop (or `--pause --now`): commit WIP to the branch, push, report, end |
| `[ABC-27] PAUSE` | Soft pause: finish the current step, commit, push, update job.json, report, then wait |
| `[ABC-27] CONTINUE` | Resume after a pause: the recorded stage and the next instruction (re-sync first if behind) |

The exact bodies are in `worker-brief.md`.
