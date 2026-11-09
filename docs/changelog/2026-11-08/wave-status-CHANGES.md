# wave-status — what changed (draft)

Why: the new delivery workflow (`~/.claude/workflows/ai-delivery-workflow.md`, section 2 stage 3, sections
4 and 5) runs several tickets at once inside a two-wave window, and an orchestrator
(`/deliver`) needs wave-status to tell it what to start. The old skill picked one ticket and
refused to look past the current wave.

## Changed

- **Two-wave window replaces "one wave only".** Base = lowest wave with open tickets. The next
  wave joins once the base is down to 2 or fewer open tickets. Never two waves ahead.
- **Ranked ready list instead of one pick.** Order: ready critical bug first (from any wave),
  then wave N, then wave N+1, then "unblocks the most", then priority, then foundational,
  then lowest key. It fills free slots up to the project's concurrency cap (read from
  `docs/workflow/README.md`, default 3).
- **One top pick is still given** for a human asking "what next?" (critical bug → finish your
  in-progress ticket → close out a merged-but-open ticket → head of the list).
- **"Ready"** now also excludes tickets with a worktree or `.delivery/jobs/` folder, and
  tickets labelled `needs-human`.
- **Ticket type** (Feature / Bug / Chore / Spike) shown in the table. A Done Spike with no
  merged PR is no longer suspicious.

## Added

- **Needs the owner** section: `needs-human` tickets, escalated PRs (`ESCALATE` decision
  comment or label), open owner guides in `docs/actions/` (front matter `status: open`).
- **Housekeeping** section: worktrees and local branches of merged PRs, `[gone]` branches,
  prunable worktree records, stale or stalled `.delivery/jobs/` folders, tickets with no
  type. Each comes with its fix (`merge-ticket <KEY>` cleanup, `git worktree prune`).
- **Machine-readable summary**: a fenced JSON block at the end with a fixed schema
  (`wave-status/1`) — window, cap and slots, ready list, start-now list, top pick, in
  progress, blocked, out of sync, needs the owner, housekeeping. Schema and example in
  `references/status-recipes.md`.
- Recipes for types, critical bugs, the cap, the owner queue and housekeeping.

## Kept

- Read-only — still changes nothing; it now also never deletes worktrees, branches or folders.
- PR cross-check and every out-of-sync verdict (merged-but-not-closed stays the headline).
- Status markers (plus 🙋 for needs-human), progress by count and by estimate, "nothing"
  lines instead of missing sections, Windows shell notes.

## Removed

- "Don't reach into the next wave" and the next-wave fallback — replaced by the window rule.
- "Offer exactly one ticket" as the whole answer — the ranked list now sits beside the pick.

## Open questions for the owner

1. **Critical bug signal.** Draft: only a tracker-marked critical bug (highest priority /
   `severity:critical` / Linear urgent) jumps the window; wording alone is "possibly
   critical". OK, or should a label like `critical` be the single source?
2. **Default cap.** Draft uses 3 when the project sets none (workflow says "typically 2–3").
   Prefer 2?
3. **Task → type mapping.** Draft does not guess whether a Jira "Task" is a Feature or a
   Chore (shown as `Task?` and flagged). Want a default?
4. **Stalled job folder threshold** set at 7 days with no file change. Right number?
5. The summary schema is new; once `/deliver` exists, confirm it parses these exact keys.

## Alignment pass (after all drafts were written)

- Job folders are `.delivery/jobs/<KEY>-<n>/` (layout defined in the `deliver` skill's
  `references/state-files.md`).
- Step 4 now matches the recipes: only a tracker-marked critical bug jumps the window; wording
  alone is "possibly critical".
- `/deliver` uses the same default cap (3) and parses the `wave-status/1` keys as written
  (question 5 settled).

## Follow-up pass

- **Local backlog:** when the project has no PM tool and uses `docs/tickets/backlog.md`
  (IDs `T-001…`, created by `/deliver <doc>`), the skill reads tickets, waves, types and links
  from `main`'s copy of that file; In Progress / In Review are derived from branches, PRs and
  job folders. Note added in "Learn this project first".

## Owner decisions applied (2026-11-08, all recommendations accepted)

Open questions 1–4 above are settled.

- **#6:** default cap **2** when none is written (SKILL, status-recipes).
- **#12:** a job folder is stalled after **2 days** with no file change.
- **#13:** unmapped Jira "Task" still shows as `Task?`; the report suggests the line
  "Task → Chore" for `docs/workflow/README.md`.
- **#15:** kept (tracker-marked only; `severity:critical` recommended).
- **#16:** more than ~3 unwaved open tickets → recommend `plan-waves`.
- **#17:** a Done Spike whose only merged PR is its docs-only record is in sync.
- **#19:** "Needs the owner" gains **Ready for your merge** (`ready-to-merge` label) — kept
  apart from escalations; summary block `needs_human.ready_to_merge`; such tickets are not
  ready and hold no slot. SKILL trimmed to 301 lines.
