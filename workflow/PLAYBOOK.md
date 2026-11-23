# Playbook — which commands to run, scenario by scenario

The workflow file (`ai-delivery-workflow.md`) explains *why*; this page is *what to type*. Every
scenario ends the same way: tickets built in their own worktrees, gate → testers → reviewers →
approver → explainer, merged one at a time, and a live board showing all of it.

```
/delivery-blueprint ──► /plan-waves ──► /deliver <KEY>  (or /factory run for GitHub issues)
   spec → tickets        waves, you       orchestrator: /wave-status → /implement-ticket ×N
   CLAUDE.md, docs       approve          → gate → testers → reviewers → approver → /merge-ticket
                                ▲                         │
                                └──── live board ◄────────┘  http://127.0.0.1:8765
```

**The board** is always the same command. The orchestrator starts it for you; you can also run it
yourself:

```bash
python "$HOME/.claude/delivery-board/board.py" serve --repo . --open      # in the project's main checkout
python "$HOME/.claude/delivery-board/board.py" serve --demo --open        # sample data, to see what it looks like
```

On the board: **Needs you** (questions with answer buttons, escalations, PRs ready to merge,
plan waiting for approval) · **Waves** (each wave, each ticket's colour) · **Pipeline** (one card
per ticket, by step, with round verdict chips and task progress) · **Activity**. Click any ticket
for its step tracker, blockers, acceptance criteria, every agent's report and screenshots, and a
feedback box. Answers typed on the board are applied on the orchestrator's next cycle; typing
the same answer in the chat applies it at once.

---

## Scenario A — Jira backlog already exists (project key `ABC`)

You have tickets in Jira. Waves may or may not exist yet.

**One-time setup per project** (skip what is done):

```text
1. In CLAUDE.md add:        @~/.claude/workflows/ai-delivery-workflow.md
                            + the "# Compact instructions" section (settings/claude-md-snippet.md)
2. Create docs/workflow/README.md from settings/docs-workflow-README.template.md
   (cap, merge path, Jira "Task" → Chore mapping, checks script name)
3. Add .delivery/ to .gitignore
4. Make sure the Atlassian MCP is connected and `gh auth status` is OK; start Orca
```

**Run it:**

| Step | You type | What happens | You decide |
|---|---|---|---|
| 1 | `/wave-status` | Read-only: is there a wave plan, what is ready, what is out of sync | — |
| 2 | `/plan-waves` *(only if step 1 says no waves)* | Reads every open ABC ticket and its links, proposes waves, writes `docs/waves/wave-plan.md` + `.delivery/wave-plan.json`. The board shows the plan as PROPOSED | Reply "apply the plan" (or which parts). It then sets wave labels / links in Jira |
| 3 | `/loop /deliver ABC` | Bootstrap (setup check, board starts, URL printed), then every cycle: start ready tickets up to the cap in Orca worktrees, run gate / testers / reviewers, merge one at a time | Answer the setup questions once (merge path etc.) |
| 4 | *(watch the board)* | Cards move Intake → Build → Gate → Testing → Review → Approve & merge | — |
| 5 | Answer questions | Click an option on the board, **or** type in the chat: `Q3: A` | Design forks, spec acceptance (medium / high risk), escalations |
| 6 | Merge PRs | Cards under **Needs you · ready to merge** link the PR. Merge on GitHub (default merge path: you merge) | Review + merge |
| 7 | *(automatic)* | Next cycle sees the merge: merge-ticket posts proof to Jira + PR, moves ABC-n to Done, cleans the worktree, starts the next ticket | — |

**Useful while it runs:**

```text
/deliver ABC --status        read-only snapshot in the chat
/deliver ABC --board         reopen the board / print its URL
/deliver ABC --dry-run       what one cycle would do, writes nothing
/deliver ABC --cap 1         slower, one ticket at a time
/deliver ABC --watcher       move the loop to its own Orca chat so this one stays free
/loop /deliver ABC           resume after you closed the chat (state is in .delivery/)
```

**Starting from a document instead of Jira tickets:** `/loop /deliver docs/spec.md` turns the
doc into tickets (you approve the list), creates them in Jira, plans waves (you approve), then
runs as above.

---

## Scenario B — one ticket only (`ABC-42`)

You want just this ticket built, reviewed and merged, without the continuous loop.

