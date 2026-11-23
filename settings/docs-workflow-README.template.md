# Delivery workflow — <Product>

PM project: <PM tool project link> · Key: `<KEY>` · Main branch: `main`

This project follows the AI delivery workflow (`~/.claude/workflows/ai-delivery-workflow.md`, imported from `CLAUDE.md`). This file holds the project's own values; where it is silent, the workflow's defaults apply. Review rules: `docs/workflow/REVIEW.md`.

## Capacity

- **Settings live in `docs/workflow/delivery.config.json`.** Run `/delivery-config` to see or change them (cap, review rounds, loop pacing, auto-accept, merge path). That file wins over this one.
- **Concurrency cap: 2** tickets in flight at once by default. (3 suits a desktop-class machine: `/delivery-config cap=3`.)
- **Device lane:** only one ticket uses the simulator / emulator / device and the dev ports at a time. The orchestrator hands the lane out; a ticket waiting for it also waits for its UI / UX reviewers.

## Merge path

- **Owner merges** (default). The agent re-checks, marks the PR ready, labels the ticket `ready-to-merge` and hands over the PR link; the owner merges (squash); `/merge-ticket` then finishes the close-out.
- To switch to **agent merges**, run `/delivery-config mergePath=agent` and allow `gh pr merge` for agents in `.claude/settings.json`. Both are required.

## Ticket type mapping

| PM tool issue type | Workflow type |
|---|---|
| Story | Feature |
| Bug | Bug |
| Task | Chore |
| Spike (or `type:spike` label) | Spike |

A `type:<name>` label wins over the issue type. Critical bugs carry `severity:critical`.

## Scripts

- **Checks:** `scripts/workflow/checks` (`.sh` / `.ps1`). `--report <path>` (`-Report` in PowerShell) writes the round file (first line `VERDICT: PASS` or `VERDICT: FAIL`); without it the script only prints the result and exit code.
- **Cost:** `scripts/workflow/cost <KEY>-<n>` prints the priced total of the ticket's agent transcripts (posted on the PR and the ticket at merge).

## Risk tiers

| Risk | When | Extra gates |
|---|---|---|
| Low | Small change, no risky area | — |
| Medium | Everything else | Security reviewer if a security surface is touched |
| High | <auth, data access rules, AI / prompt surfaces, quotas, sync, billing, account deletion / export, migrations on live data> | Security reviewer always; database tests + rollback check |

## Where things go

- Ticket records: `docs/tickets/<KEY>-<n>-<slug>.md` (links block first).
- Owner setup steps: `docs/actions/<name>.md` (front matter; `docs/actions/README.md` is generated).
- Environment recipes: `docs/setup/local-backend.md`, `docs/setup/dev-builds.md`.
- Feature guides: `docs/features/<area>.md`.
- Wave plan: `docs/waves/wave-plan.md`.
- Working state: `.delivery/` (gitignored).
- Labels: `needs-human`, `ready-to-merge`, `wave-N`, `type:<name>`, `severity:critical`.

## QA

- **QA testing status:** `<the tracker status that means "ready for QA", e.g. In QA>` (used by `/qa <KEY> --ready` and `--mine`). Environments and access: `docs/workflow/qa.config.json` (`/qa-config`). QA logins: gitignored `.env.qa.local`. Evidence: `.delivery/qa/`. A person signs off; `/qa` never moves a ticket to Done.
