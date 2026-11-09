# Changelog

## 2026-11-08 — initial version

First packaged release of the kit. Detailed notes per skill and the full list of owner decisions: [`docs/changelog/2026-11-08/`](docs/changelog/2026-11-08/) (start with `ALIGNMENT.md`).

**New**

- **`/deliver`** orchestrator (manual-only): bootstrap check of the project setup, waves via `/plan-waves` when missing, then a continuous build → gate → testers → reviewers → approver → explainer → merge cycle inside a two-wave window, a concurrency cap (default 2) and one shared device lane. Can start from a task document (`/deliver <path-to-doc>`) and create the tickets in the PM tool, GitHub Issues, or a local `docs/tickets/backlog.md`. Modes `--status`, `--dry-run`, `--watcher`, `--cap N`.
- **Eight delivery-loop agents:** tester-functional, tester-device, reviewer-code, reviewer-security, reviewer-ui, reviewer-ux, approver, explainer. Each writes one verdict file (`VERDICT: PASS | CHANGES`, tester-device also `BLOCKED`) and replies with one line; all carry `autoCompactWindow: 200000`.
- **One state schema** (`skills/deliver/references/state-files.md`) and one working folder `.delivery/jobs/<KEY>-<n>/` shared by every skill and agent.

**Changed**

- **implement-ticket** now stops at a draft PR (12 phases → 9); reads the ticket type (Feature / Bug / Chore / Spike) and adapts; Bugs reproduce first with `test-driven-development`; single-file ticket record `docs/tickets/<KEY>-<n>.md` with a links block; owner guides in `docs/actions/` with front matter.
- **verify-ticket** is the engine of tester-device: mobile as well as web, a screenshot per step, a replayable E2E flow (one per ticket), local backend + test account, PASS / CHANGES / BLOCKED.
- **merge-ticket** runs the whole close-out: `gh pr ready`, re-sync and re-gate on `main`'s checks script, merge by the project's merge path (owner merges by default, `ready-to-merge` label), proof on ticket and PR, cost, re-sync other PRs, cleanup.
- **wave-status** uses the two-wave window, ranks ready tickets to fill the cap, reports what needs the owner and leftover housekeeping, and ends with a machine-readable summary.
- **plan-waves** detects an existing plan first, handles ticket types, places spikes early and flags critical bugs; applies nothing without the owner's yes.
- **senior-pr-reviewer** gained a delivery-loop output mode (`VERDICT:` header), confidence levels and a severity crosswalk.

**Owner decisions baked in:** owner merges by default; cap 2; workers released after ~1 h waiting; stalled job folders reported after 2 days; Jira "Task" → Chore via the project's workflow doc; `severity:critical` jumps the window; spikes land as docs-only; separate `needs-human` and `ready-to-merge` labels; cost script `scripts/workflow/cost`; context windows orchestrator 300k / workers 400k / subagents 200k with a `# Compact instructions` section in each project's `CLAUDE.md`.
