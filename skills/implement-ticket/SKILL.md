---
name: implement-ticket
description: >-
  Build one tracker ticket in any repo, from intake to a draft PR ready for review: read
  the ticket, its type (Feature, Bug, Chore, Spike) and its acceptance criteria word for
  word, explore the codebase, surface the real design decisions for the human to choose,
  write the ticket record and task plan, build task by task, write an owner guide for every
  human setup step, run the project's checks script, then commit, push, open a draft PR,
  move the ticket to review and hand off to the review and test loop. Also resumes a ticket
  whose review round came back with CHANGES. Use this whenever the user names an issue key
  or ticket ("do ABC-123", "implement #412", "start the next ticket", "pick this up", "fix
  this bug ticket", "run the spike"), says "implement the ticket" / "take this from Jira to
  PR", asks for "the full process" or "the usual workflow" on a ticket, asks to resume a
  part-done ticket or to address review verdicts, or is dispatched as a worker for one
  ticket — even when they do not spell out the phases. Prefer this over ad-hoc coding on
  any ticketed work, because the type-specific intake, the decision checkpoint, the ticket
  record and the project's own checks are easy to skip without it.
---

# Implement a ticket

This skill is the **build** half of the delivery workflow
(`~/.claude/workflows/ai-delivery-workflow.md`, stage 4). It ends with a draft PR and a
hand-off. Judging the work (gate, testers, reviewers, approver, explainer) is the review and
test loop's job, not yours: you build, the loop judges. Read the workflow file once if it is
installed; this skill is self-contained when it is not.

Nine phases, in order. Each kills a class of rework that is expensive later: decisions
before code, record before plan, plan before edits, checks before the PR.

Adapt the depth to the ticket. A one-line copy fix does not need a 10-task plan; it still
needs the checks and a ticket record. Never silently drop a phase — if one genuinely does
not apply, say so in one line and move on. Track the phases in your todo list.

**Two human checkpoints.** Everything else runs without asking:

1. **Phase 3/4 — owner decisions.** You stop and the owner picks from your options. A
   low-risk ticket with no real design fork skips the questions (say so in one line).
2. **Phase 4 — owner accepts the ticket record** before any code, for medium and high risk.

Pushing and opening a **draft** PR is part of the build and needs no extra go-ahead (a
draft is not a merge request). Merging is never part of this skill.

## Learn this project first

Before Phase 1, spend a minute on the ground rules of the repo you are in. They override
every default here:

- **A project workflow doc** (for example `docs/workflow/README.md`, linked from
  `CLAUDE.md`). If it prescribes something different from this skill — where ticket records
  live, risk tiers, readiness rules, status mapping, the checks command — **the repo wins**.
  Otherwise use this skill's defaults (the layout in `references/ticket-record.md`).
- `CLAUDE.md` / `AGENTS.md` — architecture, invariants, naming, branch and commit format.
- `README.md`, `CONTRIBUTING.md`, `docs/setup/` — how to run the app and the tests.
- **The checks script** (default `scripts/workflow/checks`, `.sh` / `.ps1`; you run it without
  `--report`, its local mode). If absent: manifest scripts and CI — **CI defines "green"**.
- `docs/actions/` — how owner guides are written and whether a script generates the to-do
  list.
- `git log --oneline -15` and a recent merged PR — the real commit and PR style.

Say in one line what you learned (checks command, branch/commit format, tracker, record
location) so a wrong reading surfaces before any code is written.

---

## Phase 1 — Intake

Fetch the issue rather than trusting the branch name or a paraphrase.

- **Jira** (Atlassian MCP): cloud id via `getAccessibleAtlassianResources`, then
  `getJiraIssue`. **Local backlog.** When the project uses the local backlog (no PM tool; `docs/tickets/backlog.md`, IDs `T-001…`, format in the `deliver` skill's `references/import-tasks.md`), read the ticket's entry from that file instead (blockers Done = their entries say
  `Status: Done`) and **write nothing to it**: In Progress / In Review are derived from your
  branch and PR, merge-ticket sets Done, and comments go on the PR. **Linear / GitHub / other:** its MCP tool, or `gh issue view <n>`. No
  tracker tool: ask the human to paste the ticket.
- Read the description, every AC, the comments (late changes of mind), linked issues and any
  attached spec or design.

**Read the ticket type** (a `type:` label, or the issue type through the project's mapping,
e.g. Jira Task → Chore): **Feature, Bug, Chore or Spike**.
It decides how every later phase adapts — see the table below and
`references/ticket-types.md`. Missing or obviously wrong (a "bug" that is new behaviour) → ask.

**Copy the acceptance criteria verbatim** as a checklist; the reviewers and testers judge
against this exact list. No explicit AC: derive a checklist and confirm it in Phase 3.
Beside any criterion that cannot be observed as written ("loads fast"), propose a testable
version and confirm it — never swap in your own target silently. Check the type's required
content is there (Bug: steps, expected vs actual, severity; Spike: question, options, time
box, what "done" produces). Missing pieces are Phase 3 questions.

**Check that it may start.** Every `is blocked by` issue must be Done and the repo's
readiness rule met; otherwise stop and report what is missing. Do not start "just the parts
that don't need it".

**Pick the risk tier** from the workflow doc (default: high = auth, data access rules, AI /
prompt surfaces, quotas, sync, billing, account deletion / export, migrations on live data;
low = small and touching none of those; medium = everything else). Risk is separate from
type: a small bug in auth is still high risk.

Move the ticket to its in-progress status and re-read it to confirm. Report: one paragraph
on what it asks, type, risk tier, the AC checklist.

### How the type changes the flow

| | Feature | Bug | Chore | Spike |
|---|---|---|---|---|
| Branch / commit | `feat/…` · `feat(scope):` | `fix/…` · `fix(scope):` | `chore/` `refactor/` `docs/` `build/` `ci/` + matching commit type | `spike/…` (never merged as product code) |
| Questions | Real design forks | Only if expected behaviour is unclear | Rarely | The options, if the ticket leaves them open |
| Record | Full | Full + **root cause** | Short; AC "no behaviour change" | Findings + recommendation |
| Build | Task by task | **Reproduce with a failing test first**, then the smallest fix for the cause | Prove no behaviour change | Investigate within the time box; prototypes stay on the branch |
| Ends with | Draft PR → loop | Draft PR → loop | Draft PR → loop | Findings PR / record; follow-up tickets proposed; owner decides |

Branch format follows the repo (e.g. `<type>/<key>-<n>/<slug>`); if you are already on a
branch that names this ticket, stay on it.

## Phase 2 — Explore the codebase

Find every surface the change touches before deciding anything:

- The entry point (route, screen, command, endpoint, job) and the nearest sibling feature
  that already does something similar — matching a pattern beats inventing one.
- The data path end to end: schema/model, data layer, migrations, serialization, cache, sync.
- Authorization and validation: where checks live and where the real enforcement boundary
  is (often not the UI).
- Existing tests in the area and their layer — that tells you where yours belong.
- Config, feature flags, environment variables. Any human setup the change will need.
- **Bug:** the code path of the reported behaviour; where the failing test will sit.

Report a short file map — path → role in the change — plus anything surprising.

## Phase 3 — Ask questions

This is where the skill earns its keep. Identify decisions where two reasonable
implementations would produce materially different code, and put them to the owner with
**concrete options, trade-offs and your recommendation first**.

**First, list your assumptions** — numbered, each tagged with its source (ticket, code, or
your guess). End with: "Correct me now or I proceed with these." A guess that is also a real
fork becomes a question.

Use `AskUserQuestion` (or, as an Orca worker, the orchestration `ask` — see below), at most
~4 questions, recommendation as option 1 labelled `(Recommended)`. Good candidates: extend a
module vs add one, where a permission or validation gate belongs, database vs application
logic, schema change vs derive on read, how much adjacent refactoring, an AC that conflicts
with the data model.

Do not ask what you can determine yourself or what the repo's docs already settle. A
low-risk ticket with nothing to decide: say "no design forks" and go to Phase 4.

## Phase 4 — Decisions and the ticket record

Wait for the answers. Restate each decision in one line; if an answer opens a new fork, ask
it now.

**Write the ticket record** — one file, `docs/tickets/<KEY>-<n>.md` by default (the repo's
workflow doc wins if it says otherwise). Template, the mandatory links block (ticket link,
every PR, related tickets), per-type content and the folder form for large high-risk tickets
are in **`references/ticket-record.md`**. It holds intent, AC verbatim, design, the decisions
table (who / when) and an empty Outcome section. No PR exists yet: write `PRs: (pending)`.

**Acceptance (medium / high risk):** summarize the record with its assumptions and open
points, ask the owner to accept or change it, and **end your turn**. No plan or code in the
turn that wrote the record; answers to Phase 3 questions are not acceptance of the finished
record. Low risk proceeds without waiting. (A worker dispatched with an already-accepted
record skips this.) Post the decisions to the ticket as one comment if the workflow doc asks.

**Owner setup steps.** Every human action the ticket needs (create a project, push a
migration, set a secret, deploy a function, configure a third-party service) becomes a guide
in `docs/actions/<name>.md` **with front matter** (`status`, `tickets`, `order`, `estimate`),
then regenerate the owner to-do list with the project's script — never hand-edit the shared
list. Format in `references/ticket-record.md`. Secret names only, never values. Link the
guide in your message and on the ticket.

## Phase 5 — Plan

Write the task plan to the **gitignored working folder**:
`.delivery/jobs/<KEY>-<n>/plan.md` (add `.delivery/` to `.gitignore` if the repo lacks it,
and say so). It is working state, not needed after merge; the record keeps the *why*.

- Goal, file map, `### Task N` sections with `- [ ]` steps, test per task, risks and rollback.
- **Size:** each task fits one focused session, touches ~5 files or fewer, leaves the tree
  buildable. Order by dependency. Name the files each task touches so overlap is visible.
- If the repo mandates a test for a class of change (data-access isolation, migration,
  contract), name it in the task.
- Call out anything irreversible or shared: migrations, generated files, public contracts.
- **Bug:** task 1 is always "failing test that reproduces the report".

A trivial ticket may keep a 3-line plan in chat; say so.

## Phase 6 — Build

Work task by task, smallest coherent step first. After each task run the fast checks
(typecheck/compile plus the relevant test file) so a break is attributable.

Write code that reads like the code around it. Respect the repo's non-negotiables even when
a shortcut would work. Type-specific rules (`references/ticket-types.md`):

- **Bug:** reproduce first with the `test-driven-development` skill (red → green): the test
  must fail for the reported reason before you fix anything. Record the root cause; fix the
  cause, not the symptom, and nothing else.
- **Chore:** no behaviour change — existing tests untouched and green, no snapshot or
  contract changes unless the ticket says so.
- **Spike:** stop at the time box. Findings and recommendation go in the record.

**Helper agents.** Independent parts may go to subagents with **disjoint file ownership**:
no shared files, no git commands, each told exactly which paths it owns. You integrate.

**The plan was wrong?** Say so, adjust the plan, and add a dated deviation to the record. If
it changes behaviour, a contract or scope beyond what the owner accepted, stop and ask.

## Phase 7 — Checks and self-check

**Run the project's checks script in local mode** (default `scripts/workflow/checks` with no
`--report`: it only prints the result, so it never touches the loop's round files; the gate
passes `--report round-N/checks.md` itself). No script → the gate commands from the repo docs
and CI, in CI order. Discovery, failure recipes and gates that cannot run here:
**`references/verify-gates.md`**. Everything green, or the gap named explicitly. Paste real
output for failures; never describe a run you did not do.

**Quick self-check — read your own diff** (`git diff`, `git status` for untracked files) for
what checks cannot see: debug logging, commented-out code, stray `any` / `unwrap` / skipped
tests, unresolved TODOs, a secret or internal hostname, files outside the ticket's scope, a
README that now lies. Fix and re-run. This is not the review — the loop's reviewers do that.

## Phase 8 — Commit, push, draft PR

Details and templates: **`references/pr-and-ticket.md`**.

1. Commit in the repo's format with the type's prefix and any required trailers.
2. Push and open a **draft PR**. Its description replaces a separate build note: **what was
   built, main files, decisions, how to test** — plus the link to the ticket record. Report
   the PR link.
3. **Add the PR link to the record's links block** (`PRs:`), commit, push.
4. Comment on the ticket (PR link, one-line summary) and move it to **In Review** (or the
   repo's review status — read the transitions, never use Done). Re-read to confirm.

**Spike:** the draft PR carries the record and prototypes, marked "not for merge as product
code"; propose follow-up tickets in the record and the ticket comment for the owner. Only a
code reviewer is routed (reads the findings). The record always lands as a docs-only change (a
separate `docs/…` PR with only the record), never with the prototypes.

## Phase 9 — Hand off to the review and test loop

Write the stage file `.delivery/jobs/<KEY>-<n>/job.json` with stage `built` and round 1. Its
schema (`deliver-job/1`) is defined once, in the `deliver` skill's
`references/state-files.md`; the fields you fill and the routing flags are summarised in
**`references/review-loop.md`**. Then **stop** with a one-line report:

> `<KEY>-<n> built · <type> · <risk> risk · draft PR <url> · checks PASS · stage built r1`

The loop runs in a fixed order — **gate → testers (functional, device) → reviewers in
parallel on the round's final commit → approver → explainer** — driven by the orchestrator
`/deliver`. Without it, the user runs the same order by hand (`references/review-loop.md`);
mention this in one line when no orchestrator dispatched you.

---

## Resuming with CHANGES verdicts

When resumed for a ticket whose `.delivery/jobs/<KEY>-<n>/round-N/*.md` files contain
`VERDICT: CHANGES` (or a failed `checks.md`):

1. Read every verdict file of the latest round. List each requested change. A tester-device
   `VERDICT: BLOCKED` is not yours to fix (the approver escalates it to the owner).
2. **Fix only what they ask.** No drive-by improvements. A request you disagree with: make
   the case in one line in your report, don't silently skip it.
3. Re-run the checks (local mode) and the self-check; commit
   (`fix(scope): address review round N`), push.
4. Bump the round in `job.json` (`round: N+1`, stage `built`); stop with the one-line report.

**Max 2 extra rounds** (rounds 2 and 3). If round 3 still has CHANGES, do not fix again: set
stage `escalated`, write the one specific question for the owner, and stop.

## Running as an Orca worker (or any parallel worker)

When `/deliver` dispatched you through the `orchestration` skill (a prompt with Task and
Dispatch IDs), or a coordinator put you in a worktree with a brief, **the brief is your
contract**:

- Edit only the paths the brief says you own. A needed change elsewhere is an escalation, not
  an edit. Shared files (manifest, lockfile, build config, root layout, shared schemas)
  follow the brief's coordination rule. Never hand-merge a lockfile: rebase and reinstall.
- **Owner questions and record acceptance (medium/high) go through the orchestration `ask`**,
  never `AskUserQuestion`; answers come back the same way. Ask only what an accepted record
  doesn't settle; skip acceptance if the brief says the record is already accepted.
- Run every phase through Phase 9 (checks, commit, push, draft PR, record link, In Review,
  `job.json`), then follow the brief's stage instructions. **Never merge.**
- Finish each instruction with the **structured worker report** (`worker_done`); format in
  `references/review-loop.md`.

## References

- `references/ticket-types.md` — Feature / Bug / Chore / Spike in detail. Read at Phase 1.
- `references/ticket-record.md` — record template, links block, folder form, plan file,
  owner-guide front matter. Read at Phase 4–5.
- `references/verify-gates.md` — the checks script, discovering gates, failure recipes.
  Read at Phase 7; useful during Phase 6.
- `references/pr-and-ticket.md` — commit, draft PR body, ticket comment and transition.
  Read at Phase 8.
- `references/review-loop.md` — `job.json` fields, the round order run by hand, risk routing,
  resuming rounds, worker report. Read at Phase 9 and on resume.
