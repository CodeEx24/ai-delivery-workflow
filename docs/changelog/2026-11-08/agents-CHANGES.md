# Delivery-loop agents: what they are and how they fit

Eight new subagent files for the back half of the AI delivery workflow
(`~/.claude/workflows/ai-delivery-workflow.md`, sections 3, 6 and 8). They are
staged here as drafts and would be installed in `~/.claude/agents/`. They
work in any project: each one reads the repo's own `CLAUDE.md` / `AGENTS.md`,
`docs/workflow/README.md` and `REVIEW.md` for the stack rules, and names
stack items only as examples.

## How they fit the loop

1. `/implement-ticket` builds the ticket, opens a draft PR and creates the
   working folder `.delivery/jobs/<KEY>-<n>/` (gitignored) with `job.json`
   and `plan.md`.
2. The **gate** script runs the checks and writes `round-N/checks.md`. If it
   fails, it goes straight back to the builder and no agent is started.
3. The **testers** run next (tester-functional, and tester-device when the
   device lane is free). Both may commit tests / an E2E flow; each does
   `git pull --rebase`, then `git push`.
4. Then the **reviewers** the risk table routes run in parallel on the
   round's final commit (testers' commits included); reviewer-ui and
   reviewer-ux read that round's screenshots. Each agent reads files only
   (job folder, ticket record, PR diff), writes **one report** that starts
   with `VERDICT: PASS` or `VERDICT: CHANGES` (tester-device may also write
   `VERDICT: BLOCKED`), and replies with one line.
5. Any CHANGES → the same builder fixes it, up to two more rounds. A
   tester-device BLOCKED never goes to the builder.
6. Otherwise the **approver** writes `decision.md` (`APPROVE` or
   `ESCALATE`; BLOCKED → ESCALATE with one owner question), and the
   ticket's worker posts it on the PR.
7. APPROVE → the **explainer** writes the PR walkthrough and feature guide,
   then `/merge-ticket`. ESCALATE → one owner question, `needs-human` label.

All agents read `job.json` with the field names of the one schema in the
`deliver` skill's `references/state-files.md` (`ticket`, `type`, `risk`,
`worktree`, `branch`, `base_branch`, `pr.number`, `round`, `roles`,
`device_lane`, `blocked`).

Every report uses the same layout: verdict line, `## Summary` (3–5 bullets),
then findings with `file:line`, the failure scenario, a severity
(blocking / important / nit) and a suggested fix. Only verified blocking or
important findings cause CHANGES; nits never do.

## The agents

