# Standards gate

Makes sure a change follows the repo's engineering standards before an agent can approve it. It
applies when the repo has `.engineering/check.mjs` and `.engineering/STANDARDS.md`. Without them,
write `Standards: not installed` in `checks.md` and continue as normal.

## 1. When it runs

| Moment | Who | Mode |
|---|---|---|
| Before opening the PR | Builder | Section 2, to catch problems early |
| Every review round | Gate | Section 2, from the **main checkout's** copy, into `checks.md` |
| Every review round | `reviewer-code`, `reviewer-security` | Section 3 |
| Before APPROVE | `approver` | Section 4 |
| After the final re-sync | `merge-ticket` | Section 2 again |

## 2. Automatic checks

Run in Bash from the ticket's worktree. Use the main checkout's script so a branch cannot weaken
the checks it is judged by.

```bash
cd "<worktree>"
CHECK="<main checkout>/.engineering/check.mjs"
BASE="origin/<base_branch>"
git fetch -q origin "<base_branch>"

node "$CHECK" doctor
PR_TITLE="$(gh pr view <PR> --json title --jq .title)" \
PR_BODY="$(gh pr view <PR> --json body --jq .body)" \
PR_HEAD="$(gh pr view <PR> --json headRefName --jq .headRefName)" \
PR_BASE="$(gh pr view <PR> --json baseRefName --jq .baseRefName)" \
node "$CHECK" pr
node "$CHECK" secrets "$BASE"
NODE_OPTIONS=--max-old-space-size=5120 node "$CHECK" ratchet
git diff -z --name-only --diff-filter=ACMR "$BASE"...HEAD |
  xargs -0 -r pnpm exec prettier --check --ignore-unknown --end-of-line auto
```

Before opening the PR, the builder skips the `pr` command because no PR exists yet.

**Lint, types and formatting.** When `.engineering/baseline.json` exists, the ratchet decides lint
and type errors, and formatting is checked on changed files only. Existing debt does not fail a
ticket. New debt does. A raw `lint`, `typecheck` or repo-wide `format:check` failure in the checks
script is not a gate failure if these checks pass and every other step passes. Say so in
`checks.md`.

**Protected files.** Compare the branch with the base:

- `.engineering/baseline.json`: every value may stay the same or go down. Any increase is a FAIL.
- Any other file under `.engineering/`, or `.github/workflows/standards.yml`,
  `.github/workflows/pr-routing.yml` or `.github/CODEOWNERS`: report `KIT CHANGED`. The approver
  must escalate it.

Add this block to `round-N/checks.md`. Any FAIL makes the first line `VERDICT: FAIL`.

```markdown
## Standards
| Check | Result |
|---|---|
| Kit intact | PASS |
| Branch, title and description | PASS |
| Secret scan | PASS |
| Quality ratchet | PASS |
| Changed-file formatting | PASS |
| Protected files | PASS, or KIT CHANGED |
```

Never fix a failure by editing `.engineering/`, skipping a hook, or weakening a test or lint rule.

## 3. Rule-by-rule review

Read `.engineering/STANDARDS.md` and `docs/engineering/exceptions.md`, if it exists, then check
**the lines this change adds or modifies**.

| Reviewer | Rule groups |
|---|---|
| `reviewer-code` | `GIT`, `PR`, `NAME`, `CODE`, `ARCH`, `QA`, `REV`, `OPS`, `DOC`, `AI` |
| `reviewer-security` | `SEC`, `DATA`, `QA-4` |

- Rules tagged `[hook]` or `[ci]` are covered by section 2. Do not re-check them by hand.
- Use only rules that apply to the change, and cite the rule ID in the finding.
- **MUST** violated in changed code: `blocking`, unless the exceptions file covers that rule and
  scope.
- **SHOULD** not followed with no reason in the PR: `nit`. Use `important` only if it will cause
  real harm.
- Existing problems the change does not touch go under Notes. They are not findings.
- Project rules in `CLAUDE.md` and `docs/workflow/README.md` win on project specifics.
- Verify a finding before reporting it, as with any other finding.

Add this section to the report, even when nothing is wrong:

```markdown
## Standards
- Rules checked: CODE-2, CODE-3, QA-2, DOC-2
- Not applicable: DATA (no schema or query changes)
- MUST violations: None
- SHOULD notes: None
- Exceptions used: None
```

## 4. Approver

APPROVE only when all of these hold:

1. The gate's `## Standards` block has no FAIL, or says `Standards: not installed`.
2. `review-code.md` has a `## Standards` section, and so does `review-security.md` if it was routed.
3. No MUST violation is open.
4. Any MUST exception used is in `docs/engineering/exceptions.md` for that scope.

**ESCALATE** when:

- The gate reports `KIT CHANGED`.
- The change needs a new exception to a MUST rule.
- Reviewers disagree on whether a MUST rule was broken, after one fix round.

Add a `standards` row to the Verdicts table in `decision.md`.
