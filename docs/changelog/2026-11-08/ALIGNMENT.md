# Alignment pass — what changed and what is still yours to decide

Five drafts were written in parallel. This pass makes them agree on one state schema, one
folder layout, one round order, one meaning of BLOCKED, one owner of `gh pr ready` and one
checks-script convention. Nothing outside this staging folder was touched.

## The decisions applied everywhere

1. **One state schema:** `skills/deliver/references/state-files.md` (`deliver-job/1` job.json,
   `deliver/1` orchestrator.json, stage names, messages). Added to job.json: `base_branch`,
   `pr` as `{number, url}`, `roles` (routed roles per round), `device_lane` (grant),
   `blocked`, and `services` entries with `pid` / `started_by` / `status`. Stage `review` was
   renamed `built`; new stages `testing` / `tested`. Subagents never write job.json; the worker
   copies their results in.
2. **One folder:** `.delivery/jobs/<KEY>-<n>/` with `plan.md`, `job.json`, `round-N/checks.md`,
   `round-N/test-functional.md`, `round-N/test-device.md`, `round-N/review-*.md`,
   `round-N/screenshots/`, `decision.md`, `walkthrough.md`.
3. **Round order:** gate → testers (functional + device; both may commit, `git pull --rebase`
   then `git push`) → reviewers in parallel on the round's final commit (UI/UX read that
   round's screenshots) → approver → explainer on APPROVE. New message `TEST r<N>`;
   `DEVICE r<N>` = tester-device only; `REVIEW r<N>` = reviewers only.
