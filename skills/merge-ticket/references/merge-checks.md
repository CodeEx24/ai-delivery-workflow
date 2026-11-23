# Re-gate, merge readiness, merge paths and post-merge verification

Everything needed to answer "is this still safe to merge?", "who presses the button?" and "did
the merge actually work?". Commands are shown for Git Bash / POSIX; `git` and `gh` behave the
same in PowerShell.

## Reading the PR state

```bash
gh pr view <n> --json state,mergedAt,mergeCommit,mergedBy,baseRefName,headRefName,\
mergeable,mergeStateStatus,reviewDecision,statusCheckRollup,title,url
```

**Gotcha:** there is no `merged` JSON field (`Unknown JSON field: "merged"`). Use `state`.

```bash
# merged, and by whom?
gh pr view <n> --json state,mergedAt,mergeCommit,mergedBy \
  --jq '{state, mergedAt, sha: .mergeCommit.oid, by: .mergedBy.login}'
# every PR for a ticket (main PR + follow-up fixes)
gh pr list --search "<KEY>-<n>" --state all --json number,state,title,url,headRefName
# the worktree that has the PR branch checked out
git worktree list --porcelain     # match "branch refs/heads/<headRefName>"
```

## Re-sync the branch with main

Work in the ticket's own worktree (from `git worktree list`). First make sure it is clean; if it
has uncommitted changes, stop — someone is still working there.

```bash
git -C <worktree> status --porcelain          # must be empty
git -C <worktree> fetch origin
git -C <worktree> merge --no-edit origin/main # repo merges main into branches (squash-merge repos usually do)
# or: gh pr update-branch <n>                 # server-side merge of base into the PR
# or: git -C <worktree> rebase origin/main && git push --force-with-lease   # only if the repo rebases
```

On conflict: `git merge --abort` (or `git rebase --abort`), list the conflicted files, stop, and
hand back to the builder. The only conflicts this skill resolves are **generated files** the repo
rebuilds by script (e.g. an owner to-do list generated from front matter, a lockfile the docs say
to regenerate): run the generator, stage, continue — and say you did.

Push after the checks pass (below), not before, so a red re-gate does not leave a broken head on
the PR.

## Run main's copy of the checks script

The gate must use the default branch's version of the script, not the branch's.

```bash
git -C <worktree> show origin/main:scripts/workflow/checks.sh > "$TMP/checks-main.sh"
(cd <worktree> && bash "$TMP/checks-main.sh")           # PowerShell variant: checks.ps1
```

Adjust the path to the project's script name. If the script reads companion files from
`scripts/workflow/`, check those out from `origin/main` into a temp dir and run from there with
the worktree as the working directory. Run it in **local mode** (no `--report`, workflow 1b): it
only prints, so no round file is written; quote the result in your report and the PR close-out.

- **PASS** → push, then wait for CI.
- **FAIL** → refuse to merge. Report the failing step and the log tail; the ticket goes back to
  the builder (in the orchestrator: back to step 4 of the workflow, not a new review round
  unless code changes).
- **No checks script** → run the lint / typecheck / test / build commands from `CLAUDE.md` and
  say the project has no checks script.

## `mergeStateStatus`

| Value | Meaning | Action |
|---|---|---|
| `CLEAN` | Ready. | Merge (per merge path). |
| `BLOCKED` | Branch protection unsatisfied — missing approval, required check not run. | Report which requirement. Do not force. |
| `BEHIND` | Base moved again since the re-sync. | Re-sync and re-gate once more. |
| `DIRTY` | Conflicts. | Stop. |
| `UNSTABLE` | A non-required check is failing. | Mergeable; name the red check and let the human decide. |
| `HAS_HOOKS` / `UNKNOWN` | Still computing. | Re-poll once, then report. |

`mergeable: UNKNOWN` means GitHub has not finished computing — wait and re-read.

## Checks and reviews

