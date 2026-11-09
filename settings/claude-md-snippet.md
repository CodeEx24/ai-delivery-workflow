# CLAUDE.md snippet

Paste the block below into the project's `CLAUDE.md` (near the top for the import line, anywhere for the section). Replace `<KEY>` with the project's ticket key.

```markdown
@~/.claude/workflows/ai-delivery-workflow.md

Project-specific delivery rules (concurrency cap, merge path, ticket type mapping, checks and
cost scripts, device lane): `docs/workflow/README.md`.

# Compact instructions

State lives in files: `.delivery/orchestrator.json` and `.delivery/jobs/<KEY>-<n>/`. After
compaction, re-read them instead of trusting the summary.

When compacting, keep:

- **Orchestrator (`/deliver`, `/loop /deliver`, watcher):** the project key and concurrency
  cap; every running ticket with its stage, round and worker / dispatch ids; who holds the
  device lane; pending owner questions (needs-human, ready-to-merge); the last cycle summary.
- **Ticket worker (`/implement-ticket`):** the ticket key, type and risk; the current stage and
  round; open CHANGES items; the pending owner question; the branch, worktree path and PR URL.

Drop: file contents already committed, full test logs, review report bodies (they are in
`.delivery/jobs/<KEY>-<n>/round-N/`), and screenshots.
```
