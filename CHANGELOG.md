# Changelog

## 2026-11-23 (qa) — QA workflow for deployed tickets

- **`/qa`**: tests a deployed ticket, your assigned tickets, everything ready for testing, or a release. It builds a scenario matrix, screenshots every step, reuses the `verify-ticket` browser drivers and checks, writes an evidence report and updates the tracker. A person signs off: it never moves a ticket to Done.
- **`/qa-config`**: sets where QA may test, with access levels per environment, exact host matching, GitHub deployment checks and QA account variable names. Secrets stay in the gitignored `.env.qa.local` and are never printed. Personal settings cannot widen access.
- **`/report-bug-ticket`**: files one clean bug after searching open and recently closed tickets, adding evidence to an existing bug or linking a regression instead of creating a duplicate.
- **Engineering handoff:** every QA bug carries what another machine needs to reproduce, fix and retest it, with evidence attached to the tracker after a secret scan. Failed uploads are marked `Evidence incomplete` and labeled `qa:evidence-missing`.
- **`/qa <KEY-n> --retest`:** re-verifies failed scenarios, reruns all of them plus regressions, and reports fixed, still failing, newly failing and not run. Anything required that did not run is BLOCKED.
- **Bug fixes from QA:** builders reproduce first and add a regression test. The device tester runs the full retest, and the approver requires it to pass on the final product code.

## 2026-11-23 (settings) — personal machine settings

- **`/delivery-config --me cap=4`**: each developer can set how many tickets run on their own computer without changing the team's setting. Stored in `~/.claude/delivery.machine.json`, outside the repo.
- **Personal settings:** `cap`, `loopMinutes`, `idleReleaseMin`, `engine` and `diskWarnGb`. Merging, review rounds, auto-accept, pushing and browser testing stay team rules and cannot be overridden personally.
- **Clearer `/delivery-config`:** shows every setting, where its value comes from, allowed values, this computer's CPU, memory and suggested cap, and the exact commands to change them.

## 2026-11-23 (standards) — standards gate before approval

- **Automatic checks:** when a repo has `.engineering/`, the gate runs its kit, PR, secret, quality-ratchet and changed-file format checks, from the main checkout's copy.
- **Rule-by-rule review:** the code and security reviewers check the changed code against `.engineering/STANDARDS.md` and write a `## Standards` section citing rule IDs.
- **Approver:** cannot approve with a failed standards check, a missing Standards section or an open MUST violation.
- **Merge:** the standards checks run again after the final re-sync.
- Repos without `.engineering/` behave as before.

## 2026-11-23 (newest) — ticket records as long-term memory

- **New record name:** `docs/tickets/<KEY>-<n>-<slug>.md`. Existing records keep their names and are still found.
- **Links at the top:** ticket, every PR, related tickets, feature guide and other references.
- **New sections:** Summary for future agents, What changed, Future work and Notes for future agents. Decisions now record why.
- **Agents read past records:** before designing, `/implement-ticket` looks up related records and the feature guide, and raises a conflict instead of silently reversing a decision.
- **Close-out is required before `ready-to-merge`,** so records no longer stay at `In progress` after an owner merge.

## 2026-11-23 (latest) — ticket scope prompt

- **Plain `/deliver <KEY>` now asks what to run** instead of starting the whole backlog: **My assigned tickets (Recommended)**, **Specific tickets** (paste the numbers), or **All available tickets**, which shows a warning and needs a second confirmation.
- **All available** means your tickets plus unassigned ones. Each unassigned ticket is assigned to you just before it starts. Teammates' tickets are skipped.
- **Specific tickets** can include a teammate's ticket only after an explicit takeover confirmation, and never one they are already building.
- `--mine` and `--only` still skip the question. `/factory`, status, board and pause commands are unaffected.

## 2026-11-23 (later) — `/deliver --mine`

- **`/loop /deliver <KEY> --mine`**: runs every ticket assigned to the person running it, with no ticket list. Each cycle re-reads assignments and blockers, so new and newly unblocked tickets start automatically. The loop keeps watching while work is blocked and stops after 8 idle hours.
- **Safe for several developers**: a `--mine` run only adopts, closes out and re-syncs the operator's own tickets and PRs, and re-checks the assignee immediately before starting a ticket.

## 2026-11-23 — project settings and setup guide

- **`/delivery-config`**: show or change one project's settings in `docs/workflow/delivery.config.json`: tickets at once, review rounds, loop pacing, worker idle release, auto-accept, merge path, merge strategy, worker push, device lane, engine and disk warning. A running loop applies changes on its next cycle.
- **Auto-accept recommended options**, default **off**. When on, only routine decisions on non-high-risk tickets are accepted; escalations, sensitive areas, scope, deferrals, plans and merges still go to the owner, and every auto-accepted answer is logged.
- **Merge path**: owner merges by default, and an undecided project no longer blocks the first run. Agent merges need both `mergePath=agent` and `gh pr merge` allowed in permissions; with only one, the owner still merges.
- **`docs/GUIDE.md`**: setting up a new project, daily commands and every setting.

## 2026-11-12 — change report, owner questions, Windows paths

- **Change report** (`board/report.py`, `board.py report --repo . --ticket <KEY> [--open]`): one HTML page per ticket, never committed. Every changed file grouped by area (frontend, backend & logic, database, tests, config, docs) with its functions marked added / updated / removed, what changed, and links to the file on GitHub and locally (no diffs); the acceptance criteria; every round's verdicts; the device tester's step-by-step screenshots per criterion, labelled failed or passed run, with the failing step outlined. The explainer writes `changes.json` (schema `delivery-changes/1`) and builds it after APPROVE; merge-ticket refreshes the archived copy in `.delivery/reports/<KEY>/` before cleanup. The board links it from the ticket drawer (`/report/<KEY>/`). Screenshot names gain a caption and a `-FAIL` mark. New reference `skills/deliver/references/change-report.md`.
- **Owner questions: one decision per question** (`skills/implement-ticket/references/owner-questions.md`). Workers write every question to `job.json.questions` (`<KEY>-q<n>`) before asking; the orchestrator relays every open question each cycle as its own entry (no cap, never bundled) and answers a worker once all its questions are answered. The board shows a worker's questions straight from `job.json` ("from worker") and accepts answers to them.
- **Windows**: every board command uses `"$HOME/.claude/delivery-board/board.py"` instead of `~/...`, which PowerShell does not expand (the orchestrator silently skipped the board inbox). A failed inbox read is now reported, never skipped.

## 2026-11-11 (later) — pause and resume

- **`/deliver <KEY> --pause [keys] [--now]`** and **`--resume [keys]`**, **`/factory pause|resume`**: pause everything or single tickets without losing work. Soft (default): nothing new starts, nothing merges, each worker finishes its current step, commits, pushes and waits (`[KEY] PAUSE`); `--now` sends `STOP`. The loop ends once everything is parked; resume sends `[KEY] CONTINUE` from each ticket's recorded stage (re-sync first after a long pause). The tracker is not changed. New reference `skills/deliver/references/pause.md`; `orchestrator.json.pause`, ticket stage `paused` with `pausedFrom`.
- **`board.py pause|resume`**: pause or resume from any terminal (an inbox request applied on the next cycle). The board shows a ⏸ paused pill and pending requests.

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
