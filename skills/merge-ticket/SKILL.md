---
name: merge-ticket
description: >-
  Close out a ticket whose PR is ready, end to end: mark the draft PR ready for review, re-sync
  the branch with main and re-run the
  project's checks script (refusing on red), close the ticket record (links block, Status: Merged,
  Outcome), merge by the project's chosen merge path — or hand the owner the exact merge command
  and detect the merge afterwards — verify any post-merge deploy, post the proof where it belongs
  (AC results and step-by-step screenshots on the tracker ticket; review rounds, approver
  decision, CI and agent cost on the PR), move the ticket to Done, note deferrals on their
  follow-up tickets, re-sync every other open PR with main, and clean up the worktree, local
  branch, leftover services and the ticket's working folder. Use whenever the user or the
  delivery orchestrator says "merge the ticket", "merge ABC-118", "merge and close it out",
  "ship it", "I merged it — update the ticket", "close out the ticket", "update Jira with the
  PR", "clean up after the merge", or asks to move a ticket to Done after a PR landed. Handles
  the already-merged case as a first-class path, so it is safe to run after a human merged by
  hand. Prefer this over ad-hoc `gh pr merge` + manual tracker edits, because it refuses to merge
  on a red re-gate or mark a ticket done on a failed deploy, keeps every comment idempotent, and
  never deletes a worktree that has unpushed work.
---

# Merge a ticket and close it out

