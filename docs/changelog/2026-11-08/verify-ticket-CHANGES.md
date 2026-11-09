# verify-ticket — what changed

**Why:** the new delivery workflow has a **tester-device** role. It runs the app, walks every
acceptance criterion like a user, screenshots each step, records a replayable E2E flow and puts
the proof on the ticket. This skill is now the engine of that role. You can still run it on your
own ("verify ABC-12 in the app"). Where the two modes behave differently, the skill marks it
**(role)** or **(standalone)**.

## What's new

1. **Mobile apps, not just web.** It can drive a simulator/emulator through a mobile-automation
   MCP, Maestro, or the platform tools directly (`adb` for Android, `xcrun simctl` for iOS).
   - It installs the right dev build from `docs/setup/dev-builds.md`.
   - If the ticket added a native module and there's no matching build, it stops as BLOCKED
     instead of crashing the app.
   - It says plainly that iOS needs a Mac.
   - Web drivers are unchanged. The driver choice stays tool-agnostic.
2. **Device lane.** Only one ticket uses the simulator and dev ports at a time. When the
   orchestrator runs it, the orchestrator has already given it the lane. On its own, it checks
   that nothing else holds the lane first. At the end it stops everything it started: dev
   server, simulator, local backend.
3. **Local backend and test account.** It follows `docs/setup/local-backend.md`: port
   overrides, seed data, the test account, and a local mail catcher for login codes. It never
   uses anyone's real inbox. `.env.test` still works as a fallback.
