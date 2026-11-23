# Pause and resume

The owner can pause the whole delivery, or single tickets, without losing work, and resume later
from exactly where each ticket stopped. Pausing never changes the tracker (tickets keep their
status, e.g. In Progress) and never discards anything: work in progress is committed and pushed
to each ticket's own branch.

## Commands

| Command | Effect |
|---|---|
| `/deliver <KEY> --pause` | **Soft pause, everything.** Start nothing new, merge nothing. Each worker finishes the step it is in (a build task, a test or review round), commits and pushes, reports, and waits. A running gate finishes and is recorded but not acted on. |
| `/deliver <KEY> --pause --now` | **Hard pause, everything.** Send `STOP` to every worker now: commit work in progress to its branch, push, report what is unfinished, end. Running agents and the gate are left to finish their one file; nothing acts on it until resume. |
| `/deliver <KEY> --pause ABC-42,ABC-43` | Pause only these tickets (soft, or `--now`). The rest keep running; paused tickets free their concurrency slot, so the loop may start other ready tickets. |
| `/deliver <KEY> --resume` | Lift the pause for everything; resume each paused ticket from its recorded stage. |
| `/deliver <KEY> --resume ABC-42` | Resume only these tickets. |
| `/factory pause [#12 …] [--now]` · `/factory resume [#12 …]` | The same for `/factory` (keys `GH-12`). |
| `python "$HOME/.claude/delivery-board/board.py" pause --repo <main> [--ticket KEY] [--now] [--reason "…"]` | From a terminal or another chat: drops a pause request in `.delivery/inbox/`; the running orchestrator applies it at the start of its next cycle. |
| `python "$HOME/.claude/delivery-board/board.py" resume --repo <main> [--ticket KEY]` | The same for resume. |

Type `--pause` / `--resume` in the orchestrator's own chat for an immediate effect (it interrupts
the loop turn). In another chat, use the `board.py` commands: a second `/deliver` session would
find the lock held and must not write `orchestrator.json` itself.

`--pause` and `--resume` run one short cycle: bootstrap checks are skipped (the run already
exists), the lock is taken (or the request goes through the inbox when another session holds it).

## State (`orchestrator.json`)

```json
"pause": {
  "active": true,
  "scope": "all | tickets",
  "tickets": ["ABC-42"],
  "mode": "soft | now",
  "since": "2026-11-11T19:20:00+08:00",
  "by": "owner (chat) | owner (board.py)",
  "reason": "client demo tomorrow, freeze merges | null"
}
```

Per ticket in `tickets`: `stage: "paused"`, `pausedFrom: "<the stage it was in>"`,
`pausedAt`, `holdsSlot: false`, `waitingOn: "owner"`. `pause` is `null` when nothing is paused.

## The cycle while paused

Step 1 (sync and read) always runs: lock heartbeat, inbox (Orca and board), wave-status, reconcile.
Then:

| Cycle step | Paused (all) | Paused ticket (scope: tickets) |
|---|---|---|
| Housekeeping (merged-not-closed) | Still closes out PRs the **owner** merged by hand (that is the owner acting, and it starts nothing new) | Same |
| Advance running tickets | Soft: record each worker's report as it arrives (`worker_done` → its stage), then mark the ticket `paused` instead of sending the next stage instruction. Now: no instructions at all | Only that ticket is held |
| Device lane | Release it when its holder parks; grant to no one | Release if the paused ticket holds it |
| Merges | None (no `merge-ticket` merge, no merge lock) | None for that ticket |
| Fill capacity | Nothing starts | Paused tickets are skipped; others may start |
| Owner questions | Still relayed and still recorded (answers wait for resume) | Same |
| Board | One `pause` event; `orchestrator.json.pause` drives the banner | Same |

**Sending the pause to workers:**

- Soft → `[<KEY>] PAUSE` (body below): finish the current step, commit, push, report, then wait.
- Now → `[<KEY>] STOP` (existing message).
- Subagent engine → the same bodies through `SendMessage`.

**Ending the loop.** Once every in-scope worker has reported (or after one more wake-up for a
worker that stays silent, which is then noted), and pause scope is `all`: write the summary below
and end the loop (`ScheduleWakeup` with `stop: true`). Paused workers cost nothing while idle.
With scope `tickets`, the loop keeps running for the others.

```
## Delivery paused — <KEY> · <time>
Reason: <reason or "none given">
| Ticket | Paused at | Branch / PR | Unfinished |
| ABC-42 | building, task 3/5 | feat/abc-042/… · PR #57 (draft) | tasks 4–5 |
| ABC-45 | reviewing r2 | … · PR #59 | reviewer-ux pending |
Open questions still waiting: Q4 (ABC-45)
Resume with: /loop /deliver <KEY> --resume
```

## Resume

1. Clear `pause` (or remove the listed tickets from it); for each ticket set `stage` back to
   `pausedFrom` and recompute `holdsSlot`. If resuming would exceed the cap, resume in `ready`
   order and keep the rest `queued`, saying so.
2. Per ticket, send `[<KEY>] CONTINUE` (body below) with the instruction for its recorded stage.
   A worker that ended (hard pause, released after idling, or a subagent whose session is gone)
   is restarted with its brief plus a Resume section (stage reached, tasks committed, next step),
   as in cycle.md 3a.
3. Re-check before continuing: blockers still Done, the branch still up to date with the default
   branch (a long pause → `RESYNC` first), the device lane free.
4. One `resume` event. Under `/loop`, schedule the next wake-up as usual; a plain `--resume`
   says "run `/loop /deliver <KEY>` to keep it going" if the loop is not running.

## Messages

```
[ABC-42] PAUSE
Owner paused the delivery (reason: <reason>). Finish the step you are in, commit, push, update job.json
(stage + progress), report with worker_done, then wait. Start nothing new until CONTINUE.
```

```
[ABC-42] CONTINUE
Owner resumed. You were paused at <stage> (round N, task i/n). Re-sync with origin/<default> if behind,
then continue: <the stage instruction, e.g. "finish tasks 4-5, then built r1">.
```

## Trust rules for board.py pause / resume

Pause requests in the inbox are always safe to apply (they only stop work). Resume requests may
only lift a pause the owner set; they never start tickets that were not paused, never raise the
cap, never approve merges. Echo every applied request in the cycle output.
