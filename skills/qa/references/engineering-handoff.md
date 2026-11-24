# Engineering handoff

Every QA bug must let an engineering AI on **another machine** reproduce, fix and fully retest it
from the tracker alone. `.delivery/qa/` is local and gitignored, so **the tracker attachments are
the shared copy of the evidence**.

## Required section

Put this in the bug body. Unknown values say `unknown`; never guess. Name the account **role**,
never an email or password.

```markdown
## Engineering handoff

### Source
- Source ticket: ABC-123
- QA run: 20261123-101500
- Evidence PDF: ABC-123_QA_R1_FAILED_export-csv_20261123-1015Z_abc1234.pdf
- Failed flow: Export Flow, AC2-N1 step 2

### Environment
- Environment: staging
- URL: https://staging.example.com/tasks
- Deployed SHA: abc1234
- Browser: chromium 131
- Viewport: 1440x900
- Account role: owner

### Preconditions and test data
- Signed in as the owner QA account (`accounts.owner` in `docs/workflow/qa.config.json`)
- QA project `QA-20261123-101500 Export` with 3 tasks, one titled `Fix, then ship`

### Reproduction steps
| # | Action | Screenshot | Expected | Actual |
|---|---|---|---|---|
| 1 | Open Tasks | AC2-N1-step-01.png | Three tasks are listed | Three tasks are listed |
| 2 | Click Export | AC2-N1-step-02-FAIL.png | CSV has 3 rows | CSV has 2 rows |

### Failing scenarios
- Scenario IDs: AC2-N1
- Acceptance criteria: AC2 "<verbatim criterion>"

### Console and network
- Sanitized errors, or `none observed`, or `not watched: <reason>`

### Suspected area (hypothesis)
- Hypothesis, not confirmed: `src/export/csv.ts` does not quote commas

### Regression risk
- Other CSV exports share this helper

### Commands
- Reproduce: `/qa ABC-123 --retest --from-run 20261123-101500 --env staging`
- Retest after the fix: `/qa ABC-123 --retest --from-run 20261123-101500 --env local`
- Worker retest: follow `~/.claude/skills/qa/references/retest.md`

### Evidence
- Evidence status: complete
- Attached: evidence PDF, report.md, scenarios.json, AC2-N1-step-02-FAIL.png, console.txt, network.txt
```

If evidence did not all reach the tracker, the Evidence section instead reads:

```markdown
### Evidence
- Evidence status: Evidence incomplete
- Missing: AC2-N1-step-02-FAIL.png, network.txt (upload refused by the tracker)
- Local copy on the tester's machine: `.delivery/qa/ABC-123/20261123-101500/`
```

and the bug carries the `qa:evidence-missing` label.

## Attach, in this order

1. The evidence PDF (`~/.claude/skills/evidence-pack/SKILL.md`).
2. `report.md`
3. `scenarios.json`
4. Every `-FAIL` screenshot.
5. Sanitized logs from `logs/`

Use `~/.claude/skills/evidence-pack/references/tracker-delivery.md` for the tracker in use. If no PDF can be built,
attach every step screenshot instead and mark the evidence incomplete.

## Before attaching

```text
E="$HOME/.claude/skills/qa/qa_evidence.py"
python "$E" scan --run .delivery/qa/ABC-123/<run-id> --repo . --json
```

Findings give the file, line and kind, never the matched text.

- **Any finding:** fix the file by redacting it (`[REDACTED]`), then scan again. Never attach
  until the scan is clean.
- **`unscannable`** (for example a trace archive): do not attach it. List it as missing, or
  replace it with a sanitized export.
- **`needsVisualReview`**: open each image and video. The script cannot read them. Look for
  secrets, tokens, real names, emails and other personal data. Retake or mask any that show it.

## After attaching

Write the names the tracker confirms it holds (re-read the attachment list, do not assume) to a
file, one per line, then:

```text
python "$E" evidence --run .delivery/qa/ABC-123/<run-id> --uploaded uploaded.txt --pdf <pdf name> --repo . --json
python "$E" handoff --bug bug-body.md --repo . --json
```

| `evidence` says | Do |
|---|---|
| `complete` | Set `Evidence status: complete` |
| `Evidence incomplete` | **Do not claim the handoff is complete.** List everything in `missing`, add `qa:evidence-missing`, and keep the bug open and visible |

The bug is still filed when evidence is incomplete: a visible, honest bug beats a lost one. Run
`handoff` on the final body, and fix every problem it lists before creating the bug.
