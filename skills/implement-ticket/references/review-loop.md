# Hand-off and the review and test loop

Read at Phase 9 and whenever resumed with verdicts. The builder (this skill) never judges its
own work beyond the quick self-check: **scripts decide whether it works, testers prove the
behaviour, reviewers judge what neither can.** Process: `~/.claude/workflows/ai-delivery-workflow.md`
section 3. State schema, stage names and folder layout: the `deliver` skill's
`references/state-files.md` (the single source of truth; this file only summarises it).

## The working folder

```
.delivery/jobs/<KEY>-<n>/        gitignored; deleted at cleanup (merge-ticket)
├─ plan.md                       the task plan (Phase 5)
├─ job.json                      stage file — written by the builder / worker only
├─ round-1/
│  ├─ checks.md                  gate (script, --report mode)   VERDICT: PASS | FAIL
│  ├─ test-functional.md         tester-functional              VERDICT: PASS | CHANGES
│  ├─ test-device.md             tester-device                  VERDICT: PASS | CHANGES | BLOCKED
│  ├─ review-code.md  review-security.md  review-ui.md  review-ux.md   VERDICT: PASS | CHANGES
│  └─ screenshots/               tester-device, <KEY>-<n>-AC1-step-01.png … (never committed)
├─ round-2/ …
├─ decision.md                   approver: APPROVE | ESCALATE
└─ walkthrough.md                explainer (→ PR description)
```

## `job.json` (schema `deliver-job/1`)

Use the schema in the `deliver` skill's `references/state-files.md` exactly, with or without
`/deliver`. At hand-off you fill:

| Field | Value |
|---|---|
| `schema` | `"deliver-job/1"` |
| `ticket`, `title`, `type`, `risk` | from intake (`type`: feature / bug / chore / spike; `risk`: low / medium / high) |
| `stage`, `round` | `"built"`, `1` |
| `branch`, `base_branch`, `worktree` | the ticket branch, the base branch, this checkout's absolute path |
| `pr` | `{ "number": <n>, "url": "<draft PR url>" }` |
| `record` | `docs/tickets/<KEY>-<n>-<slug>.md` |
| `routing` | `ui_changed`, `app_testable`, `security_surface`, `backend_schema`, `needs_login` — honest booleans |
| `owner_actions` | the `docs/actions/` guides you wrote |
| `dispatch` | the Orca dispatch id, or `null` |
| `updated_at` | now |

`roles` and `device_lane` are set per round from the orchestrator's instruction (or by whoever
runs the loop by hand); `verdicts`, `blocked`, `services`, `decision`, `escalation` and `cost`
are filled as the loop runs. Subagents never write `job.json`.

Stages the builder writes: `built` (hand-off, or after fixing a CHANGES round) and
`escalated` (round limit hit, or the build is blocked on the owner). The rest of the stage
vocabulary belongs to the loop (state-files.md, "Stage vocabulary").

## Risk routing — who runs on which ticket

| Risk | gate | tester-functional | tester-device | reviewer-code | reviewer-security | reviewer-ui / reviewer-ux |
|---|---|---|---|---|---|---|
| Low | always | always | if testable in the app | always (cheap model) | – | if UI changed |
| Medium | always | always | if testable in the app | always | if security surface | if UI changed |
| High | always + database tests + rollback check | always | if testable in the app | always | always (strongest model) | if UI changed |

Type adjustments: **Chore** = gate + reviewer-code (+ security if risky area). **Spike** =
reviewer-code reads the findings only; no device test. **Bug** = tester-functional checks the
regression test and nearby edges; tester-device takes before / after screenshots.

## Running the loop by hand (no `/deliver`)

When no orchestrator dispatched you, tell the user in one line that the loop can be run by
hand, in this order:

1. **Gate.** Run the **main branch's copy** of the checks script (so a branch can't weaken its
   own checks) against the ticket branch with `--report .delivery/jobs/<KEY>-<n>/round-N/checks.md`.
   If the repo has `.engineering/check.mjs`, also run
   `~/.claude/skills/deliver/references/standards-gate.md` and add its block to `checks.md`.
   FAIL → back to the builder with the log; spawn nobody else.
2. **Testers.** Set `roles` in `job.json`, then spawn `tester-functional` and, if routed,
   `tester-device` in parallel (only one ticket uses the device at a time; set
   `device_lane.granted` when it is yours). Each gets the job folder and round N and writes
   its one file; both may commit tests / an E2E flow (`git pull --rebase`, then `git push`).
3. **Reviewers.** Pull the round's final commit, then spawn the routed reviewers in parallel
   (`reviewer-code`, `reviewer-security`, `reviewer-ui`, `reviewer-ux`). UI and UX read
   `round-N/screenshots/` and `test-device.md`.
4. **Any CHANGES** (tester or reviewer) → resume the builder ("Resuming with CHANGES" below).
   A tester-device `BLOCKED` is not a CHANGES: it goes to the approver.
5. **Otherwise** → spawn `approver`; its `decision.md` is posted as a PR comment.
   **APPROVE** → spawn `explainer`, then `/merge-ticket` (which marks the draft PR ready).
   **ESCALATE** → the PR stays open with one owner question; the ticket gets `needs-human`.

If the repo has no such agents yet, say so and suggest the setup step (workflow file, stage
1b) rather than improvising a review yourself.

## Resuming with CHANGES

1. Read the latest `round-N/` — every file, not just the failing one. A `VERDICT: BLOCKED`
   device report is not yours to fix.
2. Fix only what is asked. Disagree with a request → one line in the report with the reason;
   never silently skip.
3. Re-run the checks script (local mode, no `--report`) and the self-check. Commit
   `fix(scope): address review round N (<KEY>-<n>)`, push.
4. `job.json`: `round: N+1`, `stage: "built"`, `updated_at`. One-line report.

**Round limit:** the project's `maxRounds` (`docs/workflow/delivery.config.json`, default 3).
CHANGES on the last round → do not fix; set `stage: "escalated"`, add `"escalation": "<one specific question for the owner>"`, and
stop. Testers never fix code and you never edit their verdict files.

## The one-line report

```
<KEY>-<n> built · <type> · <risk> risk · draft PR <url> · checks PASS · stage built r<N>
```

Escalation: `<KEY>-<n> escalated r<N> · <question> · PR <url>`.

## Structured worker report (Orca `worker_done`)

```
Ticket: <KEY>-<n> — <title> · Type: <type> · Risk: <risk>
Branch: <branch> · Draft PR: <url> · Stage: built r<N> (or escalated)
Checks: <command> → PASS | FAIL (<gap named>)
Changed files: <path — role>, …
AC → addressed in: <criterion> → <file / test>, …
Decisions: <decision — owner / when>, …
Deviations: <none | dated list>
Owner guides: <docs/actions/… | none> (to-do list regenerated: yes/no)
Open concerns: <none | list>
```