```bash
gh pr checks <n>                         # name, state, link
gh pr checks <n> --watch --interval 30   # block until done
gh pr checks <n> --required              # only gating checks
gh run view <run-id> --log-failed        # why a check failed
gh pr view <n> --json reviews --jq '.reviews[] | {author: .author.login, state}'
```

- Required check failing → stop. Pending → wait. Non-required failing → mention, human decides.
- `CHANGES_REQUESTED` → stop. `REVIEW_REQUIRED` → protection will refuse; report it.
- In a workflow project, the approver's decision (`decision.md` / PR comment) must be `APPROVE`.

## Draft → ready (right before the re-gate)

```bash
gh pr view <n> --json isDraft --jq .isDraft   # true → mark it ready
gh pr ready <n>
```

Only merge-ticket marks a PR ready; builders, testers and the orchestrator leave it a draft.

## The two merge paths

The project decides this with `/delivery-config mergePath=owner|agent` (recorded in
`docs/workflow/delivery.config.json`; older projects may record it in `docs/workflow/README.md`
or `CLAUDE.md`). **Default: owner approves by merging.** Agent merges only when the owner chose it
and allow-listed the merge command for agents. Honour the choice; do not switch paths because
one is blocked.

**Agent merges.** Only when the owner chose this path and the merge command is allow-listed for
agents.

```bash
gh pr merge <n> --squash --delete-branch   # or --merge / --rebase per the repo
```

- Confirm first unless the user said "merge" this turn or the project authorises the agent to
  merge approved PRs (the orchestrator, on this path only).
- If a safety hook or permission check blocks the command even so, do not work around it (no
  `--admin`, no alternate command): fall back to the owner path and say why.
- `--auto` queues rather than merges — say "queued", and do not post proof or move the ticket.
- If the branch is checked out in a worktree, `--delete-branch` may fail to delete the local
  branch. Cosmetic — the merge happened; cleanup handles it.

**Owner approves by merging.** Prepare everything (re-gate green, CI green, record closed out,
APPROVE present), label the ticket `ready-to-merge` (local backlog: the PR), hand over the
exact command and the button, and stop. Detecting the merge later:

```bash
gh pr view <n> --json state,mergedAt,mergeCommit --jq '{state, mergedAt, sha: .mergeCommit.oid}'
```

`MERGED` → continue with post-merge verification and the rest. Still `OPEN` → report it is still
waiting (the ticket keeps `ready-to-merge`; `needs-human` is only for real escalations). If new commits landed on `main` while
waiting, the PR may show `BEHIND` again: re-gate before telling the owner again.

## Post-merge verification

```bash
# workflows that run on push to the default branch
rg -l "push:" .github/workflows/ | xargs rg -l "main"
gh run list --workflow=<name>.yml --limit 5 \
  --json status,conclusion,headSha,createdAt,databaseId \
  --jq '.[] | {status, conclusion, sha: .headSha[0:7], id: .databaseId}'
gh run watch <id>                                   # if still running
gh run view <id> --log | grep -iE "smoke|applied|deployed|healthy|OK" | tail -15
```

Match `headSha` to the merge SHA.

- **success** → quote the evidence line in the ticket comment; it beats "the workflow was green".
- **failure** → merged but **not live**. `gh run view <id> --log-failed`, report it, do not move
  the ticket to Done.
- **Database migrations applied on merge:** a failed migrate/push step or a column-contract probe
  failure means the ticket is not done, whatever the PR says.

## Non-GitHub forges

- **GitLab** — `glab mr view <n>`, `glab mr merge <n>`; same shape, pipeline first.
- **Bitbucket / Azure DevOps / Gitea** — no assumed CLI: use the owner path (ask the user to merge
  in the UI), then detect with `git fetch && git log origin/main --oneline | grep <KEY>-<n>`.
- **No forge** — `git merge --ff-only` plus push; confirm explicitly, and say there is no CI gate.
