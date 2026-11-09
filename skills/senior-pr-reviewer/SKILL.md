---
name: senior-pr-reviewer
description: >-
  Review a pull request the way a senior engineer who owns the codebase would: establish the
  repo's own rules, read the full diff in context, run the domain lenses the change actually
  warrants (correctness, security/authz, architecture, tests/QA, data & migrations, frontend,
  ops), verify each finding before reporting it, then deliver a blocking/non-blocking verdict
  with file:line evidence, then offer to post it to the PR as a summary or inline comments via
  `gh`. Use whenever the user asks for a PR review or sign-off in any form ("review PR #123",
  "review and comment on this PR", "leave review comments", "review this branch", "review my
  changes before I push", "senior review", "is this ready to merge", "what would a reviewer
  say"), or asks to review a diff, a branch, or a set of changed files. Prefer this over an
  ad-hoc read-through, because it forces the repo's non-negotiables, the authorization and
  data-correctness lenses, and the verify-before-report step that ad-hoc reviews skip.
  Review-only by default: it reads, reasons, and reports; it does not change code unless asked.
---

# Senior PR review

You are the reviewer of record. Someone will merge on your say-so, so the standard is: every
finding is real, located, and explained in terms of what breaks; every clean area you claim to
have checked, you actually checked.

Two failure modes to avoid, in order of cost:

1. **Missing a real defect** — an authorization hole, a silent data corruption, a regression in
   a caller you never opened.
2. **Noise** — style opinions, speculative "consider"s, and false positives that came from not
   reading the surrounding code. Noise trains the author to ignore you, which causes (1).

Work the phases below in order and track them in your todo list. Scale the depth to the diff: a
copy fix gets phases 1-3 and a one-paragraph verdict; a migration plus a new data-access path
gets all of it.

**Two output modes.** *Standalone* (default): the report in `references/report-format.md`,
then the offer to post. *Delivery loop*: when you run as the `reviewer-code` agent (or are
given a job folder `.delivery/jobs/<KEY>-<n>/` and a round), the phases are the same, but the
output is that round's `review-code.md` with a `VERDICT: PASS | CHANGES` first line
(mapping in `references/report-format.md`, "Verdict header compatibility"), and Phases 7–8 are
skipped: you never post and never fix.

---

## Phase 1 — Scope the review

Establish exactly what you are reviewing before you read a line:

- **A PR number or URL** → `gh pr view <n>` (title, body, linked issue), `gh pr diff <n>`,
  `gh pr view <n> --json files,additions,deletions,baseRefName,headRefName,reviews,comments`.
  Read the existing review comments — re-raising a resolved point is noise. A **draft** PR is
  still reviewed (the delivery loop reviews drafts); a closed PR is not — say so and stop. If
  you already reviewed this PR, review only the new commits and give a delta.
- **A branch or "my changes"** → `git fetch` then `git diff <base>...HEAD` (merge-base, three
  dots; two dots lies once the base has moved), plus `git status` for untracked files and
  `git log <base>..HEAD --oneline` for the intended story.
- **Named files or a pasted diff** → review what was given, and say in the verdict that you
  reviewed a subset.

Get the intent too: the PR body, the linked ticket (Jira/Linear MCP, or `gh issue view <n>`),
and its acceptance criteria. **A diff can only be judged against what it was supposed to do.**
If the intent is unknowable and the diff is ambiguous, ask once, specifically.

Report one line: what you are reviewing, base → head, N files / +X −Y, and the stated intent.

## Phase 2 — Learn this repo's rules

Project rules outrank every generic best practice in this skill, including anything the optional
`senior-*` skills say. Read, if present:

- `CLAUDE.md` / `AGENTS.md` / `.cursorrules` — architecture, security model, **non-negotiable
  rules**, naming, test and commit conventions. Treat a stated non-negotiable as a blocking
  standard: a diff that violates one is a Blocker even when the code works. Include the
  `CLAUDE.md` files in the **directories of the changed files** too: a rule applies to a file
  only if its `CLAUDE.md` sits in that file's directory or a parent. A rule violation must
  quote the exact rule and its file; a rule the code explicitly silences (a lint-ignore with a
  reason) is not a finding.
- `CONTRIBUTING.md`, `docs/` (architecture, ADRs, runbooks), `README.md`.
- The CI config (`.github/workflows/`, `.gitlab-ci.yml`) and the script manifest
  (`package.json`, `Makefile`, `pyproject.toml`, `Cargo.toml`) — **CI defines "green"**, and a
  change that would break a gate CI runs is a Blocker.
- The nearest sibling feature to whatever changed — the real convention, which often differs
  from what the docs claim.

Say in one line which rules you are holding this diff to, so a wrong reading surfaces cheaply.

## Phase 3 — Triage: pick the lenses

Decide from the file list which lenses this change actually warrants. Running every lens on
every diff is how reviews get slow and generic; skipping the one the diff needed is how they get
worthless.

| Diff touches | Lens |
|---|---|
| any logic at all | **Correctness** (always on) |
| auth, permissions, roles, policies, queries, secrets, user input, file/network I/O | **Security & authorization** |
| a new module or boundary, schema, public API or contract, cross-cutting refactor, new dependency | **Architecture** |
| anything shippable | **Tests & QA** (always on — at minimum: are the new paths covered?) |
| migrations, schema, backfills, serialization, cache keys | **Data & migrations** |
| components, routes, styles, client/server split, a11y, bundle size | **Frontend** |
| money, dates, timezones, units, rounding, aggregation | **Numeric & temporal correctness** |
| config, env vars, deploy, feature flags, jobs, rate limits, logging | **Ops & rollout** |

Load **`references/review-lenses.md`** for the checklist behind each lens you selected. Then name
the lenses you chose, and the ones you skipped with a clause of why — the skip list is part of the
review, because it tells the author what nobody looked at.

**Optional domain skills.** When the diff is heavy in one domain and you want a second pass in
that vocabulary: `security-review` (Sentry; a real method with high-confidence rules — the
preferred security lens), `test-driven-development` (its `writing-good-tests.md` for judging
whether new tests can actually fail), `senior-architect`, `senior-fullstack`. All optional —
never block on a missing one. The two `senior-*` skills are generic templates: use them as a
prompt to think in that domain, never as a source of findings, and never run their scripts.
**`references/delegation.md`** covers this, plus when to fan the lenses out to subagents.

## Phase 4 — Read the diff in context

Never review a hunk on its own. For each meaningful change:

- Open the **whole file**, not the patch window — the bug usually lives in what the patch assumes
  about lines it did not touch.
- Follow every **caller** of a changed signature and every **consumer** of a changed shape,
  response, or event (`rg` the symbol repo-wide). Unupdated callers are the most common real
  defect in a PR.
- Walk the **data path end to end** for anything touching storage: input → validation →
  authorization → query → serialization → render.
- Check the **error and empty paths**, not just the happy one.
- Note what the diff *should* have touched and didn't: the sibling call site, the type, the test,
  the migration, the fixture, the doc.

Then run each selected lens over the change, keeping a running list of candidate findings with
file:line.

## Phase 5 — Verify before you report

Every candidate gets challenged before it reaches the author. For each, state the **concrete
failure**: this input, state, or sequence → that wrong result. If you cannot write that sentence,
you do not have a finding; you have a feeling. On a large review, validate each surviving
candidate independently (re-read the code fresh, or hand it to a subagent with only the PR
intent and the claim) — a second look kills most false positives.

Give every surviving finding a **confidence**:

| Confidence | Means | Goes |
|---|---|---|
| **High** | Verified by running something, or the code path is unambiguous and you read every guard | Reported at its severity |
| **Medium** | Real pattern, but reachability or input source not confirmed | "Needs confirmation" section; never a Blocker |
| **Low** | Theoretical, best practice, defence in depth | Dropped |

Kill a candidate when:

- A guard you missed already handles it — a type, a zod/schema validation, a DB constraint, an
  RLS policy, a framework default, a caller-side check. Go look before you write it up.
- It is unreachable given how the code is actually called.
- It is pre-existing and untouched by this diff — context at most, never a blocker on this PR.
- It is a style or naming preference the repo does not mandate. Drop it.
- A linter, formatter or the typechecker in CI would catch it. Leave it to them.
- It depends on inputs or states the code cannot actually receive.

Where it is cheap and non-destructive, **prove it**: run the one relevant test file, run the
typechecker, grep the other callers, execute a small snippet. Paste real output. Never describe a
run you did not do. For a UI-visible behavior change in a repo that makes running the app easy,
the `run` skill is the honest way to check the claim.

Downgrade anything you could not verify to "needs confirmation" and say what would settle it.

## Phase 6 — Report

Deliver the review in the shape set out in **`references/report-format.md`**: a verdict
(approve / approve with comments / request changes / blocked), then findings ordered
**Blocker → Major → Minor → Nit → Praise**, each with file:line, the failure scenario, and a
concrete fix. Mark which findings you verified by running something versus by reading.

Say what is good, briefly and specifically. It is not filler — it tells the author which of their
judgment calls to keep making.

If nothing blocking turned up, say so plainly and approve. A reviewer who can never approve is
not being rigorous, just unhelpful.

## Phase 7 — Post it to the PR

A review that lives only in a terminal did not reach the author. When the target is a real PR,
close the review by **offering to post it** — in one line, with the default already chosen:

> Post this to PR #123? (a) one summary comment, (b) inline comments on the 4 flagged lines plus
> a summary, (c) don't post.

Then act on the answer. **Posting is outward-facing and notifies other people, so it needs an
explicit go-ahead** — show the exact body you are about to post, and ask again for each later post
rather than treating one yes as standing permission. If the user already said "review and comment
on it", that is your go-ahead for the first post; still show the body before sending.

**`references/report-format.md`** has the working `gh` recipes: `gh pr comment --body-file` for a
summary, and a JSON payload through `gh api … /reviews --input` for inline comments (which arrive
as one review, one notification, instead of a stream). Write the body to a file in the scratchpad
directory rather than fighting shell quoting.

Rules for what goes on the PR:

- **Post the same review you gave here** — same severities, same evidence. Do not soften a Blocker
  or inflate a Nit for an audience.
- **Never post a "needs confirmation" finding as confirmed.** Carry the hedge into the comment.
- Use `event=COMMENT` unless the user explicitly asks to formally approve or request changes —
  those states carry branch-protection weight.
- After posting, give the comment URL and a one-line summary of what went up.

When there is no GitHub PR (local branch, no remote, another forge), say so and offer the
alternatives: open the PR first, or take the review as a markdown file you can hand over.

## Phase 8 — The other two exits (only if asked)

- **Fix the findings** — review-only is the default. If asked to fix, apply findings
  smallest-first, run the repo's own gates, and report what you changed and what you left.
- **Comment on the ticket** — via the tracker's MCP, following the repo's comment conventions.
  Keep it to the verdict and blockers with a PR link; the full review belongs on the PR.
