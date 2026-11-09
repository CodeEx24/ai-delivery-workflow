# plan-waves — what changed (draft)

Why: in the new delivery workflow (`~/.claude/workflows/ai-delivery-workflow.md`, sections
section 2 stage 2, and section 5) the `/deliver` orchestrator calls plan-waves only when a project has no wave plan
yet, and every ticket now has a type (Feature / Bug / Chore / Spike) that affects ordering.

## Added

- **Step 0 — detect an existing plan.** Looks for wave markers on open tickets and for the
  plan document, and classifies: `exists`, `partial`, `proposed`, `none`. Called by `/deliver`
  with a plan already in place, it stops there and reports "skipped-existing".
- **A return block.** Every run ends with a small fenced JSON (`plan-waves/1`): plan state,
  result (skipped / proposed / applied / declined / blocked), plan document path, waves,
  unwaved tickets, whether it is waiting for approval, blocking issues, which tickets start
  first, critical bugs, and counts of changes applied.
- **Ticket types.** Reads each ticket's type, proposes one when it is missing or ambiguous
  (e.g. a bare "Task"), shows a Type column, and can set types on the go (as a `type:` label
  where the tracker cannot change the issue type).
- **Spikes early**, with an inferred edge from a spike to the tickets that depend on its
  answer. **Critical bugs flagged** (‼) and placed as early as their dependencies allow; bugs
  without severity are reported.
- **"Starts first" in the summary**: which tickets would start under the two-wave window and
  the concurrency cap, and when wave 2 would open.
- **Plan document location is a project choice** (workflow doc), default
  `docs/waves/wave-plan.md`; marked PROPOSED, then APPROVED with date after the go.
- Recipes for plan detection and for reading/setting types per tracker.

## Changed

- Apply step now offers four independent changes (wave markers, links, **types**, priority)
  instead of three.
- The detailed "reconcile a second planning source" procedure moved from SKILL.md to the
  recipes file (same rules), to keep SKILL.md under 300 lines.

## Kept

- Dependency graph with declared / structural / inferred edges, cycle, dangling and gap
  checks.
- Foundations first, guardrails with the feature they guard, no backward dependencies,
  critical path, minimal moves when re-planning, validate-only mode.
- Parallel batches and per-wave worktree conflict hotspots.
- **The hard stop:** nothing is written to the tracker without the owner's explicit go — and
  now it is explicit that a `/deliver` call is not a go either.

## Removed

- Nothing of substance.

## Open questions for the owner

1. **Setting types in Jira.** Draft prefers a `type:<name>` label over changing the issue type
   (which can need a "move" and lose fields). Fine, or should it change the issue type?
2. **"exists" threshold.** Draft treats "a few" new unwaved tickets as still `exists`, but
   reports them. Should `/deliver` instead always run plan-waves to place unwaved tickets
   (returning `partial`)?
3. **Return block** — confirm the keys once `/deliver` is written, so both sides agree.

## Alignment pass (after all drafts were written)

- No content change; the workflow reference was reworded to "section 2 stage 2". `/deliver`
  reads the `plan-waves/1` return block as written (question 3 settled).

## Follow-up pass

- **Local backlog:** reads the backlog from `docs/tickets/backlog.md` and applies wave markers
  and links by editing it on a `docs/backlog-waves` branch with one docs PR — never directly on
  the default branch. Note added in "Learn this project first".

## Owner decisions applied (2026-11-08, all recommendations accepted)

- **#6:** "starts first" uses the default cap **2** when none is written.
- **#13 / #14:** a bare Jira "Task" is proposed as Chore (applied as a `type:<name>` label on the
  go) and the "Task → Chore" mapping line is suggested.
- **#16:** `exists` allows at most ~3 unwaved tickets; more → `partial` (place the missing ones).
