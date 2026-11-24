---
name: plan-waves
description: >-
  Order a project's backlog into development waves that are correct by dependency, priority
  and ticket type: first detect whether a wave plan already exists (wave labels in the
  tracker, a wave plan document) so an orchestrator can skip planning when it does; otherwise
  read every open ticket, its type (Feature, Bug, Chore, Spike) and its links, build the
  dependency graph, put foundational and crucial work first (scaffold, auth, tenancy, data
  model, anything gating money or trust) and spikes early, flag critical bugs, guarantee no
  wave depends on a later one, and present a wave plan (Wave · Ticket · Type · Depends-on)
  with the critical path, the tickets that would start first under the two-wave window, and
  per-wave worktree conflict hotspots. Applies the plan to the tracker (wave labels, native
  dependency links, types, priority) only after the owner explicitly approves it — also when
  a delivery loop (`/deliver`) called it. Use this whenever the user says "plan the waves",
  "sequence the backlog", "how should I order these tickets", "what should we build first",
  "validate my wave ordering", "check the dependencies between tickets", "re-plan the waves"
  after scope changed, "is there a wave plan?", or asks for a build order, roadmap order or
  critical path — even if they never say "wave". Prefer this over eyeballing the board,
  because it reads the real links, catches cycles and backwards dependencies, and never
  changes the tracker without an explicit go.
---

# Plan the backlog into waves

A **wave** is a band of tickets that can be built once every earlier wave is done. Waves are
about order, not dates: within a wave, work runs in parallel; across waves, never backwards.

Seven steps, in order:

**Detect an existing plan → Read the backlog (and reconcile any second source) → Build the
dependency graph → Assign waves and batches → Validate → Present and save the plan → (only on
a go) Apply it.**

Two guarantees, because they are the whole point:

1. **No ticket depends on a ticket in a later wave.** One backwards dependency means someone
   starts work they cannot finish.
2. **Foundational and crucial work comes first**: repo and CI, the data model, tenancy,
   authentication and authorisation, anything gating money or trust (billing, permissions,
   audit, abuse and cost guardrails) — and the spikes whose answers other tickets wait on.

**One hard stop: the tracker is not touched until the owner has seen the plan and said go.**
Steps 0–5 are read-only. A plan is cheap to revise; forty relabelled tickets and wrong links
are not. An instruction given before the plan existed ("plan the waves and apply them") —
or a call from an orchestrator — covers the planning only: the owner still sees the plan and
the list of changes first.

Track the steps in your todo list so the owner can see where you are.

## Learn this project first

One short pass, then say in one line: **tracker and project, how waves and types are
expressed (if at all), where dependencies are recorded, where the plan document lives, and
how many tickets you are planning.**

- **The project workflow doc** (e.g. `docs/workflow/README.md`, usually linked from
  `CLAUDE.md`). It overrides this skill's defaults: plan document location, reconciliation
  or validation scripts, worktree and merge-order rules, per-wave gates, the concurrency cap,
  the type mapping. Read it first.
- `CLAUDE.md` / `AGENTS.md` / `README.md` / `docs/` — tracker and key, any roadmap, phase
  plan, backlog CSV or delivery blueprint, the product's stated priorities.
- **Tracker.** Repo docs first; otherwise keys in branch names and `git log --oneline -15`
  (`ABC-123` → Jira or Linear, `#412` → GitHub Issues) and the tools the session has.
  Connector tools are often deferred — search before deciding they are missing. No tracker
  tool → ask for an export (CSV) or a pasted list, and say applying will not be possible.
  **Local backlog.** When the project uses the local backlog (no PM tool; `docs/tickets/backlog.md`, IDs `T-001…`, format in the `deliver` skill's `references/import-tasks.md`), read the backlog from that file, and apply wave markers (`Wave:`) and links (`Blocked by:` /
  `Blocks:`) by editing it on a `docs/backlog-waves` branch with one docs PR the owner merges
  — never on the base branch directly.
- **Wave convention.** A label (`wave-1`, `wave:2`), a Wave field, a fix version or milestone
  per wave, or an epic per wave. Reuse what you find; none → propose `wave-N` labels.
