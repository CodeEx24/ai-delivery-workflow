# Ticket record, plan file and owner guides

Read at Phase 4–5. Defaults from `~/.claude/workflows/ai-delivery-workflow.md` section 7.
**If the repo's workflow doc prescribes another layout** (for example an older
`intent.md` / `spec.md` / `plan.md` / `verification.md` folder per ticket, or a compact
`README.md`), follow the repo and mention the difference in one line. Default to the layout
below otherwise.

## What goes where

| What | Where |
|---|---|
| Ticket record: links, spec, AC verbatim, design, decisions, what changed, future work, notes for future agents; spike findings | `docs/tickets/<KEY>-<n>-<slug>.md` (committed) |
| Task plan, stage file, review rounds, screenshots before upload | `.delivery/jobs/<KEY>-<n>/` (gitignored, deleted at cleanup) |
| What was built and how to test | The draft PR description |
| AC results, screenshots, owner decisions, final status | The ticket in the tracker (posted by the loop / merge) |
| Owner setup steps | `docs/actions/<name>.md` (committed; to-do list generated) |

The repo keeps only what a future developer or agent needs to understand **why the code is
the way it is**. Evidence that it worked goes to the ticket and the PR, not to a
verification file.

## The ticket record

**One file by default:** `docs/tickets/<KEY>-<n>-<slug>.md`. Use the **folder form**
`docs/tickets/<KEY>-<n>-<slug>/` with `README.md` as the record only for large, high-risk tickets
whose record would pass roughly 300 lines or that have separate artifacts (a data contract,
migration plan, security analysis, diagrams: `data-model.md`, `migration.md`,
`security.md`…).

**Name:** `<slug>` is 3–6 lowercase words from the title, the same as the branch slug, for example
`docs/tickets/ABC-123-quote-status-filter.md`.

**Finding a record:** look for `docs/tickets/<KEY>-<n>-*.md`, then `docs/tickets/<KEY>-<n>-*/README.md`,
then the older `docs/tickets/<KEY>-<n>.md` and `docs/tickets/<KEY>-<n>/README.md`. Never match on
`<KEY>-<n>*` alone, because `ABC-12*` also matches `ABC-123`. Do not rename existing records.

**Keep it safe to reuse:** no secrets, tokens, real customer data or production values. Name
environment variables, never their values.

If the repo has a template (`docs/tickets/_TEMPLATE.md` or similar), copy it. Otherwise:

```markdown
# <KEY>-<n> — <title>

Ticket: <tracker link>
PRs: (pending)
Related: blocked by <KEY>-<n> · follow-up <KEY>-<n> · deferred to <KEY>-<n>
Feature guide: (filled at merge)
References: designs, specs, docs, ADRs, earlier ticket records read for this work, or none
Type: Feature | Bug | Chore | Spike · Risk: Low | Medium | High · Status: In progress

## Summary for future agents
Filled at merge, 3–5 lines: what exists now, and the one thing to know before changing it.

## Intent (spec)
What problem, for whom, desired outcome. Assumptions (source: ticket / code / guess).

## Acceptance criteria
Copied verbatim from the ticket. Any confirmed testable rewording beside the original.

## Design
Approach, data and API changes, files that matter, edge cases, security / privacy / cost.

## Decisions
| decision | options | choice | why | who / when |

## What changed
Filled at merge: behaviour, key files, data and migrations, APIs, config and env var names.

## Outcome
Filled at merge: deviations from the design, and deferred criteria with the owner's decision.

## Future work
Known limitations, follow-up tickets with keys, options rejected for now and when to revisit.

## Notes for future agents
Gotchas, what not to undo and why, related records, what to read first.
```

**Per type, add:**

- **Bug:** `## Root cause` (what, why, why tests missed it) and the reproducing test name.
- **Chore:** keep it short; the AC includes "no behaviour change" and the Design section says
  how that is proven.
- **Spike:** `## Findings`, `## Recommendation`, `## Proposed follow-ups` instead of Design.

**Links block rules (mandatory):**

- The block sits at the top: the tracker link, **every PR** for the ticket (main PR and any
  follow-up fix PRs), related tickets (blockers, follow-ups, deferrals), the feature guide and
  other useful references.
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
Branch: <branch> · Worktree: <path> · Record: docs/tickets/<KEY>-<n>-<slug>.md

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