This is step 7 of the AI delivery workflow (`~/.claude/workflows/ai-delivery-workflow.md`:
section 2 stage 7, and sections 4, 7 and 8 are the authority; the working folder and
`job.json` follow the `deliver` skill's `references/state-files.md`). It also works on its own in a repo that does not
use that workflow: every workflow artifact below (checks script, ticket record, working folder,
cost script) is used **if the project has it** and skipped with a one-line note if not.

Seven steps, in order:

**Resolve & check state → Ready + re-gate (draft → ready, re-sync, checks) → Close the ticket
record → Merge (per the merge path) → Post the proof → Move to Done → Re-sync other PRs & clean
up.**

The order matters. Everything after the merge assumes the merge happened and worked; calling a
ticket Done when its re-gate was red or its deploy failed is worse than not touching it.

**Hard stops:**
- Merging is outward-facing and hard to undo. **The default merge path is "owner approves by
  merging".** The agent merges only when the owner has allowed the merge command for agents
  (allow-listed in settings) and the project's merge path says "agent merges", or when the
  user said "merge it" / "ship it" this turn. Otherwise prepare everything and hand over.
- If the PR is **already merged**, there is nothing to confirm — skip to step 5.

Track the steps in your todo list so the human can see where you are.

## Learn this project's rules first

One pass, then say in one line what you found:

- `CLAUDE.md` / `AGENTS.md` / `docs/workflow/README.md` — merge strategy (usually squash), the
  **merge path** (agent merges with an allowed command, or *owner approves by merging*), the
  checks script (e.g. `scripts/workflow/checks.sh` / `.ps1`), the cost script (default name
  `scripts/workflow/cost`), the worktree tool
  (e.g. Orca), the PM tool and its done status, the `ready-to-merge` label (waiting for the
  owner's merge) and the `needs-human` label (real escalations).
- `.github/workflows/` — gating checks, and **what runs on push to the default branch** (deploy,
  migration-apply, release): that run is part of this job (step 4b).
- `git log --oneline -10` on the default branch — the real merge style.

Report: merge strategy, merge path, checks script found or not, post-merge workflow found or not.

**Local backlog.** When the project uses the local backlog (no PM tool; `docs/tickets/backlog.md`, IDs `T-001…`, format in the `deliver` skill's `references/import-tasks.md`), read/write `docs/tickets/backlog.md` instead of the PM tool: in step 3, on the PR branch, set the
entry's `Status: Done`, add the PR to `PRs:` and append a Log line (and, when the entry points
to a local ticket file via `Record:`, set that file's `**Status: 🟢 Done**`, its `PRs:` line, its
Outcome and a `🟢 merged` Log line too), so it lands with the merge
(already merged by hand → a tiny docs PR, like the ticket record). Step 5's ticket proof goes
into the PR close-out comment (screenshots via `gh pr comment --attach` when `gh` supports it,
else linked from the job folder); step 6 is satisfied by the merged entry.

---

## Step 1 — Resolve the target and check its state

The target may be a ticket key, a PR number/URL, or nothing (current branch's PR). A ticket may
have **several PRs** (main PR plus follow-up fixes) — find them all:

```bash
gh pr list --search "<KEY>-<n>" --state all --json number,state,title,url,headRefName
gh pr view <n> --json state,isDraft,mergedAt,mergeCommit,mergedBy,baseRefName,headRefName,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup,url
```

The field is `state` (`OPEN` / `MERGED` / `CLOSED`); there is no `merged` field.

| State | Path |
|---|---|
| `MERGED` | **Already-merged path.** Report who merged and when; skip steps 2 and 4 (step 3 becomes a follow-up docs fix if the record is incomplete — see the reference). Go to 4b. |
| `OPEN` | Continue to step 2. |
| `CLOSED` unmerged | Stop. Reopening is the human's decision. |

In a workflow project, also confirm the approver said **APPROVE** (`decision.md` in
`.delivery/jobs/<KEY>-<n>/`, `job.json.decision`, or the decision comment on the PR).
`ESCALATE` or no decision is a stop: the ticket belongs in `needs-human`, not in a merge. Read
the worktree path, branch, base branch and PR number from `job.json` when it exists.

## Step 2 — Ready + re-gate: mark ready, re-sync with main, re-run the checks

Another ticket may have merged since the review loop passed, so the green it earned is stale.

1. **Draft → ready.** If the PR is still a draft (`isDraft`), run `gh pr ready <n>`. This skill
   is the only one that does this (builders and the orchestrator leave the PR as a draft), and
   it happens right before the re-gate so CI runs once more on a ready PR.
2. **Re-sync** the PR branch with the latest `main` in the ticket's worktree, the way the repo
   does it (merge `origin/main` into the branch, or `gh pr update-branch`, or rebase if the repo
   rebases). **Conflicts → stop**: abort the merge/rebase, report the files, send it back to the
   builder. Only resolve purely mechanical conflicts (a generated file the repo regenerates by
   script, e.g. a generated owner to-do list) — regenerate, never hand-merge.
3. **Run the checks script from `main`'s copy** (so a branch cannot weaken the checks it is
   judged by), against the re-synced branch, in local mode (no `--report`: the result goes in
   your report and the PR close-out, not into a round file). `references/merge-checks.md` has
   the recipe. Without a checks script, run the commands `CLAUDE.md` lists.
4. **Red → refuse to merge.** Report the failing step with the log tail. Do not offer to merge
   past it unless the user explicitly overrides in those words.
5. Push the re-synced branch and wait for **CI green** on the new head (`gh pr checks <n>
   --watch`). Then read merge readiness: `mergeStateStatus` (`DIRTY`/`BLOCKED`/`BEHIND`),
   `reviewDecision` (`CHANGES_REQUESTED` is a stop). Details in `references/merge-checks.md`.

## Step 3 — Close the ticket record (before the merge, so it lands with it)

If the project keeps a ticket record (`docs/tickets/<KEY>-<n>.md`, or `docs/tickets/<KEY>-<n>/README.md`
for large tickets), update it **on the PR branch** so the squash carries it:

- **Links block:** the ticket link and **every PR** for the ticket (from step 1); add any missing.
  Related tickets (blockers, follow-ups, deferred-to) present.
- **Status:** `Merged`.
- **Outcome section:** deviations from the design, known limitations, follow-up tickets
  (with keys), deferred criteria (with the owner's decision and the follow-up key), and the
  feature guide link (`docs/features/<area>.md`, written by the explainer).

Facts only, from the working folder, PR and ticket — never invent an outcome. Commit
(`docs(<scope>): close out ticket record (<KEY>-<n>)` or the repo's equivalent), re-run the
ticket record check if the checks script has one, push, wait for CI again.

## Step 4 — Merge, per the project's merge path

**Agent merges** (only when the owner allowed the merge command for agents and the project's
merge path says so, or the user just said merge):

```bash
gh pr merge <n> --squash --delete-branch      # strategy per the repo
```

Never `--admin` unless the user asks for exactly that. If refused, report the exact message.

**Owner approves by merging** (the default: whenever the project has not chosen agent merges
with the merge command allowed): do everything up to the merge, then stop and hand over:

> Ready for your merge: <PR URL> — re-gate green on <short SHA>, CI green, approver APPROVE.
> Merge with: `gh pr merge <n> --squash --delete-branch` (or the green "Squash and merge"
> button). Then tell me "merged" or re-run merge-ticket and I will finish the close-out.

Add the **`ready-to-merge`** label to the ticket (local backlog: to the PR) while it waits —
not `needs-human`, which is kept for real escalations. On the next run, step 1 finds `MERGED`
and continues from 4b. The orchestrator may poll the PR state instead.

### Step 4b — Verify what the merge triggered

**Do not skip this**, on either path. If a workflow runs on push to the default branch, match
its run to the merge SHA and watch it. Success → quote the evidence line (smoke probe,
migration applied, health check). Failure → the change is merged but **not live**: post that
on the ticket, do not move it to Done, tell the user plainly. Recipes in `references/merge-checks.md`.

## Step 5 — Post the proof where it belongs

Evidence goes to the tools people look at, never duplicated. Full templates, markup rules and
the idempotency markers are in `references/proof-and-comments.md`.

**On the ticket (PM tool)** — one close-out comment plus attachments:
- AC results table (each criterion verbatim → PASS / FAIL / Deferred → evidence).
- Step-by-step screenshots (`<KEY>-<n>-AC1-step-01.png` …) attached to the issue. The device
  tester usually attached them already: check the issue's attachments and upload only what is
  missing. Use the tracker API; if it cannot upload files, use a signed-in browser session
  (e.g. the browser driver's file-upload action on the issue's attachment input).
- Owner decisions and deferrals (who, when, follow-up key), the PR link(s), merge SHA, deploy
  result, final status.

**On the PR** — one close-out comment:
- Test and review summary **per round** (gate, testers, reviewers: verdict + one line each).
- Approver decision, CI result on the merged head, deploy result.
- **Cost of the ticket's agents**, from the project's cost script if it has one (else omit and say so).
- A **link to the ticket's proof comment** instead of re-uploading the images.

**Idempotent:** read existing comments first; if a close-out already exists, post only a short
delta (or nothing). Never post the same summary twice.

**Deferrals:** for each criterion deferred by the owner, add a comment on the **follow-up
ticket** too: what was deferred from which ticket, the owner's decision, the link back.

## Step 6 — Move the ticket to Done

Fetch transitions and pick by **name**, never a hardcoded id. Merged + deploy green (or no
deploy) → the done status; deploy failed or pending → leave it and say why; a separate release
step the team tracks → its intermediate status. Remove `ready-to-merge` (and `needs-human`
if this run added it).

## Step 7 — Re-sync the other open PRs, then clean up

**Re-sync every other open PR** (the merge just moved `main` under them). For each:
merge `origin/main` into it in **its own worktree**, re-run the checks script (main's copy),
push. Skip — and report — any worktree with uncommitted changes or a builder mid-stage (its
stage file says so): never commit someone else's work in progress. Conflicts you cannot resolve
mechanically → abort, report the PR and files, leave it for its builder. Recipes in
`references/after-merge.md`.

**Clean up this ticket** (only after step 5 succeeded — the working folder holds the evidence):

1. **Worktree:** confirm it is clean (`git status --porcelain` empty) and has nothing unpushed;
   anything left → stop and report, never discard. Prefer the tool that manages it (e.g. the
   Orca CLI for Orca worktrees) over raw `git worktree remove`. Stop any process still running
   in it first.
2. **Local branch:** delete it (`git branch -D` is needed after a squash merge — only once the
   PR is confirmed `MERGED`). Remote branch: deleted by `--delete-branch`, else delete it.
3. `git worktree prune`.
4. **Leftovers:** stop dev servers, simulators/emulators and local backends started for the
   ticket (`job.json.services` entries still `running`, or the local backend recipe); delete
   downloads made for it (e.g. dev build archives).
5. **Working folder:** delete `.delivery/jobs/<KEY>-<n>/` (if it lived inside the worktree it is
   already gone — check the main checkout too).

## Step 8 — Report

PR link(s), merge SHA, re-gate result, deploy result, ticket link and new status, proof comment
links (ticket + PR), cost, re-synced PRs (pushed / conflicted / skipped), and what was cleaned up
or left (with the reason).

---

## What this skill will not do

- **Merge on a red re-gate or red CI**, resolve real conflicts, or force-merge with `--admin`.
- **Merge without APPROVE** in a workflow project, or merge itself when the merge path says the
  owner merges (the default) or the merge command is not allowed for agents.
- **Mark a ticket Done when the post-merge deploy failed.**
- **Delete a worktree or branch with uncommitted or unpushed work**, or delete the working
  folder before the proof is posted.
- **Post duplicate comments** or re-upload screenshots already on the ticket.
- **Write the implementation story from scratch.** It closes out; the build and review detail
  come from the builder, testers, approver and explainer.

## References

- `references/merge-checks.md` — re-sync recipes, running main's copy of the checks script,
  merge readiness (`mergeStateStatus`, checks, reviews), the two merge paths, post-merge deploy
  verification, non-GitHub forges.
- `references/proof-and-comments.md` — ticket record close-out, ticket and PR comment templates,
  screenshot attachment (API and browser fallback), idempotency markers, deferral notes, tracker
  markup (Jira wikimarkup vs Markdown), transitions.
- `references/after-merge.md` — re-syncing other open PRs safely, worktree/branch cleanup
  (Orca or raw git), stopping leftover services, deleting the working folder.
