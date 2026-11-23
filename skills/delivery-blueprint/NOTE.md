# delivery-blueprint — read me first

**This folder is a mirror of the claude.ai-synced skill. Edit the source in claude.ai** (Settings → Capabilities → Skills), not here. Claude Code receives it through skill sync, so the installer skips this folder unless you pass `--with-blueprint` / `-WithBlueprint` (for machines without claude.ai sync).

**The mirror is incomplete.** The local synced copy this was taken from (2026-11-08) ends mid-sentence in two places:

- `SKILL.md` stops inside Step 4, at "Dependencies o…" in the ticket-doc scaffold bullet (Step 5 "Verify before delivering" and anything after it are missing).
- `references/formats.md` stops inside section 7, the AGENTS.md template, at "<core invariant 1, …".

Re-export the full skill from claude.ai and replace these files before relying on this copy.

## Recommended updates so blueprints match the workflow

Checked against the visible part of the skill. It already produces: CLAUDE.md + AGENTS.md (locked stack, folder tree, naming table, branch/commit rules, skills section, reuse-first, documentation discipline, DoR/DoD, commands), a `docs/tickets/` folder with a `_TEMPLATE.md`, a dependency-ordered wave and sprint plan, and a PM import CSV with wave labels and a Blocked By column.

Still missing (add these in claude.ai):

1. **Workflow import line** in the generated CLAUDE.md: `@~/.claude/workflows/ai-delivery-workflow.md`.
2. **`# Compact instructions` section** in the generated CLAUDE.md (what the orchestrator and ticket workers keep after compaction; see `settings/claude-md-snippet.md` in this kit).
3. **Ticket record template** as a single file `docs/tickets/<KEY>-<n>-<slug>.md` with the links block (Ticket / PRs / Related) and the line `Type · Risk · Status`, then Intent · Acceptance criteria · Design · Decisions · Outcome (workflow section 7). The current template uses different sections (Overview · Implementation details · API changes · Database changes · …) and has no links block.
4. **`docs/workflow/README.md`** with: concurrency cap (2 by default), device lane rule (one ticket on the simulator/device at a time), merge path (owner merges by default; "agent merges" only if allowed), ticket type mapping (e.g. Jira "Task" → Chore), checks script `scripts/workflow/checks` (`--report <path>` mode), cost script `scripts/workflow/cost <KEY>-<n>`, risk tiers and gates, plus `docs/workflow/REVIEW.md`. Template: `settings/docs-workflow-README.template.md`.
5. **`docs/actions/`** for owner setup steps: each guide with front matter (`status: open | done`, `tickets`, `order`, `estimate`) and a generated `docs/actions/README.md` (never a hand-edited numbered list).
6. **`docs/setup/`** with `local-backend.md` (port overrides, seed data, test account, local mail catcher) and `dev-builds.md` (dev build id per native-dependency set).
7. **`docs/features/`** for feature guides (one per feature area, template in workflow section 8).
8. **`.delivery/` in `.gitignore`** (the delivery loop's working folder).
9. **Ticket types** Feature / Bug / Chore / Spike on every ticket (`type:<name>` label where the PM tool's issue types don't map), with the type-specific content (Bug: repro steps, expected vs actual, severity; Spike: question, options, time box). Add `severity:critical`, `needs-human` and `ready-to-merge` labels to the import guide.
10. **Stub scripts** `scripts/workflow/checks` and `scripts/workflow/cost` (or a ticket in Wave 1 that creates them), following workflow section 6.
