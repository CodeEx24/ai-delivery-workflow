# The change report

One HTML page per ticket that tells the owner, in one place, **what changed and how it was
proven**. It is never committed: it lives under `.delivery/`, which is gitignored.

What the page shows:

1. **Header**: ticket key and title, type, risk, branch → base, approver decision, PR link.
2. **Summary**: 3–5 plain-language bullets, plus counts (files changed, functions touched,
   files per area).
3. **What changed**: every changed file, grouped by area (Frontend · Backend & logic ·
   Database · Tests · Config & tooling · Docs · Other). For each file:
   - the file name, `added` / `updated` / `deleted` / `renamed`, and links to the file (on
     GitHub on the ticket branch, and the local copy);
   - one or two sentences on what changed in it and why;
   - its functions / components / tables / policies, each `added`, `updated` or `removed`,
     with what changed in it.
   No diffs: the PR has them.
4. **Acceptance criteria**: each AC with its status and evidence.
5. **Testing and review rounds**: each round's verdicts and, for the device tester, every
   criterion's **step-by-step screenshots**, labelled "Failed run" or "Passed run". The step
   that failed is outlined in red ("failed here"), the proving step of a pass in green. Click a
   screenshot to enlarge it.

## Where it lives

| Path | What |
|---|---|
| `<worktree>/.delivery/jobs/<KEY>/report.html` | Built in the job folder; images linked by relative path |
| `<main checkout>/.delivery/reports/<KEY>/report.html` (+ its screenshots) | The archived copy. It survives merge-ticket's cleanup, which deletes the job folder |

The live board links it from the ticket's drawer ("Change report") and serves it at
`http://127.0.0.1:<port>/report/<KEY>/`.

## Who builds it, and when

| Moment | Who | Command |
|---|---|---|
| After APPROVE, once `walkthrough.md` and `changes.json` are written | explainer | `python "$HOME/.claude/delivery-board/board.py" report --repo <main checkout> --ticket <KEY>` |
| Right before the job folder is deleted | merge-ticket (step 7) | the same command (refreshes the archived copy) |
| Any time, by hand | the owner or the orchestrator | the same command; add `--open` to open it |

Before the explainer runs, the page still works: files and functions come from `git diff`
(base = `job.json.base_branch`, else the repo's default branch `origin/HEAD`), areas are guessed
from the paths, and each file says "No explanation yet".

## `changes.json` (schema `delivery-changes/1`, explainer writes)

`<job folder>/changes.json`. Every changed file appears, with every function added, changed or
removed in it. Plain language, for someone who has never seen the feature.

```json
{
  "schema": "delivery-changes/1",
  "summary": [
    "The Timesheet page opens on this week and has Week, Month and Range views.",
    "Clicking a day opens a panel with that day's entries."
  ],
  "files": {
    "app/dashboard/timesheet/_components/timesheet-day-panel.tsx": {
      "area": "frontend",
      "what": "New side panel listing one day's entries (start, end, task, project, note).",
      "symbols": [
        { "name": "TimesheetDayPanel", "kind": "component", "change": "added",
          "what": "Renders the selected day's entries; closes on Escape or an outside click." }
      ]
    },
    "supabase/migrations/20261110_timesheet_view.sql": {
      "area": "database",
      "what": "Adds a read-only view the calendar queries; no table changes.",
      "symbols": [
        { "name": "timesheet_days", "kind": "view", "change": "added",
          "what": "Hours per user per day, settled entries only, RLS through the base table." }
      ]
    }
  },
  "howToTry": ["Sign in as the test account", "Open Timesheet", "Switch to Month"],
  "notes": ["Figma was unavailable; the layout follows the record's D4."]
}
```

| Field | Rule |
|---|---|
| `summary` | 3–5 bullets: what the user can now do, no jargon |
| `files.<path>` | Repo-relative path exactly as `git diff --name-only` prints it; **every** changed file |
| `area` | `frontend`, `backend`, `database`, `tests`, `config`, `docs` or `other`: where a reader would look for it, not only its extension (an API route under `app/` is `backend`) |
| `what` | 1–2 sentences: what changed in this file and why |
| `symbols[]` | Every function, component, hook, route handler, class, type, table, view, policy, migration step or test suite added, changed or removed. `change` is `added`, `modified` or `removed`; `what` is one sentence on what it does now or what changed |
| `howToTry` *(optional)* | Steps a reviewer can follow locally |
| `notes` *(optional)* | What the reviewer should know: risks, follow-ups, deviations from the record |

## Screenshot names the report understands

`<KEY>-AC<k>[-before|-after]-step-<nn>[-<what it shows>][-FAIL].png` in
`round-<N>/screenshots/`, e.g. `PP-013-AC4-step-03-month-360-FAIL.png`. The words after the
step number become the caption; `-FAIL` marks the step that proves a criterion is not met. If a
failing criterion has no `-FAIL` screenshot, the report falls back to the tester's per-AC status
in `test-device.md` and outlines that criterion's last step.
