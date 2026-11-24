# Worker brief and stage instructions

The orchestrator writes one brief per ticket to `.delivery/briefs/<KEY>-<n>.md` in the main
checkout, fills every `{{…}}` (`{{KEY}}` is the full ticket key, e.g. `ABC-27`), and starts
the worker with it:

```
ORCA orchestration worker-start --run {{RUN_ID}} --spec-file .delivery/briefs/{{KEY}}.md \
  --task-title "{{KEY}} {{TITLE_SHORT}}" --worktree new-top-level --name {{WORKTREE_NAME}} \
  --agent {{WORKER_AGENT}} --display-name "{{KEY}} · {{TITLE_SHORT}}" \
  --comment "dispatched by /deliver" --setup run --json
```

- **Context window** (`context-limits.md`): if the loaded Orca guide shows a way to pass env
  or agent launch flags, start the worker with `CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000` (or
  `--autocompact 400k`). If not, start it as above and keep "worker window not set" as an info
  gap; the brief's "Context" section still applies.
- **Local backlog** (`tracker.kind: "local"`): `{{TICKET_URL}}` is
  `docs/tickets/backlog.md#<id>`; the brief's tracker steps read that file and write nothing to
  it (see the note in the brief).
- `{{WORKTREE_NAME}}`: short and filesystem-safe, e.g. `abc-027-today-inbox`. Always pass
  `--base-branch origin/<repo.baseBranch>`, and put that branch in the brief, so the worker never falls back to the repo default. Add `--model` only if
  `policy.workerModel` is set.
- From the receipt store `taskId`, `dispatchId`, the worktree id and path in
  `orchestrator.json`. If it fails, do not rerun: read `failedStage` and the recovery reference.
- Fill **Owns / Must not edit / Shared files** from the wave plan's worktree assignments. If
  the plan gives none, derive them from the ticket's area (`src/features/<area>/**`, its route
  files, its tests, `docs/tickets/<KEY>*`, `docs/features/<area>.md`) and list the project's
  shared files explicitly.

Everything between the lines below is the brief, sent verbatim after filling.

---