**Option 1 — guided (recommended):** let the orchestrator run the full loop for one ticket.

```text
/loop /deliver ABC --only ABC-42
```

It starts only ABC-42 and still runs the gate, testers, reviewers and approver; the board shows
that one card; it stops once ABC-42 is merged or waiting on you. Blockers and the two-wave
window still apply: if ABC-42 is blocked, it says by what instead of starting it.

**Option 2 — by hand, step by step** (no orchestrator; good for a hotfix or for learning):

| Step | You type | Result |
|---|---|---|
| 0 | *(optional)* `git worktree add ../myapp.worktrees/ABC-42 -b feat/abc-042/<slug> origin/main`, then open Claude Code in that folder (or use an Orca "new worktree") | Isolated checkout |
| 1 | `/implement-ticket ABC-42` | Intake (type, AC word for word), explore, questions to you, ticket record `docs/tickets/ABC-42.md`, plan, build, checks, draft PR, Jira → In Review. `job.json` and progress are written from the first minute |
| 2 | `python "$HOME/.claude/delivery-board/board.py" serve --repo . --open` | The board shows ABC-42's card and task progress (no orchestrator needed) |
| 3 | "run the review loop for ABC-42" | The same session runs the round by hand (implement-ticket `references/review-loop.md`): **gate** (main's checks script with `--report`) → **tester-functional** (+ **tester-device**) → **reviewers** → any CHANGES → it fixes and repeats (max 3 rounds) → **approver** → **explainer** |
| 3b | `/verify-ticket ABC-42` *(optional, any time)* | Walks every AC in the real app with step-by-step screenshots |
| 4 | Review and merge the PR on GitHub | You merge |
| 5 | `/merge-ticket ABC-42` | Re-checks, posts proof on Jira + PR, moves ABC-42 to Done, cleans the worktree and branch. Safe to run after you merged by hand |

Escalation (approver says ESCALATE, or round 3 still has CHANGES): the PR stays open with one
question. Answer it in the chat ("for ABC-42: defer AC4 to a follow-up"), then say "resume
ABC-42".

---

## Scenario C — GitHub issues with the `factory` label

Your work lives in GitHub Issues. Only issues a maintainer labels `factory` get built.

**One-time setup:** the same CLAUDE.md / docs / `.gitignore` steps as Scenario A, plus
`gh auth status` (logged in). `/factory run` creates the labels on your yes: `factory`,
`factory:building`, `factory:needs-info`, `needs-human`, `ready-to-merge`, `severity:critical`.

**Queue work** — any of:

```bash
gh issue edit 12 --add-label factory          # opt an existing issue in
gh issue create --title "Export tasks as CSV" --label factory --body-file issue.md
```

or in Claude Code: `/factory new: users can export their tasks as CSV` (it drafts the issue with
acceptance criteria, shows it, and creates it on your yes).

Dependencies: put `Blocked by #10` in the issue body (or use GitHub's native "blocked by").
Urgent bug: add `severity:critical` and it jumps the queue.

**Run it:**

| Step | You type | What happens | You decide |
|---|---|---|---|
| 1 | `/loop /factory run` | Bootstrap (labels; engine = Orca if running, else background subagents; board starts), reads the `factory` queue, orders it (critical → unblocks most → priority → oldest), starts up to the cap | Create missing labels (yes / no) |
| 2 | *(board + GitHub)* | Each issue gets `factory:building` and a status comment; its card moves through the steps | — |
| 3 | Unclear issue? | The factory comments on the issue with numbered questions and adds `factory:needs-info`. It shows on the board under **Needs you** | Answer on the issue, on the board, or `/factory Q2: B` |
| 4 | Feedback mid-flight | `/factory #12 use the existing CSV helper in src/lib/csv.ts` (or the feedback box in the board's ticket drawer) | — |
| 5 | Ready to merge | Issue and card show `ready-to-merge` with the PR link (the PR says `Closes #12`) | Merge on GitHub |
| 6 | *(automatic)* | Proof comment, labels removed, issue closed by the merge, worktree cleaned, next issue starts | — |

**Other factory commands:**

```text
/factory run #12 #15                 only these issues
/factory plan                        wave-plan just the factory issues (you approve; adds wave labels)
/factory status                      read-only snapshot
/factory board                       reopen the board
/factory reject #14 duplicate of #9
/factory what's blocking #15?
/factory run --engine subagents      no Orca: workers run as background subagents of this chat
```

---

## Scenario D — brand-new project (`/delivery-blueprint` first)

```text
1. /delivery-blueprint      answer the intake (stack, PM tool, depth) → workbook, backlog,
                            Jira CSV or live push, CLAUDE.md + AGENTS.md
2. Import the CSV into Jira (or let it push live), then do Scenario A's one-time setup
3. /plan-waves              the blueprint already proposes waves; this checks them against the
                            real tickets and links, and writes .delivery/wave-plan.json for the board
4. /loop /deliver <KEY>     Scenario A from step 3
```

On GitHub Issues instead of Jira: after step 1, create the issues with the `factory` label and
follow Scenario C.

---

## Scenario E — only a description, no ticket yet

Someone says "add CSV export to the tasks page" and nothing exists in any tracker.

| Step | You type | What happens | You decide |
|---|---|---|---|
| 1 | `/new-ticket "Add CSV export to the tasks page"` | Finds the tracker, reads the repo, drafts the ticket: title, type, description, testable acceptance criteria (Given / When / Then), out of scope, risk, size, assumptions. Asks only what blocks it | Answer the blocking question(s), if any |
| 2 | *(review the draft)* | Shows exactly what will be created and where | "yes", or edits |
| 3a | *(PM tool connected)* | Creates it in Jira / Linear / GitHub Issues and gives you the key and link | — |
| 3b | *(no PM tool)* | Writes `docs/tickets/T-013.md` (description, AC, PR link, log, **Status: 🔴 To do**) and indexes it in `docs/tickets/backlog.md` | Commit it straight to `main`, or as a small docs PR |
| 4 | "build it now" (or `/new-ticket "…" --build`) | Runs implement-ticket: branch, file turns **🟡 In progress**, then **🟡 In review** with the PR link when the draft PR opens | Design questions, if any |
| 5 | "run the review loop for T-013", or `/loop /deliver T --only T-013` | Gate → testers → reviewers → approver; escalation turns it **🔴 Blocked — <reason>** | Answer escalations |
| 6 | Merge the PR, then `/merge-ticket T-013` | The file turns **🟢 Done** with the merge date and outcome | Merge |

Status key in the file: 🔴 To do / blocked · 🟡 In progress / in review · 🟢 Done · ⚪ Won't do.
On `main` you only ever see 🔴 or 🟢 (workers never edit `main`); the live 🟡 state is on the
ticket's branch, its PR and the live board.

Shortcuts:

```text
/new-ticket "Fix: login redirects to / instead of the page I came from" --type bug
/new-ticket "Add CSV export" --build            draft → approve → build right away
/new-ticket "Add CSV export" --loop             draft → approve → full loop for just this ticket
/implement-ticket "Add CSV export"              also works: it calls /new-ticket first
```

---

## Daily cheat sheet

| I want to… | Type |
|---|---|
| See everything at a glance | the board (`/deliver ABC --board`, `/factory board`) |
| Know what to work on next | `/wave-status` |
| Answer a question | a board button, or `Q3: B` in the orchestrator chat |
| Unstick an escalated ticket | answer its question, or `/factory #12 <feedback>` / "resume ABC-42 with …" |
| Pause everything (safe: workers finish their step, commit, push, wait) | `/deliver ABC --pause` · `/factory pause` |
| Pause everything right now | `/deliver ABC --pause --now` |
| Pause one ticket | `/deliver ABC --pause ABC-42` |
| Pause from another terminal | `python "$HOME/.claude/delivery-board/board.py" pause --repo . [--now] [--reason "…"]` |
| See what a ticket changed (files, functions, screenshots) | `python "$HOME/.claude/delivery-board/board.py" report --repo . --ticket ABC-42 --open` (or "Change report" in the board's ticket drawer) |
| Resume after a pause | `/loop /deliver ABC --resume` · `/factory resume` (or `--resume ABC-42` for one) |
| Resume after closing the chat | `/loop /deliver ABC` or `/loop /factory run` |
| Close out a PR I merged by hand | `/merge-ticket ABC-42` |
| Re-plan after scope changed | `/plan-waves` ("re-plan the waves") |
| Turn a sentence into a ticket | `/new-ticket "<description>"` |
