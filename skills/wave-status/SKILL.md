---
name: wave-status
description: >-
  Report where the project stands and what to start next: find the two-wave window (the
  lowest wave with open tickets, plus the next wave once the lowest is down to its last one
  or two), read each ticket's status and type from the tracker, cross-check every ticket
  against the repo's GitHub pull requests, flag anything out of sync — above all tickets
  whose PR merged but which were never closed — rank the ready tickets to fill the
  project's concurrency cap (a ready critical bug first), name the single top pick, list
  what needs the owner (needs-human tickets, escalated PRs, ready-to-merge PRs, open owner
  guides), report
  housekeeping left behind (worktrees and branches of merged PRs, stale delivery job
  folders), and end with a machine-readable summary an orchestrator can consume. Use this
  whenever the user says "what should I work on next?", "what's next", "check the current
  wave", "wave status", "where are we", "how far along is wave 2", "is anything out of
  sync?", "did I forget to close a ticket", "which tickets are ready", "what needs me?",
  or starts a work session wanting a pick from the backlog — and whenever a delivery loop
  (`/deliver`) needs to know what to start — even if nobody mentions waves. Prefer this
  over reading the board alone, because the board says what people remembered to update,
  while the PR cross-check says what actually happened. Read-only: it reports and
  recommends, and changes nothing in the tracker, the repo, or the file system.
---

# Wave status, the ready list and the next pick

Seven steps, in order:

**Find the window → Read the board → Cross-check the PRs → Rank what is ready → What needs
the owner → Housekeeping → Report (with the summary block).**

The cross-check earns its keep: a tracker records what somebody remembered to update; the
repo records what happened. A PR merged days ago on a ticket still In Progress makes the next
ticket look blocked and "what's next" come out wrong.

**This skill is read-only.** It does not transition, comment, label, assign, merge, delete
branches or remove worktrees; it names the fix and the skill that does it, so it is safe on
every cycle of a delivery loop.

**Two readers.** A human asking "what next?" wants one pick with a reason. An orchestrator
(`/deliver`) wants the ranked ready list, the free slots and the owner queue in a form it can
parse. The report serves both: prose and tables first, the fenced JSON summary last.

## Learn this project first

One short pass, then say in one line what you detected: **tracker and project, how waves and
ticket types are expressed, the GitHub repo, who "you" are, and the concurrency cap.**

- `CLAUDE.md` / `AGENTS.md` / `README.md` — tracker and key, branch naming (how keys appear
  in branch names), what counts as Done. If the project imports a delivery workflow file,
  this skill follows its window and readiness rules (they match the ones below).
- **`docs/workflow/README.md`** (or wherever the project keeps delivery rules) — the
  **concurrency cap** (tickets in flight at once) and anything it says about the device lane,
  the `needs-human` / `ready-to-merge` label names, or the wave plan location. No cap written
  down → default to 2 and say "cap 2 (default; none set in the project)"; a range like "2–3"
  → use the upper bound and quote the range.