**reviewer-code** reviews the change for correctness, whether it matches the
acceptance criteria (nothing missing, nothing extra), the repo's rules and
reuse of existing code. Any test that was weakened, skipped or special-cased
to pass is an automatic CHANGES. It borrows the lenses and the
"verify before you report" rule from the senior-pr-reviewer skill (and points
to that skill's lens checklist instead of copying it). Inputs: job folder,
ticket record, PR diff. Output: `round-N/review-code.md`. Model: Sonnet
(the orchestrator passes Haiku for low-risk tickets). Tools: Read, Grep,
Glob, Bash (git, gh, single test runs), Write (its one report).

**reviewer-security** looks for ways the wrong person could read, change or
spend something: authorization, data access rules (e.g. row-level security),
secrets, injection, AI / prompt surfaces, data leaks and risky migrations.
Each finding must be written as a concrete attack. It always runs on
high-risk tickets. Output: `round-N/review-security.md`. Model: Opus. Tools:
same read-only set as reviewer-code.

**reviewer-ui** checks the visual side from the code and, when present, the
device tester's screenshots: design-system components and tokens used,
accessibility (labels, roles, touch-target size, contrast) and consistency
with nearby screens. It never runs the app. Output: `round-N/review-ui.md`.
Model: Sonnet (Haiku for low risk). Tools: read-only set.

**reviewer-ux** judges the user's flow from the device tester's step-by-step
screenshots and the acceptance criteria: is it clear, does every path end
somewhere, are empty, error, loading and offline states handled, and is the
wording plain? It does not drive the app. Output: `round-N/review-ux.md`.
Model: Sonnet. Tools: read-only set.

**tester-functional** writes automated tests for every acceptance criterion,
plus edge cases (empty, deleted, offline, invalid input or links), runs them
with the full suite, and commits and pushes the tests on the ticket branch.
It may edit test files only and never fixes product code; a failing test goes
back to the builder. Output: `round-N/test-functional.md` with an
AC → test → result table. Model: Sonnet. Tools: Read, Grep, Glob, Bash,
Edit, Write.

**tester-device** takes the single device lane, installs the right dev build,
starts the local backend and signs in as the test account if needed, walks
each criterion like a user and takes a screenshot of every step
(`<KEY>-<n>-AC1-step-01.png`…). It records the same path as a replayable E2E
flow and commits it as a test, attaches the screenshots to the ticket with
one comment per criterion (through a browser if the PM tool can't upload),
then releases the lane. It follows the `verify-ticket` skill (preloaded) and
never fixes code. Output: `round-N/test-device.md`. Model: Sonnet. Tools:
inherits the session's tools (minus Agent and NotebookEdit), because the
simulator, browser and PM-tool tools differ per project.

**approver** reads every verdict, the gate result and the AC table. It
approves only if everything passed and every criterion is met (or its
deferral is recorded with your decision). It always escalates when you must
act, when a check only a human can do is needed, on scope or criteria
changes, security exceptions, and deploy / infrastructure / billing changes,
and then asks you **one** specific question with a recommendation. Output:
`decision.md`, posted on the PR by the ticket's worker. Model: Opus. Tools:
read-only set.

**explainer** runs only after APPROVE. It writes a plain-language PR
walkthrough (with a Mermaid data-flow diagram) to `walkthrough.md`, inserts
it into the PR description below "What was built / How to test" without
losing the existing text, adds 3–6 inline guide comments on key parts of the
diff, creates or updates `docs/features/<area>.md`, links it from the ticket
record's Outcome, and commits those docs on the branch. Model: Sonnet. Tools:
Read, Grep, Glob, Bash (git, gh), Edit, Write.

## Open questions for you

1. **Timing of reviewer-ux (and reviewer-ui).** The workflow says all
   reviewers run in parallel, but reviewer-ux judges from the device
   screenshots. Proposal: the orchestrator starts reviewer-ux (and
   reviewer-ui when screenshots matter) after tester-device finishes. Both
   agents fall back to code-only review and say so if no screenshots exist.
   OK, or update section 3 of the workflow?
2. **Testers committing in parallel.** Both testers commit and push to the
   same branch at the same time, while reviewers read it. The agents rebase
   and retry, and reviewers record the commit they reviewed. Alternative:
   testers run first, reviewers after. Which do you prefer?
3. **Blocked device checks.** A criterion the device tester could not reach
   (missing build, no backend) is reported as "Blocked", not as CHANGES,
   because the builder can't fix it; the approver then escalates. Agree?
4. **tester-device tool list.** It inherits all session tools so it can use
   whatever simulator / browser / PM-tool MCPs a project has. Tighter would
   mean listing exact MCP names per machine. Keep it inherited?
5. **`job.json` fields.** The agents expect key, type, risk, worktree,
   branch, base, PR number, round, routed roles and the device-lane grant.
   The orchestrator / `/implement-ticket` must write these; confirm the
   names when that part is built.
6. **Approver's always-escalate list.** It uses the list you gave (owner
   action, human-only check, scope / AC change, security exception, deploy /
   infra / billing). The reference factory also escalates on every migration
   and every new dependency. Add those for this project?
7. **Explainer commits after approval.** Its docs commit lands after APPROVE;
   the pre-merge re-gate in `/merge-ticket` covers it. Fine, or should the
   explainer run before the approver?

## Alignment pass (after all drafts were written)

- Questions 1, 2, 3 and 5 are **settled**: testers run first, reviewers after them on the
  round's final commit (so reviewer-ui / reviewer-ux always have that round's screenshots, and
  testers no longer rebase-and-retry against reviewers); tester-device writes
  `VERDICT: BLOCKED` with a `Blocked: <reason>` line, which the approver escalates; `job.json`
  field names come from the `deliver` skill's `references/state-files.md`.
