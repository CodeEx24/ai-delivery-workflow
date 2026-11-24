# AI delivery workflow

A reusable process for taking a product from idea to merged, verified code with Claude Code, a project management (PM) tool and parallel git worktrees. It applies to any project and stack; stack items appear only as examples. The post-build loop is modelled on the "Software Factory for Claude Code" (github.com/zazencodes/zazencodes-season-3).

**How to use this file:** keep it as one Markdown file (for example `~/.claude/workflows/ai-delivery-workflow.md`) and import it from each project's `CLAUDE.md` with a line `@~/.claude/workflows/ai-delivery-workflow.md`, so every session follows it without being prompted. Project-specific values (commands, ports, ticket key, PM tool) live in the project's own `CLAUDE.md`, `docs/workflow/README.md` and `docs/setup/`, never in this file.

Legend: **(human)** owner decision or action · **(agent)** Claude Code skill or subagent · **(script)** deterministic command.

## Quick start (existing projects)

- **`/deliver <PROJECT-KEY>`** — manual-only (you type it; it never starts from a phrase). Runs the whole flow for a project that already has tickets. It checks the project setup first (bootstrap), plans waves with `/plan-waves` if there are none (you approve the plan), then keeps building, testing, reviewing and merging ready tickets within the two-wave window. Recommended form: **`/loop /deliver <PROJECT-KEY>`**, so it keeps going without you prompting it.
  - `--watcher` — runs the loop in its own Orca chat, so this chat stays free.
  - `--status` — read-only: what is running, waiting and ready. Changes nothing.
  - `--dry-run` — shows what one cycle would start, advance, merge and ask. Writes nothing.
  - `--cap N` — allows fewer tickets in flight at once for this run. Going above your effective cap (your machine setting, else the project's, default 2) needs your yes. To set your own limit: `/delivery-config --me cap=N`.
- **`/deliver <path-to-file-or-doc>`** — the same, but it starts from a document that lists tasks (spec, notes, backlog, PRD, meeting notes; a local `.md` / `.txt` / `.pdf` / `.docx`, or a URL / Google Doc / Notion page when a connector exists). It turns each task into a ticket (title, type, testable AC, dependencies, size) and shows you the list. After you approve it, it creates the tickets in the project's PM tool, which gives them real IDs. With no PM tool connected, the default is GitHub Issues when the repo is on GitHub and `gh` works; otherwise (offline or private experiments) local IDs `T-001…` in `docs/tickets/backlog.md`. Then it plans waves and runs the flow as above.
  - `--only <KEY>-<n>[,…]` — start only these tickets (one-ticket runs).
  - `--board` — open the live delivery board (below).
- **`/factory run`** — the same engine fed by GitHub issues labeled `factory` instead of a whole backlog. Issue labels track each step (`factory:building`, `factory:needs-info`, `needs-human`, `ready-to-merge`); `/factory <anything>` answers questions, gives feedback, rejects, or files a new labeled issue. Recommended form: **`/loop /factory run`**. Works without Orca (workers become background subagents).
- **Live delivery board** — `python "$HOME/.claude/delivery-board/board.py" serve --repo . --open` (the orchestrator starts it for you). One page for the whole delivery: the wave plan, every ticket's step, round verdicts, acceptance criteria, blockers, your open questions (answerable from the page) and an activity feed, refreshed every 2 s. Try it with `--demo`.
- **New project?** Start with `/delivery-blueprint`, then `/deliver`.
- **Which commands for my situation?** See `PLAYBOOK.md` in the kit's `workflow/` folder: Jira backlog, one ticket only, GitHub issues, new project.

---

## Base branch

Every project has a **base branch**: tickets start from it and PRs target it. Wherever this workflow says `main` or "default branch" about ticket work, it means the base branch. The **release branch** is production.

```text
python "$HOME/.claude/skills/delivery-config/config.py" --repo . branch [--base <branch>] --json
```

| Result | Do |
|---|---|
| `base` is set | Use it |
| `needsChoice` | Ask once with AskUserQuestion, recommended option first, then save it with `/delivery-config baseBranch=<branch>` |
| `requiresConfirmation` | The run targets production while the repo has an integration branch. Warn, and get an explicit yes |

A repo with no `staging` is normal: the AI offers its default branch, usually `main`, and asks once. An unattended `/loop` never picks a branch by itself: it stops and asks. The resolver also reads `.engineering/config.json`, so a repo that already declares its branches is never asked. `--base <branch>` overrides the saved value for one run. Confirm every new PR's `baseRefName` matches.

## 1. The workflow at a glance

```
 0 /delivery-blueprint ── PRD, CLAUDE.md, epics + tickets in the PM tool, docs layout
 1 Tooling ───────────── aitmpl.com / /find-skills: skills, agents, commands,
                         settings, hooks, MCPs, mods, plugins
 1b Project setup ────── checks script, agent files, permissions + merge path,
                         hook tuning, local backend recipe, dev build registry,
                         needs-human + ready-to-merge views, cost tracking
 2 /plan-waves ───────── dependency graph → waves in the PM tool (labels + links)
 3 /wave-status ──────── open waves, PM tool ⇄ GitHub cross-check, ready tickets
 4 /implement-ticket ─── one worktree per ready ticket, run in parallel
     │                   + docs/actions guide for every human setup step
     ▼
 5 Review + test loop ─ gate (script)
     │                  → testers: functional + device (tests / E2E flow committed,
     │                    screenshots → PM tool)
     │                  → reviewers in parallel on the final commit:
     │                    code · security · UI · UX (UI / UX read the screenshots)
     │  CHANGES ◄──────── any CHANGES: builder fixes, max 2 more rounds
     ▼ all PASS (a BLOCKED device check goes to the approver, not the builder)
 6 Approver ──────────── APPROVE → explainer (PR walkthrough + feature guide)
                         → /merge-ticket   ·   ESCALATE → needs-human
                         (waiting for the owner's merge → ready-to-merge)
 7 Close out ─────────── draft → ready, re-gate, merge, proof + cost on PR and
                         ticket, ticket Done, re-sync open PRs, delete worktree + branch

 Orchestrator (/loop) runs steps 3–7 continuously within a two-wave window,
 a concurrency cap and one shared device lane.
```

---

## 2. Stage by stage

### 0. Delivery blueprint — `/delivery-blueprint` (agent) + review (human)

Start every product here. It produces the artifacts everything else reads:

- Product brief / PRD, epics, features and user stories with **testable acceptance criteria**, story points and dependencies, created in the PM tool.
- `CLAUDE.md` and `AGENTS.md`: locked tech stack, folder structure, naming, project invariants, Definition of Ready / Done, commands — and the import line for this workflow file.
- The docs skeleton: the ticket record template (`docs/tickets/`, section 7), delivery rules (`docs/workflow/README.md` with risk tiers and gates, `REVIEW.md`), `docs/actions/` for owner steps, `docs/setup/` for environment recipes, `docs/features/` for feature guides.

Already have a project with a task document but no tickets? `/deliver <path-to-doc>` turns the document into tickets: in the PM tool; with none connected, in GitHub Issues when the repo is on GitHub and `gh` works, else in a local `docs/tickets/backlog.md` with IDs `T-001…`. You approve the list before anything is created (see the Quick start).

### 1. Install the tooling — choose (human) + `/find-skills` (agent)

Browse **aitmpl.com** (Claude Code templates) or ask `/find-skills` what exists for the stack. Install only what the project needs; every extra hook or MCP server costs context and attention.

| aitmpl.com category | What it is | What to pick for this workflow |
|---|---|---|
| **Skills** | Packaged instructions Claude loads for a kind of task | Workflow: `plan-waves`, `wave-status`, `implement-ticket`, `verify-ticket`, `merge-ticket`, a PR reviewer, worktree tooling. Stack: framework and platform best practices, security, QA. |
| **Agents** | Subagents with their own role, tools and model | The review and test roles in section 3, plus explorer and planner. |
| **Commands** | Slash commands that start a routine | Entry points: `/delivery-blueprint`, `/plan-waves`, `/implement-ticket`, a commit / PR command, a check runner, the orchestrator (`/deliver`). |
| **Settings** | `settings.json` presets (permissions, environment, model) | Allow-lists for routine commands, deny-lists for destructive ones, the merge permission chosen in 1b. |
| **Hooks** | Scripts the harness runs on events (before/after a tool, on stop) | Safety gates on edits and destructive commands, run-the-checks when the builder finishes, cost and scope notices, session summaries. |
| **MCPs** | Servers that connect Claude to outside tools | The PM tool (e.g. Jira, Linear), the backend / database, current library docs (e.g. Context7), a browser driver for UI checks and file uploads. |
| **Mods** | Changes to Claude Code's own interface | A status line with branch, ticket and cost; a panel for tickets in flight and `needs-human` items. Optional. |
| **Plugins** | Bundles of skills, agents, commands and hooks | A stack plugin (e.g. the framework's official skills) or a delivery plugin, instead of installing pieces one by one. |

### 1b. Project setup — once per project (agent, with owner approval)

Each item below is used by a later step; set them up before the first ticket.

| Item | What to create | Used by |
|---|---|---|
| **Checks script** | `scripts/workflow/checks` (`.sh` / `.ps1`): install with a frozen lockfile, lint, typecheck, tests, build, migration and database checks, ticket record check. Two modes: **`--report <path>`** (`-Report` in PowerShell) writes that file — first line `VERDICT: PASS` or `VERDICT: FAIL`, then the commands and the log tail; the gate passes `.delivery/jobs/<KEY>-<n>/round-N/checks.md`. **Without it** the script only prints the result and exit code (local mode: the builder, its hook and the pre-merge re-gate), so it never writes a round file. | Gate (step 5), builder hook, pre-merge re-gate |
| **Agent files** | `.claude/agents/` for reviewer-code, reviewer-security, reviewer-ui, reviewer-ux, tester-functional, tester-device, approver, explainer — checklists tailored to the stack, each writing one file. | Step 5, step 6 |
| **Feature guides** | `docs/features/` with one guide per feature area, created by the blueprint or by the first ticket that touches the area (template in section 8). | Explainer (step 6) |
| **Permissions and merge path** | Allow-list routine commands. **Default merge path: the owner approves by merging** (the agent prepares, labels the ticket `ready-to-merge`, the owner clicks). The agent merges only if the owner explicitly allows the merge command (e.g. `gh pr merge`) for agents and records "agent merges". Safety checks may otherwise block an agent from admin-merging even with chat approval. | Steps 4–7 |
| **Hook tuning** | Keep safety gates on destructive commands; exempt routine source and docs folders from fact-check prompts on first edit where the hook supports it. | Every step |
| **Local backend recipe** | `docs/setup/local-backend.md`: how to start a local backend with **port overrides** (defaults can clash with other projects), seed data, a **test account**, and where login codes land (a local mail catcher), so device checks never need anyone's real inbox. | Device tester |
| **Dev build registry** | `docs/setup/dev-builds.md`: the current development build id per native-dependency set and how to install it. A build missing a native module crashes at start. | Device tester |
| **Owner to-do list, generated** | Each `docs/actions/*.md` guide has front matter (`status`, `tickets`, `order`, `estimate`); a small script builds `docs/actions/README.md` from it. Never hand-edit a shared numbered list: it conflicts on almost every merge. | Step 4, orchestrator |
| **`needs-human` and `ready-to-merge` views** | Two labels (and saved filters) in the PM tool: `needs-human` for real escalations and owner actions, mirroring the open owner guides; `ready-to-merge` for approved PRs waiting for the owner's merge, so merges never mix with escalations. | Steps 6–7, orchestrator |
| **Cost tracking** | `scripts/workflow/cost <KEY>-<n>` (use this name and write it in `docs/workflow/README.md`): sums the ticket's subagent transcripts (model and token counts), prices them and prints the total, which goes into the PR summary and the ticket. | Step 7, orchestrator |
| **Concurrency cap and device lane** | In `docs/workflow/README.md`: how many tickets may be in flight — **2 by default** when nothing is written; 3 on a desktop-class machine if you write it down — and that only one ticket uses the simulator / device at a time. | Orchestrator |
| **Ticket type mapping** | In `docs/workflow/README.md`: how the PM tool's issue types map to section 5's types, e.g. **Jira "Task" → Chore**. Without it a "Task" is shown as `Task?` and flagged. | Steps 3–4 |
| **Context limits** | Smaller compaction windows for long-running sessions (orchestrator ~300k, ticket workers ~400k tokens, subagents 200k) and a `# Compact instructions` section in `CLAUDE.md`. A SessionStart (`compact`) hook that reprints the orchestrator state only if compactions turn out to lose state. Recommended by the `/deliver` bootstrap; settings are written only with the owner's yes. Details in section 4, "Context limits". | Orchestrator, ticket workers |

### 2. Plan the waves — `/plan-waves` (agent) + approve (human)

Reads every open ticket and its links, builds the dependency graph and orders the backlog into **waves**: foundations first (scaffold, auth, data model, anything gating money or trust), no wave depending on a later one, critical path marked. After the owner approves, it writes the plan to the PM tool as `wave-N` labels and "blocks / is blocked by" links, and to a wave plan document with batches and worktree conflict hotspots. On a project that uses the local backlog, the wave and the links go into each entry of `docs/tickets/backlog.md`. `/deliver` runs this step for you when no waves exist, including right after it has created tickets from a document. Re-run it when more than ~3 open tickets have no wave (`/wave-status` reports them). Approving the ticket list is not approving the waves: each one needs its own yes.

### 3. Pick the work — `/wave-status` (agent)

Ticket statuses are cross-checked against GitHub PRs (a merged PR on a ticket still "In Progress" is flagged and closed out first). A ticket is **ready** when it is To Do, nobody is on it, and every blocker is Done. Ready tickets start right away, within the **two-wave window** and the concurrency cap (section 4).

### 4. Implement in parallel — `/implement-ticket × N` (agent) in git worktrees, decide + accept (human)

Each ready ticket gets its own worktree and branch (e.g. `feat/<key>-<n>/<slug>`) and runs `/implement-ticket`:

1. Read the ticket, note its **type** (Feature, Bug, Chore, Spike; section 5), copy the acceptance criteria (AC) **word for word**, check blockers, set the risk tier, move the ticket to In Progress. The type decides how the next steps adapt.
2. Explore the code; ask the owner only the real design forks, each with a recommendation. **(human)**
3. Write the **ticket record** `docs/tickets/<KEY>-<n>-<slug>.md` (section 7): intent, AC, design, decisions. For medium/high risk the owner accepts it before code. The task-by-task plan goes in the working folder (`.delivery/jobs/<KEY>-<n>/plan.md`); it isn't needed after merge. **(human)**
4. Build task by task; independent parts go to helper agents with disjoint file ownership (no shared files, no git commands).
5. **Every human setup step becomes an owner guide** in `docs/actions/<name>.md` with front matter, then regenerate the to-do list: purpose, prerequisites, numbered steps, expected result, verify, checklist, if-it-fails; secret *names*, never values. Typical examples: create the database project, push a migration, set an API key, deploy a function, configure a third-party service, update a legal page.
6. Run the checks script in local mode (no `--report`; the builder hook does this automatically), commit, push, and open a **draft PR** whose description says what was built, the main files, decisions and how to test (this replaces a separate build note). Write the stage file (`job.json`, stage `built`) and hand off to step 5.

### 5. Review and test loop — gate (script), testers and reviewers (agents)

Step 4 *builds*, step 5 *judges*: **scripts decide whether it works, testers prove the behaviour, reviewers judge what neither can.** Detailed in section 3.

### 6. Approve, explain or escalate — approver + explainer (agents), escalations (human)

The approver reads every verdict and the AC table. The decision is posted as a PR comment.

- **APPROVE** → the **explainer** writes the PR walkthrough, adds inline guide comments on the key parts of the diff, and updates the feature guide (section 8). Then `/merge-ticket`.
- **ESCALATE** → the PR stays open with one specific question for the owner (also posted on the ticket), and the ticket gets the `needs-human` label. The approver always escalates on: an owner action, a check only a human can run or unblock (a device check the tester reported `BLOCKED`: a physical device, a missing dev build or test account, a paid service), a scope or AC change ("defer this criterion to a follow-up ticket?"), a security exception, deploy / infra / billing changes, and **migrations on live data**. A new dependency alone is not a reason (the security reviewer covers risky ones).
- **Deferrals need the owner's word and a follow-up ticket.** "Partial" is honest; a criterion moves elsewhere only by an explicit owner decision, recorded in the ticket record, the PR, the ticket and the follow-up ticket.

### 7. Merge and close out — `/merge-ticket` (agent), merge (human or agent, per the merge path)

1. Mark the draft PR ready (`gh pr ready`; only `/merge-ticket` does this), then re-sync the branch with the base branch and run the checks again (another ticket may have merged since).
2. Merge (squash), per the merge path chosen in 1b. On the default path (owner merges) the ticket gets `ready-to-merge` and the agent hands over the PR link; after the owner merges, `/merge-ticket` finishes the steps below.
3. Make sure the ticket record's link block has the ticket and every PR, then post the proof where section 7 says: AC results and step-by-step screenshots on the **ticket**; test and review results, CI and **cost of the ticket's agents** on the **PR**. Update the ticket record's "Outcome" section (deviations, known limitations, follow-ups).
4. Move the ticket to Done; note deferred checks on their follow-up ticket.
5. **Re-sync every other open PR** with the base branch, re-run their checks, push.
6. **Clean up:** delete the worktree (with its dependencies folder) and the local branch, prune worktree records, delete leftover downloads and local services started for the ticket.

---

## 3. The review and test loop

`/implement-ticket` covers intake, spec writing and building (with the owner's decisions), so the factory roles are used for the back half only, plus two testers. Each round runs the roles in a fixed order (below); the table lists them in that order. The state file schema, stage names and message names are defined once, in the `deliver` skill's `references/state-files.md`.

| Role | Does | Writes | Model |
|---|---|---|---|
| gate **(script)** | Runs `scripts/workflow/checks` from **the base branch's copy** | `round-N/checks.md` | none |
| tester-functional | Writes acceptance tests per AC, including edge cases (empty, deleted, offline, invalid input or links), runs them with the suite; edits and commits test files only | `round-N/test-functional.md` (AC → test → result) | Sonnet |
| tester-device | Runs the app locally, walks each AC like a user, step-by-step screenshots, records a replayable E2E flow, attaches the screenshots to the ticket | `round-N/test-device.md` (PASS / CHANGES / BLOCKED), `round-N/screenshots/` (→ ticket), E2E flow file (committed as a test) | Sonnet |
| reviewer-code | Correctness, scope, repo rules, weakened or skipped tests (the testers' new tests included) | `round-N/review-code.md` | Haiku / Sonnet |
| reviewer-security | Authorization, data access rules, secrets, injection, AI / prompt surfaces, data leaks | `round-N/review-security.md` | Opus |
| reviewer-ui | Design system, tokens, accessibility (labels, roles, touch targets), from the code and the round's screenshots | `round-N/review-ui.md` | Haiku / Sonnet |
| reviewer-ux | Judges the flow from the round's screenshots: clarity, empty and error states, copy | `round-N/review-ux.md` | Sonnet |
| approver | Reads all verdicts and the AC table; APPROVE or ESCALATE | `decision.md` (→ PR comment) | Opus |
| explainer | After APPROVE: explains the change for a reviewer who doesn't know the feature; updates the feature guide | `walkthrough.md` (→ PR description), inline PR comments, `docs/features/<area>.md` | Sonnet |

Everything lives in the **gitignored working folder** `.delivery/jobs/<KEY>-<n>/`: `plan.md`, `job.json` (the stage file), `round-N/checks.md`, `round-N/test-functional.md`, `round-N/test-device.md`, `round-N/review-*.md`, `round-N/screenshots/`, `decision.md`, `walkthrough.md`. It carries the loop and is deleted at cleanup; results are posted to the ticket and the PR (section 7).

### Round order

1. **Gate** (script) → `round-N/checks.md`. FAIL → back to the builder; nothing else runs.
2. **Testers**: tester-functional and tester-device (when routed and the device lane is free; otherwise it runs as soon as the lane frees up). Both may commit to the branch (acceptance tests, the E2E flow); each runs `git pull --rebase`, then `git push`.
3. **Reviewers** in parallel — code, security, UI, UX as routed — on the **final commit of the round** (the testers' commits included). UI and UX read that round's screenshots and `test-device.md`. Reviewers run whatever the testers reported, so one fix round addresses everything.
4. **Approver**, once every routed role has written and none asked for CHANGES.
5. **Explainer**, on APPROVE only.

### Rules that make the loop reliable

- **Gate before testing, and again before merge.** A failing gate goes straight back to the builder with the log; no tester or reviewer is spawned.
- **The gate runs the base branch's copy of the checks script**, so a branch can't weaken the checks it is judged by. Tests aren't protected (features update them), but the code reviewer fails any test that was weakened or skipped.
- **Verdict files.** Every review and test report starts with `VERDICT: PASS` or `VERDICT: CHANGES` (tester-device may also write `VERDICT: BLOCKED`); `checks.md` starts with `VERDICT: PASS` or `VERDICT: FAIL`; `decision.md` starts with `APPROVE` or `ESCALATE`. A round ends only when every routed role has written. Any CHANGES resumes the same builder, at most twice, then escalate.
- **BLOCKED is not a code failure.** tester-device writes `VERDICT: BLOCKED` with a line `Blocked: <reason>` when a criterion can't be checked for reasons the builder can't fix (missing dev build, missing test account or local backend, a physical device needed). It never resumes the builder. The approver ESCALATEs with one owner question — provide what is missing (the device check then re-runs) or defer the criterion — unless the owner already deferred it in the ticket record.
- **Testers never fix code.** A failing test goes back to the builder; testers only add or edit tests and E2E flows.
- **State is files, so work resumes.** Each ticket's working folder holds every in-flight artifact, so a crashed or compacted session picks up from the last stage.
- **Agents reply with one line**; the detail lives in their file, so the orchestrator's context stays small with several tickets in flight.

### Risk routing (who runs on which ticket)

| Risk | gate | functional tester | code | security | ui / ux | device tester |
|---|---|---|---|---|---|---|
| Low (small, no risky area) | always | always | Haiku | – | if UI changed | if testable in the app |
| Medium | always | always | Sonnet | if security surface | if UI changed | if testable in the app |
| High (auth, data access rules, AI / prompt surfaces, quotas, sync, billing, account deletion / export, migrations on live data) | always + database tests + rollback check | always | Sonnet | Opus, always | if UI changed | if testable in the app |

### Device proof, step by step (tester-device)

1. Take the device lane (one ticket at a time). Install the build from the dev build registry and start the app the way the repo documents it. If the feature needs login or backend data, follow the local backend recipe and sign in as the test account.
2. For each AC, perform it like a user and capture every step: `<KEY>-<n>-AC1-step-01.png`, `-step-02.png`…, saved in `round-N/screenshots/` in the working folder (not committed). A criterion that can't be reached for a reason the builder can't fix is BLOCKED, with the reason.
3. Record the same path as a replayable E2E flow (e.g. Maestro, Playwright) so it becomes a regression test — **one flow per ticket** covering its ACs, split per AC only when the ACs are independent flows (or the E2E folder's convention says so); commit it on the ticket branch (`git pull --rebase`, then `git push`).
4. Build the labeled evidence PDF (`evidence-pack` skill) and deliver it to the project's tracker: native attachment, file in a comment, browser, then PR. Then post a comment: each AC with its numbered steps and the matching screenshot names. The PR links to that ticket comment instead of duplicating the images.
5. Release the device lane: stop the dev server, simulator and any local backend started for this ticket.

---

## 4. The orchestrator: continuous delivery loop

The main session runs as a loop (`/loop` or a `/deliver` command, waking itself on a schedule) and keeps the pipeline moving without being asked. Each cycle:

1. **Read the board:** wave status for the open waves, cross-checked with GitHub PRs.
2. **Fill capacity** up to the concurrency cap with ready tickets from the two-wave window.
3. **Advance every running ticket** to its next stage: build → gate → testers → reviewers → approver → explainer → merge. The device lane is handed out one ticket at a time.
4. **Surface what needs the owner:** escalations and owner-action steps get the `needs-human` label, approved PRs waiting for the owner's merge get `ready-to-merge`, each with a line in the run summary and the matching `docs/actions` guide linked. A worker waiting on the owner for ~1 hour is released (its files stay) and resumed when the answer arrives. A ticket's working folder with no change for 2 days and no live worker is reported as stalled.
5. **Close out every merge** (step 7): proof and cost posted, other open PRs re-synced, worktree and branch deleted, leftovers removed.
6. **Keep the live board current:** one activity line per action, the backlog snapshot for the Waves strip, and the answers the owner typed on the board applied like chat answers. The board reads only the state files; ticket workers keep their `job.json` (with task progress) current from the first minute, so a silent worker is visible as "quiet 40m".
6. **Stop** only when nothing in the window is ready and everything left waits on the owner, and send one summary (tickets merged, cost per ticket, what needs the owner).

### Two-wave window

| Situation | What the orchestrator may start |
|---|---|
| Lowest open wave N has 3 or more open tickets | Ready tickets from wave N only |
| Wave N has only 1–2 open tickets left | Ready tickets from wave N, then ready tickets from wave N+1 |
| Wave N still has any open ticket | **Never** wave N+2 or later |
| Wave N is done | The window moves up: N+1 becomes the base, and N+2 may open once N+1 is down to 1–2 open tickets |
| A **critical bug** is ready (data loss, security, app unusable) | Start it next, ahead of the window (section 5) |

"Ready" always means: To Do, nobody on it, and every "is blocked by" link Done. A ticket with an open blocker never starts, whatever wave it is in.

### Context limits

Long-running sessions fill their context and compact. Plan for compaction rather than fight it: **state lives in files** (`.delivery/orchestrator.json`, each ticket's `.delivery/jobs/<KEY>-<n>/`), and every cycle re-reads it instead of trusting conversation memory.

| Session | Window | Keep after compaction |
|---|---|---|
| Orchestrator (`/loop /deliver`, or the watcher) | `CLAUDE_CODE_AUTO_COMPACT_WINDOW=300000` or launch with `--autocompact 300k`; the watcher is launched with it | project key, cap, running tickets with stage and worker ids, device-lane holder, pending owner questions, last cycle summary — everything else is in `.delivery/` |
| Ticket worker (Orca, `/implement-ticket`) | ~400k, through the launch env or flag if Orca can pass it, otherwise as a setting | ticket key, stage, round, open CHANGES items, pending owner question — the plan and round reports are in `.delivery/jobs/<KEY>-<n>/` |
| Review / test subagents | fresh context per run; `autoCompactWindow: 200000` in the agent frontmatter (Claude Code v2.1.296 or later), otherwise defaults | — |

Supported controls: `autoCompactWindow` in `settings.json` (100000–1000000 tokens), the `--autocompact <size>` launch flag, the `CLAUDE_CODE_AUTO_COMPACT_WINDOW` env var (overrides both), `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` (1–100, can only lower the trigger, applies to main sessions and subagents), and `autoCompactEnabled`. What survives is set by a `# Compact instructions` section in the project's `CLAUDE.md` (recommended), or by a PreCompact hook whose output (≤ 10,000 characters) becomes the summary instructions. A SessionStart hook with matcher `compact` runs after compaction and can print a short state summary from `.delivery/orchestrator.json` — add it only if compactions turn out to lose state.

Not possible: a `/loop` iteration, a skill or a hook cannot run `/compact` or `/clear` (they arrive as plain text), and no hook event reports token usage (only the status line JSON has `context_window.used_percentage`). The `/deliver` bootstrap recommends the windows and the compact instructions and **writes none of them without the owner's yes**.

Subagents can start their own subagents (by default up to 3 levels below the main conversation, `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`; at most 20 at once, `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`). Ticket builders are still Orca workers: only a full session can ask the owner a question, and each ticket needs its own worktree session. Respect the limits anyway: a worker runs at most six review and test subagents at once (two testers, then four reviewers), and those subagents should not start nested helpers of their own.

---

## 5. Ticket types

Every ticket has one type, set in the PM tool as a `type:<name>` label (or the issue type when it maps directly; e.g. Jira "Task" → Chore, written in `docs/workflow/README.md`). `/implement-ticket` reads it at intake and adapts; the rest of the pipeline (gate, routed testers and reviewers, approver, merge, cleanup) is the same for all types.

| | **Feature** | **Bug** | **Chore** | **Spike** |
|---|---|---|---|---|
| Use for | New or changed behaviour from a user story | Something behaves wrongly against what was specified or expected | Maintenance with no behaviour change: refactor, dependency upgrade, tooling, CI, docs, cleanup | An open question: research, prototype, choose between options |
| Ticket must contain | User story, testable AC, dependencies, story points | Steps to reproduce, expected vs actual, environment, severity; AC "Given [steps], then [correct result]" + "a regression test covers it" | What changes and why, and "no behaviour change" as an AC (all existing tests stay green) | The question, the options, a time box, and what "done" produces |
| Branch / commit | `feat/…` · `feat(scope): …` | `fix/…` · `fix(scope): …` | `chore/` `refactor/` `docs/` `build/` `ci/` · matching commit type | `spike/…` (never merged as product code; the record lands as a docs-only change) |
| How step 4 adapts | Full flow: questions → ticket record → build | **Reproduce first** with a failing test, find the root cause and record it in the ticket record and the PR, make the smallest fix that addresses the cause; questions only if the expected behaviour is unclear | Short ticket record; prove "no behaviour change" (same tests pass, no snapshot or contract changes unless intended) | Investigate within the time box; write the findings and recommendation into the ticket record; prototypes stay on the branch |
| Tests and reviews | Full routing by risk (section 3) | Functional tester checks the regression test and nearby edge cases; device tester takes **before and after** screenshots if visible in the app; routing by risk | Gate + code reviewer; security reviewer if it touches risky areas (e.g. auth or dependency upgrades with security impact) | Code reviewer reads the findings, not product code; no device test |
| Ends with | Merge + proof on the ticket | Merge + proof on the ticket (before / after) | Merge | The ticket record always lands as a **docs-only** PR (prototypes stay on the spike branch); the owner decides on the recommendation; new Feature / Bug / Chore tickets are created and placed in waves (`/plan-waves`) |

**Notes**

- **Severity sets urgency for bugs.** A critical bug (data loss, security, app unusable) may jump the two-wave window: the orchestrator starts it next, ahead of other ready tickets. Only a tracker-marked one counts: label it `severity:critical` (Highest / Blocker priority also counts). Everything else waits its turn like any ticket.
- **A bug found in an open PR** is fixed on that PR's branch in its review loop, not as a new ticket.
- **A bug from QA (`qa:found`)** carries an Engineering handoff and its evidence on the tracker. The builder reproduces it before changing code (or stops with `cannot reproduce` and evidence) and adds a regression test. The device tester reruns the source ticket's full scenario set (`~/.claude/skills/qa/references/retest.md`), and the approver requires a passing result on the final product code.
- **Fixing QA issues:** `/fix-ticket <KEY-n>` reads the `🐞 Issues Found` comment and bugs, then checks the live PR. An open PR is fixed on its branch. Merged work gets a new `fix/<key>-<n>/<slug>` branch, worktree and PR linked to the ticket.
- **Unknown cause?** Investigate first with a debugging skill (or a short Spike), then file the Bug with what was found.
- **Risk is separate from type.** A small bug in authentication is still high risk and gets the security reviewer.

## 6. Checks script template

```
<install with a frozen lockfile>
<lint> && <typecheck>
<unit + integration tests>
<build>
<local migration check>                 # if the app has a local database
<database tests> + <rollback check>     # if the change touches the backend schema
<ticket record check>                   # record exists: links block (ticket + PRs), AC, decisions
<standards gate>                        # if .engineering/ exists: skills/deliver/references/standards-gate.md
# CI on the PR runs the same, plus any bundle / secret scans
```

## 7. Where things go

The repo keeps only what a future developer or agent needs to understand **why the code is the way it is**. Evidence that a ticket worked goes to the tools people already look at: the ticket for the owner, the PR for the technical trail.

| What | Where | Why there |
|---|---|---|
| **Ticket record**: intent, AC (verbatim), design, decisions (who / when), deviations, known limitations, follow-ups; for spikes the findings and recommendation | `docs/tickets/<KEY>-<n>-<slug>.md` (one file, committed) | Long-lived context next to the code; read by future tickets and agents |
| Evidence PDFs and the Evidence Index, AC results table, owner decisions and deferrals, escalation questions, final status | **The ticket** in the PM tool (attachments + comments) | What the owner reads and audits |
| What was built and how to test (draft PR description), gate results, test and review verdicts (one summary comment per round), approver decision, CI, cost of the ticket's agents | **The PR** on GitHub | The technical trail, kept with the diff |
| Acceptance tests and E2E flows written by the testers | The codebase (test folders, e.g. `.maestro/`, `e2e/`) | They are code: they run in CI and guard against regressions |
| Task plan, stage file, `round-N/` reports, `decision.md`, screenshots before upload | `.delivery/jobs/<KEY>-<n>/` (gitignored), deleted at cleanup | Working state that carries the loop and lets a crashed session resume |
| Owner setup steps | `docs/actions/<name>.md` (committed, list generated) | Instructions the owner follows, often outside a single ticket |
| **PR walkthrough**: what the change does, how to try it, data flow, key functions, review order | **The PR description** on GitHub (drafted in the working folder, posted with `gh pr edit --body-file`) | It explains one change at one point in time, next to the diff; stays with the PR after merge |
| **Feature guide**: how a feature area works today | `docs/features/<area>.md` (committed, updated by every ticket that touches the area) | The current map of the code for future developers and agents |

**One file by default, a folder only when it earns it.** A single record means one read gives a future developer or agent the intent, criteria, design, decisions and outcome together, with nothing repeated across files that can drift apart. Use a folder `docs/tickets/<KEY>-<n>-<slug>/` (with `README.md` as the record) only for large, high-risk tickets whose record would pass roughly 300 lines or that have separate artifacts, such as a data contract, a migration plan, a security analysis or diagrams (`data-model.md`, `migration.md`, `security.md`…).

**Links are mandatory.** Every record starts with a link block: the ticket in the PM tool, **every PR** for the ticket (including follow-up fix PRs), and related tickets (blockers, follow-ups, deferrals). The PR link is added when the draft PR opens and checked again at merge; the ticket record check fails if the ticket link or the PR link is missing once a PR exists.

**Ticket record template**

```
# <KEY>-<n> — <title>

Ticket: <PM tool link>
PRs: <PR link> (main) · <PR link> (follow-up fix)
Related: blocked by <KEY>-<n> · follow-up <KEY>-<n> · deferred to <KEY>-<n>
Feature guide: docs/features/<area>.md
References: designs, specs, docs, ADRs, earlier ticket records
Type: Feature | Bug | Chore | Spike · Risk: Low | Medium | High · Status: In progress | Merged

## Summary for future agents   what exists now, and the one thing to know (filled at merge)
## Intent (spec)               what problem, for whom, desired outcome
## Acceptance criteria         copied verbatim from the ticket
## Design                      approach, data and API changes, files that matter
## Decisions                   | decision | options | choice | why | who / when |
## What changed                behaviour, key files, data, APIs, config (filled at merge)
## Outcome                     deviations and deferred criteria (filled at merge)
## Future work                 limitations, follow-ups, options rejected for now (filled at merge)
## Notes for future agents     gotchas, what not to undo and why, what to read first
```

**Before designing a ticket, read the records for related work** (`docs/tickets/`, by linked ticket, feature area, file path and keyword) and the feature guide. Follow earlier decisions, or raise a conflict as an owner question. The current code wins where an old record disagrees with it.

---

## 8. Explaining the change: PR walkthrough and feature guides

Reviewers are faster with a map: what changed, where the data comes from, which files to read first. Two documents provide it, for two different readers. Neither repeats the ticket record, which keeps the *why*.

| | Answers | Where | Lifetime |
|---|---|---|---|
| Ticket record | Why was it built this way? (decisions, AC) | `docs/tickets/` | Frozen at merge |
| **PR walkthrough** | What does this change do, and how do I review it? | PR description | Lives on the PR |
| **Feature guide** | How does this part of the app work today? | `docs/features/<area>.md` | Updated by every later ticket |

**When:** the explainer runs only after every check, tester and reviewer has passed and the approver said APPROVE, so it describes the final code. It writes plain language for a developer who has never seen the feature.

**PR walkthrough template** (posted as the PR description, below "What was built / How to test")

```
## What this PR does            plain language, 3–5 bullets, no jargon
## Try it                       numbered steps + link to the screenshots on the ticket
## What changed for the user    screens, pages, buttons, messages added or changed
## How it works                 Mermaid diagram of the data flow, e.g.
                                screen → hook → repository → local DB → sync → server
## Key functions                | function | file | what it does | called by |
## Data and API changes         tables, columns, migrations, endpoints, access rules
## How <the tricky part> works  e.g. "How filters work": short explanation + example
## Review in this order         1. schema  2. data layer  3. state / hooks  4. screens  5. tests
## Where to look closely        risky spots (security, sync, migrations) and why
## What's tested where          | acceptance criterion | test name | file |
## Not in this PR               out of scope, known limits, follow-up tickets
```

**Inline guide comments:** a few short PR review comments on the key hunks ("the filter is applied here", "this guard prevents duplicate names"), so the reviewer is guided through the diff itself. Only where it helps; not on every file.

**Feature guide template** (`docs/features/<area>.md`)

```
# <Feature area>
Tickets: <KEY>-<n> (created) · <KEY>-<n> (added X) …

## What it does             for the user, in plain language
## Screens                  where it appears, what each control does
## Data model               tables / collections and how they relate
## Data flow                Mermaid diagram: UI → state → data layer → storage → server
## Main functions and files | function / component | file | role |
## Rules and edge cases     validation, limits, permissions, offline behaviour
## How to extend it         where to add a new field, filter, screen
```

**Optional for large PRs:** a code tour (`.tours/<KEY>-<n>.tour`, e.g. with a code-tour skill) that steps a reviewer through the changed files in order inside the editor.