```markdown
# Ticket worker brief — {{KEY}}: {{TITLE}}

You are an Orca worker started by the `/deliver {{PROJECT_KEY}}` orchestrator. This brief is
your contract; read nothing else to start except what it points to. The process is
`~/.claude/workflows/ai-delivery-workflow.md` (stage 4 for building, section 3 for the review
loop). The project's rules are in `CLAUDE.md` and `{{WORKFLOW_DOC}}`; they win over defaults.

## Ticket
- Ticket: {{KEY}} — {{TICKET_URL}}
- Type: {{TYPE}} · Provisional risk: {{RISK}} (confirm at intake; tell me if it changes) · Wave {{WAVE}} · Priority {{PRIORITY}}
- Blockers: {{BLOCKERS_DONE}} (all Done at dispatch, re-checked by the orchestrator)
- Branch: `{{BRANCH}}` from `origin/{{DEFAULT_BRANCH}}`. If Orca named this worktree's branch
  differently, rename it first: `git branch -m {{BRANCH}}`.
- Existing design artifacts: {{ARTIFACTS_OR_NONE}} ({{ACCEPTED_OR_NOT}})

## Context
Your session may compact during a long ticket. Your state is in files, not this chat:
`.delivery/jobs/{{KEY}}/job.json` (stage, round, verdicts, blocked), `plan.md` and the
`round-N/` reports. After any compaction, re-read `job.json` and the latest round's files
before acting. When summarising, keep: ticket key, stage, round, open CHANGES items, any
pending owner question.

## Tracker
{{TRACKER_NOTE}} <!-- PM tool: "Jira ABC via the Atlassian MCP" etc. Local backlog: "This
project uses the local backlog docs/tickets/backlog.md. Read your ticket there; do not edit
that file (In Progress / In Review are derived from your branch and PR; merge-ticket sets
the after-merge status). Comments go on the PR. With a PM tool, move the ticket by event:
`statuses target --event <start|prOpened>` (`~/.claude/skills/delivery-config/references/statuses.md`)." -->

## Owned paths
- **Owns (may edit):** {{OWNED_PATHS}}
- **Must not edit:** {{FORBIDDEN_PATHS}}
- **Shared files** ({{SHARED_FILES}}): {{COORDINATION_RULE}}. Lockfile conflicts: rebase and
  reinstall, never hand-merge. Migrations: {{MIGRATION_RULE}}.
- Needing anything outside these is a `SCOPE` question, not an edit.

## Your job, part 1 — build (now)
Run `/implement-ticket {{KEY}}` here as a parallel worker (its "Running as an Orca worker"
section applies) with these settings:

1. **Questions for the owner** go through
   `orca orchestration ask --question "[{{KEY}}] OWNER: <question>" --options "<A (recommended)>,<B>,…"`,
   then end your turn; Orca wakes you with the answer. Never use AskUserQuestion — the owner
   is not watching this chat. Ask only what the record, this brief and the repo docs don't settle.
   Follow `~/.claude/skills/implement-ticket/references/owner-questions.md`:
   **one decision per question**, each written to `job.json.questions` (`{{KEY}}-q<n>`) before
   the `ask`, all open questions in one `ask`, one line per question id. Never bundle forks into
   one question or hide them in a spec approval ("Accept? Sub-questions: …"). Before ending the turn, make sure `job.json` and the job
   folder hold everything needed to continue: after ~1 hour waiting on the owner the
   orchestrator releases this worker and resumes it (or a fresh one) from those files.
2. **Record acceptance** (medium/high risk, or whatever `{{WORKFLOW_DOC}}` requires): write the
   ticket record, then `ask --question "[{{KEY}}] SPEC-APPROVAL: <record path> — <one-line summary>"`
   (the approval is `{{KEY}}-q1`; each open point that is a real decision is its own question,
   the rest go under `notes`)
   and end your turn. No code before the answer says accepted.
3. **Push and draft PR: {{PUSH_POLICY}}.** This is the go-ahead for implement-ticket Phase 8:
   push the ticket branch and open a **draft** PR. Never mark it ready (merge-ticket does that
   right before the pre-merge re-gate), never merge,
   never push to `{{DEFAULT_BRANCH}}`, never force-push except `--force-with-lease` on your own
   branch after a rebase.
4. **Owner setup steps** become `docs/actions/<name>.md` guides with front matter, then
   regenerate the owner to-do list with `{{ACTIONS_LIST_CMD}}`. Secret names only, never values.
5. Keep `.delivery/jobs/{{KEY}}/job.json` current at every stage change, schema
   `deliver-job/1` (below). That file is how the orchestrator knows where you are.
6. Run the checks script in its local mode (no `--report`: it only prints) before the PR;
   the round files are written by the orchestrator's gate, never by you.
7. Finish part 1 at stage `built` round 1 (implement-ticket's hand-off): run
   `orca orchestration send --type worker_done --outcome succeeded --phase built --task-id <task> --dispatch-id <dispatch> --subject "[{{KEY}}] built" --body "<structured worker report>"`
   (use the exact worker_done command your Orca preamble gives you if it differs). Then stop.
   The orchestrator runs the gate itself, from `{{DEFAULT_BRANCH}}`'s copy of the checks
   script. Do not run the review loop on your own.

## Your job, part 2 — stage instructions (later, as follow-up messages)
Each instruction arrives as a message `[{{KEY}}] <STAGE> …`. Do exactly that stage, update
`job.json`, report with `worker_done` (phase = the stage you ended in), and stop.

Every round runs in this order (`state-files.md`, "Round order"): gate (the orchestrator's) →
**TEST** → (**DEVICE** if the lane was busy) → **REVIEW** → **APPROVE**. Copy the roles and the
device-lane grant each instruction gives into `job.json` (`roles`, `device_lane`) before
spawning anyone. Every subagent gets: the job folder `.delivery/jobs/{{KEY}}/`, round N, the
ticket URL, the record path and the PR number/URL; everything else it reads from `job.json`.
Each writes its one `round-N/<file>.md` and replies with one line. If an agent file is missing,
use a general-purpose subagent with that role's row from workflow section 3 as its checklist,
and say so in your report.

- **TEST r<N>** — set stage `testing`. Spawn the listed testers **in parallel**
  (`tester-functional`; `tester-device` only if this message grants the device lane). Both may
  commit test files / an E2E flow to the branch; each does `git pull --rebase`, then
  `git push`. When the listed testers have written: copy their first lines into `verdicts`,
  tester-device's started/stopped services into `services` and any `Blocked:` lines into
  `blocked`; stage `tested`, report. Do not start reviewers yourself — wait for `REVIEW`.
- **DEVICE r<N>** — the lane was granted later in the round. Run only `tester-device`
  (workflow section 3, "Device proof"), using `{{LOCAL_BACKEND_RECIPE}}` and
  `{{DEV_BUILD_REGISTRY}}`. Make sure every dev server, simulator and local backend it started
  is stopped and recorded in `job.json.services`; stage `tested`, report. The lane is released
  by that report.
- **REVIEW r<N>** — set stage `reviewing`. `git pull` so you hold the round's final commit
  (testers' commits included), then spawn the listed reviewers **in parallel** (models as
  given). `tester-device` builds and delivers the evidence PDF. `reviewer-ui` and `reviewer-ux` read `round-N/screenshots/` and `test-device.md`
  when tester-device ran. When all have written: stage `reviewed`, report.
- **FIX r<N>** — set stage `fixing`. Follow implement-ticket "Resuming with CHANGES verdicts"
  (read every file of round N, including `checks.md` when the gate failed; fix only what is
  asked; a `BLOCKED` device check is not yours to fix). Commit, push, `round: N+1`, stage
  `built`, report. If this would be round
  {{MAX_ROUNDS_PLUS_ONE}}, do not fix: stage `escalated` with one specific question.
- **APPROVE** — set stage `approving`. Spawn `approver`: it reads every verdict and the AC
  table and writes `decision.md` (first line `APPROVE` or `ESCALATE`; a `BLOCKED` device check
  means ESCALATE with one owner question). Post it as a PR comment.
  On `APPROVE`, spawn `explainer`: `walkthrough.md` → `gh pr edit --body-file` (keep the "What
  was built / How to test" part above it), a few inline guide comments, and the feature guide
  `docs/features/<area>.md` committed and pushed. Post one summary comment per round on the PR
  if not done yet. Run `{{COST_CMD}}` for this ticket's cost into `job.json.cost`. Stage
  `ready_to_merge`, report. On `ESCALATE`: put the one question on the PR and the ticket, stage
  `escalated`, report.
- **RESUME** — the owner answered: apply the answer exactly (record it in the ticket record's
  Decisions table with who/when), then continue from the stage the message names.
- **RESYNC** — merge `origin/{{DEFAULT_BRANCH}}` into your branch, resolve conflicts inside
  your owned paths (anything else: report, don't guess), re-run the checks, push, report.
- **STOP** — commit work in progress to your branch, push, report what is unfinished, end.
- **PAUSE** — finish the step you are in, commit, push, update `job.json` (stage and
  `progress`), report, then wait; start nothing new until **CONTINUE**.
- **CONTINUE** — re-sync with the base branch if behind, then carry on from the stage the
  message names.

## job.json (`deliver-job/1`)
Fields: `schema`, `ticket`, `title`, `type`, `risk`, `stage`, `round`, `branch`,
`base_branch`, `worktree`, `dispatch`, `pr` {`number`, `url`}, `record`, `routing`
{`ui_changed`, `app_testable`, `security_surface`, `backend_schema`, `needs_login`}, `roles`,
`device_lane` {`granted`, `round`, `granted_at`}, `acceptance` [{`id`, `text`, `status`,
`evidence`}], `verdicts`, `blocked` [{`ac`, `reason`}], `decision`, `escalation`,
`owner_actions`, `services` [{`kind`, `port`, `pid`, `name`, `started_by`, `status`}], `cost`,
`last_error`, `updated_at`. Stages: `intake`, `awaiting_owner`, `building`, `built`,
`testing`, `tested`, `reviewing`, `reviewed`, `fixing`, `approving`, `ready_to_merge`,
`escalated`, `blocked`, `failed`. Full schema: the orchestrator's `state-files.md` (deliver skill).
Be honest in `routing`: it decides which reviewers and testers judge your work.

## Rules
- Stay inside the ticket and the owned paths. Never edit settings, permissions, hooks,
  `CLAUDE.md`, other worktrees, or tracker structure.
- Testers never fix code; you never edit a verdict file.
- Report faithfully: commands you ran with their results; "not run" for what you didn't.
- **worker_done report format:** Ticket · Type · Risk · Branch · PR URL · Stage + round ·
  Checks command → result · Changed files · AC → evidence · Decisions · Deviations · Owner
  guides · Open concerns. One line at the top: `{{KEY}} <stage> r<N> · <PR URL> · <verdict summary>`.
```

