# `/deliver` — new skill (draft)

**Status:** draft in staging. Nothing is installed; nothing in `~/.claude/`, the repo or Jira was
touched. To install later, copy this folder to `~/.claude/skills/deliver/`. It needs the
workflow file at `~/.claude/workflows/ai-delivery-workflow.md` and the updated `wave-status`,
`plan-waves`, `implement-ticket` and `merge-ticket` skills being drafted alongside it.

## What it is

`/deliver <PROJECT-KEY>` is the "factory manager" for a project. It runs steps 3–7 of the AI
delivery workflow without you having to prompt each step: it picks ready tickets, starts a
builder for each one in its own Orca worktree, sends the work through checks, testers and
reviewers, merges approved PRs one at a time, and comes back to you only for decisions and
merges that are yours.

It doesn't write product code itself. Each ticket gets its own **worker**: a full Claude
session in its own Orca worktree, running `/implement-ticket`. It has to be a full session
because only a full session can ask you questions (subagents can't), and each ticket needs its
own worktree and branch. (Subagents *can* start subagents, up to 3 levels deep and 20 at once
per session; those are limits to respect, not the reason for this design.)

## What it does, step by step

**First run (setup, done once and re-checked quickly after that)**

1. **Finds the project.** It reads `CLAUDE.md` and the docs to work out the tracker (Jira for
   the project where this was first used), the GitHub repo and the main branch, then looks up the key in Jira to make sure
   it exists. It also checks that Orca is running and that `gh` is logged in.
2. **Checks the project setup** against the workflow's checklist: the checks script, the
   reviewer and tester agent files, how merging works, the local backend recipe, the dev build
   registry, the generated owner to-do list, the `needs-human` label, the concurrency cap, and
   whether `.delivery/` is ignored by git. You get one table of what's missing and how to fix
   it. It only asks you about the gaps that would stop it. It never changes your settings or
   permissions on its own.
3. **Checks the waves.** If Jira already has `wave-N` labels, it carries on. If not, it runs
   `/plan-waves`, shows you the plan, and **waits for your go** before anything is written to
   Jira.
4. **Saves its state** to `.delivery/orchestrator.json`, so it can pick up where it left off
   after a crash, a restart or a context reset. It also picks up tickets that are already in
   progress, so nothing gets started twice.

**Every cycle (each time it wakes up)**

1. **Reads the board** with `/wave-status`: which waves are open, what's ready, what's in
   progress, what's waiting on you, and anything left behind (for example a merged PR whose
   ticket was never closed).
2. **Tidies up first.** It closes out tickets whose PR already merged, because that can unblock
   other tickets.
3. **Moves each running ticket one step forward:**
   built → **gate** (it runs the checks script itself, using the copy on `main` so a branch
   can't weaken its own checks) → **testers** (functional, and on-device when the device lane
   is free) → **reviewers** (chosen by the ticket's risk, on the commit the testers left) →
   if any of them ask for changes, the builder fixes them (at most 2 extra rounds) →
   **approver** → on APPROVE the **explainer** writes the PR walkthrough → **merge** with
   `/merge-ticket`. On ESCALATE the ticket gets the `needs-human` label and you get one
   specific question.
4. **Shares the phone/simulator.** Only one ticket at a time gets the "device lane" for its
   on-device test. The others wait their turn.
5. **Starts new tickets** up to the cap (default 2), in wave order with critical bugs
   first. Before each start it checks Jira again to confirm every blocker is Done.
6. **Passes on the workers' questions** in one numbered batch, with its recommendation first.
   You answer whenever you like, for example "Q3: A".
7. **Checks every merge was cleaned up:** the proof is on the ticket and the PR, the ticket is
   Done, the other PRs are updated with `main`, and the worktree, branch and working folder
   are deleted. It also checks free disk space.
8. **Stops** once nothing can move without you, and sends one summary: what merged (with PR
   links, rounds and cost), what's waiting on you (with the `docs/actions` guide for each),
   and how to start it again.

## How to run it

| Command | Use it when |
|---|---|
| `/loop /deliver ABC` | **Recommended.** It keeps going by itself: every 5–10 minutes while workers are busy, less often while it waits on you. It stops by itself with a summary. |
| `/deliver ABC` | You want one pass: setup plus one cycle. Afterwards it tells you how to keep it running. Workers it started keep working. |
| `/deliver ABC --watcher` | You want your current chat free. Setup runs here, so any questions get answered while you're present. Then the loop moves to its own Orca chat. |
| `/deliver ABC --status` | Read-only check on where things stand. |
| `/deliver ABC --dry-run` | Shows what it *would* do. Changes nothing. |
| `--cap 2` | Run fewer tickets at once (useful when the PC is busy). |
| `--takeover` | Take over from an orchestrator session that has died. |

**Watcher vs. current session.** The watcher runs in its own Orca chat. That keeps your chat
free, it carries on if you close this chat, and it starts with a fresh context. The costs: it
is one more Claude session using memory, and its questions and permission prompts show up in
*that* chat (Orca marks it with an unread dot), not here. Pre-allow the routine commands or the
watcher will sit waiting on a prompt.

## What it will ask you

- **Once, at setup:**
  - Who merges: you click merge (the default), or the agent merges — only if you allow
    `gh pr merge` for agents yourself.
  - Whether workers may push their ticket branch and open **draft** PRs (recommended).
  - How to keep `.delivery/` out of git (recommended: a local `.git/info/exclude` entry now, and
    a small chore later to add it to `.gitignore`).
  - Whether to apply the wave plan, if there isn't one yet.
- **While it runs:**
  - Design choices the ticket doesn't settle.
  - Accepting the ticket record for medium and high risk tickets (you read the spec before
    any code).
  - Escalations, for example "defer this criterion to a follow-up?".
  - Owner actions (with a `docs/actions/` guide).
  - "Ready for your review" plus the PR link, if you are the one who merges (the ticket gets
    the `ready-to-merge` label meanwhile).

## Files it keeps (all gitignored)

- `.delivery/orchestrator.json`: the orchestrator's memory. It holds the project, the cap,
  each running ticket's stage and worker, who has the device lane, the merge lock, your open
  questions, and what has merged so far.
- `.delivery/briefs/<KEY>-<n>.md`: the brief each worker started with.
- `.delivery/jobs/<KEY>-<n>/` inside each ticket's worktree: `job.json` (the ticket's current
  stage), the review rounds, the approver's decision and the walkthrough. It is deleted when
  the ticket is cleaned up after merge.

