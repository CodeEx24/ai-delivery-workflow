# Report format

## Severity ladder

Assign severity by consequence, not by how much code it takes to fix.

| Severity | Means | Merge? |
|---|---|---|
| **Blocker** | Breaks correctness, leaks or exposes data, bypasses the real enforcement boundary, loses or corrupts data, breaks a CI gate, or violates a stated non-negotiable rule of the repo. | No |
| **Major** | Works today but will bite: an unhandled real-world case, a missing mandated test, an N+1 or unbounded query on a live path, a contract change with an unmigrated consumer, a silent failure mode. | Fix in this PR |
| **Minor** | Real but contained: a confusing name on a public surface, a missing edge-case test, a doc that now lies, a duplicated rule that can drift. | Author's call |
| **Nit** | Cosmetic, non-mandated preference. Prefix literally with `Nit:` so it is trivially skippable. Keep these rare. | Ignorable |
| **Praise** | A judgment call worth repeating. One or two, specific. | — |

Pre-existing problems the diff did not touch are **Context**, not findings. Name them once, say
they are out of scope, and move on.

Other vocabularies map onto this ladder (so reports from other reviewers can be merged):

| Here | ecc / generic | Sentry security-review | Delivery loop (`review-*.md`) |
|---|---|---|---|
| Blocker | CRITICAL | Critical / High | blocking |
| Major | HIGH | Medium | important |
| Minor | MEDIUM | Low | nit |
| Nit | LOW | — | nit |

## Verdict

Open with the verdict so the author knows where they stand in one line:

- **Approve** — nothing blocking or major. Say it plainly.
- **Approve with comments** — no blockers; the majors are the author's to land.
- **Request changes** — at least one Blocker or an unaddressed Major.
- **Blocked / cannot assess** — you could not get the diff, the intent, or a gate result you need.
  Say exactly what is missing.

## Verdict header compatibility

The first line is machine-readable so other tools can reuse the report:

| Mode | First line |
|---|---|
| Standalone | `## Review: <PR title or branch>  —  <Approve \| Approve with comments \| Request changes \| Blocked>` |
| Delivery loop (`reviewer-code`) | `VERDICT: PASS` or `VERDICT: CHANGES` |

Verdict mapping: Approve and Approve with comments → `VERDICT: PASS`; Request changes →
`VERDICT: CHANGES` (only for **High-confidence** Blockers or Majors). Blocked / cannot assess
→ in the loop, `VERDICT: CHANGES` with one Blocker "cannot assess: <what is missing>" **only
if the builder can supply it** (no PR description, no ticket record); if only the owner can
(access, a missing environment), write no verdict and tell the worker why, so it escalates.
In the loop, use the `review-code.md` sections (Summary, Findings, Previous findings, Notes,
Scope) from the reviewer-code agent file; each finding keeps this skill's shape below.

## Finding shape

Every finding, in this order:

```
**[Severity] Short claim** — `path/to/file.ts:42`

What breaks: <input / state / sequence> → <wrong result>.

Why: <the mechanism, one or two sentences, referencing the code that is actually there>

Fix: <the concrete change, or a diff/snippet when it is short>

Verified: ran `npm test -- foo.test.ts` (output below) | read-only, needs confirmation by <what>
Confidence: High | Medium
```

Rules:

- **One finding per defect.** Do not bundle three unrelated issues into one bullet.
- **Locate it.** `file:line` on every finding; a finding without a location is not actionable.
- **No naked "consider".** Either it matters and you can say why, or it does not belong in the
  review.
- **Quote the guard you checked** when you decided something was *not* a problem and the author
  might reasonably think it is — that is how a review builds trust.
- **Ordering:** Blocker → Major → Minor → Nit → Praise, and within a severity, highest-consequence
  first.

## Full report skeleton

```markdown
## Review: <PR title or branch>  —  <verdict>

<base>…<head> · N files · +X −Y · Intent: <one line>
Rules held to: <repo rules that governed this review>
Lenses: correctness, security, tests · Skipped: frontend (no UI files), migrations (none)

### Blockers
…

### Major
…

### Minor / Nits
…

### Needs confirmation
- <Medium-confidence item> — `file:line` — what would settle it

### Verified
- `npm run typecheck` — clean
- `npx vitest run src/lib/foo.test.ts` — 12 passed
- Not run: full suite (slow), RLS suite (needs Docker)

### Good
- <specific thing worth repeating>

### Manual check before merge
- <the one thing a human should click or run>
```

