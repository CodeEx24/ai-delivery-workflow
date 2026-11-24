# Recipes for wave status

Queries for reading waves, ticket types and status per tracker, fetching and matching pull
requests, reading the owner queue, and the housekeeping checks. Tool and field names vary by
connector version and project configuration — the loaded tool's own description is the
authority. Everything here is a read.

## Contents

- [Jira](#jira)
- [GitHub Issues](#github-issues)
- [Linear](#linear)
- [Ticket types and critical bugs](#ticket-types-and-critical-bugs)
- [Concurrency cap](#concurrency-cap)
- [Pull requests](#pull-requests)
- [Matching PRs to tickets](#matching-prs-to-tickets)
- [Is there activity on a ticket with no PR?](#is-there-activity-on-a-ticket-with-no-pr)
- [Needs the owner](#needs-the-owner)
- [Housekeeping](#housekeeping)
- [The summary block](#the-summary-block)
- [Shell notes for Windows](#shell-notes-for-windows)

## Jira

Through the Atlassian connector. The tools are usually deferred: load
`getAccessibleAtlassianResources`, `searchJiraIssuesUsingJql`, `getJiraIssue`,
`atlassianUserInfo`. If two Atlassian connectors are present, use one consistently.

1. `getAccessibleAtlassianResources` once for the cloud id; `atlassianUserInfo` for the
   current user's account id and display name.
2. **Find the waves.** When waves are labels, one query over the project's open work shows
   which exist:

   ```
   searchJiraIssuesUsingJql(
     cloudId,
     jql: "project = VD AND statusCategory != Done ORDER BY key ASC",
     fields: ["summary","status","labels","priority","assignee","issuelinks",
              "issuetype","parent","fixVersions","resolution"],
     maxResults: 100)
   ```

   Page until there is no `nextPageToken`. The lowest wave label present among these open
   tickets is the base wave N; count its open tickets to decide whether N+1 joins the window
   (≤ 2 open). (If no open ticket carries any wave label, either everything waved is done or
   the project has no waves — a second query for `labels in (wave-1, wave-2, …)` or a look at
   a few done tickets tells you which.) This same result gives the `needs-human` tickets and
   the open Bugs of every wave — filter it locally rather than querying again.
3. **Read the whole window**, done tickets included, for the percentage:

   ```
   jql: "project = VD AND labels in (wave-2, wave-3) ORDER BY key ASC"
   ```

   For other conventions: `fixVersion = "Wave 2"`, `"Wave" = "Wave 2"` (a custom field, by
   its name in quotes), `parent = VD-10` (an epic per wave).
4. **Status category:** `fields.status.statusCategory.name` is `To Do`, `In Progress` or
   `Done`. Show `fields.status.name` in the table but group by category.
5. **Resolved but not delivered:** `fields.resolution.name` of `Won't Do`, `Duplicate`,
   `Cannot Reproduce` and similar — leave out of the percentage.
6. **Dependencies:** in `fields.issuelinks`, for the `Blocks` type, an entry with
   `inwardIssue: Y` on ticket X reads "X is blocked by Y" (X depends on Y); an entry with
   `outwardIssue: Y` reads "X blocks Y". The linked issue's status is included in the entry,
   so a blocker's state is available without a second fetch.
7. **Time in status**, for the stale check, needs the changelog, which the search does not
   return. `fields.updated` is a cheap proxy: an In Progress ticket not updated in a long
   while is worth mentioning. Call it "not updated since", not "stale since".

## GitHub Issues

```
gh issue list --state all --limit 1000 --json number,title,state,stateReason,labels,milestone,assignees,body,closedAt
gh api user --jq .login
```

- Raise `--limit` above the issue count; the default of 30 truncates silently.
- Waves are usually labels (`wave-2`) or milestones; filter locally, or with
  `--label wave-2` / `--milestone "Wave 2"`.
- **Status** is coarse: open or closed. "In progress" is usually a label, a Projects status
  field, or simply "has an assignee and an open PR". Say which signal you used.
- A closed issue with `stateReason: NOT_PLANNED` is resolved, not delivered.
- **Mismatches are rarer here** because a PR body containing `Closes #42` closes the issue on
  merge. The cases that remain: the PR said `Refs #42` or nothing, or the PR merged into a
  non-default branch (auto-close only fires on the default branch).
- Dependencies: native blocked-by relations where the repo uses them
  (`gh api repos/{owner}/{repo}/issues/<n>/dependencies/blocked_by`; a 404 means the feature
  is unavailable — fall back to text), otherwise `Blocked by #12` / `Depends on #12` lines in
  the body.

## Linear

Through the Linear connector: list the team's or project's issues with state, labels,
priority, assignee, and relations.

- State **type** is the category: `backlog` / `unstarted` → to do, `started` → in progress,
  `completed` → done, `canceled` → resolved but not delivered.
- Linear's GitHub integration often moves issues automatically when a PR merges, so check
  whether it is installed before reporting a mismatch as an oversight — but still report it.
- Linear branch names embed the issue key in lower case (`user/vd-42-short-title`).

## Ticket types and critical bugs

- **Jira:** `fields.issuetype.name`. A `type:` label, if the project uses one, wins over the
  issue type (projects that cannot change issue types add the label instead).
- **GitHub Issues:** a `type:` label (`type:bug`, `type:spike`), or the native issue type
  where the organisation uses them (`gh api repos/{owner}/{repo}/issues/<n> --jq .type.name`;
  `null` means none).
- **Linear:** a type label (`Bug`, `Feature`, `Chore`, `Spike`), or the team's convention.
- **Mapping** to Feature / Bug / Chore / Spike: the project's mapping if it states one;
  otherwise Story → Feature, Bug → Bug, Task / Sub-task / Improvement → show raw with `?`
  (it could be a Feature or a Chore — do not guess), and suggest the recommended line
  "Task → Chore" for `docs/workflow/README.md`.

**Critical bug** = a Bug that the tracker marks as top severity: Jira priority `Highest` /
`Blocker` or a severity field / `severity:critical` label; GitHub `severity:critical` or `P0`
label; Linear priority 1 (urgent). Wording in the summary such as "data loss", "security",
"crash on start" supports it but is not enough alone — say "possibly critical" and let the
human decide; only a tracker-marked critical bug jumps the window in the summary block.

## Concurrency cap

Look in `docs/workflow/README.md` (or the workflow doc `CLAUDE.md` links) for a line about
tickets in flight, concurrency, parallel worktrees or slots, e.g. "concurrency cap: 3" or
"at most 2–3 tickets in flight". Take a single number as given; for a range take the upper
bound and quote the text. Nothing found → 2, reported as the default. The cap counts tickets
being built or in the review loop; tickets waiting on the owner do not hold a slot.

## Pull requests

One call covers the whole cross-check:

```
gh pr list --state all --limit 300 --json number,title,headRefName,baseRefName,state,isDraft,mergedAt,closedAt,url,body
```

- `state` is `OPEN`, `MERGED` or `CLOSED`. There is no `merged` field; asking for one is an
  error.
- Raise `--limit` if the repo has more PRs than that since the wave began; the list is
  newest first, so an older merged PR can fall off the end. If a ticket in the wave has no
  match and the list was truncated, search for it specifically before concluding there is no
  PR: `gh pr list --state all --search "VD-41" --json number,title,headRefName,state,mergedAt,url`.
- The base branch: `python "$HOME/.claude/skills/delivery-config/config.py" --repo . branch --json` (`base`, else `recommended`). This report never saves it.
- The default branch: `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name`.

For an open PR that is the candidate for "finish this first", its readiness is cheap to add:

```
gh pr view <n> --json reviewDecision,mergeStateStatus,statusCheckRollup,isDraft
```

`reviewDecision` (`APPROVED` / `CHANGES_REQUESTED` / `REVIEW_REQUIRED`), `mergeStateStatus`
(`CLEAN`, `BLOCKED`, `BEHIND`, `DIRTY`), and whether every entry in `statusCheckRollup`
concluded successfully. Read these for the one or two PRs that matter, not for all of them.

## Matching PRs to tickets

Look for the ticket key in the PR's `headRefName`, `title`, then `body`, in that order of
trust — a key in the branch name or title means the PR is *for* that ticket; a key that only
appears in the body may be a passing mention ("follow-up to VD-12").

- **Whole-key match, case-insensitive.** The key must not be followed by another digit:
  `VD-4` matches `feat/vd-4-login` and `[VD-4] Login`, not `VD-42`. As a pattern:
  `(?<![A-Za-z0-9])VD-4(?![0-9])` with case-insensitive matching.
- **GitHub Issues keys** are `#42`: look for `#42` not followed by a digit, and for closing
  keywords (`Closes`, `Fixes`, `Resolves`) to tell a PR that delivers the issue from one that
  mentions it.
- **Several PRs for one key** is normal (a fix-up, a split delivery, a revert). Read them
  together: the ticket has landed only when at least one merged into the project's base branch and
  none is still open. A PR whose title starts with `Revert` and names the same key means the
  work was backed out — treat the ticket as not landed and say so.
- **Base branch.** `baseRefName` must be the project's base branch (or the release branch the repo's
  docs name) for a merge to count. A PR merged into another feature branch is part of a
  stack; follow it to the PR that carries it into the project's base branch.
- **A body-only match** is weak evidence. Report the mismatch as "possibly" and show the PR
  title so the user can judge.

## Is there activity on a ticket with no PR?

Before calling an In Progress ticket possibly stale, look for work that has not become a PR
yet:

```
git fetch --prune
git branch -a -i --list "*vd-45*"
git log --all --oneline -i --grep "VD-45" -5
```

A recent branch or commit means it is in flight, just unpublished. Report what you found
("branch `feat/vd-45-export`, last commit 2 days ago, no PR yet"). `git fetch` only updates
remote-tracking refs; it does not touch the working tree. If the session has no network or
the fetch fails, say the branch check used local refs only.

Also look for a worktree or job folder for the key (both mean someone — or an agent — is on
it, even with no commits yet): the `git worktree list --porcelain` output from
[Housekeeping](#housekeeping), and `.delivery/jobs/<KEY>-<n>/` in the main checkout and each
worktree (match the folder name case-insensitively, whole key).

## Needs the owner

**Tickets.** Filter the open-ticket result for the `needs-human` label (or the label the
workflow doc names). For each, the latest comment usually holds the question: Jira
`getJiraIssue` with `fields: ["comment"]` for those few tickets only; GitHub
`gh issue view <n> --json comments`.

**Escalated PRs.**

```
gh pr list --state open --label needs-human --json number,title,headRefName,url
gh pr list --state open --label ready-to-merge --json number,title,headRefName,url
```

`ready-to-merge` (or the label the workflow doc names) marks an approved PR waiting for the
owner's merge. List those under "Ready for your merge", never as escalations.

Then, for the open PRs of window tickets only (not every PR in the repo), read the latest
comments and look for an approver decision starting with `ESCALATE`:

```
gh pr view <n> --json comments,labels
```

A later `APPROVE` comment supersedes an earlier `ESCALATE`. Quote the question line that
follows `ESCALATE`.

**Owner guides.** `Glob docs/actions/*.md` (skip the generated `README.md`), then read each
file's YAML front matter:

```
---
status: open        # open | done
tickets: [VD-46]
order: 3
estimate: 10 min
---
```

List those with `status: open`, sorted by `order` (missing order last). A guide without
front matter: list it as "status unknown (no front matter)". Cross-reference `tickets` with
the board: all Done → suggest closing the guide; a ready ticket listed → the guide comes
first.

## Housekeeping

All read-only. Run from the main checkout.

```
git worktree list --porcelain
git branch --format "%(refname:short) %(upstream:short) %(upstream:track)"
```

- **Worktree of a merged PR:** each `worktree` block has a `branch refs/heads/<name>` line;
  match `<name>` to a PR `headRefName` with `state: MERGED` (from the PR list already
  fetched), or to a Done ticket's key. The main checkout itself is never a leftover.
- **Branch of a merged PR:** same match for local branches. `[gone]` in the track column
  means the remote branch was deleted (usually after merge). Do not rely on
  `git branch --merged`: squash merges leave the branch looking unmerged.
- **Prunable:** a worktree block containing `prunable` — the folder is gone, the record is
  not. Fix: `git worktree prune`.
- **Job folders:** `Glob .delivery/jobs/*/` in the main checkout and in each worktree path.
  The folder name is the ticket key. Stale when the ticket is Done or its PR merged/closed;
  stalled when the ticket is open but the newest file in the folder is older than 2 days
  (`git` does not track it — check file times with the Glob results or `ls -lt`).
- A worktree with uncommitted changes or unpushed commits is reported with that warning
  (`git -C <path> status --porcelain`, `git -C <path> log @{u}..`), because the cleanup must
  not destroy work.

Report each item with its fix — `merge-ticket <KEY>` for merged-PR leftovers (its cleanup
checks clean-and-pushed before removing anything), `git worktree prune` for prunable
records — and never run the fix.

## The summary block

The last thing in every report is one fenced `json` block. An orchestrator (`/deliver`, a
`/loop` cycle) parses it instead of the prose, so its shape is a contract:

- **Always present**, even when the cross-check could not run or nothing is ready.
- **Stable keys.** Every key below appears every time. Unknown values are `null`; empty
  lists are `[]`. Never omit a key, never invent a value.
- **Same facts as the prose.** If the two disagree, the report is wrong — fix it first.
- Ticket keys exactly as the tracker shows them. One block, nothing after it.

| Key | Meaning |
|---|---|
| `schema` | `"wave-status/1"` — bump only on a breaking change. |
| `generated_at` | ISO 8601 timestamp. |
| `tracker` / `repo` | e.g. `"jira:VD"` / `"owner/repo"` (`null` when not on GitHub). |
| `pr_crosscheck` | `{ "ran": bool, "reason": string\|null }`. |
| `window` | `{ "base": int, "base_open": int, "next": int\|null, "next_open": bool }`; `null` with no waves. |
| `fallback_unit` | With no waves, the unit used instead (`"sprint: Sprint 7"`), else `null`. |
| `concurrency` | `{ "cap": int, "cap_source": path\|"default", "in_flight": int, "free_slots": int }`. |
| `ready` | **In start order.** Each `{ key, title, type, wave, priority, critical, unblocks: [keys], reason }`; `wave` `null` for an unwaved critical bug; `type` one of Feature/Bug/Chore/Spike or the raw name with `?`. |
| `start_now` | The first `free_slots` keys of `ready`. |
| `top_pick` | `{ key, action: "implement"\|"finish"\|"merge"\|"close-out", reason, runner_up }` or `null`. |
| `in_progress` | `{ key, type, status, assignee, pr, pr_state: "open"\|"draft"\|null, ci: "green"\|"red"\|"pending"\|null, needs_human, job_folder }`. |
| `blocked` | `{ key, waiting_on: [ { key, state: "merged-not-closed"\|"in-progress"\|"to-do"\|"needs-human" } ] }`. |
| `out_of_sync` | `{ key, kind, tracker_status, pr, pr_merged_at, fix }`; `kind`: `merged-not-closed`, `closed-too-early`, `started-not-marked`, `possibly-stale`, `abandoned`, `outside-window`. |
| `needs_human` | `{ tickets: [ {key, question} ], escalated_prs: [ {pr, key, question} ], ready_to_merge: [ {pr, key, ci} ], owner_guides: [ {path, tickets, order, estimate, note} ] }`. `ready_to_merge` = labelled `ready-to-merge` (waiting for the owner's merge, not an escalation). |
| `housekeeping` | `{ kind, key, path, branch, pr, warning, fix }`; `kind`: `worktree-merged`, `branch-merged`, `branch-gone`, `worktree-prunable`, `job-folder-stale`, `job-folder-stalled`, `type-missing`; `warning` e.g. "uncommitted changes". |
| `unwaved_open` | Open tickets with no wave. |

**How an orchestrator reads it:** close out `merged-not-closed` items first (they may unblock
tickets); start `start_now` in order and nothing outside `ready`; advance `in_progress`
tickets, skipping `needs_human: true`; surface `needs_human` in the run summary; stop when
`ready` is empty and every `in_progress` ticket waits on the owner; run housekeeping fixes
only through `merge-ticket`.

Example (abridged lists, every key present):

```json
{
  "schema": "wave-status/1",
  "generated_at": "2026-11-08T09:14:00+08:00",
  "tracker": "jira:VD",
  "repo": "acme/vd-app",
  "pr_crosscheck": { "ran": true, "reason": null },
  "window": { "base": 2, "base_open": 2, "next": 3, "next_open": true },
  "fallback_unit": null,
  "concurrency": { "cap": 3, "cap_source": "docs/workflow/README.md", "in_flight": 1, "free_slots": 2 },
  "ready": [
    { "key": "VD-77", "title": "Edits lost after sync", "type": "Bug", "wave": null, "priority": "Highest",
      "critical": true, "unblocks": [], "reason": "critical bug: data loss" },
    { "key": "VD-46", "title": "Export settings", "type": "Chore", "wave": 2, "priority": "High",
      "critical": false, "unblocks": ["VD-50", "VD-52"], "reason": "wave 2, unblocks 2" }
  ],
  "start_now": ["VD-77", "VD-46"],
  "top_pick": { "key": "VD-77", "action": "implement", "reason": "ready critical bug", "runner_up": "VD-46" },
  "in_progress": [
    { "key": "VD-43", "type": "Feature", "status": "In Review", "assignee": "you", "pr": 91,
      "pr_state": "open", "ci": "green", "needs_human": false, "job_folder": true }
  ],
  "blocked": [ { "key": "VD-45", "waiting_on": [ { "key": "VD-41", "state": "merged-not-closed" } ] } ],
  "out_of_sync": [
    { "key": "VD-41", "kind": "merged-not-closed", "tracker_status": "In Progress", "pr": 87,
      "pr_merged_at": "2026-11-06T15:02:00Z", "fix": "merge-ticket VD-41" }
  ],
  "needs_human": {
    "tickets": [ { "key": "VD-39", "question": "Defer AC3 to a follow-up ticket?" } ],
    "escalated_prs": [ { "pr": 85, "key": "VD-39", "question": "Defer AC3 to a follow-up ticket?" } ],
    "ready_to_merge": [ { "pr": 86, "key": "VD-40", "ci": "green" } ],
    "owner_guides": [ { "path": "docs/actions/set-api-key.md", "tickets": ["VD-46"], "order": 3,
      "estimate": "10 min", "note": "ready ticket VD-46 needs this first" } ]
  },
  "housekeeping": [
    { "kind": "worktree-merged", "key": "VD-38", "path": "../wt/vd-38", "branch": "feat/vd-38/login",
      "pr": 80, "warning": null, "fix": "merge-ticket VD-38" }
  ],
  "unwaved_open": ["VD-77"]
}
```

## Shell notes for Windows

The user may be in PowerShell or Git Bash. To stay correct in both:

- `gh` and `git` arguments are the same in each. Prefer `--json` and read the JSON yourself
  over long `--jq` filters: a jq filter containing double quotes is mangled by Windows
  PowerShell's native-argument quoting. Short filters with no inner quotes
  (`--jq .defaultBranchRef.name`) are safe.
- Quote glob patterns given to `git branch --list` so the shell does not expand them.
- Read repo files with the Read/Grep/Glob tools rather than `cat`, `grep` or `ls`.
- Run the tracker query and the `gh pr list` call in parallel; neither depends on the other.