- **Tracker.** Go by the repo's docs first; otherwise by keys in branch names and
  `git log --oneline -15` (`ABC-123` → Jira or Linear, `#412` → GitHub Issues) and by the
  tools the session has. Connector tools are often deferred — search for them before deciding
  they are missing.
  **Local backlog.** When the project uses the local backlog (no PM tool; `docs/tickets/backlog.md`, IDs `T-001…`, format in the `deliver` skill's `references/import-tasks.md`), read tickets, waves, types and links from **`main`'s copy** of that file instead of the
  PM tool. Its Status is only To Do / Done / Won't do; derive In Progress / In Review from an
  open branch, PR or `.delivery/jobs/<ID>/` folder. A merged PR whose entry is not Done is
  `merged-not-closed` as usual.
- **Wave convention.** Sample a few tickets: a label (`wave-1`, `wave:2`), a Wave field, a fix
  version or milestone per wave, or an epic per wave. The tracker is the live source; a wave
  plan document is context — mention it if they disagree.
- **Ticket type.** The issue type, or a `type:` label (`type:bug`). Map to the four delivery
  types — **Feature, Bug, Chore, Spike** — using the project's mapping if it states one
  (common: Story → Feature, Bug → Bug, Task → Chore). Anything unmapped is shown as its raw
  name with `?` and counted in Housekeeping as "type not set".
- **Repo.** `gh repo view --json nameWithOwner,defaultBranchRef` and `gh auth status`. If
  `gh` is missing, unauthenticated, or the remote is not GitHub, say the PR cross-check
  cannot run and why — in the report too, so an unchecked board never reads as "in sync".

Use Read, Grep and Glob for files. `references/status-recipes.md` has every query.

## Step 1 — Find the two-wave window

Read every ticket that has a wave, with status. **Open** means not in the done category
(in progress and in review are open).

- **Base wave N** = the lowest-numbered wave with at least one open ticket — even if work has
  started on a later one.
- **Wave N+1 joins the window** only when wave N has **two or fewer** open tickets.
- **Never N+2 or later** while wave N has any open ticket.
- When wave N is done, the window moves up: N+1 becomes the base.

Say it in one line: "Window: wave 2 (5 open) — wave 3 not yet open" or "Window: wave 2
(2 open) + wave 3".

Cases that do not fit:

- **No waves.** Say so, offer `plan-waves`, and meanwhile fall back to the project's unit of
  work (active sprint, nearest open milestone), naming the fallback.
- **Every wave done.** Say so; list open tickets with no wave.
- **Open tickets with no wave.** Count and list them; they are invisible to the window until
  placed (a critical bug among them still jumps the queue, Step 4). More than ~3 unwaved →
  recommend running `plan-waves` to place them.
- **Work in progress outside the window** (N+1 before it opened, or N+2). Report it — it
  may be deliberate; it should not be silent.
- **The user asked about one wave** → report that wave and name the window if it differs.

## Step 2 — Read the board

For each ticket in the window: key, title, **type**, status, assignee, priority, estimate if
any, labels, and dependency links. Also fetch every open ticket labelled `needs-human` and
every open Bug in any wave (for Steps 4–5).

Group by status **category**, not name: **Done** (won't-do / duplicate is *resolved*, not
delivered: out of the percentage, marked ⚫) · **In progress** (including In Review / In QA;
show the real status name) · **To do**.

Progress per wave is `done ÷ (done + in progress + to do)` by count; add it by estimate when
estimates exist. Never blend the two.

## Step 3 — Cross-check the pull requests

Fetch the repo's PRs once (open, merged, closed) and match them to tickets by key in branch
name, title, or body. Rules in the recipes file; the two that matter most: **match the whole
key** (`VD-4` is not `VD-42`, case-insensitive), and **only a merge into the default branch
(or the documented release branch) counts as landed.**

| Tracker says | PRs say | Verdict |
|---|---|---|
| To do / In progress / In review | A PR **merged** into the default branch, none still open | **Merged but not closed** — the headline. PR number and merge date. Fix: `merge-ticket <KEY>` (already-merged path: verifies deploy, posts proof, closes, cleans up). |
| Done | No merged PR; one still open | **Closed too early.** |
| Done | No PR at all | Usually fine (Spike, decision, config). Mention only if the ticket clearly called for code. |
| To do | An open PR exists | **Started but not marked** — not available to pick. |
| In progress | No branch, PR, worktree, job folder or recent commit | **Possibly stale** — note assignee and "not updated since". |
| In progress / In review | Open PR | In sync. Note CI and review state when cheap. |
| In progress / In review | PR closed unmerged, nothing open | **Abandoned attempt.** |
| Any | One PR merged, another open for the key | Multi-PR ticket, still in progress — not a mismatch. |

A Done Spike with only a docs-only record PR is in sync. Also run the headline check over **earlier waves and tickets with no wave**. Report each
mismatch with evidence and its one fix; never fix it here.

## Step 4 — Rank what is ready

A ticket is **ready** when all hold:

- Status is **To do**, and **nobody is on it**: unassigned or assigned to the current user,
  and no open PR, remote branch, worktree, or `.delivery/jobs/<KEY>-<n>/` folder for it.
- **Every "is blocked by" link is Done.** A blocker whose PR merged but whose ticket lags
  counts as done for readiness — say so ("ready once VD-41 is closed; PR #87 merged").
- It is not labelled `needs-human` or `ready-to-merge`.

Everything else in To do is **blocked**: name each one's blockers and their state. A ticket
assigned to someone else is theirs — list it separately, never as ready.

**Order the ready list** (this is the order an orchestrator starts them):

1. **Critical bugs first, ahead of the window.** A ready Bug the tracker marks critical (data
   loss, security, app unusable: highest priority, `severity:critical`; wording alone is only
   "possibly critical"), from any wave or none. An open blocker still stops it.
2. **Window order**: wave N, then wave N+1 (if open).
3. **Unblocks the most**: how many open tickets depend on it, directly or through a chain;
   critical-path tickets win ties.
4. **Priority.**
5. **Most foundational** (data model, auth, tenancy, anything gating money or trust), and a
   Spike before the tickets waiting on its answer.
6. **Lowest key**, so the order is stable between runs.

**Slots.** `in flight` = window tickets in progress or in review that are not waiting on the
owner (an escalated or `ready-to-merge` PR holds no slot; it is listed in Step 5). `free slots` = cap − in
flight, never below 0. **Start now** = the first `free slots` tickets of the ready list.

**Top pick for a human** — one ticket, decided in this order, stopping at the first rule
that separates:

1. **A ready critical bug** beats everything.
2. **Finish before starting.** If the user has a ticket in progress or in review in the
   window, the pick is to finish (or merge) that one.
3. **Clear a cheap mismatch first** when it unblocks others (`merge-ticket <KEY>`).
4. Otherwise the head of the ready list.

State the pick and reason in one line and the runner-up in another. Offer
`implement-ticket <KEY>`; never start it.

If nothing is ready, say so and say what would unblock the window soonest. Never reach into
N+2; tickets in N+1 before the window opens are not offered, even as a fallback.

## Step 5 — What needs the owner

One section, four sources, so the owner sees everything waiting on them in one place:

- **`needs-human` tickets** (the label name the workflow doc gives, default `needs-human`),
  any wave: key, title, and the question if the latest comment carries one.
- **Escalated PRs**: open PRs labelled `needs-human`, or whose latest approver decision
  comment starts with `ESCALATE`. Show the PR link and the one-line question.
- **Ready for your merge**: tickets or open PRs labelled `ready-to-merge` (approved, waiting
  for the owner's merge; kept apart from escalations). Show the PR link and its CI state.
- **Open owner guides**: `docs/actions/*.md` whose front matter has `status: open`, sorted by
  `order`. Show the file, its `tickets`, and `estimate`. Flag a guide whose tickets are all
  Done ("guide still open; tickets done — close the guide?") and a ready ticket that a guide
  lists ("VD-46 needs `docs/actions/set-api-key.md` first").

No `docs/actions/` folder → say "no owner guides folder". Nothing waiting → say "Nothing needs
the owner." Do not omit the section.

## Step 6 — Housekeeping

Left-behinds that should not exist once `merge-ticket` has closed a ticket out. Report each
with its fix; touch nothing.

- **Worktrees of merged PRs**: `git worktree list --porcelain`; a worktree whose branch
  belongs to a merged PR (or a Done ticket) should have been removed.
- **Local branches of merged PRs**: match local branch names to PR `headRefName` with state
  MERGED (squash merges defeat `git branch --merged`, so match by name), plus branches whose
  upstream is `[gone]`.
- **Stale job folders**: `.delivery/jobs/<KEY>-<n>/` in the main checkout or any worktree whose
  ticket is Done or whose PR merged or closed; also one with no file changed in 2+ days
  while its ticket is still open (a stalled run worth resuming).
- **Prunable worktree records** (`prunable` in the porcelain output).
- **Tickets with no type** in the window.

Fix for merged-PR leftovers: `merge-ticket <KEY>` (its cleanup step removes worktree, branch
and job folder after checking they are clean and pushed). For prunable records:
`git worktree prune`. Nothing found → "Housekeeping: clean."

## Report format

```
## Wave status — <project> · window: wave <N> (<o> open)<+ wave N+1>

Detected: <tracker/project> · waves via <label|field|milestone> · types via <issue type|label>
· <owner/repo> · you are <account> · cap <c> (<source>)

Progress: wave <N> ✅ <d>/<t> (<p>%) · 🟡 <i> in progress · 🟢 <r> ready · 🔴 <b> blocked
          <wave N+1 line when it is in the window>
Slots: <in flight> of <cap> in flight · <free> free

| | Ticket | Type | Title | Status | Assignee | PR | Depends on |
|---|---|---|---|---|---|---|---|
| ✅ | VD-38 | Feature | … | Done | you | #80 merged 25 Sep | — |
| ⚠️ | VD-41 | Bug | … | In Progress | you | #87 merged 28 Sep | VD-38 ✅ |
| 🟡 | VD-43 | Feature | … | In Review | you | #91 open, CI green | — |
| 🟢 | VD-46 | Chore | … | To Do | — | — | VD-38 ✅ |
| 🔴 | VD-45 | Feature | … | To Do | — | — | VD-41 ⚠️ |

### ⚠️ Out of sync
- VD-41 — tracker says In Progress, PR #87 merged into main on 28 Sep. → `merge-ticket VD-41`
(or "Nothing out of sync." / "PR cross-check not performed: <reason>.")

### 🟢 Ready, in start order
1. VD-77 · Bug · critical (data loss) — jumps the window
2. VD-46 · Chore · wave 2 · P1 · unblocks VD-50, VD-52
Start now (2 free slots): VD-77, VD-46

### 🔴 Blocked
- VD-45 — waiting on VD-41 (PR merged; ticket not closed)

### 🙋 Needs the owner
- VD-39 — needs-human: "Defer AC3 to a follow-up?" · PR #85 ESCALATE
- VD-40 — ready-to-merge: PR #86 approved, CI green — merge it
- docs/actions/set-api-key.md — open · tickets VD-46 · ~10 min

### 🧹 Housekeeping
- Worktree `../wt/vd-38` (branch feat/vd-38/login) — PR #80 merged. → `merge-ticket VD-38`

### Next
**VD-43** — yours, in review, CI green: merge it before starting anything new.
Runner-up: VD-46 (unblocks two tickets).

<fenced JSON summary — schema in references/status-recipes.md, "The summary block">
```

**Status markers.** Every row starts with one marker; every "Depends on" entry carries the
marker of the ticket it names. ✅ done · 🟡 in progress / in review, in sync · 🟢 ready ·
🔴 blocked · ⚠️ out of sync (takes precedence over 🟡 / ✅) · ⚫ resolved without delivery ·
🙋 needs the owner (a `needs-human` or `ready-to-merge` ticket, in place of 🟡/🔴). Use markers in rows, the
progress line and section headings only — not in prose.

Sort the table done → in progress → to do, or split per wave when the window holds two.
Never drop a section heading without its explicit "nothing" line — an absent section reads
as one that was never checked.

**The summary block** goes last, always, in the exact shape given in the summary-block
section of `references/status-recipes.md`: window, cap and slots, ready list in start order,
start-now list, top pick, in progress, blocked, out of sync, needs the owner, housekeeping. Keys are
stable; values the run could not determine are `null`, never guessed.

## What this skill will not do

- **Change anything** — no transitions, comments, labels, assignments, merges, branch or
  worktree removal, file deletion. It names the fix and the skill that performs it.
- **Call a board in sync when the PR cross-check did not run.**
- **Offer a ticket outside the window** (N+2 while N is open; N+1 before it opens), except a
  ready critical bug.
- **List as ready** a ticket with an open blocker, one someone else is on, or one waiting on
  the owner.
- **Offer several top picks as equals** — one pick, one runner-up (the ranked list is for
  filling slots).
- **Re-plan the waves.** A backwards dependency or an unplaced ticket is reported, with
  `plan-waves` as the fix.

## References

- `references/status-recipes.md` — tracker queries (Jira, GitHub Issues, Linear), types and
  critical bugs, the concurrency cap, PR fetching and matching, owner queue, housekeeping
  commands, the summary block schema with an example, Windows shell notes. Read before
  Step 1, and its summary-block section again before writing the report.
