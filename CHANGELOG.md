# Changelog

## 2026-11-11 — `/factory` and the live delivery board

Inspired by zazencodes' "software factory v2" (label-driven GitHub issue queue, file-based state, a polling HTML board), rebuilt on this kit's engine instead of a second pipeline.

**New**

- **`/factory`** (manual-only): open GitHub issues labeled `factory` are the queue. Same engine as `/deliver` (worktrees, implement-ticket, gate, testers, reviewers, approver, explainer, merge-ticket). Issue labels track each step (`factory:building`, `factory:needs-info`, `needs-human`, `ready-to-merge`); unclear issues get one marker comment with numbered questions; talk mode (`/factory Q3: B`, `/factory #12 <feedback>`, `reject`, `new: <feature>`); optional waves (`/factory plan`). Issue text is quoted as data; only author / operator / write-access comments count.
- **Subagent engine** (`skills/factory/references/subagent-engine.md`): runs workers as background subagents when Orca is not available, with testers and reviewers spawned by the orchestrator at depth 1. Also `/deliver --engine subagents`.
- **Live delivery board** (`board/` → `~/.claude/delivery-board/`): Python standard library server + one HTML page, 127.0.0.1 only. One view of the wave plan, every ticket's step (intake → build → gate → test → review → approve → merge → done), round verdict chips, task progress, acceptance criteria, blockers, real liveness (newest file change, "quiet 40m"), owner questions with answer buttons, a per-ticket feedback box, agent reports and screenshots, and an activity feed. Answers go to `.delivery/inbox/` and are applied on the next cycle within strict trust rules (open questions only; never plan approvals, merges or settings). `--demo` shows sample data. Host-header, origin and per-session token checks; no directory-listing dependency (unlike the original).
- **`workflow/PLAYBOOK.md`**: commands by scenario — Jira backlog, one ticket only, GitHub issues, new project.
- **`/deliver --only <keys>`** and **`/deliver --board`**.
- **`/delivery-init`**: one command to set up a project (marked CLAUDE.md block, `docs/workflow/README.md`, `.gitignore`; settings only on an explicit yes). The installers copy `settings/` into it as templates.
- **`INSTALL.md`** and an **MIT `LICENSE`**.
- **`/new-ticket "<description>"`**: one sentence → drafted ticket (testable AC, risk, size, assumptions) → owner approves → created in Jira / Linear / GitHub Issues, or as a local `docs/tickets/T-<nnn>.md` (doubles as the ticket record) with a colour status 🔴 To do / 🟡 In progress / 🟡 In review / 🔴 Blocked / 🟢 Done / ⚪ Won't do, PR link and log. implement-ticket accepts a description and calls it; implement-ticket sets 🟡 on the branch, merge-ticket sets 🟢. Playbook scenario E.

**Changed**

- **deliver**: bootstrap starts the board; each cycle drains the board inbox, writes `orchestrator.json.backlog` and one `events.jsonl` line per action. New reference `references/board.md`. `state-files.md` documents `events.jsonl`, `wave-plan.json`, `board.json`, `inbox/`, `flavor`, `backlog`, `orca.engine`, `agentId`, `job.json.progress` / `questions`, and `GH-<n>` keys for GitHub issues.
- **plan-waves** writes `.delivery/wave-plan.json` (PROPOSED, then APPLIED) beside the plan document.
- **implement-ticket** writes `job.json` from the first minute and keeps `progress` (phase, task i/n) current; GitHub-issue PRs carry `Closes #<n>`.
- **Installers** copy `board/` to `~/.claude/delivery-board/` and print the demo command.

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
