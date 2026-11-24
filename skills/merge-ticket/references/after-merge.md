# After the merge: re-sync other PRs, then clean up

Two jobs, in this order: keep every other open PR current with the new `main`, then remove
everything this ticket left behind. Both are careful by default — they report rather than
destroy when anything looks like live work.

## Re-sync every other open PR

```bash
gh pr list --state open --json number,headRefName,isDraft,url
git worktree list --porcelain        # map each headRefName to its worktree, if any
```

For each open PR (except ones the user excluded):

1. **Is someone working on it?** Skip and report if any of these hold:
   - its worktree has uncommitted changes (`git -C <wt> status --porcelain` not empty);
   - its `job.json` in `.delivery/jobs/<KEY>-<m>/` shows a stage in progress (`building`,
     `fixing`, `testing`, `reviewing`, `approving`; the
     orchestrator re-syncs it when that stage ends);
   - the branch has local commits not on the remote (`git -C <wt> rev-list @{u}..HEAD`), i.e.
     someone is about to push.
2. **Where to work:** its own worktree if it has one. No worktree → a temporary one:
   `git worktree add "$TMP/resync-<m>" <headRefName>` (remove it afterwards). Never check the
   branch out in the main checkout over other work.
3. **Merge main in:** `git fetch origin && git merge --no-edit origin/main` (or the repo's
   update method; `gh pr update-branch <m>` is an alternative that needs no local checkout but
   skips the local checks).
4. **Conflicts:** resolve only generated files by re-running their generator. Anything else →
   `git merge --abort`, record the PR and files, move on.
5. **Checks:** run main's copy of the checks script (see `merge-checks.md`). Red → do not push;
   report it — the PR's builder owns the fix (in the orchestrator, the ticket goes back to its
   builder).
6. **Push** when green. Draft PRs too: they are someone's next merge.

Report a table: PR · result (pushed / conflict: files / checks red: step / skipped: reason).

## Clean up this ticket

Run only after the proof is posted (the working folder holds the screenshots and reports).

### 1. Stop what is running

Processes started for the ticket keep files locked (a worktree with a running dev server cannot
be removed on Windows):

- Dev server / bundler: the port in `job.json.services` (entries still `running`) or `docs/setup/local-backend.md`. Find and
  stop the process listening on it (`netstat -ano | findstr :<port>` + `taskkill /PID <pid>` on
  Windows; `lsof -ti :<port> | xargs kill` elsewhere). Stop only processes this ticket started.
- Local backend: the recipe's stop command with the ticket's project name / port overrides
  (e.g. `docker compose -p <project> down`, or the backend CLI's stop command run in the worktree).
- Simulator / emulator booted for the ticket: shut it down (e.g. `xcrun simctl shutdown <udid>`,
  `adb -s <serial> emu kill`) unless the device lane says another ticket now holds it.
- Terminals the worktree tool opened for the ticket (e.g. Orca terminals): close them.

### 2. Remove the worktree

```bash
git -C <wt> status --porcelain              # must be empty
git -C <wt> fetch origin
git -C <wt> rev-list @{u}..HEAD 2>/dev/null # must be empty (nothing unpushed)
```

Untracked files are dependencies and build output only (`node_modules`, `build/`, the gitignored
working folder)? Fine. Anything else (a stray edit, an unpushed commit) → **stop and report**;
never discard someone's work. Note: after a squash merge the branch's commits are not ancestors
of `main`, so "is merged" means the PR state is `MERGED`, not `git branch --merged`.

Then remove it with the tool that manages it:

- **Orca-managed worktree** → the Orca CLI (load the `orca-cli` skill for the exact command,
  e.g. its worktree remove/archive command), so Orca's own records stay consistent.
- **Other worktree tools** → their remove command.
- **Plain git** → `git worktree remove <wt>` (add `--force` only when the remaining untracked
  files are dependency/build folders you checked above).

A long path or locked file on Windows can make removal fail half way: close processes using the
folder and retry; then delete the leftover directory.

### 3. Branches and records

```bash
git branch -D <headRefName>                       # -D: squash merges are not "merged" to git
git push origin --delete <headRefName> 2>/dev/null # only if --delete-branch did not already
git worktree prune
git fetch --prune
```

Delete the local branch only after confirming the PR is `MERGED` and the worktree is gone. Also
remove any temporary re-sync worktrees from the step above.

### 4. Leftovers

- Downloads made for the ticket (dev build archives, test fixtures fetched at run time) — from
  the stage file or the scratch/temp folder the ticket used.
- Test data the device tester created in a **shared** environment (it should have used the
  local backend; if not, list what it created for the owner rather than deleting blindly).

### 5. The working folder

Delete `.delivery/jobs/<KEY>-<n>/`. It is gitignored, so it may live in the ticket's worktree
(already gone) or in the main checkout — check both. Do not delete it if any proof upload failed;
report the paths instead. Never remove `<main checkout>/.delivery/evidence/` during cleanup.

### Report

What was stopped, removed and deleted; anything left in place and why (unpushed work, failed
upload, locked folder), with the exact path so the owner can act.
