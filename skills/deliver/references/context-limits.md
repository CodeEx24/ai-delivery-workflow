# Context limits

Bootstrap step 2c, plus the rules that keep a long run safe across compactions. Process
context: workflow section 4, "Context limits". The orchestrator and workers run for hours, so
they **will** compact. The design assumes it: every cycle re-reads `.delivery/orchestrator.json`
and the `job.json` files, and nothing important lives only in the conversation.

## What Claude Code supports (verified against the official docs)

| Control | Where | Notes |
|---|---|---|
| `autoCompactWindow` | `settings.json` | tokens, 100000–1000000 |
| `--autocompact <size>` | launch flag | e.g. `claude --autocompact 300k` |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | env var | overrides the two above |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | env var, 1–100 | can only **lower** the trigger; applies to main sessions and subagents |
| `autoCompactEnabled` | `settings.json` | true / false; keep true for long runs |
| `autoCompactWindow` | subagent frontmatter | Claude Code **v2.1.296+** |
| `# Compact instructions` | section in the project `CLAUDE.md` | default compaction instructions |
| PreCompact hook | `settings.json` hooks | stdout (≤ 10,000 chars) becomes the summary instructions |
| SessionStart hook, matcher `compact` | `settings.json` hooks | runs after compaction; stdout re-injects state |

**Not possible:** a `/loop` iteration, a skill or a hook cannot run `/compact` or `/clear`
(they arrive as plain text). No hook event reports token usage; only the status line JSON has
`context_window.used_percentage`. So nothing here can "compact at the end of a cycle" on
purpose — rely on the window and good instructions.

## Recommendations

| Session | Window | Compact instructions keep |
|---|---|---|
| Orchestrator (`/loop /deliver`, watcher) | `CLAUDE_CODE_AUTO_COMPACT_WINDOW=300000` or `--autocompact 300k` | project key, cap, running tickets with stage / worker (dispatch) ids, device-lane holder, pending owner questions, last cycle summary. "Everything else is in `.delivery/`." |
| Ticket worker | ~400k (`CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000` or `--autocompact 400k`) | ticket key, stage, round, open CHANGES items, pending owner question. "Plan and round reports are in `.delivery/jobs/<KEY>-<n>/`." |
| Review / test subagents | `autoCompactWindow: 200000` in the agent files (set in the staged agents; needs v2.1.296+, otherwise remove the line and rely on defaults) | fresh context per run; nothing to keep |

Suggested `CLAUDE.md` section (the owner adds it, or approves you adding it on a docs branch):

```markdown
# Compact instructions
When compacting a /deliver orchestrator: keep only the project key, the concurrency cap, the
running tickets with stage and worker ids, the device-lane holder, pending owner questions and
the last cycle summary; everything else is in .delivery/. When compacting a ticket worker: keep
the ticket key, stage, round, open CHANGES items and any pending owner question; the plan and
round reports are in .delivery/jobs/<KEY>-<n>/.
```

**Not recommended by default:** a SessionStart (`compact`) hook. Propose it only once
compactions have actually lost state (a cycle acted on stale memory despite the files). Then,
owner-approved, in the project `.claude/settings.json`: a small script that prints project key, cycle count, each `tickets` entry (key · stage ·
waitingOn · dispatchId), the device-lane holder and unanswered `ownerQuestions` from
`.delivery/orchestrator.json` — under 40 lines. In a worker worktree it prints the job.json
stage, round and `blocked` instead.

## Bootstrap step 2c

1. Detect: `echo $CLAUDE_CODE_AUTO_COMPACT_WINDOW` (PowerShell `$env:…`), the
   `autoCompactWindow` / `autoCompactEnabled` values in user, project and local settings, a
   `# Compact instructions` section in `CLAUDE.md`, any PreCompact / SessionStart(`compact`)
   hooks already present (report them; do not recommend adding one), and `claude --version`
   (≥ 2.1.296 for the agent frontmatter field).
2. Print one table row per item: found · recommended · fix. All gaps are **info** (never
   blocking); repeat them in the stop summary until fixed.
3. Offer, in one question with a recommendation: (A) I write the `# Compact instructions`
   section on a docs branch — recommended; (B) you apply it and the windows yourself (via
   `/update-config` for settings); (C) skip. No hook in this offer; it comes up only if a later
   compaction loses state. **Never write settings,
   hooks or `CLAUDE.md` without that yes** (hard rule 6).
4. The current session's window can't change mid-session: tell the owner how to relaunch
   (`CLAUDE_CODE_AUTO_COMPACT_WINDOW=300000 claude`, or `claude --autocompact 300k`) — or use
   `--watcher`, which launches a fresh session with the window if Orca can pass it.

## Ticket workers

`worker-brief.md` adds the window to `worker-start` when Orca can pass env or agent flags
(check the loaded `orchestration` / `orca-cli` guide; flags differ by Orca version). If it
cannot, the brief's "Context" section still tells the worker what to keep and where its state
lives, and the stop summary lists "worker window not set" as an info gap.

## Subagent limits

Subagents can start subagents (default up to 3 levels below the main conversation,
`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`; at most 20 at once per session,
`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`). The orchestrator spawns none for tickets; a worker
runs at most six at once (two testers, then up to four reviewers). Ticket builders remain Orca
workers because only a full session can ask the owner questions and each ticket needs its own
worktree session.
