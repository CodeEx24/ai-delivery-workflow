# Ticket record, proof placement and tracker updates

Where evidence goes (workflow section 7): the **ticket** carries what the owner reads and audits;
the **PR** carries the technical trail; the **repo** keeps only the ticket record (the *why*).
Nothing is duplicated — the PR links to the ticket's proof comment.

## Contents

- [Finding the ticket key and every PR](#finding-the-ticket-key-and-every-pr)
- [Closing the ticket record](#closing-the-ticket-record)
- [Gathering the facts](#gathering-the-facts)
- [Idempotency](#idempotency)
- [Ticket close-out comment](#ticket-close-out-comment)
- [Attaching screenshots](#attaching-screenshots)
- [PR close-out comment](#pr-close-out-comment)
- [Deferrals on the follow-up ticket](#deferrals-on-the-follow-up-ticket)
- [Tracker markup](#tracker-markup)
- [Transitions](#transitions)

## Finding the ticket key and every PR

Priority: branch name (`feat/<key>-<n>/slug`), PR title, commit messages, PR body, the ticket
record's links block. Normalise case (`abc-12` → `ABC-12`). Several distinct keys → ask.

```bash
gh pr view <n> --json title,body,headRefName,commits \
  --jq '[.title, .headRefName, .body, (.commits[].messageHeadline)] | join(" ")' \
  | grep -oiE '[A-Z][A-Z0-9]{1,9}-[0-9]+' | sort -u
gh pr list --search "<KEY>-<n>" --state all --json number,state,url   # all PRs for the ticket
```

## Closing the ticket record

File: `docs/tickets/<KEY>-<n>-<slug>.md` (or `docs/tickets/<KEY>-<n>-<slug>/README.md`). Edit only these parts:

```
Ticket: <PM tool link>                                  ← present and correct
PRs: <PR link> (main) · <PR link> (follow-up fix)       ← every PR, add missing
Related: blocked by … · follow-up … · deferred to …     ← add follow-ups/deferrals created in the loop
Type: … · Risk: … · Status: Merged                      ← set Merged

## Outcome
- Deviations: <what differs from ## Design, and why> | none
- Known limitations: <…> | none
- Follow-ups: <KEY>-<n> <title> · … | none
- Deferred: AC3 → <KEY>-<n> (owner decision, <date>) | none
- Feature guide: docs/features/<area>.md
```

Sources: the approver's `decision.md`, round reports in `.delivery/jobs/<KEY>-<n>/`, the PR
description/walkthrough, ticket comments. If a fact is unknown, write what is known and flag it
in the report — never invent.

**Normal path:** commit on the PR branch before the merge so it lands in the squash.
**Already-merged path:** if the record on the base branch is incomplete, open a tiny follow-up PR
(`docs/<key>-<n>/close-out-record`, commit `docs(<scope>): close out ticket record (<KEY>-<n>)`),
add it to the links block itself, and merge it through the same merge path. Do not push to the base branch
directly unless the project explicitly allows doc commits there.

No ticket record convention in the repo → skip and say so.

## Gathering the facts

| Fact | Where to read it |
|---|---|
| AC verbatim | ticket record `## Acceptance criteria`, else the ticket |
| AC results + screenshot names | `round-N/test-device.md`, `round-N/test-functional.md` (latest round), else the device tester's ticket comment |
| Per-round verdicts | every `round-N/*.md` first line (`VERDICT: …`) + its summary line |
| Approver decision | `decision.md` (first line `APPROVE` / `ESCALATE`) or its PR comment |
| Owner decisions / deferrals | ticket record `## Decisions`, ticket comments |
| CI | `gh pr checks <n>` on the merged head |
| Cost | `scripts/workflow/cost <KEY>-<n>` (the standard name, recorded in `docs/workflow/README.md`; another name only if that doc says so) prints the total; omit if none |

Read all of this **before** cleanup deletes the working folder.

## Idempotency

Re-runs are normal (owner-merge path, crashed session). Before writing anything:

- **GitHub PR:** close-out comments carry a hidden marker on the first line:
  `<!-- merge-ticket:close-out <KEY>-<n> -->`. Find it with
  `gh pr view <n> --json comments --jq '.comments[] | select(.body | contains("merge-ticket:close-out")) | .url'`.
  Found → edit it in place if facts changed (`gh api -X PATCH repos/{owner}/{repo}/issues/comments/<id> -f body=@file`)
  or skip. Not found → post.
- **Tracker:** wikimarkup has no hidden comments, so use a fixed heading `Close-out — <KEY>-<n>`
  and search the issue's comments for it (and for the PR URL). Found → post only a short delta
  (deploy finished, follow-up filed) or nothing.
- **Attachments:** list the issue's attachments and upload only filenames not already there.

## Ticket close-out comment

Jira wikimarkup shown; use Markdown for Linear / GitHub Issues.

```
h2. Close-out — <KEY>-<n>

*Merged* via PR [#<n>|<url>] to {{main}} on <date> (squash {{<sha7>}}). Follow-up PRs: <list or none>.
Deploy: <workflow> [run <id>|<url>] — *success* | no post-merge deploy.

h3. Acceptance criteria

||#||Criterion (verbatim)||Result||Evidence||
|AC1|<text>|PASS|<KEY>-<n>-AC1-step-01.png … step-04.png|
|AC2|<text>|PASS|test {{<test name>}} (functional)|
|AC3|<text>|Deferred → <KEY>-<m>|owner decision <date>|

h3. Step-by-step proof

Screenshots are attached to this ticket; steps per criterion are in the device test comment
[<link to tester-device comment>] (or listed here if none exists: AC → numbered steps → file).

h3. Decisions and deferrals

* <decision> — <who>, <date>
* AC3 deferred to <KEY>-<m> — <owner>, <date>

h3. Final status

Done. Ticket record: {{docs/tickets/<KEY>-<n>-<slug>.md}} · Feature guide: {{docs/features/<area>.md}}
```

Variants:
- **Deploy failed** → heading `Merged — deploy FAILED, change is not live`, the failing step in
  `{noformat}`, "Leaving this ticket in <status> until the deploy succeeds." No Done.
- **Already merged by someone else, proof already posted** → a two-line delta: merge fact + deploy.

## Attaching screenshots

Source: `.delivery/jobs/<KEY>-<n>/round-<N>/screenshots/` (`<KEY>-<n>-AC<k>-step-<nn>.png`; latest round first). The device tester usually
uploaded them already — upload only the missing ones.

1. **API first.** If the tracker connector or CLI can upload attachments (e.g. Jira REST
   `POST /rest/api/3/issue/<KEY>/attachments` with an API token the user configured, Linear's
   file upload), use it.
2. **Browser fallback** when the API cannot upload (many MCP connectors cannot): use a signed-in
   browser session — open the issue in a new tab, find the hidden attachment `<input type=file>`,
   and set the files with the driver's file-upload action (e.g. Claude in Chrome `file_upload`,
   Playwright `browser_file_upload`). Confirm the attachments appear, then close your tab.
3. Neither possible → say so, list the local paths, and **do not delete the working folder**;
   the owner needs the files.

## Evidence PDFs

Link the ticket's `📁 Evidence Index` in the close-out instead of listing every screenshot. Use the
individual screenshot route above only when no PDF exists.

## PR close-out comment

Markdown. Links to the ticket proof instead of embedding images.

```
<!-- merge-ticket:close-out <KEY>-<n> -->
## Close-out — <KEY>-<n>

**Merged** <date> · squash `<sha7>` · ticket: <ticket URL> · proof (AC table + screenshots): <ticket comment URL>

### Review and test rounds
| Round | Gate | Functional | Device | Code | Security | UI | UX |
|---|---|---|---|---|---|---|---|
| 1 | PASS | CHANGES — <one line> | PASS | PASS | – | PASS | CHANGES — <one line> |
| 2 | PASS | PASS | PASS | PASS | – | PASS | PASS |
| pre-merge re-gate | PASS on `<sha7>` (re-synced with the base branch) | | | | | | |

### Approver
APPROVE — <one-line reason> (<link to decision comment>)

### CI and deploy
CI: green on `<sha7>` (<checks link>) · Deploy: <run link> success | none

### Cost of this ticket's agents
<total> (<model: tokens, cost> …) — from `<cost script>` | not tracked in this project
```

## Deferrals on the follow-up ticket

For each deferred criterion, comment on the follow-up ticket (idempotent: search for the source
key first):

```
h3. Deferred from <KEY>-<n>

AC<k> of <KEY>-<n> ("<verbatim text>") was deferred here by <owner> on <date>. Reason: <…>.
Source PR: <url> · Close-out: <ticket comment url>
```

Make sure the follow-up ticket is linked to the source ("relates to" / "is blocked by" as the
project uses) and listed under `Related:` in the ticket record.

## Tracker markup

Jira comment bodies use **wikimarkup**, not Markdown:

| Want | Write | Not |
|---|---|---|
| Heading | `h2. Title` | `## Title` |
| Bold | `*bold*` | `**bold**` |
| Inline code | `{{code}}` | `` `code` `` |
| Code / log block | `{noformat}` … `{noformat}` | fences |
| Link | `[text|https://url]` | `[text](url)` |
| Table header / row | `||a||b||` / `|a|b|` | Markdown tables |
| Bullet / numbered | `* item` / `# item` | `- item` / `1. item` |

Blank line before a list; avoid `*` and `_` inside `{{…}}`. Some connectors accept Markdown or
ADF instead — check the connector's description. Linear and GitHub Issues use Markdown.

## Transitions

Never hardcode an id — fetch and match by name:

```
getTransitionsForJiraIssue(cloudId, key)  →  pick by name  →  transitionJiraIssue(cloudId, key, {id})
```

| Situation | Status |
|---|---|
| Merged, deploy green or none | the done status (`Done` / `Closed` / `Resolved`) |
| Merged, deploy failed | leave it, or back to `In Progress` — never Done |
| Merged, deploy running | wait; if the user cannot wait, leave it and say so |
| Separate release step tracked | the intermediate status (`Ready for Release`, `In QA`) |
| Waiting for the owner to merge | leave it; add the `ready-to-merge` label (not `needs-human`) |

Wanted status not offered → the workflow needs an intermediate hop; take the obvious two-step
path if one exists and say so, else report the options. Verify the new status in the response.
Remove the `ready-to-merge` label once the ticket is Done, and `needs-human` if an escalation
on this ticket was resolved and nothing else waits on the owner.

**Other trackers:** Linear — its connector, states fetched the same way. GitHub Issues —
`gh issue comment` / `gh issue close` (check whether `Closes #n` already closed it). No tracker —
put the close-out on the PR only and say so.

**Attribution:** follow the user's own convention for AI attribution in comments and commits.
