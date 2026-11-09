# Ticket record, plan file and owner guides

Read at Phase 4–5. Defaults from `~/.claude/workflows/ai-delivery-workflow.md` section 7.
**If the repo's workflow doc prescribes another layout** (for example an older
`intent.md` / `spec.md` / `plan.md` / `verification.md` folder per ticket, or a compact
`README.md`), follow the repo and mention the difference in one line. Default to the layout
below otherwise.

## What goes where

| What | Where |
|---|---|
| Ticket record: intent, AC verbatim, design, decisions, deviations, outcome; spike findings | `docs/tickets/<KEY>-<n>.md` (committed) |
| Task plan, stage file, review rounds, screenshots before upload | `.delivery/jobs/<KEY>-<n>/` (gitignored, deleted at cleanup) |
| What was built and how to test | The draft PR description |
| AC results, screenshots, owner decisions, final status | The ticket in the tracker (posted by the loop / merge) |
| Owner setup steps | `docs/actions/<name>.md` (committed; to-do list generated) |

The repo keeps only what a future developer or agent needs to understand **why the code is
the way it is**. Evidence that it worked goes to the ticket and the PR, not to a
verification file.

## The ticket record

**One file by default:** `docs/tickets/<KEY>-<n>.md`. Use the **folder form**
`docs/tickets/<KEY>-<n>/` with `README.md` as the record only for large, high-risk tickets
whose record would pass roughly 300 lines or that have separate artifacts (a data contract,
migration plan, security analysis, diagrams: `data-model.md`, `migration.md`,
`security.md`…).

If the repo has a template (`docs/tickets/_TEMPLATE.md` or similar), copy it. Otherwise:

```markdown
# <KEY>-<n> — <title>

Ticket: <tracker link>
PRs: (pending)
Related: blocked by <KEY>-<n> · follow-up <KEY>-<n> · deferred to <KEY>-<n>
Type: Feature | Bug | Chore | Spike · Risk: Low | Medium | High · Status: In progress

## Intent
What problem, for whom, desired outcome. Assumptions (source: ticket / code / guess).

## Acceptance criteria
Copied verbatim from the ticket. Any confirmed testable rewording beside the original.

## Design
Approach, data and API changes, files that matter, edge cases, security / privacy / cost.

## Decisions
| decision | options | choice | who / when |

## Outcome
Filled at merge: deviations, known limitations, follow-ups, feature guide link.
```

**Per type, add:**

- **Bug:** `## Root cause` (what, why, why tests missed it) and the reproducing test name.
- **Chore:** keep it short; the AC includes "no behaviour change" and the Design section says
  how that is proven.
- **Spike:** `## Findings`, `## Recommendation`, `## Proposed follow-ups` instead of Design.

**Links block rules (mandatory):**

- The block sits at the top: the tracker link, **every PR** for the ticket (main PR and any
  follow-up fix PRs), related tickets (blockers, follow-ups, deferrals).
- Write `PRs: (pending)` until the draft PR exists, then replace it with the link in the same
  build (Phase 8) and push. Add every later PR on the same ticket.
- The project's ticket-record check fails if the ticket link is missing, or the PR link once
  a PR exists — so never leave it to the merge step.

**Deviations:** when the plan or design changes during the build, add a dated line under
Decisions or Outcome ("2026-03-04 — switched X to Y because Z; owner told: yes/no").

**Deferrals need the owner's word.** An AC moves to a follow-up only by explicit owner
decision, recorded in the record, the PR, the ticket and the follow-up ticket.

## The plan file

`.delivery/jobs/<KEY>-<n>/plan.md` — gitignored working state. Make sure `.delivery/` is in
`.gitignore` (add it and say so if not). The bar: someone who never saw this conversation
could build from the plan alone.

```markdown
# Plan — <KEY>-<n>
Branch: <branch> · Worktree: <path> · Record: docs/tickets/<KEY>-<n>.md

## Goal
## File map            path → role in the change (owned paths, for parallel work)
### Task 1 — <name>    files touched (≤ ~5)
- [ ] step
- [ ] test: <which test proves it>
### Task 2 — …
## Risks and rollback  migrations, generated files, contracts, anything irreversible
```

## Owner guides (`docs/actions/`)

Every human setup step becomes one guide, `docs/actions/<kebab-name>.md`. Follow the repo's
existing guides if any; otherwise:

```markdown
---
status: open            # open | done
tickets: [<KEY>-<n>]    # every ticket that needs this step
order: 30               # sort position in the owner to-do list
estimate: 10m           # how long the owner should expect
---

# <Action in plain words>

**Why:** what this unblocks.
**Prerequisites:** accounts, access, tools.

## Steps
1. …  (exact menus, commands, values to choose — secret NAMES only, never values)

## Expected result
## Verify
## Checklist
- [ ] …
## If it fails
```

Then **regenerate the owner to-do list** (usually `docs/actions/README.md`) with the
project's script (look in `scripts/` or the workflow doc). **Never hand-edit the shared
list**: a numbered list edited by parallel branches conflicts on almost every merge. If no
script exists, leave the README untouched, say so, and suggest adding the generator (setup
item in the workflow file, stage 1b).

Link the guide in your message and on the ticket. If a later step of the build is blocked on
the guide, say which and continue with what isn't.