Keep the whole thing as short as the diff allows. A 40-line diff does not get a 400-line review.

## Posting to the PR

Outward-facing, and it notifies every subscriber. Show the exact body first and get a go-ahead;
that approval covers that post, not the next one.

Prerequisites, checked once before you compose anything: `gh auth status` (a token with `repo`
scope) and `gh repo view --json nameWithOwner` to confirm you are pointed at the right repository.
If the PR belongs to a different repo than the working directory, pass `--repo <owner>/<name>` on
every command.

**Always write the body to a file** in the scratchpad directory and pass it by path. Review bodies
contain backticks, newlines, `$`, and quotes — inline `--body "..."` mangles them.

### Option A — one summary comment (the usual choice)

One notification, reads as a whole, survives a force-push:

```bash
gh pr comment <n> --body-file "<scratchpad>/review.md"
```

### Option B — inline comments plus a summary, as a single review

Anchors each finding to its line, and arrives as one notification rather than a stream. Build a
JSON payload and pipe it through `--input`, which is the only reliable way to send an array of
comments:

```bash
cat > "<scratchpad>/review.json" <<'JSON'
{
  "event": "COMMENT",
  "body": "## Review: <title> — request changes\n\n<summary, verdict, verified list>",
  "comments": [
    {
      "path": "src/lib/foo.ts",
      "line": 42,
      "side": "RIGHT",
      "body": "**[Blocker]** <claim>\n\nWhat breaks: …\n\nFix: …"
    },
    {
      "path": "src/lib/bar.ts",
      "start_line": 10,
      "line": 14,
      "side": "RIGHT",
      "body": "**[Major]** <claim> …"
    }
  ]
}
JSON
gh api "repos/{owner}/{repo}/pulls/<n>/reviews" -X POST --input "<scratchpad>/review.json"
```

Comment bodies: a short claim, the failure, the fix. Add a GitHub suggestion block
(```` ```suggestion ````) only when committing it fixes the issue entirely (small, one hunk);
larger fixes are described, not suggested. One comment per unique issue. When linking code
outside the diff, use a permalink with the **full** commit SHA and a line range with a line of
context (`https://github.com/<owner>/<repo>/blob/<full-sha>/path/file.ts#L41-L44`).

Constraints the API enforces — violate one and the whole review is rejected, not just the comment:

- `line` must be a line **present in the diff** for that file, on the matching `side` (`RIGHT` for
  added/context lines in the head, `LEFT` for removed lines). Get the valid line numbers from
  `gh pr diff <n>` rather than from the file on disk.
- A multi-line comment uses `start_line` + `line`, both inside the same hunk.
- `path` is repo-relative, exactly as the diff spells it.
- A comment on a file the PR did not touch is not possible — put those findings in the summary
  body instead.

### `event` values

| Value | Effect |
|---|---|
| `COMMENT` | Leaves the review without a formal state. **The default.** |
| `REQUEST_CHANGES` | Formally blocks; counts against branch protection. Only on explicit request. |
| `APPROVE` | Formally approves; can unblock a merge. Only on explicit request — and never on your own PR, which GitHub rejects anyway. |

### Replying to an existing thread

Continue the conversation instead of opening a parallel one:

```bash
gh api repos/{owner}/{repo}/pulls/<n>/comments/<comment_id>/replies \
  -X POST -f body="<reply>"
```

Get `<comment_id>` from `gh api repos/{owner}/{repo}/pulls/<n>/comments --jq '.[] | {id,path,line,user:.user.login}'`.
Resolving threads is the author's call, not the reviewer's — do not resolve for them.

### After posting

- Report the URL the command returned (`gh pr view <n> --json comments` or the API response
  `html_url`) plus one line on what went up.
- Do not post the same review twice. If a re-review is wanted after new commits, review the new
  commits (`git diff <old-head>..<new-head>`) and post a short delta, not a repeat.
- Never post a finding you marked "needs confirmation" as though it were confirmed — carry the
  hedge into the comment text.

## Commenting on the ticket

Use the tracker's MCP tool and the repo's stated comment conventions. Keep it to the verdict and
the blockers with a link to the PR — the full review belongs on the PR, not the ticket.
