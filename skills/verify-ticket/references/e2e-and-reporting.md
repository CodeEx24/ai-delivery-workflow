# E2E flows, the report file and the ticket comment

What the run leaves behind: a replayable flow in the repo, a verdict file in the working folder,
screenshots and a step comment on the ticket. Nothing else.

## Contents

- [Recording the replayable E2E flow](#recording-the-replayable-e2e-flow)
- [The report file: test-device.md](#the-report-file-test-devicemd)
- [Attaching screenshots to the ticket](#attaching-screenshots-to-the-ticket)
- [The per-AC step comment](#the-per-ac-step-comment)
- [Linking from the PR](#linking-from-the-pr)
- [Standalone report in the terminal](#standalone-report-in-the-terminal)

## Recording the replayable E2E flow

The flow repeats **the same path you walked**, so it becomes a regression test that runs in CI.

1. **Where:** the project's existing E2E folder and naming (look at neighbouring flows). If
   none exists, report "no E2E tool in this project" and skip — adding a tool is an owner
   decision.
2. **Shape:** **one flow per ticket** covering its criteria in order, split into one flow per
   criterion only when the criteria are independent flows (different entry points or states)
   or the folder's own convention says so; name it with the key, e.g.
   `<area>/<key>-<n>-<slug>.yaml` or `<area>/<key>-<n>.spec.ts` (per AC: `<key>-<n>-ac1-<slug>`). Put the ticket
   key and AC text in a comment at the top.
3. **Selectors:** test ids / accessibility labels / roles you used in the step log. No raw
   coordinates unless there is no alternative (say so in a comment).
4. **Assertions:** the observable result you wrote down before the run, at the same points.
5. **Secrets:** the test account via the tool's env mechanism, never literal credentials.
6. **Start state:** reset to a known state (clear app state, sign in via the shared sub-flow if
   the folder has one — reuse it rather than duplicating login steps).
7. **Replay once** against the running app; it must pass. A flaky or failing replay is a finding,
   not something to tune until green by weakening assertions.

Example (Maestro):

```yaml
# <KEY>-<n> AC1: "<verbatim criterion>"
appId: <bundle or package id>
---
- launchApp:
    clearState: true
- runFlow: ../shared/sign-in.yaml          # existing shared sub-flow, if any
- tapOn:
    id: "quick-add-input"
- inputText: "Buy milk tomorrow"
- tapOn: "Add"
- assertVisible: "Buy milk"
- assertVisible: "Tomorrow"
```

Example (Playwright):

```ts
// <KEY>-<n> AC1: "<verbatim criterion>"
test('<key>-<n> ac1: <slug>', async ({ page }) => {
  await page.goto('/inbox');
  await page.getByRole('textbox', { name: 'Add a task' }).fill('Buy milk tomorrow');
  await page.getByRole('button', { name: 'Add' }).click();
  await expect(page.getByText('Buy milk')).toBeVisible();
});
```

**(role)** Commit only the flow file(s) on the ticket branch, using the repo's commit
convention (e.g. `test(<scope>): e2e flow for <KEY>-<n> AC1–AC3`), and push. Do not stage
anything else; if `git status` shows other changes in the worktree, leave them alone and mention
them. **(standalone)** Leave it uncommitted and tell the user the path.

## The report file: test-device.md

Path: `.delivery/jobs/<KEY>-<n>/round-<N>/test-device.md`. First line exactly `VERDICT: PASS`,
`VERDICT: CHANGES` or `VERDICT: BLOCKED` — the orchestrator and the approver read only that line
(and line 2 for BLOCKED) to route.

```
VERDICT: CHANGES
Blocked: AC3 needs a dev build with the new camera module   ← only when a criterion is BLOCKED

# Device test — <KEY>-<n>: <title> — round <N>

Target: <local web on branch X @ sha7 | Android emulator <avd>, dev build <id> | preview URL>
Driver: <tool>          Signed in as: <role> (test account from the local backend recipe)
Backend: <local, recipe ports> | none needed

| # | Acceptance criterion (verbatim) | Result | What I observed | Screenshots |
|---|---|---|---|---|
| AC1 | … | ✅ PASS | … | <KEY>-<n>-AC1-step-01 … 05 |
| AC2 | … | ❌ FAIL | Expected …; saw … | <KEY>-<n>-AC2-step-01 … 03 |
| AC3 | … | ⚠️ BLOCKED | No dev build with the new camera module | — |
| AC4 | … | ➖ NOT VERIFIABLE HERE | Covered by <test / CI job> | — |

## Steps
AC1
1. <action> → <what the screen showed> — <KEY>-<n>-AC1-step-01.png
2. …

## Console / logs / network
<none on the surfaces exercised | list with screen + message | not watched: reason>
Pre-existing noise: <one line, or none>

## Observations
Persistence: … · Negative case: … · Unhappy path: … · Small screen / offline: …

## E2E flow
<path> — replayed: PASS | FAIL (<why>) | not recorded: <reason> · commit <sha7> (role)

## Fixes needed (CHANGES only, most important first)
1. …
```

Verdict rules:
- `PASS` — every app-verifiable AC passed in this run, the flow replays, no defect seen.
- `CHANGES` — any FAIL, a new error caused by the change, or a failed replay: the builder must
  fix something.
- `BLOCKED` — no FAIL, but at least one AC could not be checked for a reason the builder can't
  fix (dev build, test account / local backend, key, physical device, paid service). Line 2:
  `Blocked: <reason>`. Not a code failure: the approver escalates it with one owner question.
- Any BLOCKED criterion adds the `Blocked: <reason>` line 2, whatever the verdict.

## Attaching screenshots to the ticket

1. List the issue's existing attachments; upload only names not already there (re-runs and later
   rounds must not duplicate files). For a later round, upload the new round's files; keep the
   same naming (add `-r<N>` before `.png` if a name would collide with an earlier round's file).
2. **API first** (the tracker connector or CLI, e.g. Jira REST attachments with a configured
   token). Many MCP connectors cannot upload files.
3. **Browser fallback:** a signed-in browser session (Claude in Chrome in the user's profile, or
   another driver that is signed in) — open the issue in a new tab, find the hidden attachment
   `<input type=file>`, set the files with the driver's file-upload action, confirm they appear,
   close the tab.
4. Neither works → say so in the report and the comment, and leave the files in the working
   folder for the owner.

## The per-AC step comment

One comment per round, on the ticket (Jira wikimarkup shown; Markdown for Linear / GitHub
Issues). Fixed heading for idempotency: search the comments for `Device test — <KEY>-<n> — round <N>`;
if found, edit or skip.

```
h2. Device test — <KEY>-<n> — round <N>

Result: *PASS* | *CHANGES* | *BLOCKED* · Target: <…> · Driver: <…> · E2E flow: {{<path>}}

h3. AC1 — <verbatim criterion> — PASS

# <action> — <KEY>-<n>-AC1-step-01.png
# <action> — <KEY>-<n>-AC1-step-02.png
# <result seen> — <KEY>-<n>-AC1-step-03.png

h3. AC2 — <verbatim criterion> — FAIL

# …
Expected: … · Saw: …

h3. Console / network

<none | list>
```

Jira can show an attached image inline with `!<filename>|thumbnail!`; use it if the project
likes inline images, otherwise filenames are enough. Never include credentials or the test
account's password. Never change the ticket's status.

## Linking from the PR

The PR does not get the images. Add the link to the ticket comment where the round's results
live: **(role)** put it in your one-line reply so the orchestrator includes it in the round
summary comment on the PR; **(standalone)** add it to the PR description under "How to test"
(`gh pr edit <n> --body-file …`, editing only that line) when the user agrees.

## Standalone report in the terminal

When not run by the orchestrator, also show the report in the conversation (same table), with a
plain verdict word for the user:

| File verdict | Say |
|---|---|
| `VERDICT: PASS` | **READY** |
| `VERDICT: CHANGES` | **NEEDS FIXES** — the list (plus what is blocked, if anything) |
| `VERDICT: BLOCKED` | **INCOMPLETE** — what must be unblocked (e.g. point at `setup-env` for a key) |
