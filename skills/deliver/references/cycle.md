# The cycle

One cycle per wake-up, whether the wake came from ScheduleWakeup, from Orca mail, from a
finished background gate, or from an owner message. Same steps every time; most cycles do
little. Keep your own output short: one line per action, the detail lives in files.

## 1. Sync and read

1. **Lock.** Refresh `lock.heartbeatAt`; if another fresh holder exists, stop (state-files.md).
2. **Main checkout.** `git status --porcelain` must be empty; `git pull --ff-only`. Dirty or
   diverged → do not cycle; report. (`main`'s checks script and agent files are read from here.)
3. **Inbox.** Drain with a plain consuming `ORCA orchestration check --json` until it returns
   nothing. Handle each message by type: `worker_done` → step 3 event; `question` → step 6;
   `escalation` with `stopReason` → the worker stopped without reporting: `worker-show`,
   steer with `send`, or report. Never `check --wait`, never a watch script.
   Then the **board inbox**: `python "$HOME/.claude/delivery-board/board.py" inbox --repo <main> --take`.
   Never write `~/` in this command (PowerShell does not expand it). If the command fails, say
   so in the cycle output and list `.delivery/inbox/*.json` by hand; never skip the inbox silently.
   `answer` items are handled as owner answers (step 6), `feedback` items as escalation answers
   or owner notes, within the trust rules in `board.md`. Echo each one in the cycle output.
   `control` items (`pause` / `resume`, from `board.py pause|resume`) are applied first, as in
   `pause.md`.
   **Paused?** If `orchestrator.json.pause.active`, every later step follows the "while paused"
   table in `pause.md` (no new starts, no merges, no stage instructions to paused tickets).
4. **Board.** Run `wave-status` and parse the fenced `wave-status/1` block (stable keys). Use
   its `ready` order, `start_now`, `in_progress`, `blocked`, `out_of_sync`, `needs_human`,
   `housekeeping`, `concurrency`. If `pr_crosscheck.ran` is false, say so; do not merge or
   close out anything this cycle on board data alone. Rewrite `orchestrator.json.backlog` from
   the block (every open ticket of the window and the waves after it, with status, wave and
   blockers) so the live board's Waves strip is current (`board.md`).
5. **Reconcile** `orchestrator.json` with each ticket's `job.json` (read from its worktree)
   and the board. Disagreements are findings: e.g. job `ready_to_merge` but PR closed → stop
   that ticket, report.

## 2. Housekeeping first

| Board finding | Action |
|---|---|
| `out_of_sync: merged-not-closed` | `merge-ticket <KEY>` (already-merged path: deploy check, proof, Done, cleanup). It may unblock ready tickets, so do it before filling capacity. |
| `housekeeping: worktree-merged / branch-merged / worktree-prunable` | Through merge-ticket's cleanup (step 7). With `warning` (uncommitted or unpushed work) → report, never discard. |
| `job-folder-stalled` (no file change for 2 days, ticket open, no live worker) | `worker-show`; resume with `send` or report. |
| `closed-too-early`, `abandoned`, `possibly-stale` | Report in the summary; no action. |
| `type-missing` | Report; the worker treats it as Feature unless the owner says otherwise. |

## 3. Advance running tickets

For each ticket in `tickets`, take **at most one action per new event** (a report, a finished
gate, an owner answer). No new event → nothing to do for that ticket.

Every round runs in the order of `state-files.md`, "Round order": **gate → testers → reviewers
→ approver → explainer**.

| Current state (orchestrator stage / job stage) | Event | Action → new stage |
|---|---|---|
| `dispatched` / `intake`, `building` | — | Nothing; the worker runs implement-ticket. |
| any / `awaiting_owner` | worker `ask` | Step 6 (relay). `holdsSlot: false`, `waitingSince` set; released after ~1 hour (3a step 3). |
| `dispatched` / `built` r1 | `worker_done phase built` | Queue the gate → `gating` (or wait in `gate.queue`). |
| `gating` | background gate finished, PASS | Compute routing. Send `TEST r<N>` with the routed testers; include tester-device only if the device lane can be granted now (step 4) → `testing`. No tester routed (e.g. a Spike) → send `REVIEW r<N>` → `reviewing`. |
| `gating` | gate FAIL | Send `FIX r<N>` with the log path → `gate_failed`. A failed gate starts no tester or reviewer. |
| `testing` / `tested` | `worker_done phase tested` | tester-device routed but not yet run → `device_wait` until the lane is free, then `DEVICE r<N>` (step 4). Every routed tester written → send `REVIEW r<N>` with the routed reviewers → `reviewing` (whatever the testers' verdicts: one fix round then covers everything). |
| `reviewing` / `reviewed` | `worker_done phase reviewed` | Read every `round-N/*.md` first line. Any `CHANGES` → `FIX r<N>`. Otherwise (all PASS, tester-device possibly `BLOCKED`) → send `APPROVE` → `approving`. A `BLOCKED` alone never sends `FIX`. |
| `gate_failed` / `fixing` → `built` r<N+1> | `worker_done phase built` | Gate again (round N+1). |
| any / `escalated` | `worker_done phase escalated` | Step 3a. |
| `approving` / `ready_to_merge` | `worker_done phase ready_to_merge` | Verify `decision.md` first line is `APPROVE`, the walkthrough is in the PR body, PR head = branch head. Queue the merge (step 3b). merge-ticket marks the draft ready. |
| any / `blocked`, `failed` | `worker_done --outcome failed` | Report with `last_error`; label `needs-human` only if the owner must act; `holdsSlot: false`. |

**Round limit.** `round` counts review rounds, up to `policy.maxRounds` (default 3: round 1 + 2
extra). CHANGES on the last round, or that many gate failures in a row → send `FIX r<N>` with the
line "round limit reached — do not fix; escalate with one specific question". The brief tells the worker
to set `escalated` instead of fixing. Never skip to `APPROVE` to get past the limit.

### Routing (decided by the orchestrator, from `job.json`)

Workflow section 3 table, applied to `risk`, `type` and `routing` flags:

| Role | Phase | Runs when |
|---|---|---|
| gate | gate | always (high risk: the checks script's database tests + rollback check must run — confirm in `checks.md`) |
| tester-functional | testers | always (Chore: checks "no behaviour change"; Spike: no) |
| tester-device | testers | `app_testable` (not Spike), and the device lane is enabled for this ticket |
| reviewer-code | reviewers | always — `haiku` for low risk, else `sonnet` (Spike: reads findings only) |
| reviewer-security | reviewers | high risk always (`opus`); medium if `security_surface`; Chore touching auth/deps with security impact |
| reviewer-ui | reviewers | `ui_changed` (reads the round's screenshots when tester-device ran) |
| reviewer-ux | reviewers | `ui_changed` (judges from the round's screenshots; code-only if there are none) |

Store the list in `tickets[KEY].routing` and send each phase's roles in its instruction (the
worker copies them into `job.json.roles`); `pendingRoles` = routed roles without a verdict file
for the round yet. A round is complete only when `pendingRoles` is empty.

### The gate

- One gate at a time (`policy.gateConcurrency`); others wait in `gate.queue` (FIFO, critical
  bugs first). Mark `waitingOn: "gate"`.
- Run **the main checkout's copy** of the checks script with the ticket's worktree as the
  working directory, in the background (Bash or PowerShell `run_in_background`), in **report
  mode** (workflow 1b convention: `--report <path>` writes the round file; without it the
  script only prints, which is the builder's local mode), e.g.
  `cd "<worktreePath>" && bash "<mainCheckout>/scripts/workflow/checks.sh" --report ".delivery/jobs/<KEY>-<n>/round-<N>/checks.md"`
  (`.ps1`: `pwsh -File "<mainCheckout>\scripts\workflow\checks.ps1" -Report "<same path>"`).
  If the script has no report mode yet, capture its output and write `round-N/checks.md`
  yourself: first line `VERDICT: PASS` or `VERDICT: FAIL`, the command, exit code, and the last
  ~60 log lines.
- No checks script (degraded setup) → run CI's commands in CI's order the same way and say so
  in `checks.md` and on the PR.
- The finished background task wakes you; that is the gate event.

### 3a. Escalations

On `escalated` (ESCALATE decision — including a device check the tester reported `BLOCKED` —
round limit, or blocked on the owner):

1. Make sure the one specific question is on the PR and the ticket (the worker posts it; check,
   don't duplicate). Add the tracker's `needs-human` label.
2. Add it to `ownerQuestions` (`kind: "escalation"`), with your recommendation and any
   `docs/actions/` guide from `job.json.owner_actions`.
3. `holdsSlot: false`, `waitingOn: "owner"`, `waitingSince` now. Once it has waited
   **~1 hour** (`policy.idleReleaseMin`, default 60) — or sooner if memory is tight — release the
   worker (`ORCA orchestration worker-release --dispatch <id>`); its job folder and worktree
   stay. On the answer, `send` reopens it, or start a fresh worker in the same worktree with a
   resume brief. The same applies to workers waiting on a relayed question (step 6).
4. On the owner's answer: send `RESUME` with the answer and the stage to continue from (for a
   BLOCKED device check: the owner provided what was missing → `DEVICE r<N>` again, then
   `APPROVE`; the owner deferred the criterion → record it, then `APPROVE`); remove
   `needs-human` once nothing else waits on the owner; it re-enters capacity (it needs a free
   slot; resumed tickets go ahead of new ones).
5. A **deferral** of an acceptance criterion needs the owner's explicit word and a follow-up
   ticket — creating that ticket is a tracker change the owner's answer must authorize.

### 3b. Merging — one at a time

Preconditions, all re-checked right before: `decision.md` = `APPROVE`; job `ready_to_merge`;
no `CHANGES_REQUESTED`; CI not red; `mergeLock.holder` is null.

1. Take `mergeLock`; stage `merging`.
2. Run **`merge-ticket <KEY>`**. It marks the draft PR ready (`gh pr ready`; merge-ticket owns
   that step), re-syncs with the default branch and re-runs main's copy of the checks script
   (the pre-merge re-gate), merges per the merge path, verifies the deploy,
   posts the proof (AC results + screenshots on the ticket; verdicts, decision, CI and cost on
   the PR), moves the ticket to Done, re-syncs the other open PRs, and cleans up.
   - **Agent merge path** (`policy.mergePath` is `agent`, which `delivery-config` reports only
     when the merge command is allowed for agents): it merges with `policy.mergeStrategy`.
     Expect `MERGED` and a merge SHA in its report.
   - **Owner merge path (the default):** it stops at the hand-over and labels the ticket
     `ready-to-merge` (not `needs-human`). Stage `awaiting_owner_merge`, release the merge lock,
     `holdsSlot: false`, release the worker after ~1 hour like any owner wait, and tell the owner: "**Ready for your review** — <PR URL>
     (re-gate green on <sha>, CI green, APPROVE). Merge it, and I'll finish the close-out." Each
     cycle check `gh pr view <n> --json state,mergedAt`; on `MERGED` take the lock again and run
     `merge-ticket <KEY>` (already-merged path).
   - Re-gate or CI red, conflicts, deploy failure → merge-ticket stops. Release the lock; send
     `FIX` or `RESYNC` to the worker, or escalate; never retry the merge past it.
3. Release `mergeLock`. Only then may the next ticket merge.
4. Other open PRs merge-ticket skipped (builder mid-stage, conflicts) → note them; send
   `RESYNC` to each at its next stage boundary (never mid-stage).

## 4. Device lane

- Holder: one ticket. Queue: FIFO, critical bugs and resumed tickets first.
- Grant it with the round's testers when the holder field is free: include tester-device in
  `TEST r<N>`, set `deviceLane.holder`, `waitingOn: null`. If the lane is busy, `TEST r<N>`
  carries tester-functional only; when tester-functional has written, the ticket waits in
  `device_wait`, `waitingOn: "device-lane"`; on grant send `DEVICE r<N>`. Reviewers never start
  before tester-device has written (they need its screenshots and the round's final commit).
- The holder's `worker_done phase tested` with `test-device.md` written releases the lane
  (`PASS`, `CHANGES` or `BLOCKED` alike). Check `job.json.services` shows its simulator / dev
  server / backend stopped; otherwise note it. Grant to the next in queue in the same cycle.
- A holder silent for > 45 min → `worker-show`; do not reassign the lane until the holder is
  confirmed stopped or has reported.

## 5. Fill capacity

`free = policy.cap − count(holdsSlot)`. While `free > 0`, take the next key of `ready` (wave-
status order: critical bugs first, then window order, unblocks-most, priority; with
`policy.only` set, only those keys, and a listed key that is not in `ready` is reported with
the reason) and check:

1. **Blockers:** re-read the ticket's "is blocked by" links in the tracker now — every one Done.
   A blocker whose PR merged but ticket is not closed → close it out first (step 2), not around it.
2. **Project entry rules:** readiness label/status; for medium/high risk, design accepted if the
   workflow doc requires it before a worktree (otherwise the worker asks SPEC-APPROVAL).
3. **Window:** wave ∈ {base, next if `window.next_open`}, or critical bug.
4. **No collision:** owned paths and hotspots don't overlap a running ticket's; migration
   hotspot: one in-flight branch at a time.
5. **Machine:** free disk above `policy.diskWarnGb`.

Pass → write the brief (`worker-brief.md`), `worker-start`, record the ticket (`dispatched`,
`holdsSlot: true`), comment on the Orca worktree card. Fail → skip with the reason in the
cycle line. Never take a ticket from outside `ready`.

## 6. Owner questions

- **Answer yourself** when the answer follows from the brief, the accepted record, the workflow
  file, the project docs, or an earlier owner answer — `reply --id <message_id>`, and say so in
  the cycle line. `SCOPE` requests: grant only if no running ticket owns the path; otherwise
  tell the worker to wait or escalate.
- **One question, one entry.** Follow `~/.claude/skills/implement-ticket/references/owner-questions.md`.
  Every cycle, sweep every job folder's `job.json.questions` for open entries not yet in
  `ownerQuestions` (match on `jobQuestion`), and add each as its **own** entry with
  `jobQuestion: "<KEY>-q<n>"`, its own options and recommendation. Never merge several into one
  entry or summarize them as "Sub-questions: …". A worker `ask` that bundles forks without
  `job.json.questions`: split it yourself, one entry per fork, and remind the worker of the guide.
- **Auto-accept (only when `policy.autoAcceptRecommended` is on; default off).** Answer an open
  question with its recommended option when **all** hold: its `kind` is `decision` or
  `spec-approval`; it has a `recommendation` naming one listed option; the ticket is not high
  risk; and it does not touch auth, permissions, data access rules, secrets, billing, personal
  data, deletion, production, or migrations on live data. **Always relay** escalations, round-limit
  and `BLOCKED` questions, `scope`, `needs-info` and `action` questions, deferred acceptance
  criteria, ticket lists, wave plans, setup decisions, and any merge. Record
  `answer`, `answeredAt` and `answeredBy: "auto"` on the entry, log an `answer` event
  ("auto-accepted <KEY>-q<n>: <option>"), and list it in the cycle output and the stop summary.
- **Relay** the rest. Every open question every cycle (no cap), grouped by ticket, newest context first:

  ```
  ## Questions for you (reply like "Q3: A")
  Q3 · ABC-30 Reminders (https://…/browse/ABC-30) — Snooze length options?
      Recommended: A — 10 / 30 / 60 min, matches the settings screen.  B — free entry.
  Q4 · ABC-27 SPEC-APPROVAL — docs/tickets/ABC-27.md (medium risk): accept? open question: …
      Recommended: accept.
  ```
  Use AskUserQuestion only when nothing else can move until the answer (e.g. stop condition
  would otherwise be reached), and then put up to 4 open questions in it, never just one while
  others wait; otherwise post the list and keep cycling.
- **Answer the worker once its questions are all answered** (or the owner says "go with your
  recommendations"): one `reply` listing every `<KEY>-q<n>: answer`. Board answers carry
  `jobQuestion`; map them to that entry.
- **Map answers** from the owner's messages ("Q3: A", "accept ABC-27", free text) to
  `ownerQuestions`, `reply` to the worker's message id, record `answeredAt`/`answer`. Unclear
  answer → ask back once, briefly.
- Owner-action guides (`docs/actions/*.md` with `status: open`) that block a ready ticket are
  listed with their link and estimate; the ticket is not started until the owner says done.

## 7. After each merge — verify the close-out

merge-ticket reports what it did; check it actually happened:

| Check | How |
|---|---|
| PR merged | `gh pr view <n> --json state,mergeCommit` → `MERGED` |
| Ticket Done | Re-read the ticket status |
| Proof posted | Ticket comment with AC results + screenshots; PR comment with verdicts, decision, CI, cost |
| Worktree gone | `git worktree list`, `ORCA worktree list --json` (remove with `ORCA worktree rm --worktree <id> --json` if left and clean) |
| Branch gone | `git branch --list <branch>`; remote deleted |
| Working folder gone | `.delivery/jobs/<KEY>-<n>/` absent in the main checkout too |
| Worker released | `ORCA orchestration worker-list --json` shows no active terminal for the dispatch |
| Services stopped | No listener from `job.json.services` (`ORCA ports --all --json`) |
| Disk | Free space on the worktree drive; warn under `policy.diskWarnGb` |

Anything left with uncommitted or unpushed work → report, never delete. Then move the ticket
to `history` (PR URL, merge SHA, rounds, cost, leftovers) and remove it from `tickets`.

## 8. Persist and decide

Write `orchestrator.json`; append one line to `.delivery/orchestrator.log.md`:
`2026-11-08 14:20 · c12 · gate ABC-27 r2 PASS → TEST · merged ABC-25 (#29) · started ABC-31 · Q3 relayed · next 600s`.

**Events for the board.** Each action in the cycle output also gets one line in
`.delivery/events.jsonl`, written as it happens (not batched at the end), through
`python "$HOME/.claude/delivery-board/board.py" event --repo <main> --kind <kind> --ticket <KEY> --text "<line>"`:
`dispatch` (worker started), `gate` (result), `verdict` (a round's testers / reviewers settled),
`stage` (stage change), `question` (relayed), `answer` (applied), `escalate`, `merge`, `error`,
and one `cycle` line here (`cycle 12 · in flight 3/3 · next 600s`, no ticket).

Then check the stop condition (SKILL.md) and either send the summary and stop, or schedule the
next wake-up.

### Cycle output (each turn)

```
Cycle 12 · wave 2 (3 open) + wave 3 · in flight 3/3 · device: ABC-30 · merge lock: free
- ABC-25 merged → https://github.com/owner/repo/pull/29 (cleanup verified)
- ABC-27 gate r2 PASS → TEST r2 sent (tester-functional; device queued behind ABC-30)
- ABC-31 started (wave 3, worktree abc-031-reminders)
Questions for you: Q3 (see above)
Next check in 10 min.
```

### Stop summary

```
## Delivery paused — <KEY> · <date>
Nothing more can move without you.

Merged this run
| Ticket | PR | Rounds | Cost |
| ABC-25 Settings shell | https://github.com/owner/repo/pull/29 | 2 | $4.12 |

Waiting on you
| Ticket | Why | What to do |
| ABC-30 | ESCALATE: defer AC4? | Answer Q3 · PR https://… |
| ABC-33 | Owner action | docs/actions/set-push-key.md (10 min) |
| ABC-24 | `ready-to-merge`: ready for your review/merge | https://github.com/owner/repo/pull/27 |

Blocked behind those: ABC-35 (on ABC-30), ABC-36 (on ABC-33)
Setup gaps still open: dev build registry (device tests skipped on native tickets)
Resume with `/loop /deliver <KEY>` once you've answered.
```

## `--status` output

Read-only: lock holder and heartbeat, mode, cap and in-flight, each ticket's stage/round/
waitingOn with PR link, device lane and queue, merge lock, open owner questions, last cycle
and next wake. Add a fresh wave-status progress line. Change nothing.
