---
name: evidence-pack
description: >-
  Shared procedure for turning a test run into a labeled, timestamped evidence PDF, delivering it
  to whichever project tracker the repo uses, and keeping one Evidence Index on the ticket. Used by
  verify-ticket, tester-device, qa, fix-ticket and merge-ticket.
user-invocable: false
---

# Evidence pack

Each test run leaves three things:

| File | Used by | Purpose |
|---|---|---|
| Evidence PDF | People | Step-by-step proof, grouped by named flow |
| `scenarios.json` | `/fix-ticket`, `/qa --retest` | Exact steps and results to rerun |
| Failed-step PNGs | People and AI | Full-quality proof of each failure |

## File name

```text
<KEY-n>_<DEV|QA|FIX|RETEST>_R<round>_<PASSED|NOTES|FAILED|BLOCKED>_<title>_<YYYYMMDD-HHMMZ>_<sha7>.pdf
ABC-123_QA_R1_FAILED_quote-status-filter_20261124-1415Z_d4e5f6a.pdf
```

Time is UTC. Files are never overwritten. The script derives the result from the scenarios.

## Flow names

Give every scenario a `flow`: a short user-facing name such as `Login Flow`. **Reuse the exact name**
from earlier runs on the ticket, so a flow can be followed from development through QA and fixes.
Prefer `steps` as objects when each step has its own result:

```json
{"id": "AC1-P1", "flow": "Login Flow", "ac": "AC1", "type": "positive", "status": "passed",
 "steps": [{"action": "Open sign in", "expected": "Form is shown", "actual": "Form is shown",
            "screenshot": "screenshots/AC1-P1-step-01.png"}],
 "screenshots": ["screenshots/AC1-P1-step-01.png"]}
```

## Build

Scan and open every image first. The script cannot read them, so `--visual-reviewed` is your
statement that they show no secrets, tokens or real personal data.

```text
P="$HOME/.claude/skills/evidence-pack/evidence_pack.py"
python "$P" build --scenarios <run>/scenarios.json --ticket <KEY-n> --stage QA --round 1 \
  --title "<ticket title>" --out "$MAIN/.delivery/evidence/<KEY-n>" --visual-reviewed --repo . --json
```

`$MAIN` is the main checkout: `dirname "$(git rev-parse --path-format=absolute --git-common-dir)"`.
Keeping PDFs there means they survive when a ticket's worktree is removed. `.delivery/` is gitignored.

| Stage | Written by | Extra arguments |
|---|---|---|
| `DEV` | `verify-ticket`, `tester-device` | none |
| `QA` | `/qa` | `--responds-to <latest DEV or FIX PDF>` when there is one |
| `FIX` | `/fix-ticket` | `--responds-to <failed PDF> --before <its scenarios.json>` |
| `RETEST` | `/qa --retest` | `--responds-to <FIX or failed PDF> --before <prior-scenarios.json>` |

Exit 1 means unsafe evidence: redact it, or review the images, and build again. A failed build
never turns into a pass. Report the evidence as incomplete.

## Deliver

Follow `references/tracker-delivery.md`. Upload the PDF, `scenarios.json`, every `-FAIL` PNG,
`report.md` when the stage has one, and sanitized logs.

## Evidence Index

After upload, read the file names the tracker holds into a file, one per line, then:

```text
python "$P" index --ticket <KEY-n> --names names.txt --focus "<firstFailure>" --format <markdown|text>
```

Use `--format markdown` for Jira through the Atlassian connector too (`jira` is only for the older wiki-markup API). Post the output as the ticket's single `📁 Evidence Index` comment, and link each document to its attachment URL when the tracker gives one. `checkFirst` is the document to
open first, and `openFailure` is the newest QA or retest that has not passed.
