# `senior-pr-reviewer` — changes (draft)

**Status:** draft in staging, copied from `~/.claude/skills/senior-pr-reviewer/` and improved.
Nothing installed. To install, copy this folder over the original (keep a backup). Scope is
unchanged: review-only, verify before report, offer to post with an explicit go-ahead.

## Why

It is now the **primary method of the `reviewer-code` agent** in the AI delivery workflow (the
agent preloads it). The agent needs a report it can reuse directly (a `VERDICT:` first line and
the loop's severities), and the skill benefited from a few rules the overlapping reviewers have.

## What changed

**Two output modes** (`SKILL.md` intro, `report-format.md` "Verdict header compatibility").
Standalone keeps the `## Review: … — <verdict>` header. In the delivery loop the first line is
`VERDICT: PASS | CHANGES`; Approve / Approve with comments → PASS, Request changes → CHANGES
(High-confidence Blockers / Majors only), "cannot assess" → CHANGES only when the builder can
supply what is missing, otherwise no verdict and the worker escalates. Phases 7–8 (post, fix)
are skipped in the loop.

**Confidence levels** (`SKILL.md` Phase 5, finding shape, report skeleton). Every finding is
High or Medium; Medium goes to a "Needs confirmation" section and is never a Blocker; Low is
dropped.

**Severity crosswalk** (`report-format.md`). Blocker / Major / Minor / Nit mapped to ecc
CRITICAL / HIGH / MEDIUM / LOW, Sentry Critical-High / Medium / Low, and the loop's blocking /
important / nit, so reports from different reviewers merge cleanly.

**Scoping and noise rules** (Phase 1, 2, 5). Draft PRs are reviewed (the loop reviews drafts);
closed PRs are not; a repeat review is a delta. `CLAUDE.md` rules apply only to files in that
file's directory or below, must be quoted with their file, and explicitly silenced rules are not
findings. Kill candidates a linter / formatter / typechecker in CI would catch, and ones that
depend on impossible inputs. On large reviews, validate each surviving candidate independently.

**Inline comment hygiene** (`report-format.md`). Suggestion blocks only when committing them
fixes the issue entirely; one comment per unique issue; permalinks with the full SHA and a
context line.

**Optional skills** (`SKILL.md` Phase 3, `delegation.md`). `security-review` (Sentry) and
`test-driven-development` (obra) replace `senior-security` and `senior-qa` as the optional
lenses; the built-in `/security-review` note points at the same-named Sentry skill.

## Provenance

- **Taken from `ecc:code-review`** (ecc plugin, `commands/code-review.md`): the severity
  vocabulary for the crosswalk; the decision rule "zero CRITICAL/HIGH and validation passes →
  approve, only MEDIUM/LOW → approve with comments, any HIGH → request changes" (folded into the
  verdict mapping); "a PR URL works as well as a number". Not taken: its fixed thresholds
  (functions > 50 lines, files > 800 lines, emoji, console.log) — repo rules decide those.
- **Taken from the built-in `code-review`** (claude-plugins-official, `commands/code-review.md`):
  high-signal-only stance and its false-positive list (linter-catchable, pre-existing, silenced
  in code, depends on specific inputs); `CLAUDE.md` rules scoped to the file's directory and
  quoted; independent validation of each candidate; suggestion blocks only when they fully fix;
  one comment per issue; full-SHA permalinks. Not taken: skipping draft PRs (the loop reviews
  drafts) and its fixed agent fan-out.
- **Taken from `security-review`** (Sentry): High / Medium / Low confidence with "report only
  High, note Medium as needs verification".

## Open question for the owner

1. Replace the installed skill with this version (recommended — the standalone behaviour is the
   same apart from the confidence line and the "Needs confirmation" section), or keep both and
   point the agent at the staged copy?

## Owner decisions applied (2026-11-08, all recommendations accepted)

- **#31:** accepted — this staged copy replaces the installed `senior-pr-reviewer`. Installing
  it is a separate step; no file content changed for this decision.
