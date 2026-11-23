# Ticket types

Read at Phase 1. Every ticket has one type, set in the tracker (issue type, or a `type:`
label). The type changes intake, record, build and what the PR ends with; the review loop
after the hand-off is the same for all types, routed by **risk**, not type. Source:
`~/.claude/workflows/ai-delivery-workflow.md` section 5. A repo's own workflow doc wins
where it differs.

## Feature — new or changed behaviour from a user story

- **Ticket must contain:** user story, testable AC, dependencies, story points.
- **Branch / commit:** `feat/…` · `feat(scope): …`.
- **Flow:** full — questions → ticket record → (acceptance for medium/high) → plan → build.
- **Record:** intent, AC verbatim, design, decisions, outcome.
- **Review loop:** full routing by risk.

## Bug — behaves wrongly against what was specified or expected

- **Ticket must contain:** steps to reproduce, expected vs actual, environment, severity; AC
  shaped "Given [steps], then [correct result]" + "a regression test covers it". Missing:
  ask for it in Phase 3, or derive it from the report and confirm.
- **Branch / commit:** `fix/…` · `fix(scope): …`.
- **Questions:** only if the expected behaviour is unclear.
- **Build, in this order:**
  1. **Reproduce first**, following the `test-driven-development` skill (invoke it if
     installed; it is the method for this step): write one minimal test that fails *for the
     reported reason* (not a typo or a missing fixture), watch it fail, and keep the failing
     output for the record. Name the production change that would make it fail, assert real
     behaviour rather than mocks (its `writing-good-tests.md`). Not installed → the same
     red-before-green rule applies.
  2. **Find the root cause.** Trace why, not just where. If the cause is unknown after a
     reasonable look, stop: recommend investigating with a debugging skill or a short Spike,
     and report what you found.
  3. **Smallest fix that addresses the cause.** No refactors, no drive-by fixes; propose
     those as separate tickets.
  4. The failing test now passes (green) and the project's **full** test command stays green
     — not just the new file; any other failure goes in the report by name. Refactor only
     after green.
- **Record and PR:** a `## Root cause` section in the record (what, why, since when if
  known, why the existing tests missed it) and the same in the PR description, plus
  "reproduced by `<test name>`".
- **Review loop:** the functional tester checks the regression test and nearby edge cases;
  the device tester takes before / after screenshots if the bug is visible in the app.
- **QA bugs (`qa:found`):** read the Engineering handoff and attachments first, reproduce the
  failure before changing code (or stop and report `cannot reproduce` with evidence), add the
  regression test, and pass the full retest in `~/.claude/skills/qa/references/retest.md`.
- **Severity:** a critical bug (data loss, security, app unusable) may jump the wave window —
  the orchestrator's call, not yours.
- **A bug in an open PR** is fixed on that PR's branch in its review loop, not as a new
  ticket.

## Chore — maintenance with no behaviour change

Refactor, dependency upgrade, tooling, CI, docs, cleanup.

- **Ticket must contain:** what changes and why, and "no behaviour change" as an AC.
- **Branch / commit:** `chore/` `refactor/` `docs/` `build/` `ci/` with the matching commit
  type.
- **Record:** short — intent, AC, what changed, decisions if any.
- **Prove no behaviour change:** existing tests untouched and green; no snapshot, contract,
  public API or migration changes unless the ticket explicitly intends them. If a test had
  to change, that is a behaviour change: stop and ask. State the proof in the PR ("same N
  tests pass, no snapshots changed").
- **Review loop:** gate + code reviewer; security reviewer if it touches a risky area (auth,
  a dependency upgrade with security impact).

## Spike — an open question

Research, prototype, choose between options.

- **Ticket must contain:** the question, the options, a time box, what "done" produces.
- **Branch:** `spike/…`. Prototypes stay on the branch and are **never merged as product
  code**.
- **Build:** investigate within the time box. At the box, stop and write up what you have —
  an honest "not settled, here is what's left" is a valid result.
- **Record:** `## Findings` (what was tried, evidence, numbers) and `## Recommendation` (one
  option, why, the cost of the others), plus `## Proposed follow-ups`: Feature / Bug / Chore
  tickets with title, type, one-line scope, AC sketch and dependencies.
- **Ends with:** the owner decides on the recommendation; follow-up tickets are created and
  placed in waves (`/plan-waves`); the spike closes without a product merge. The record
  **always** lands on the main branch as a docs-only change (a `docs/…` PR carrying only
  `docs/tickets/<KEY>-<n>-<slug>.md`, opened from the default branch); no need to ask.
- **Review loop:** the code reviewer reads the findings, not product code; no device test.
  Do not create the follow-up tickets yourself unless the owner says so.

## Type is not risk

Risk is set separately (Phase 1). A one-line bug in authorization is high risk and gets the
security reviewer; a large docs chore is low risk.
