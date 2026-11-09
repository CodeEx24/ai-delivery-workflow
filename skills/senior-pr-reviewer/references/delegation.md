# Delegation: optional skills, subagents, and the built-in reviewers

## Optional domain skills

Preferred where installed: **`security-review`** (Sentry) for the security lens and
**`test-driven-development`** (obra; its `writing-good-tests.md`) for judging whether new tests
can fail. They replace `senior-security` and `senior-qa`, which stay installed but are no
longer referenced. The remaining community skills below are optional — check for them only when the
diff is genuinely heavy in that domain, and never block on a missing one.

| Skill | Reach for it when the diff is heavy in |
|---|---|
| `senior-architect` | a new boundary or module, schema or contract change, cross-cutting refactor, dependency choice |
| `senior-fullstack` | broad app-layer change across UI, API, and data together |

Install (global, one per command):

```bash
npx claude-code-templates@latest --skill development/senior-architect
npx claude-code-templates@latest --skill development/senior-fullstack
```

**What they actually are.** As shipped, these are thin generic templates: their `references/*.md`
are placeholder patterns ("Pattern 1: Best Practice Implementation"), and their scripts scaffold
or audit *whole projects* — they do not read a diff. So:

- Use one as a **thinking frame** for a second pass in that domain's vocabulary. It can surface a
  category you skipped.
- **Never treat their output as findings.** Every finding still has to come from this repo's code
  and survive Phase 5 verification.
- **Never run their scaffolding or auditing scripts during a review.** A review does not write
  files, generate projects, or run a pentest tool. `pentest_automator.py` in particular points
  tooling at a target — out of scope for reviewing a diff, and not something to run against
  anything you have not been explicitly authorized to test.
- If one turns out to have real substance in a later version, it still ranks below the repo's own
  `CLAUDE.md` and `references/review-lenses.md`.

## The built-in reviewers

Two built-ins overlap and compose well — prefer them over the community skills for actual defect
finding:

- **`/code-review`** — the mechanical correctness sweep over the current diff, at a chosen effort
  level, with a verify pass and structured findings. Good as the *first* pass inside Phase 4 on a
  large diff: let it enumerate correctness candidates, then spend your own attention on the lenses
  it does not cover (authorization intent, architecture fit, rollout, repo non-negotiables) and on
  Phase 5.
- **`/security-review`** — a focused security pass over the branch's pending changes. The
  installed **`security-review` skill** (Sentry, OWASP-based, high-confidence reporting) has
  the same name and is the better method when present: reach for it in place of hand-rolling
  the security lens when the diff is substantially about auth or data exposure.

Their findings are candidates, not conclusions. You still own the verdict, and you still delete
what does not survive verification.

## Subagents

Default: do the review yourself. Reviewing is exactly the work that suffers from a summarized
hand-off, and a small diff fans out into more coordination than it saves.

Fan out only when the diff is genuinely large — roughly **15+ files or 500+ changed lines** — and
splits cleanly. Then dispatch one agent per lens (not per file), in a single message so they run
concurrently, each with:

- the lens and its checklist from `references/review-lenses.md`,
- the specific file list it owns,
- the repo rules from Phase 2,
- the instruction to return **candidate** findings with `file:line` and a failure scenario, and to
  say plainly what it could not verify.

Then do Phase 5 yourself on everything that comes back, in one place, with the whole diff in view.
Cross-lens defects — a caller in a file another agent owned, a rule violated across two lenses —
only show up at the merge step, so never skip it.

Sweeps that are cheap to delegate and safe to trust: "find every caller of X repo-wide", "list
every consumer of this response shape", "which test files touch this module". Those are searches,
not judgments.

## Reviewing your own work

When the diff is yours, the review still runs unchanged — with one addition: you are the least
reliable judge of whether the approach was right, because you already argued yourself into it.
Give the architecture lens an extra pass, and state explicitly which of your own judgment calls a
different engineer would plausibly have made differently.