- Screenshots live in `round-N/screenshots/` (was `<job>/screenshots/`).
- tester-device lists the services it started and stopped; the worker copies them into
  `job.json.services` (subagents never write `job.json`).
- Questions 4, 6 and 7 stay open (see ALIGNMENT.md).

## Follow-up pass — skill wiring

| Agent | Preloads (`skills:`) | Change |
|---|---|---|
| reviewer-security | `security-review` (Sentry) | Method = the skill (confidence and severity mapped onto `review-security.md`), plus an "On top of the security-review skill" checklist |
| tester-functional | `test-driven-development` (obra) | Method section ("a test you never saw fail proves nothing", adapted to testing after the build) + addendum: edge-case catalogue, coverage expectations, test naming |
| tester-device | `verify-ticket` (as before) | verify-ticket loads `playwright-cli` + `webapp-testing` for web projects (frontmatter can't be conditional) |
| reviewer-code | `senior-pr-reviewer` (staged improved copy) | Method = the skill in its delivery-loop mode; skips posting and fixing |
| reviewer-ui | — | Optional aids `design:accessibility-review`, `design:design-critique` (plugin, not guaranteed → not preloaded) + fallback checklist |
| reviewer-ux | — | Optional aids `design:ux-copy`, `design:design-critique` + fallback checklist |

All eight agents now carry `autoCompactWindow: 200000` (needs Claude Code v2.1.296+; this
machine runs 2.1.319). On older versions remove the line.

Provenance:

- **reviewer-security — taken from `senior-security`:** threat modelling for high-risk tickets
  (assets, actors, entry points, trust boundaries; STRIDE as the prompt) — the skill itself is
  a generic template, so only the idea was kept. **Taken from `ecc:security-review`:** secrets
  in client bundles and newly tracked `.env` files, `ENABLE ROW LEVEL SECURITY` on every new
  table, per-user rate limits on expensive operations, lockfile changes. **Taken from the
  built-in security review idea:** focus on the branch's changes, verify before reporting.
  Kept from the earlier draft: RLS / data access rules, AI and prompt-injection surfaces (now
  with indirect injection and LLM keys in client code), migration safety (expanded: policy
  gaps, locks, deploy order).
- **tester-functional — taken from `ecc:tdd-workflow`:** ~80% coverage target applied to
  changed lines (repo threshold wins), edge cases incl. errors and boundaries, test isolation,
  arrange–act–assert, semantic names. **Taken from `senior-qa`:** nothing usable (template
  content); listed so you know it was checked.
- **reviewer-ui / reviewer-ux — taken from `design:accessibility-review`, `design:design-critique`,
  `design:ux-copy`:** the WCAG items, first-impression check, CTA / error / empty-state /
  confirmation copy patterns, in the fallback checklists.

The overlapping skills (`senior-security`, `ecc:security-review`, `ecc:tdd-workflow`,
`senior-qa`, `ecc:browser-qa`, `ecc:e2e-testing`, `ecc:code-review`) stay installed but are no
longer referenced by these agents.

## Owner decisions applied (2026-11-08, all recommendations accepted)

- **#24 approver:** always-escalate list adds **migrations on live data**; a new dependency
  alone is not a reason (reviewer-security covers risky ones).
- **#21 tester-device:** one E2E flow per ticket; per AC only for independent flows or by the
  folder's convention.
- **#23, #29, #32:** kept (tool list, `autoCompactWindow`, design skills as optional aids).
