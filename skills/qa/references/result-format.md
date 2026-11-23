# Result format: run file, scenarios file and tracker comment

## Choosing the result

Apply in order and stop at the first match:

1. Any AC scenario failed, or an S1 or S2 defect was found → `❌ QA FAILED`
2. Any required scenario is blocked or unverified → `🚫 QA BLOCKED`
3. Minor findings (S3 or S4), derived AC, or an unverified SHA → `⚠️ QA PASSED WITH NOTES`
4. Everything planned passed on a verified build → `✅ QA PASSED`

`💡` improvements never change the result. Zero scenarios executed is always `🚫 QA BLOCKED`.
A retest takes its result from `qa_evidence.py retest` (`references/retest.md`).

## report.md

The first line is the result, with nothing before it.

```markdown
✅ QA PASSED

# QA report: ABC-123 <ticket title>

QA run 20261123-101500

| | |
|---|---|
| Environment | staging (qa-data-only) |
| URL | https://staging.example.com |
| Deployed SHA | abc1234 (deployed: true) |
| Account role | owner |
| Browser / viewport | chromium 131, via playwright-cli / 1440x900 |
| Date | 2026-11-23 10:15 UTC |
| Depth / focus | standard / ui, a11y |
| Counts | 14 planned · 12 passed · 1 failed · 1 blocked |

## Acceptance criteria

| AC | Criterion (verbatim) | Result | Scenarios | Evidence |
|---|---|---|---|---|
| AC1 | ... | PASS | AC1-P1, AC1-N1, AC1-E1, AC1-R1 | screenshots/AC1-P1-step-01..04 |

## Scenarios

| ID | Type | Expected | Actual | Result | Evidence |
|---|---|---|---|---|---|
| AC1-P1 | Positive | ... | ... | PASS | screenshots/AC1-P1-step-01..04 |

## Retest (retest runs only)

| Group | Scenarios |
|---|---|
| Previously failed, now passing | AC2-N1 |
| Still failing | none |
| Newly failing (regression) | none |
| Not run | none |

## Checks

- Viewports (375 / 768 / 1440): ...
- Dark mode: ... | not supported
- Accessibility (axe): ... A clean scan covers only part of WCAG. Keyboard pass: ...
- Console: ... | not watched: <reason>
- Network: ... | not watched: <reason>
- Performance: ... | not in scope

## Bugs

| Bug | Severity | Title | Scenario | Action |
|---|---|---|---|---|
| ABC-140 | S2 | ... | AC2-N1 | new |

## Blocked

- <scenario>: <reason> → <who or what would unblock it>

## 💡 Improvements

- ...

## Leftover test data

None. | <record, marker QA-20261123-101500, why it could not be removed>

## Evidence

Folder: `.delivery/qa/ABC-123/20261123-101500/` (local to this machine)
Tracker upload: complete | **Evidence incomplete. Missing: <files and reason>**

## Sign-off

A person must review this and move the ticket. QA never moves a ticket to Done.
```

Never include an account email, password, token, cookie or real personal data.

## scenarios.json

Written at the start of execution and updated after each scenario. A retest reads this file, so
keep the steps and expected results complete enough to run again on another machine.

```json
{
  "schema": "qa-scenarios/1",
  "ticket": "ABC-123",
  "runId": "20261123-101500",
  "result": "QA PASSED",
  "environment": "staging",
  "url": "https://staging.example.com",
  "access": "qa-data-only",
  "deployedSha": "abc1234",
  "deployed": true,
  "role": "owner",
  "browser": "chromium",
  "viewport": "1440x900",
  "date": "2026-11-23T10:15:00Z",
  "depth": "standard",
  "focus": ["ui", "a11y"],
  "counts": {"planned": 14, "passed": 12, "failed": 1, "blocked": 1},
  "scenarios": [
    {
      "id": "AC1-P1",
      "ac": "AC1",
      "type": "positive",
      "required": true,
      "writes": false,
      "preconditions": "Signed in as owner, QA project with 12 tasks",
      "steps": ["Open Tasks", "Click Export"],
      "expected": "CSV downloads with every visible task",
      "actual": "CSV downloaded with 12 rows",
      "status": "passed",
      "screenshots": ["screenshots/AC1-P1-step-01.png"],
      "logs": ["logs/console.txt"]
    }
  ],
  "created": [{"kind": "task", "marker": "QA-20261123-101500", "removed": true}],
  "bugs": []
}
```

`status` is one of `planned`, `passed`, `failed`, `blocked`. `required` defaults to `true`. A
`passed` scenario with neither `screenshots` nor `logs` counts as not run in a retest.

## Tracker comment

Markdown is shown. Use the tracker's own markup (Jira wiki markup, for instance). The first line
is the result.

```markdown
✅ QA PASSED

**QA run 20261123-101500** · staging · `abc1234` · role: owner · chromium · 2026-11-23
14 planned · 12 passed · 1 failed · 1 blocked

| AC | Result | Evidence |
|---|---|---|
| AC1 <verbatim> | PASS | AC1-P1-step-01..04 |

**Bugs:** ABC-140 (S2)
**Blocked:** <scenario and reason, or none>
**💡 Improvements:** <or none>
**Leftover test data:** none
**Evidence:** complete | Evidence incomplete. Missing: <list>

Waiting for a person to sign off. QA does not move tickets to Done.
```

## Issues Found comment

Post this as a second comment on every `❌ QA FAILED` run, so a developer can see the problem
without opening the report. Use the tracker's own markup. Give every failure its numbered steps.
Possible security issues name the area and bug only, with no exploit detail.

```markdown
🐞 Issues Found · QA run 20261123-101500

**Bug status:** 🔴 2 open · Tested on: staging · `abc1234` · role: owner
**Ticket moved to:** <status> | not moved: <reason>

### 🟠 S2 · ABC-140 · Filter resets after refresh
Scenario: AC3-P1 · AC3 "<verbatim criterion>"

| # | Step | Expected | Actual | Screenshot |
|---|---|---|---|---|
| 1 | Open Quotes | List is shown | List is shown | AC3-P1-step-01.png |
| 2 | Filter by Draft | Only drafts | Only drafts | AC3-P1-step-02.png |
| 3 | Refresh the page | Filter stays | ❌ Filter is cleared | AC3-P1-step-03-FAIL.png |

Error: <sanitized console or network error, or none observed>

**Fix it:** `/fix-ticket ABC-123`
**Retest after the fix:** `/qa ABC-123 --retest`
```

| Severity | Emoji |
|---|---|
| S1 Critical | 🔴 |
| S2 High | 🟠 |
| S3 Medium | 🟡 |
| S4 Low | 🔵 |

## Labels

| Result | Label |
|---|---|
| `✅ QA PASSED` | `qa:passed` |
| `⚠️ QA PASSED WITH NOTES` | `qa:passed-with-notes` |
| `❌ QA FAILED` | `qa:failed` |
| `🚫 QA BLOCKED` | `qa:blocked` |
| Any `💡` item | also `qa:improvement` |
| Evidence did not all reach the tracker | also `qa:evidence-missing` |
| `/fix-ticket` has a fix in review | also `qa:fix-ready`, removed by a passing retest |

Remove the other three result labels whenever you add one. Remove `qa:evidence-missing` only after
the missing files are attached and `qa_evidence.py evidence` reports `complete`. Keep emoji out of
ticket titles.
