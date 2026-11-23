# Subagent engine (no Orca)

When Orca is not running (or with `--engine subagents`), the orchestrator runs ticket workers as
**background subagents** of its own session instead of Orca worktree sessions. Same brief, same
stages, same job folders, same board; only the transport changes. `/factory` uses it by default
without Orca; `/deliver --engine subagents` uses it the same way.

**Trade-offs to state in the setup table:** workers live only as long as this orchestrator
session (closing the chat stops them; `--watcher` is not available); subagents cannot ask the
owner directly, so questions take one extra hop; nested depth and concurrency limits apply
(`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`, default 3; `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`,
default 20).

## Topology

```
orchestrator session (main checkout)
├─ worker-GH-12   background subagent, builds in ../<repo>.worktrees/GH-12   (implement-ticket)
├─ worker-GH-15   background subagent, builds in ../<repo>.worktrees/GH-15
├─ tester-functional / tester-device / reviewer-* / approver / explainer
│                 spawned by the ORCHESTRATOR per stage (depth 1), not by the worker
└─ gate           main's checks script, run_in_background, as in deliver
```

Keeping testers and reviewers at depth 1 (spawned by the orchestrator) avoids deep nesting and
lets the orchestrator run each round's reviewers in one message, in parallel. The agents already
take "job folder + round" as input.

## Worktrees

```bash
git fetch origin
git worktree add ../<repo>.worktrees/GH-12 -b feat/gh-012/<slug> origin/<default-branch>
```

A sibling folder keeps the main checkout's tools (test runners, linters, file watchers) from
scanning other branches. Record `worktreePath` and `branch` in `orchestrator.json`. Run the
project's setup (install) in the worktree before the worker starts, as the brief says.
merge-ticket's cleanup removes it (`git worktree remove`), and the board finds it through
`git worktree list`.

## Starting a worker

Agent tool call (load deferred tools with ToolSearch if needed):

- `subagent_type`: `general-purpose` (it needs every tool: edit, shell, git, gh, skills)
- `run_in_background`: true
- `description`: `GH-12 worker`
- `prompt`: the filled brief from the deliver skill's `references/worker-brief.md`, with these
  replacements in its header:

```markdown
You are a background subagent worker (not an Orca worker) started by the orchestrator.
Your checkout is {{WORKTREE_PATH}}: cd there first; never edit the main checkout.
- You cannot ask the owner anything and have no Orca. When a question needs the owner (design
  fork, record acceptance, scope outside owned paths): follow
  `~/.claude/skills/implement-ticket/references/owner-questions.md`:
  one entry per decision in job.json `questions` (`{ "id": "<KEY>-q<n>", "kind": "...", "q": "...",
  "options": ["A - ...", "B - ..."], "recommendation": "A - because ..." }`), never several forks
  in one entry; set `stage: "awaiting_owner"`, and end your turn with the one-line report.
- "worker_done" means: end your turn with one line `REPORT <KEY> <stage> r<N> — <summary>`.
  Everything else goes in job.json and your files.
- Keep job.json `progress` current (phase, task i/n) so the owner's board shows where you are.
- Never spawn testers, reviewers, the approver or the explainer yourself: the orchestrator does.
  Your later instructions (FIX, RESUME, STOP) arrive as messages to you.
```

Store the returned agent id in `orchestrator.json.tickets[KEY].agentId`. The completion
notification wakes the orchestrator (no polling), exactly like Orca mail.

## Mapping Orca operations

| Deliver says (Orca) | Subagent engine |
|---|---|
| `worker-start` with the brief | Agent tool, background, prompt = brief (above) |
| `send --to dispatch:<id>` `[KEY] FIX r<N>` / `RESUME` / `RESYNC` / `STOP` / `OWNER NOTE` | `SendMessage` to the worker's agent id with the same body |
| `[KEY] TEST r<N>`, `DEVICE`, `REVIEW r<N>`, `APPROVE` | The orchestrator spawns those agents itself (background, one message per stage so they run in parallel), each with the job folder, round and worktree path. After each finishes, read its file's first line and update `orchestrator.json`. The worker copies verdicts into `job.json` on its next instruction; until then the board reads the round files directly. |
| `worker_done` report | The background completion notification + the worker's one-line `REPORT` |
| `ask` (owner question) | `job.json.questions` + stage `awaiting_owner` → the orchestrator records `ownerQuestions` and relays them in the batch; the answer goes back with `SendMessage` |
| `orchestration check` (inbox) | Not needed: completions arrive as notifications. Still drain the board inbox. |
| `worker-show` / `worker-read` | Read the worker's `job.json`, its job folder and `git -C <worktree> log` |
| `worker-release` after ~1 h on the owner | Nothing to release: a finished subagent costs nothing while idle. Resume it with `SendMessage`. |

## Resume after the orchestrator session ended

Background subagents die with their session. On the next `/factory run` (or `/deliver`):

1. For each ticket in an active stage whose agent no longer answers, read its `job.json`,
   `plan.md`, branch and `git log` in its worktree.
2. Start a **fresh** worker with the brief plus a "Resume" section: the stage it reached, the
   tasks already committed (from the plan's ticked boxes and the log), and what to do next.
   Tell it to verify the branch state before writing anything, so nothing is built twice.
3. Agents of an unfinished round are re-spawned only for files that are missing.
