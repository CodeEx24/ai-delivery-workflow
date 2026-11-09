# merge-ticket — what changed

**Why:** the skill now does step 7 of the new AI delivery workflow ("Merge and close out"). It
used to be "merge, comment the PR link on the ticket, move it to Done". Now it runs the whole
close-out, so nothing is left for you to tidy up by hand after a merge. It still works in repos
that don't use the workflow: anything it can't find (a checks script, a ticket record, a cost
script) is skipped, and it tells you it skipped it.

## What's new

1. **Re-check before merging.** Another ticket may have merged since the review passed. So the
   skill first brings the branch up to date with `main`, re-runs the checks script (always the
   copy from `main`, so a branch can't weaken its own checks) and waits for CI. If anything is
   red, it won't merge. It only fixes conflicts in generated files, by re-running their script.
2. **Merge path.** It follows the project's choice. Either the agent may merge, or **you approve
   by merging**. On your path it gets everything ready, gives you the exact command or button,
   marks the ticket `needs-human`, and stops. When you've merged, run it again (or let the
   orchestrator poll) and it finishes the close-out. The "already merged" path still works as
   before.
3. **It needs the approver's APPROVE.** In a workflow project it won't merge if the decision is
   ESCALATE or missing.
4. **It closes the ticket record.** It updates `docs/tickets/<KEY>-<n>.md`: the links block
   lists the ticket and every PR, Status becomes Merged, and the Outcome section gets
   deviations, limitations, follow-ups, deferrals and the feature guide link. This is committed
   on the PR branch **before** the merge, so it lands in the same squash commit.
5. **Proof goes in the right place, once.**
   - On the ticket: the AC results table, step-by-step screenshots (it uploads only the ones the
     device tester didn't), decisions and deferrals, and the final status.
   - On the PR: a table of every review/test round, the approver's decision, CI and deploy
     results, and the cost of the ticket's agents. The PR links to the ticket comment and
     doesn't copy the images.
   - Comments carry a marker or a fixed heading, so running it again edits or skips instead of
     posting duplicates.
   - If the tracker API can't upload files, it uploads screenshots through a signed-in browser.
6. **Deferrals** are also noted on the follow-up ticket.
7. **After the merge:**
   - It updates every other open PR with `main`, re-runs its checks and pushes. It skips PRs
     someone is working on and reports conflicts.
   - It cleans up: stops the dev server, simulator and local backend, removes the worktree
     (through Orca when Orca manages it), deletes the local branch, prunes worktree records, and
     deletes leftover downloads and `.delivery/jobs/<KEY>-<n>/`.
   - It never deletes anything that holds uncommitted or unpushed work.

## Kept

- The order: verify, then merge, then report.
- Refusing on red CI, conflicts, CHANGES_REQUESTED or a failed deploy.
- Never using `--admin`.
- Checking the post-merge deploy.
- Never hardcoding transition ids.
- Jira wikimarkup rules.
- Confirming before a merge unless you gave the go-ahead.
- The `state`-not-`merged` gotcha.

## Removed or restructured

- `references/jira-update.md` → replaced by `references/proof-and-comments.md`. It keeps the
  markup and transition sections and adds the ticket record, proof templates, screenshot upload
  and idempotency markers.
- New `references/after-merge.md` covers re-syncing other PRs and cleanup.
- `references/merge-checks.md` now also covers re-syncing, running `main`'s copy of the checks
  script, and the two merge paths.
- The frontmatter description is rewritten to cover the new scope and trigger phrases ("clean
  up after the merge").
- The old example key `TH-118` is replaced with `<KEY>-<n>` / `ABC-118`.

## Open questions for you

1. **When the Outcome is written.** The workflow says to update the record's Outcome "after
   merge". I write it on the branch just before the merge, so no second PR is needed. If the PR
   was already merged by hand, it opens a tiny docs PR instead. OK, or would you rather allow
   direct doc commits to `main`?
2. **Updating other PRs: merge or rebase?** I default to merging `main` in, which is safe with
   squash merges and needs no force-push. Rebase is used only if the repo says so.
3. **Cost script name and output.** The skill assumes "a script that takes the ticket key and
   prints a total". Once yours exists, a fixed command name in `docs/workflow/README.md` would
   let the skill call it without guessing.
4. **Owner path and `needs-human`.** Should the ticket really get the `needs-human` label while
   it waits for your merge, or would you rather have a separate "ready to merge" label so
   merges don't get mixed up with real escalations?

## Alignment pass (after all drafts were written)

- **merge-ticket now owns `gh pr ready`** (draft → ready). It is the first sub-step of step 2,
  right before the pre-merge re-gate; `/deliver` no longer does it.
- The pre-merge re-gate runs main's copy of the checks script in local mode (no `--report`),
  so it never writes a round file; the result goes in the report and the PR close-out.
- `job.json` (schema in the `deliver` skill's `references/state-files.md`) is the source for
  the decision, worktree, PR number and the `services` to stop at cleanup; a ticket is
  "mid-stage" when its stage is `building`, `fixing`, `testing`, `reviewing` or `approving`.

## Follow-up pass

- **Local backlog:** with no PM tool, step 3 sets the entry's `Status: Done`, adds the PR and a
  Log line in `docs/tickets/backlog.md` on the PR branch (so it lands with the merge); the
  ticket proof goes into the PR close-out comment instead of a tracker comment. Note added
  under "Learn this project's rules first".

## Owner decisions applied (2026-11-08, all recommendations accepted)

Open questions 1–4 above are settled (#3, #4 keep; #20, #19 below).

- **#1:** "owner approves by merging" is the default path; the agent merges only when the owner
  allowed the merge command for agents (or said "merge it" this turn). SKILL, merge-checks.
- **#19:** while waiting for the owner's merge the ticket (local backlog: the PR) gets
  **`ready-to-merge`**, removed at Done; `needs-human` stays for real escalations. SKILL,
  merge-checks, proof-and-comments.
- **#20:** the cost script is `scripts/workflow/cost <KEY>-<n>` (name recorded in
  `docs/workflow/README.md`). SKILL, proof-and-comments.
