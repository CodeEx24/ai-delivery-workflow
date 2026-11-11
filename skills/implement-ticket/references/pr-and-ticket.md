# Commit, draft PR, and ticket hand-off

Read at Phase 8. The build ends with a **draft** PR whose description says what was built and
how to test it — this replaces a separate build note. Pushing a branch and opening a draft
need no extra go-ahead; merging is never part of this skill (`/merge-ticket` does it after
the review loop approves).

## 1. Match the repo's conventions (check, do not assume)

```bash
git log --oneline -15                      # real commit style
git branch --show-current                  # already on the ticket branch?
git remote -v                              # GitHub? GitLab? something else?
gh pr list --state merged --limit 5        # real PR titles
gh pr view <n> --json title,body           # a real PR body to mirror
ls .github/PULL_REQUEST_TEMPLATE* .github/pull_request_template.md 2>/dev/null
```

The repo's own docs (`CLAUDE.md`, `CONTRIBUTING.md`, workflow doc) win over anything below.
Where docs and recent history disagree, follow history and mention the discrepancy.

## 2. Branch

Already on a branch that names this ticket (common in a per-ticket worktree)? **Stay on
it.** Otherwise create one from the default branch in the repo's format, with the prefix the
ticket type implies (`references/ticket-types.md`), e.g. `feat/<key>-<n>/<slug>`,
`fix/…`, `chore/…`, `refactor/…`, `docs/…`, `spike/…`. Never commit to the default branch.

## 3. Commit

- Repo format; Conventional Commits with the type prefix by default
  (`feat(scope): … (<KEY>-<n>)`, `fix(scope): …`, `chore(scope): …`).
- Subject imperative, under ~72 characters. Body: why, owner decisions, anything a reviewer
  would ask.
- **Add the attribution or sign-off trailers this session's instructions require.**
- Never `--no-verify` or skip signing; if a hook fails, fix the cause.

```bash
git status --short          # no stray files, no secrets, no .delivery/ content
git add <paths>             # or -A after checking status
git commit -F <message-file>
```

Check the diff for secrets one last time. A committed credential is a rotation incident.

## 4. Push and open the draft PR

```bash
git push -u origin <branch>
gh pr create --draft --title "<title>" --body-file <body-file> --base <default-branch>
```

Title in the repo's PR style, usually the commit subject. If the repo has a PR template, fill
it. **GitHub Issues tracker** (`GH-<n>` keys, including `/factory`): the body must contain the
line `Closes #<n>` so the merge closes the issue. Default body:

```markdown
## What was built
<2–4 sentences in the reviewer's terms: what changed and why.>

Ticket: <tracker link> · Record: docs/tickets/<KEY>-<n>.md
Type: <type> · Risk: <risk>

## Main files
- `<path>` — <role>
- `<path>` — <role>

## Decisions
- <decision> — <choice> (<owner / date>)

## How to test
1. <setup: seed, account, flag — or "none">
2. <steps a reviewer follows>
3. Expected: <result>

Checks: `<checks command>` — PASS (<or: gap named — runs in CI>)

## Owner actions
<docs/actions/… guides this needs, or "none">
```

Add per type: **Bug** — `## Root cause` and "Reproduced by `<test>`". **Chore** — the
no-behaviour-change proof. **Spike** — "Not for merge", a findings summary and the proposed
follow-ups.

Do not put an AC results table, E2E evidence or review verdicts in the body — the review
loop adds those (round summary comments, approver decision, explainer walkthrough). Add the
PR-description attribution line if this session's instructions require one. Report the PR
link as soon as it exists.

## 5. Link the PR in the ticket record

Replace `PRs: (pending)` in `docs/tickets/<KEY>-<n>.md` (or the record's README in folder
form) with the PR link, commit (`docs(<scope>): link PR in ticket record`), push. The
ticket-record check fails once a PR exists without it. Every later PR on the same ticket is
appended to that line.

## 6. Update the ticket

Comment once, then transition:

> **Built — draft PR ready for review.** <one-line summary>
> **PR:** <link> · **Branch:** `<branch>` · **Record:** `docs/tickets/<KEY>-<n>.md`
> **Owner actions:** <guides, or none>

- **Jira:** `addCommentToJiraIssue`, then `getTransitionsForJiraIssue` and
  `transitionJiraIssue` — read the available transitions rather than guessing names.
- **Linear / GitHub issues:** the equivalent comment + state change.
- **Local backlog** (`docs/tickets/backlog.md`, no PM tool): read/write that file instead of
  the PM tool — but in practice write nothing here: the comment goes on the PR, and the status
  is derived from the draft PR (only merge-ticket edits the entry, on the PR branch).

Move it to **In Review** (or `Code Review` / `Review` — the repo's review status). If there is
none, leave the status and say so. **Never Done** — Done happens after merge. Re-read the
issue to confirm status and comment. Keep it idempotent: on a re-run (e.g. after a CHANGES
round), update or skip rather than posting a duplicate comment.

## 7. CI

CI starts on push. You do not need to wait for it before handing off — the gate and the loop
cover it — but if it is already red when you write the one-line report, say so; a red CI run
on your own push is yours to fix before handing off.

```bash
gh pr checks
gh run view <run-id> --log-failed
```