---

## Stage instruction bodies

Send with `ORCA orchestration send --to dispatch:<id> --type dispatch --task-id <task> --subject "<subject>" --body "<body>"`.
Keep bodies short; the brief explains each stage.

```
[ABC-27] TEST r1
Gate PASS (round-1/checks.md). Run in parallel: tester-functional.
Device lane: NOT granted yet (busy) — skip tester-device; I will send DEVICE r1.
```

```
[ABC-27] DEVICE r1
Device lane granted to ABC-27 now (device_lane: granted, round 1). Run tester-device only. Release services when done.
```

```
[ABC-27] REVIEW r1
Testers written (test-functional PASS, test-device BLOCKED: needs a physical device). Pull the final commit, then run in parallel:
reviewer-code (model: sonnet), reviewer-ui, reviewer-ux (screenshots in round-1/screenshots/).
```

```
[ABC-27] FIX r1
CHANGES in round 1: review-code.md, test-functional.md (or: gate FAIL — round-1/checks.md, log tail inside).
Fix only what they ask, push, then round 2 / stage built. This is extra round 1 of 2.
```

```
[ABC-27] APPROVE
All routed roles PASS for round 2 (or tester-device BLOCKED). Run approver; on APPROVE run explainer and the cost script.
```

```
[ABC-27] RESUME
Owner answered Q3 (2026-11-08 14:10): "Defer AC4 to a follow-up; create it in wave 3." Record the decision, then run APPROVE.
```

Model hints follow the routing table: reviewer-code `haiku` for low risk, else `sonnet`;
reviewer-security `opus`; testers, reviewer-ui/ux and explainer `sonnet`; approver `opus`. The
agent files' own `model` frontmatter wins when present.