4. **A screenshot for every step,** not one per criterion. They are named
   `<KEY>-<n>-AC1-step-01.png` … and saved in `.delivery/jobs/<KEY>-<n>/round-N/screenshots/` (the layout defined in the `deliver` skill's `references/state-files.md`), which is never
   committed. Bug tickets get before/after screenshots.
5. **Replayable E2E flow.** The path it walked is saved as a flow (Maestro or Playwright,
   whatever the project uses) and replayed once to confirm it passes. In the role it commits
   only that test file. On its own it leaves the file uncommitted.
6. **Report file.** It writes `round-N/test-device.md`, starting with `VERDICT: PASS`,
   `VERDICT: CHANGES` or `VERDICT: BLOCKED`, plus the per-AC table, the steps, console/log/network errors, and the
   E2E result.
7. **Proof on the ticket.** It uploads the screenshots (through a signed-in browser if the
   tracker API can't upload) and posts one comment per round listing each AC's numbered steps
   with the matching screenshot names. The PR links to that comment. Running it again doesn't
   create duplicates.

## Kept

- "Report only what was observed." A pass you didn't watch never counts.
- The four statuses (PASS / FAIL / BLOCKED / NOT VERIFIABLE HERE) and the pass/fail table.
- Writing down the expected result before acting.
- Checking persistence, the negative case and the unhappy path.
- Never fixing code, never printing credentials, never touching production without a
  go-ahead, never changing ticket status.
- The per-driver browser reference (lightly edited: per-step screenshots, the mail catcher, the
  upload fallback).

## Changed or removed

- **Verdict words.** READY / NEEDS FIXES / INCOMPLETE are no longer the file verdict. The file
  says PASS, CHANGES or BLOCKED (see "Alignment pass" below). On its own, the skill still shows
  READY / NEEDS FIXES / INCOMPLETE to you in the terminal.
- **Posting to the ticket** used to be "offer only". In the role it now always posts; on its
  own it posts when the project's workflow puts device proof on the ticket, otherwise it offers.
- **New references:** `references/mobile-drivers.md` and `references/e2e-and-reporting.md`
  (flow recording, report template, ticket comment, upload).
- The example key `VD-81` is replaced with `<KEY>-<n>` / `ABC-12`. The description is
  rewritten so it also triggers on "verify in the app / on the simulator", "device test" and
  "step-by-step screenshots".

## Open questions for you

1. **BLOCKED → CHANGES.** The workflow allows only PASS or CHANGES. I map a blocked criterion
   to CHANGES plus a `Blocked: needs owner` line so the approver can escalate. Would you rather
   have a third verdict word, or is this enough?
2. **Lane mechanism.** The workflow says "one shared device lane" but doesn't define a lock.
   On its own, the skill detects a busy lane by looking for a booted simulator or occupied dev
   ports. Do you want a real lock file (e.g. `.delivery/device-lane`) defined in
   `docs/workflow/README.md`?
3. **Who commits the E2E flow.** In the role the tester commits the flow file on the ticket
   branch itself. If you'd rather the builder commit it (to keep testers out of git), the
   orchestrator would need to pick the file up.
4. **One flow per AC or per ticket?** I default to the existing folder's convention, else one
   per AC. Do you have a preference?

## Alignment pass (after all drafts were written)

- Open question 1 is **settled** with a third verdict word: `test-device.md` starts with
  `VERDICT: PASS`, `VERDICT: CHANGES` (the builder must fix something) or `VERDICT: BLOCKED`
  (a criterion can't be checked for a reason the builder can't fix: missing dev build, test
  account / local backend, physical device). Line 2 is `Blocked: <reason>`. BLOCKED never goes
  back to the builder; the approver escalates it. The old `needs owner|builder` split is gone.
  Standalone terminal words: PASS → READY, CHANGES → NEEDS FIXES, BLOCKED → INCOMPLETE.
- In the role, the lane grant is read from `job.json.device_lane` (schema in the `deliver`
  skill's `references/state-files.md`); started/stopped services are listed in the report.
- Question 3 is settled as drafted: the tester commits the flow itself (`git pull --rebase`,
  then `git push`); reviewers start only after the testers.

## Follow-up pass

- **Preferred web drivers:** `playwright-cli` (Microsoft — driving, step screenshots, console /
  network, tracing and video, test generation) and `webapp-testing` (Anthropic — server
  lifecycle helper, console-log capture, screenshots). Claude in Chrome, Playwright MCP, Orca's
  browser and Chrome DevTools MCP are fallbacks. Step 3 tells the tester to load the two skills
  for web projects (the tester-device agent preloads only verify-ticket, since frontmatter can't
  be conditional). A global `npm install -g @playwright/cli@latest` needs the owner's OK.
- `references/browser-drivers.md`: new sections "Every web run", "Preferred: playwright-cli",
  "Preferred: webapp-testing", "Keeping the E2E flow stable"; driver order rewritten.
- Taken from `ecc:browser-qa`: smoke pass per touched page (new console errors, 4xx/5xx), the
  three breakpoints 375 / 768 / 1440 px, dark mode, axe-core scan with the "covers ~30–40% of
  WCAG, keyboard pass is the manual half" caveat, "no baseline → visual comparison not
  performed", read-only blast-radius rule for non-local URLs, redacting screenshots. Not taken:
  its SHIP / DO-NOT-SHIP verdict (we keep PASS / CHANGES / BLOCKED) and its Claude-in-Chrome-first
  preference.
- Taken from `ecc:e2e-testing`: stable locators (role / test id), no fixed timeouts,
  independent flows, a `--repeat-each=3` flake check, never quarantining a new flow,
  `trace: 'on-first-retry'` as the suggestion when the repo has no config. Not taken: Page
  Object Model scaffolding and CI workflow templates (repo decisions).

## Owner decisions applied (2026-11-08, all recommendations accepted)

- **#21:** E2E shape is **one flow per ticket**, split per AC only when the ACs are independent
  flows or the folder's convention says so (SKILL step 7, e2e-and-reporting). Open question 4 settled.
- **#30:** skills never install `@playwright/cli` globally; if missing they fall back to the next
  driver and suggest the owner run `npm install -g @playwright/cli@latest` once (SKILL,
  browser-drivers). This replaces "needs the owner's OK" above.
- **#9:** kept — no device-lane lock file until tickets run by hand in parallel.