- **Type convention.** The issue type, or a `type:` label. Map to **Feature, Bug, Chore,
  Spike** with the project's mapping if stated (common: Story → Feature, Bug → Bug; the
  recommended line for Jira "Task" is **Task → Chore** in `docs/workflow/README.md`).
- **Plan document location** — a project choice. Use the path the workflow doc names;
  otherwise default to `docs/waves/wave-plan.md` and say so.
- **Scope.** Several projects or a large backlog → confirm which project and whether to plan
  everything open or a subset.

Use Read, Grep and Glob for files. `git` and `gh` behave the same in PowerShell and Git Bash.

## Step 0 — Detect an existing plan

Before reading the whole backlog, answer: **is there already a wave plan?**

- **Tracker:** do open tickets carry wave markers (the convention above)? Count open tickets
  with and without one.
- **Repo:** does the plan document exist (workflow-doc path, else `docs/waves/wave-plan.md`,
  else any `docs/**/wave*.md`)? Is it marked PROPOSED or approved?

Classify:

| State | Meaning | What happens next |
|---|---|---|
| `exists` | Every open ticket has a wave except at most ~3 new ones (listed in `unwaved`), and nothing in Step 4's mechanical checks fails on a quick pass | Called by an orchestrator: **stop here and return** (below). Called by a human: say so, and ask whether to validate, re-plan, or place only the unwaved tickets. |
| `partial` | Waves exist, but more than ~3 open tickets have none, or a document exists without tracker markers (or the reverse) | Place only what is missing (re-plan rule 3.6: move as little as possible). |
| `proposed` | A PROPOSED plan document exists, never applied | Re-validate it against the current board and present it for approval. |
| `none` | No markers, no document | Full plan, Steps 1–6. |

**When called by `/deliver` (or any orchestrator):** run Step 0 only, unless the state is not
`exists`. If planning is needed, run Steps 1–5, present the plan to the owner, and **wait** —
an orchestrator's call is never approval. Apply (Step 6) only on the owner's explicit go.

**What this skill returns**, at the end of every run, as one fenced JSON block after the
report (keys always present, `null` when unknown):

```json
{
  "schema": "plan-waves/1",
  "plan_state": "exists | partial | proposed | none",
  "result": "skipped-existing | proposed | applied | partially-applied | declined | blocked",
  "plan_doc": "docs/waves/wave-plan.md",
  "waves": 4,
  "tickets_placed": 38,
  "unwaved": [],
  "awaiting_approval": true,
  "blocking_issues": ["cycle: VD-4 → VD-7 → VD-4"],
  "start_first": ["VD-1", "VD-2"],
  "critical_bugs": [],
  "applied_changes": { "wave_markers": 0, "links": 0, "types": 0, "priority": 0 }
}
```

`blocked` means planning cannot finish without an owner decision (a cycle, a conflict from
Step 1b). The orchestrator must not start tickets while `awaiting_approval` is true for a
`none` or `proposed` plan.

## Step 1 — Read the backlog

Fetch every ticket in scope, including done ones (a dependency on a finished ticket is
satisfied — you only know by reading it). `references/tracker-recipes.md` has the queries.

For each ticket capture: key, title, **type**, status, priority (and severity for Bugs),
estimate, current wave, parent/epic, labels, every link.