## Safety rules it follows

- It never merges when anything is red: checks, CI, the deploy, or a missing APPROVE.
- It never starts a ticket that has an open blocker. It re-checks Jira each time, not just
  the plan file.
- It never changes how Jira is set up (statuses, fields, filters, waves, new tickets) without
  your OK.
- It keeps to the concurrency cap, runs one check (gate) at a time, gives one ticket the
  device at a time, and merges one PR at a time.
- It never touches your settings, permissions, hooks or `CLAUDE.md`.
- It reports what actually happened. "Merged" means GitHub says merged, and a check it didn't
  run is reported as "not run".

## Limitations

- **PC memory.** Each worker is a full Claude session, and its review helpers run on top of
  that. The default cap is 2; write 3 in `docs/workflow/README.md` only on a desktop-class
  machine, and use `--cap 1` if things slow down.
- **Orca must be running.** Workers live in Orca, and Orca is what wakes the orchestrator when
  a worker reports. If Orca closes, the loop pauses. Start Orca again, then run
  `/loop /deliver ABC` and it picks up from its files.
- **The loop lives in a chat.** With `/loop`, closing that chat stops the loop. Use
  `--watcher` if you want it to keep going.
- **Device tests need setup.** Without a local backend recipe and a dev build registry,
  on-device tests are skipped or escalated rather than faked.