4. **BLOCKED:** tester-device writes `VERDICT: BLOCKED` + `Blocked: <reason>` when the builder
   can't fix the obstacle. Never sends FIX; the approver escalates with one owner question
   (or the owner's recorded deferral lets it approve).
5. **`gh pr ready`:** merge-ticket only, first sub-step of step 2, right before the re-gate.
6. **Checks script:** `scripts/workflow/checks` with `--report <path>` writes the round file
   (the gate passes `round-N/checks.md`); without it, it only prints (builder, hook, pre-merge
   re-gate).

## Per file

| File | Change |
|---|---|
| `workflows/ai-delivery-workflow.md` | §1 diagram (new round order, BLOCKED, draft→ready at close-out); §1b checks script row (`--report` vs local mode); §2 stage 4 (local mode, `job.json` stage `built`), stage 6 (BLOCKED as an escalation reason), stage 7 (`gh pr ready` by merge-ticket); §3 intro points to state-files.md, role table in round order, full folder list, new "Round order" subsection, rules (verdict words incl. BLOCKED and `checks.md` PASS/FAIL, BLOCKED rule), device proof steps (screenshots path, commit); §4 cycle order. |
| `skills/deliver/references/state-files.md` | Declared single source of truth; folder tree per decision 2; job.json fields added + "who decides / who reads" table; stage vocabulary (`built`, `testing`, `tested`; orchestrator `testing`); new "Round order and verdict words"; messages `TEST` / `DEVICE` / `REVIEW` redefined; `holdsSlot` list updated. Example keys `ABC-…`, neutral paths. |
| `skills/deliver/references/cycle.md` | Stage table rewritten for gate → TEST → (DEVICE) → REVIEW → APPROVE; BLOCKED never FIX; `gh pr ready` removed (merge-ticket does it); routing table with phases; gate uses `--report`; device lane granted with the testers; escalation resume path for BLOCKED; job folder path; neutral examples. |
| `skills/deliver/references/worker-brief.md` | Part-2 instructions TEST / DEVICE / REVIEW in order, copy `roles` / `device_lane` / `services` / `blocked` into job.json; local-mode checks; "phase 12" → Phase 8; stage `built`; full field list; example bodies. |
| `skills/deliver/references/bootstrap.md` | Checks script row notes `--report`; default cap 3 (same as wave-status); `built` stage for adopted work; neutral examples. |
| `skills/deliver/SKILL.md` | Description and cycle step 3–4 use the new order and BLOCKED rule; gate passes `--report`; merge-ticket marks ready; refs to sections 1–8; job folder path. |
| `skills/deliver/CHANGES.md` | Project name replaced by "the project where this was first used"; new order; alignment note. |
| `skills/implement-ticket/SKILL.md` | Local-mode checks; Phase 9 → stage `built`, schema pointer to state-files.md, new loop order; BLOCKED not the builder's; worker section tightened (297 lines). |
| `skills/implement-ticket/references/review-loop.md` | Rewritten: no own job.json default — table of fields from state-files.md; folder tree with verdict words; manual loop in the new order; stage `built`. |
| `skills/implement-ticket/references/verify-gates.md` | §0 documents `--report` vs local mode. |
| `skills/implement-ticket/references/ticket-record.md` | Owner-guide front matter `status: open \| done` (matches wave-status and deliver). |
| `skills/implement-ticket/CHANGES.md` | Open questions 1–2 marked settled; alignment note. |
| `skills/verify-ticket/SKILL.md` | Three verdicts PASS / CHANGES / BLOCKED with `Blocked: <reason>`; lane grant from `job.json.device_lane`; services listed in the report; BLOCKED status definition sharpened. |
| `skills/verify-ticket/references/e2e-and-reporting.md` | Report template, verdict rules, ticket comment result and terminal mapping use BLOCKED. |
| `skills/verify-ticket/references/mobile-drivers.md` | Missing dev build = owner action, not a builder fix. |
| `skills/verify-ticket/CHANGES.md` | Verdict bullets updated; alignment note. |
| `skills/merge-ticket/SKILL.md` | Step 2 starts with `gh pr ready`; re-gate in local mode; reads decision / worktree / PR / services from job.json; section refs fixed ("section 2 stage 7"). |
| `skills/merge-ticket/references/merge-checks.md` | Local-mode re-gate (no pre-merge round file); new "Draft → ready" section. |
| `skills/merge-ticket/references/after-merge.md` | Services from `job.json.services`; "mid-stage" = named job stages. |
| `skills/merge-ticket/CHANGES.md` | Alignment note. |
| `skills/wave-status/SKILL.md` | Job folder `<KEY>-<n>`; critical-bug rule matches its recipes (tracker-marked only); 300 lines. |
| `skills/wave-status/references/status-recipes.md` | Job folder path. |
| `skills/wave-status/CHANGES.md`, `skills/plan-waves/CHANGES.md` | Section refs reworded; alignment notes. |
| `agents/tester-functional.md` | Testers phase; job.json field names; simple pull-rebase-push (no retry against reviewers); routed except Spikes. |
| `agents/tester-device.md` | job.json fields + `device_lane.granted`; `round-N/screenshots/`; `VERDICT: BLOCKED` + `Blocked:` line, what counts as Blocked vs Fail; services listed for the worker; reply includes ticket comment URL. |
| `agents/reviewer-code.md`, `reviewer-security.md` | Reviewers phase; job.json field names; code reviewer also reviews the testers' new tests. |
| `agents/reviewer-ui.md`, `reviewer-ux.md` | Reviewers phase; job.json field names; `round-N/screenshots/`; tester-device always done first; code-only fallback when BLOCKED / not routed. |
| `agents/approver.md` | Reads `roles`, `blocked`, `owner_actions`; BLOCKED → escalate unless owner deferral recorded; worker (not orchestrator) posts decision. |
| `agents/explainer.md` | job.json field names. |
| `agents/CHANGES.md` | "How they fit" rewritten for the new order; questions 1, 2, 3, 5 settled. |

Unchanged: `implement-ticket/references/{pr-and-ticket,ticket-types}.md`,
`merge-ticket/references/proof-and-comments.md`, `verify-ticket/references/browser-drivers.md`,
`plan-waves/SKILL.md`, `plan-waves/references/tracker-recipes.md`. Project names now appear
only as marked examples (`ABC-27`, "e.g. Maestro", "Expo:" in a driver example).

## Open decisions for the owner

Each: **what the drafts do now** → my recommendation.

### Merge and permissions

1. **Who merges.** Bootstrap asks once; recommends "owner approves by merging" unless the merge
   command is already allowed. → Keep. If you want agent merges, allow `gh pr merge` yourself.
2. **Workers push and open draft PRs.** Asked once at bootstrap; recommended yes. → Yes.
3. **Ticket record close-out timing.** Written on the PR branch just before the merge; if
   already merged by hand, a tiny docs PR. → Keep; no direct commits to `main`.
4. **Updating other open PRs after a merge.** Merge `main` in (no force-push); rebase only if
   the repo says so. → Keep merge.
5. **Explainer commits after APPROVE.** Its docs commit is covered by the pre-merge re-gate.
   → Keep (it should describe the final code).

### Scheduling and capacity

6. **Default concurrency cap.** 3 when the project sets none (wave-status and deliver now
   agree). → 3 on a desktop, `--cap 2` on a laptop; write the number in `docs/workflow/README.md`.
7. **Reviewers after a tester CHANGES.** Reviewers still run, so one fix round covers
   everything. → Keep (fewer rounds against the 3-round cap).
8. **Device lane holds up reviewers.** A ticket waiting for the device lane also waits for its
   reviewers (they need the final commit and screenshots). → Accept for now; revisit if the
   queue gets long (option: run code/security early, UI/UX after).
9. **Standalone device-lane lock.** Orchestrator tracks the lane; standalone verify-ticket
   only checks for a booted simulator or busy dev ports. → Fine until you run tickets by hand
   in parallel; then add a `.delivery/device-lane` lock file.
10. **Idle workers waiting on you.** Kept open; released only if memory is tight. → Release
    after ~1 hour waiting; they can be resumed.
11. **Starting `/deliver` from phrases** ("run the factory"). Allowed. → Make it manual-only
    (`disable-model-invocation: true`) until you trust it.
12. **Stalled job folder threshold.** 7 days with no file change. → Lower to 2 days.

### Ticket types and waves

13. **Jira "Task" → type.** Not guessed; shown as `Task?` and flagged (unless the project
    states a mapping). → Map Task → Chore in the project's workflow doc.
14. **Setting types in Jira.** A `type:<name>` label rather than changing the issue type.
    → Keep the label.
15. **Critical bug signal.** Only a tracker-marked one (Highest/Blocker priority or
    `severity:critical`) jumps the window. → Keep; use the `severity:critical` label.
16. **"Plan exists" threshold.** A few new unwaved tickets still count as `exists` (reported).
    → Keep, and run `/plan-waves` when more than ~3 are unwaved.
17. **Spike records.** Never merged as product code; record lands as a docs-only change, asking
    if the workflow doc is silent. → Land it as docs-only, always.
18. **Projects on the old ticket layout** (intent/spec/plan/verification folders) keep it.
    → Switch per project when convenient; no rush.

### Proof and labels

19. **Label while waiting for your merge.** `needs-human`. → Use a separate `ready-to-merge`
    label so merges don't mix with real escalations.
20. **Cost script.** Assumed: takes the ticket key, prints a total; otherwise "not tracked".
    → Name it `scripts/workflow/cost` in `docs/workflow/README.md`.
21. **E2E flows: one per AC or per ticket.** Follows the folder's convention, else one per AC.
    → One per ticket unless ACs are independent flows.
22. **Checks script for the first project.** Missing; the gate runs CI's commands meanwhile.
    → File a small chore to add it, with the `--report` mode.

### Agents

23. **tester-device tool list.** Inherits all session tools (minus Agent, NotebookEdit).
    → Keep; tighten once the MCP set is stable.
24. **Approver's always-escalate list.** Owner action, human-only or BLOCKED check, scope/AC
    change, security exception, deploy/infra/billing. The reference factory also escalates on
    every migration and new dependency. → Add migrations on live data; skip new dependencies
    (the security reviewer covers risky ones).

## Follow-up pass

Quick start, file mode, skill wiring, context limits, and one correction. Staging only;
nothing installed.

### Files

| File | Change |
|---|---|
| `workflows/ai-delivery-workflow.md` | New "Quick start (existing projects)"; §2 stage 0 and 2 mention `/deliver <doc>` and the local backlog; §1b "Context limits" row; §4 new "Context limits" subsection (windows, compact instructions, hooks, what's impossible, subagent nesting limits) |
| `skills/deliver/SKILL.md` | File mode in description, argument hint, modes table, argument parsing table; bootstrap 2b (import) and 2c (context limits); local-backlog offer; topology corrected; watcher launched with the smaller window; cycle re-reads state from files (284 lines) |
| `skills/deliver/references/import-tasks.md` | **New.** Document → tickets, dedupe, approval, PM-tool or local-backlog creation, local ticket format and rules, mapping file |
| `skills/deliver/references/context-limits.md` | **New.** Supported controls, recommendations, bootstrap step 2c, worker window, subagent limits |
| `skills/deliver/references/{bootstrap,state-files,worker-brief}.md` | No-tracker row + context-limits row; `tracker.kind: local`, `import` block; worker "Context" + "Tracker" sections and window note |
| `skills/{wave-status,plan-waves,merge-ticket}/SKILL.md`, `skills/implement-ticket/SKILL.md` + `references/pr-and-ticket.md` | Local-backlog notes where tickets are read / written |
| `skills/implement-ticket/SKILL.md` + `references/ticket-types.md` | Bug reproduce-first uses `test-driven-development` |
| `skills/verify-ticket/SKILL.md` + `references/browser-drivers.md` | `playwright-cli` + `webapp-testing` preferred for web; global install needs owner OK; "Every web run" checks and E2E stability merged from ecc |
| `skills/senior-pr-reviewer/` | **New in staging** (copy of the owner's skill, improved: loop output mode with `VERDICT:` header, confidence levels, severity crosswalk, noise rules, comment hygiene) + `CHANGES.md` |
| `agents/*.md` | `skills:` preloads (security-review, test-driven-development, senior-pr-reviewer, verify-ticket); security "On top of…" checklist; functional-tester method + addendum; UI/UX optional aids + fallback checklists; `autoCompactWindow: 200000` on all eight |
| `CHANGES.md` in deliver, wave-status, plan-waves, merge-ticket, implement-ticket, verify-ticket, agents | "Follow-up pass" sections with "Taken from <skill>" provenance |

### Correction

Subagents **can** spawn subagents (3 levels by default, 20 at once per session). The deliver
topology and its CHANGES no longer say otherwise. Builders stay Orca workers: only a full
session can ask the owner questions, and each ticket needs its own worktree session.

### New owner decisions

25. **Local backlog landing.** The import and later wave changes land through a docs PR you
    merge; tickets start only once `backlog.md` is on `main`. → Keep (direct commit only on a
    brand-new repo, if you say so at approval).
26. **Local status on `main`.** Only To Do / Done / Won't do; In Progress / In Review derived
    from branches, PRs, job folders, so workers never edit `backlog.md`. → Keep (avoids merge
    conflicts and a dirty main checkout).
27. **No-PM-tool default.** Bootstrap offers GitHub Issues (if `gh` works) or the local backlog.
    → GitHub Issues when the repo is on GitHub; local backlog for offline/private experiments.
28. **Context windows.** Orchestrator 300k, workers 400k, subagents 200k; `# Compact
    instructions` in each project's `CLAUDE.md`; optional SessionStart(`compact`) hook. → Yes to
    the windows and the CLAUDE.md section; the hook only if compactions turn out to lose state.
29. **`autoCompactWindow` in agent frontmatter** needs v2.1.296+ (this machine: 2.1.319). →
    Keep; remove the line on machines with older Claude Code.
30. **Global `@playwright/cli`.** Not installed by any skill; asked first. → Install it once
    yourself (`npm install -g @playwright/cli@latest`) if you want it on every web project.
31. **Replace the installed `senior-pr-reviewer`** with the staged copy. → Yes (standalone
    behaviour unchanged apart from confidence lines).
32. **Design plugin skills** are optional aids, not preloaded. → Keep unless the design plugin
    is guaranteed on every machine.

## Decisions applied (owner accepted all recommendations, 2026-11-08)

Paths are relative to this staging folder. CHANGES.md files got an "Owner decisions applied" section where their skill changed.

1. Merge path default = owner approves by merging; agent merges only if the owner allowed the merge command — changed: workflows/ai-delivery-workflow.md (1b, stage 7), skills/deliver/SKILL.md, skills/deliver/references/{bootstrap,cycle,state-files}.md, skills/merge-ticket/SKILL.md, skills/merge-ticket/references/merge-checks.md
2. Workers push and open draft PRs — no change needed
3. Ticket record close-out timing — no change needed
4. Merge `main` into other open PRs — no change needed
5. Explainer commits after APPROVE — no change needed
6. Default concurrency cap = 2 when none is written (3 on a desktop if written in `docs/workflow/README.md`) — changed: workflows/ai-delivery-workflow.md, skills/deliver/SKILL.md, skills/deliver/references/{bootstrap,state-files}.md, skills/wave-status/SKILL.md, skills/wave-status/references/status-recipes.md, skills/plan-waves/SKILL.md
7. Reviewers still run after a tester CHANGES — no change needed
8. Device lane holds up reviewers — no change needed
9. Standalone device-lane lock — no change needed
10. Release workers after ~1 hour waiting on the owner (resumable) — changed: workflows/ai-delivery-workflow.md (§4), skills/deliver/SKILL.md, skills/deliver/references/{cycle,state-files,worker-brief}.md
11. `/deliver` manual-only (`disable-model-invocation: true`, phrase triggers removed) — changed: skills/deliver/SKILL.md, workflows/ai-delivery-workflow.md (quick start)
12. Stalled job folder threshold 2 days — changed: skills/wave-status/SKILL.md, skills/wave-status/references/status-recipes.md, skills/deliver/references/cycle.md, workflows/ai-delivery-workflow.md (§4)
13. Map Jira Task → Chore in the project's workflow doc — changed: workflows/ai-delivery-workflow.md (1b row, §5), skills/deliver/references/{bootstrap,state-files}.md, skills/wave-status/references/status-recipes.md, skills/plan-waves/SKILL.md, skills/implement-ticket/SKILL.md (skills still never guess; they propose the mapping line)
14. Types as a `type:<name>` label — no behaviour change; wording aligned in workflows/ai-delivery-workflow.md (§5) and skills/plan-waves/SKILL.md
15. Critical bug = tracker-marked, `severity:critical` label — no behaviour change; `severity:critical` named as the recommended signal in workflows/ai-delivery-workflow.md (§5), skills/deliver/references/{bootstrap,state-files}.md
16. Run `/plan-waves` when more than ~3 tickets are unwaved — changed: workflows/ai-delivery-workflow.md (§2), skills/wave-status/SKILL.md, skills/plan-waves/SKILL.md (`exists` ≤ ~3 unwaved, else `partial`)
17. Spike record always lands as docs-only — changed: workflows/ai-delivery-workflow.md (§5), skills/implement-ticket/SKILL.md, skills/implement-ticket/references/ticket-types.md, skills/wave-status/SKILL.md
18. Old ticket layout switches per project — no change needed
19. Separate `ready-to-merge` label while waiting for the owner's merge; `needs-human` only for real escalations — changed: workflows/ai-delivery-workflow.md, skills/deliver/SKILL.md, skills/deliver/references/{bootstrap,cycle,state-files,import-tasks}.md, skills/merge-ticket/SKILL.md, skills/merge-ticket/references/{merge-checks,proof-and-comments}.md, skills/wave-status/SKILL.md ("Needs the owner" → "Ready for your merge"), skills/wave-status/references/status-recipes.md (`needs_human.ready_to_merge`)
20. Cost script named `scripts/workflow/cost` — changed: workflows/ai-delivery-workflow.md (1b), skills/deliver/references/{bootstrap,state-files}.md, skills/merge-ticket/SKILL.md, skills/merge-ticket/references/proof-and-comments.md
21. One E2E flow per ticket unless ACs are independent flows — changed: workflows/ai-delivery-workflow.md (§3), skills/verify-ticket/SKILL.md, skills/verify-ticket/references/e2e-and-reporting.md, agents/tester-device.md
22. Small chore to add the checks script with `--report` — changed: skills/deliver/references/bootstrap.md (proposes that Chore; filing it stays an owner-approved tracker action)
23. tester-device tool list — no change needed
24. Approver also escalates on migrations on live data, not on new dependencies — changed: agents/approver.md, workflows/ai-delivery-workflow.md (stage 6)
25. Local backlog lands through a docs PR — no change needed
26. Local status on `main` only To Do / Done / Won't do — no change needed
27. No PM tool → GitHub Issues when the repo is on GitHub and `gh` works, local backlog otherwise — changed: workflows/ai-delivery-workflow.md (quick start, stage 0), skills/deliver/SKILL.md, skills/deliver/references/bootstrap.md
28. Windows + `# Compact instructions` yes; SessionStart hook only if compactions lose state — changed: workflows/ai-delivery-workflow.md (1b, §4), skills/deliver/SKILL.md (2c), skills/deliver/references/{bootstrap,context-limits}.md
29. `autoCompactWindow` in agent frontmatter — no change needed
30. Owner installs `@playwright/cli` globally once; skills never install it — changed: skills/verify-ticket/SKILL.md, skills/verify-ticket/references/browser-drivers.md
31. Staged senior-pr-reviewer replaces the installed one — no content change (noted in skills/senior-pr-reviewer/CHANGES.md; installation is a separate step)
32. Design plugin skills stay optional aids — no change needed