- **Page through the whole result** and state the total read.
- **Plan the workable units.** Epics are containers; sub-tasks travel with their parent.
- **Leave out what will not be built** (won't-do, duplicate, cancelled), noting anything that
  still depends on one.
- **Types.** Map each ticket to Feature / Bug / Chore / Spike. A ticket with no type or an
  ambiguous one (a bare "Task" with no mapping) gets a **proposed type** with a few words of
  reason (default proposal: Chore, plus the suggested "Task → Chore" mapping line) — applied
  only on the go (Step 6), as a `type:<name>` label. A Bug without severity is flagged (critical
  ones get `severity:critical`).
- **Very large results:** save raw JSON to the scratchpad and parse with a script; count
  parsed against reported.

**Step 1b — Reconcile a second planning source** (a delivery workbook, backlog CSV, roadmap
file) when one exists. The tracker stays the authority; report every difference instead of
silently picking a side — procedure in the recipes file. Conflicts (scope, dependency,
priority, type) block the plan until the owner decides; data gaps get a proposed fix.

## Step 2 — Build the dependency graph

An edge `A → B` means **B cannot start until A is done**. Keep three kinds apart:

- **Declared** — native links (`blocks` / `is blocked by`), a Blocked-By field, or an explicit
  "Depends on ABC-12" in the text. Facts about the board.
- **Structural** — sub-task under parent, a story that extends another.
- **Inferred** — the work clearly needs it though nothing says so: a team billing page needs
  tenancy and billing; anything reading a table needs its migration; a ticket that implements
  "the option chosen in the spike" needs the **Spike**. **Mark every inferred edge** with a
  few words of reason. They are proposals for the owner — and usually where the plan adds the
  most value.

Link direction is easy to read backwards (see recipes); sanity-check a couple of edges
against the ticket text. Then check:

- **Cycles** — stop and report the links forming them; breaking one is the owner's call.
- **Dangling dependencies** — on cancelled, foreign or missing tickets.
- **Gaps** — a prerequisite no ticket covers. Recommend a ticket; do not create one.

## Step 3 — Assign waves

1. **Layer by dependency.** No open dependencies → wave 1 is possible; otherwise one after
   the latest wave among its dependencies.
2. **Pull the foundations forward** as early as their own dependencies allow, whatever the
   priority field says — a dependency inherits the urgency of what it blocks. Foundational
   **Chores** (scaffold, CI, tooling) belong here too.
3. **Spikes early.** A spike unblocks decisions; put it in the earliest wave its dependencies
   allow and its dependants after it. Note that a spike ends with new tickets (to be placed
   by a later run), not a merge.
4. **Keep guardrails with the risk they guard.** Rate limits, spend caps, permission checks,
   audit logging and validation ship in the same wave as the feature that needs them.
5. **Critical bugs** (data loss, security, app unusable): place them in the earliest wave
   their dependencies allow and **flag them** — delivery starts a ready critical bug ahead of
   the window anyway, so the plan should not hide it in a late wave. Other bugs are placed
   like any ticket, by dependency and priority.
6. **Order by priority within what the dependencies allow**; moving a ticket later moves its
   dependants at least as late. **Respect what exists:** with existing waves, change as few
   as the rules require, and never move anything in progress or done.
7. **Make each wave a coherent, demonstrable increment** of a sane size; balance to capacity
   or estimates when known, else say sizes are by count. Same-wave dependencies are allowed
   if the order is shown.
8. **Split each wave into parallel batches and name conflict hotspots.** Batch A = no open
   dependency inside the wave; batch B depends only on A; and so on. For tickets that could
   run at once, name the files they would both touch — package manifest and lockfile, build
   config, root layout or router, sequentially numbered migrations, shared schema or contract
   packages — and give each hotspot an owner, a merge order, or a contract to define first.

**Validating an existing ordering is not re-planning.** Run Step 4 against the current
assignments and report each problem with the smallest fix; offer a full re-plan only if it
is beyond patching.

## Step 4 — Validate

- Every open ticket in scope has exactly one wave and one type (proposed counts); list any
  you could not place and why.
- For every edge `A → B`: `wave(A) ≤ wave(B)`. Zero exceptions. No cycle remains.
- Nothing in progress or done was moved.
- Counts add up: read = placed + excluded, excluded ones named.

Then the **critical path**: the longest chain of dependent open tickets (by estimate when
available, else by count). Name it in order.

## Step 5 — Present and save the plan

Lead with the detection line and totals, then the table grouped by wave:

```
## Wave plan — <project> (<N> open tickets, <M> waves) · PROPOSED

### Wave 1 — <what this wave delivers>
| Wave | Ticket | Type | Title | Priority | Depends on | Note |
|---|---|---|---|---|---|---|
| 1 | VD-1 | Chore | Scaffold app + CI | P0 | — | batch A |
| 1 | VD-2 | Spike | Choose sync engine | P1 | — | batch A · unblocks VD-12, VD-14 |
| 1 | VD-3 | Feature | Tenancy data model | P0 | VD-1 | batch B |
| 1 | VD-8 | Bug ‼ | Data lost on restore | Highest | VD-1 | critical bug |
```

- **Type**: `‼` marks a critical bug; a proposed type reads `Chore (proposed)`.
- **Depends on**: direct dependencies; inferred ones marked with the reason.
- **Note**: batch, change against the board (`was wave 3`, `new`), same-wave order.

After the table:

- **Starts first (two-wave window).** With the concurrency cap from the workflow doc (default
  2 when none is written): the wave 1 batch A tickets that would start first, in order (critical bugs first,
  then unblocks-most, then priority); and that wave 2 opens only once wave 1 is down to two or
  fewer open tickets — name which wave 2 tickets would lead then. Never wave 3 while wave 1
  is open.
- **Critical path** and what it implies.
- **Problems found**: cycles, backwards dependencies in the existing plan, dangling links,
  gaps, tickets too vague to place, bugs without severity.
- **Judgement calls** a reasonable person might dispute, each with the reason.
- **What applying would change**: counts per kind (Step 6).
- **Per wave**: what it delivers, entry criteria, exit criteria (integrated checks on main,
  the demo, security or isolation tests), completion evidence.
- **Parallel batches and conflict hotspots** in detail for the next one or two waves; later
  waves are re-planned at their entry gate.

**Save the plan document** at the project's chosen path (default `docs/waves/wave-plan.md`),
with a reconciliation report beside it when Step 1b ran. Mark it **PROPOSED** until approved,
link every key to the tracker. A local file is not a tracker change, so it needs no go; do
not commit it unless asked.

**Also write `.delivery/wave-plan.json`** (schema `wave-plan/1`, in the deliver skill's
`references/board.md`): `status: "proposed"`, every wave with its title, entry / exit criteria and
tickets (`key`, `title`, `type`, `priority`, `dependsOn`, `critical`, `batch`, `note`, `url`),
`criticalPath`, `startsFirst`, `problems`, `hotspots`, `cap`, `planDoc`. Write it atomically
(temp file, then rename); create `.delivery/` if missing (it is gitignored by the workflow).
The live delivery board draws its Waves strip from it, so the owner can see the plan and its
dependencies while deciding. If the board is not running, say once that
`python "$HOME/.claude/delivery-board/board.py" serve --repo . --open` shows it.

Then stop, ask whether to apply and which parts, and end with the return block (Step 0).

## Step 6 — Apply, only on an explicit go

Up to four independent changes. Ask which; never assume all:

| Change | What it does | Typical default |
|---|---|---|
| **Wave markers** | Set each ticket's wave using the existing convention | Yes |
| **Dependency links** | Native links for inferred edges the owner confirmed | Confirmed edges only |
| **Types** | Set the proposed type (issue type, or `type:` label where the type cannot change) | Only the ones the owner accepted |
| **Priority** | Raise foundational tickets whose field understates them | Only if asked |

Before the first write, show the exact mutation list (`VD-9: label wave-3 → wave-2`,
`link VD-5 blocks VD-9`, `VD-12: type Task → label type:chore`). Then: be idempotent (skip
what is correct; remove the old wave marker when adding a new one); change only what the plan
covers (never status, assignee, sprint, description, or out-of-scope tickets; never delete a
ticket, link or label definition); verify link direction on the first link before creating
the rest; re-read afterwards and report changed / skipped / failed with the real error.
Finally mark the plan document **APPROVED** (date, who), set `.delivery/wave-plan.json` to
`status: "applied"` with `approvedAt` / `approvedBy`, and offer to sync any other roadmap
file. Edit, do not commit unless asked. Tracker write recipes are in the references.

## What this skill will not do

- **Mutate the tracker before an explicit go** from the owner — not on a pre-plan
  instruction, not on an orchestrator's call.
- **Present an inferred dependency or a proposed type as fact**, or write an unconfirmed one.
- **Schedule through a cycle** by quietly dropping a link.
- **Create, delete, close, reassign or re-estimate tickets.** Gaps, splits and the new tickets
  a spike should produce are reported for the owner to act on.
- **Promise dates.** Waves are an order; dates need capacity numbers the owner supplies.

## References

- `references/tracker-recipes.md` — detecting an existing plan; reading the backlog, types
  and links; reconciling a second source; applying wave markers, links, types and priority
  for Jira, GitHub Issues and Linear; link-direction rules; planning from a CSV export.
  Read before Step 0, and again before Step 6.