- **Cost per ticket** only shows up if the project has a cost script.
- **Jira screenshot uploads** go through the browser (the Jira connector can't upload files).
  This is done by the device tester and merge-ticket, not by `/deliver`.

## Open questions for you

1. **Strictly manual?** Right now the skill also starts from phrases like "run the factory".
   If you only want it to start when you type `/deliver`, add `disable-model-invocation: true`
   to its frontmatter.
2. **Merge path for the project where this was first used.** You click merge, or the agent
   merges? Your current notes say to "merge after verified, with proof", which reads as
   agent-merges. If so, the merge command needs to be allowed in settings, and you would make
   that change yourself.
3. **Cap.** That project's docs say at most 3 workers until CI exists. Keep 3, or start
   with 2 while we see how the PC copes?
4. **Gate runner.** That project has no `scripts/workflow/checks` script yet. Until it does,
   the gate runs CI's commands (lint, typecheck, tests, plus the ticket docs check). Should I
   propose a small chore ticket to add the script (with the `--report` mode)?
5. **Releasing idle workers.** Should workers waiting on you be shut down straight away to save
   memory (they can be brought back), or kept open so you can read their chat?

## Alignment pass (after all drafts were written)

- `references/state-files.md` is now the single source of truth for `job.json`
  (`deliver-job/1`), `orchestrator.json`, stage names, the job folder layout and messages.
  New `job.json` fields: `base_branch`, `pr` as `{number, url}`, `roles`, `device_lane`,
  `blocked`, and `services` entries with `pid` / `started_by` / `status`. Stage `review` was
  renamed `built`; new stages `testing` / `tested`.
- Round order is now gate → testers → reviewers → approver → explainer. New message
  `TEST r<N>`; `DEVICE r<N>` runs tester-device only; `REVIEW r<N>` runs reviewers only.
- tester-device may answer `BLOCKED`; that never sends `FIX`; the approver escalates.
- `gh pr ready` moved to merge-ticket. The gate passes `--report <path>` to the checks script.
- Default cap aligned with wave-status: 3.
- Example keys are `ABC-…` instead of the first project's keys.

## Follow-up pass

- **File mode.** `/deliver <path-or-URL>` (an existing `.md` / `.txt` / `.pdf` / `.docx`, or a
  URL / Google Doc / Notion link when a connector can read it) runs a new bootstrap step 2b,
  "Import tasks from a document" (`references/import-tasks.md`): split the doc into tickets
  (title, type, testable AC, dependencies, size, risk hint, source excerpt), dedupe against
  existing tickets, show the list, **wait for your approval**, create them in the PM tool with
  type and blocks / is-blocked-by links — or in a local `docs/tickets/backlog.md` with IDs
  `T-001…` when no PM tool is connected — and record the mapping in
  `.delivery/import-<date>.md`. Then waves (your second approval), then the normal cycle.
  Argument parsing: `^[A-Z][A-Z0-9]{1,9}$` is a key; an existing file or a readable URL is a
  document; anything else → ask.
- **Local backlog rules** (in `import-tasks.md`, mirrored by wave-status, plan-waves,
  implement-ticket and merge-ticket): committed on the default branch via a docs PR; on `main`
  the status is only To Do / Done / Won't do (In Progress / In Review are derived from branches,
  PRs and job folders, so workers never edit the file); merge-ticket sets Done on the PR branch;
  comments and screenshots live on the PR.
- **Context limits** (bootstrap step 2c, `references/context-limits.md`): recommends an
  orchestrator window of ~300k (`CLAUDE_CODE_AUTO_COMPACT_WINDOW=300000` / `--autocompact 300k`,
  also for the watcher launch), ~400k for workers (passed through `worker-start` if Orca can),
  `autoCompactWindow: 200000` in the agent files, a `# Compact instructions` section and an
  optional SessionStart(`compact`) hook. Every cycle re-reads state from files. Nothing is
  written to settings, hooks or `CLAUDE.md` without your yes.
- **Correction:** the topology no longer claims subagents cannot spawn subagents (they can: 3
  levels by default, 20 at once per session). Builders stay Orca workers because only a full
  session can ask you questions and each ticket needs its own worktree session.
- `state-files.md`: `tracker.kind` adds `local` (+ `backlogFile`); new `import` block.
  `worker-brief.md`: "Context" and "Tracker" sections; worker window note.
- SKILL.md is 284 lines (detail moved to the two new references).

## Owner decisions applied (2026-11-08, all recommendations accepted)

Numbers refer to ALIGNMENT.md. Open questions 1–5 above are now settled.

- **#1 merge path:** owner approves by merging is the default; agent merges only if the owner
  allow-listed `gh pr merge` (bootstrap, cycle, state-files).
- **#6 cap:** default **2** when the project writes none (3 on a desktop if written in
  `docs/workflow/README.md`). SKILL, bootstrap, state-files.
- **#10 idle workers:** a worker waiting on the owner ~1 hour is released
  (`policy.idleReleaseMin` 60, `waitingSince`) and resumed from its files. SKILL, cycle,
  state-files, worker-brief.
- **#11 manual-only:** `disable-model-invocation: true`; phrase triggers removed from the description.
- **#12 stalled:** 2 days (cycle housekeeping row; wave-status owns the check).
- **#13 / #15:** bootstrap records `tracker.typeMap` and proposes "Task → Chore";
  `severity:critical` is the recommended critical-bug signal.
- **#19 `ready-to-merge`:** approved PRs waiting for the owner's merge get this label
  (`tracker.readyToMergeLabel`); `needs-human` only for real escalations.
- **#20 cost script:** `scripts/workflow/cost`. **#22:** bootstrap proposes a Chore for the checks
  script with `--report`.
- **#27 no PM tool:** GitHub Issues by default when the repo is on GitHub and `gh` works; local
  backlog otherwise.
- **#28 context limits:** windows + `# Compact instructions` recommended; the SessionStart hook
  only if compactions lose state (context-limits, bootstrap, SKILL 2c).
