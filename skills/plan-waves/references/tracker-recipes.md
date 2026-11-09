# Tracker recipes for wave planning

How to read a backlog with its links, and how to write a wave plan back, per tracker. Tool
and field names vary by connector version and by project configuration — the loaded tool's
own description is the authority, and a field you cannot find by name should be looked up on
a real ticket rather than guessed.

## Contents

- [Detecting an existing plan](#detecting-an-existing-plan)
- [Ticket types](#ticket-types)
- [Jira](#jira)
- [GitHub Issues](#github-issues)
- [Linear](#linear)
- [Reconciling a second planning source](#reconciling-a-second-planning-source)
- [No tracker tool: planning from an export](#no-tracker-tool-planning-from-an-export)
- [Shell notes for Windows](#shell-notes-for-windows)

## Detecting an existing plan

Cheap, read-only, done before the full backlog read (Step 0).

- **Jira.** Labels cannot be wildcard-searched in JQL, so read the open tickets' labels and
  scan locally:
  `jql: "project = VD AND statusCategory != Done"`, `fields: ["labels","fixVersions","parent"]`,
  paged. Count tickets with a label matching `^wave[-:_ ]?\d+$` (case-insensitive), a fix
  version named like `Wave 2`, or a Wave custom field value. A spot check of done tickets
  (`statusCategory = Done`, `maxResults: 20`) shows whether a convention was used before.
- **GitHub Issues.** `gh label list --search wave --json name` for wave labels;
  `gh api repos/{owner}/{repo}/milestones` (read the `title` fields) for wave milestones; then
  `gh issue list --state open --limit 1000 --json number,labels,milestone` to count open
  issues with and without one.
- **Linear.** List open issues with labels, project and milestone; look for wave-named ones.
- **Repo.** The workflow doc's plan path; else `docs/waves/wave-plan.md`; else
  `Glob docs/**/*wave*.md`. Read the first lines for `PROPOSED` / `APPROVED` and a date.

Classify `exists` / `partial` / `proposed` / `none` as the SKILL.md table says. If tracker
and document disagree (different wave for a ticket), that is `partial`: the tracker is live,
report the drift.

## Ticket types

Every ticket should carry one delivery type: **Feature** (new or changed behaviour),
**Bug** (wrong against specified or expected), **Chore** (no behaviour change: refactor,
upgrade, tooling, CI, docs), **Spike** (an open question, time-boxed, ends in a
recommendation and new tickets, not a merge).

| Tracker | Read | Set (on the go only) |
|---|---|---|
| Jira | `fields.issuetype.name`; a `type:` label if the project uses one wins | Changing issue type often needs a "move" the connector cannot do, and may drop fields. Prefer adding a `type:<name>` label (labels list is replaced — send the full list). Change `issuetype` via `editJiraIssue` only if the project's workflow doc says so and the type exists in the project (`getJiraProjectIssueTypesMetadata`). |
| GitHub Issues | `type:` label, or the native issue type where the organisation uses them (`gh api repos/{owner}/{repo}/issues/<n> --jq .type.name`) | `gh issue edit <n> --add-label type:chore` (create the label once). |
| Linear | A type label (`Bug`, `Feature`, …) | Add the label (check whether the tool replaces or appends). |

Default mapping when the project states none: Story → Feature, Bug → Bug, Spike / Research →
Spike; Task, Sub-task, Improvement are ambiguous — propose a type from the description
("upgrade", "refactor", "CI" → Chore; user-visible behaviour → Feature) and mark it proposed.

**Severity for bugs:** Jira priority `Highest`/`Blocker` or a severity field / label; GitHub
`severity:critical` or `P0`; Linear priority 1. Critical = data loss, security, app unusable.
A Bug with no severity is flagged in Problems found.

## Jira

Through the Atlassian connector. The tools are usually deferred: load
`getAccessibleAtlassianResources`, `searchJiraIssuesUsingJql`, `getJiraIssue`, and — only
when applying — `editJiraIssue`, `createIssueLink`, `getIssueLinkTypes`. If two Atlassian
connectors are present, use either, but the same one throughout.

### Read

1. `getAccessibleAtlassianResources` once for the cloud id. If it returns several sites, ask
   which.
2. Search the project, asking explicitly for the fields the plan needs — the default field
   set leaves out links:

   ```
   searchJiraIssuesUsingJql(
     cloudId,
     jql: "project = VD ORDER BY key ASC",
     fields: ["summary","status","issuetype","priority","labels","issuelinks",
              "parent","fixVersions","assignee"],
     maxResults: 100)
   ```

   Narrow with JQL when the scope is a subset: `AND statusCategory != Done`,
   `AND parent = VD-10`, `AND fixVersion = "MVP"`. Read the done tickets too (a second query
   with `statusCategory = Done` and a light field list is enough) so satisfied dependencies
   are recognised.
3. **Page until there is no `nextPageToken`.** State the total read.
4. Story points, sprint and a "Wave" field are custom fields with site-specific ids. To find
   them, fetch one representative ticket with `fields: ["*all"]` and look for the values you
   expect; then request those `customfield_*` ids in the search.

Status: use `status.statusCategory` (`To Do` / `In Progress` / `Done`) rather than the status
name — names are per-workflow, categories are not.

### Link direction

Each entry in a ticket's `issuelinks` has a `type` (`name`, `inward`, `outward`) and
**either** an `inwardIssue` **or** an `outwardIssue`. For the standard `Blocks` type
(inward "is blocked by", outward "blocks"), reading ticket X:

| Entry on X has | Read it as | Edge |
|---|---|---|
| `inwardIssue: Y` | X *is blocked by* Y | `Y → X` (X depends on Y) |
| `outwardIssue: Y` | X *blocks* Y | `X → Y` (Y depends on X) |

The same link appears on both tickets, once from each side — de-duplicate. Only some link
types mean dependency: `Blocks` and any custom "Depends on" type do; `Relates`, `Duplicate`
and `Clones` do not. Project sites can rename or add types, so check the type's inward and
outward phrases rather than assuming from the name.

Also scan descriptions for dependencies written as text ("Blocked by: VD-12", "Depends on
VD-12", a "Dependencies" heading) — backlogs imported from CSV often carry them only there.
Treat an explicit statement like that as declared.

### Apply

- **Wave label.** `editJiraIssue` with `fields: { "labels": [...] }` **replaces the whole
  label list.** Build the new list from the ticket's current labels: drop any old wave label,
  add the new one, keep everything else. Sending only `["wave-2"]` silently strips every
  other label on the ticket.
- **Wave custom field / fix version.** Set it by its field id or name through `editJiraIssue`
  in the shape the field expects (a select field wants `{ "value": "Wave 2" }`, a version
  wants `[{ "name": "Wave 2" }]`). Use only options that already exist; a missing option or
  version is something to report, not create.
- **Dependency link.** `createIssueLink` with `type: "Blocks"`,
  **`inwardIssue` = the blocker, `outwardIssue` = the blocked ticket**. So "VD-9 is blocked
  by VD-5" is `inwardIssue: VD-5, outwardIssue: VD-9`. Create one, re-read VD-9 and confirm
  it shows "is blocked by VD-5", then create the rest. Check for an existing link first;
  Jira will happily store duplicates.
- **Priority.** `editJiraIssue` with `fields: { "priority": { "name": "High" } }`, using a
  priority name the project actually has.

Do not transition tickets, reassign them, or edit descriptions as part of applying a plan.

## GitHub Issues

Through `gh`. Confirm the repo and auth first: `gh repo view --json nameWithOwner` and
`gh auth status`.

### Read

```
gh issue list --state all --limit 1000 --json number,title,state,stateReason,labels,milestone,assignees,body
```

- Raise `--limit` above the issue count; the default of 30 truncates silently.
- **Waves** are usually labels (`wave-1`) or milestones. **Priority** is usually a label
  (`P0`, `priority: high`) or a Projects field.
- **Dependencies** live in up to three places:
  - Native issue dependencies ("blocked by" / "blocking") and sub-issues, where the repo
    uses them. These are not in `gh issue list` output; read them through the REST API
    (`gh api repos/{owner}/{repo}/issues/<n>/dependencies/blocked_by`). If that endpoint
    returns 404, the feature is not available for the repo — fall back to the text
    conventions and say so.
  - Text in the body: `Blocked by #12`, `Depends on #12`, a `## Dependencies` section, or a
    task list of issue references.
  - A tracking issue whose task list enumerates children (structural).
- A closed issue with `stateReason: NOT_PLANNED` is not done work — exclude it, and flag
  anything depending on it.
- Pull requests are not issues; `gh issue list` already excludes them.

### Apply

- **Wave label.** Create the labels once (`gh label create wave-2 --description "Wave 2"`;
  it errors harmlessly if the label exists), then per issue:
  `gh issue edit <n> --add-label wave-2 --remove-label wave-3`. Unlike Jira this is
  additive — other labels are untouched.
- **Milestone as wave.** `gh issue edit <n> --milestone "Wave 2"` (the milestone must exist).
- **Dependency.** Native, where available: `POST
  repos/{owner}/{repo}/issues/<blocked>/dependencies/blocked_by` with the blocker's
  **issue id** (the numeric database id from `gh api repos/{owner}/{repo}/issues/<n> --jq .id`,
  not the issue number). Where it is not available, append a `Blocked by #<n>` line to the
  blocked issue's body — read the current body first and write the whole thing back with
  `gh issue edit <n> --body-file <file>`, since editing the body replaces it.
- **Priority.** Swap the priority label the same way as the wave label.

## Linear

Through the Linear connector (load its list/get/update issue tools).

- **Read:** list the team's or project's issues with state, priority, labels, cycle, project,
  parent, and relations. Linear priority is numeric: 1 urgent, 2 high, 3 medium, 4 low,
  0 none.
- **Dependencies:** issue relations of type *blocks* / *blocked by*. As with Jira, each
  relation is visible from both issues — de-duplicate, and read the direction from the
  relation's own wording.
- **Waves:** commonly a label, a project, a milestone within a project, or a cycle. Cycles
  are time-boxed and auto-roll, so do not repurpose them as waves unless the team already
  does.
- **Done:** state type `completed`; `canceled` is not done work.
- **Apply:** update the issue's labels (check whether the tool replaces or appends — if it
  replaces, send the full list as for Jira), create a *blocks* relation, set priority.

## Reconciling a second planning source

When the repo also holds a planning input (delivery workbook, backlog CSV, roadmap file), the
tracker stays the authority for identity, status, priority, type and links. Compare field by
field and report every difference instead of silently picking a side:

- Match on a stable ID (a blueprint/source ID written into the ticket, or an exact title).
  Report anything unmatched on either side, and duplicates.
- Compare title, type, priority, wave or phase, parent/epic, dependency set, estimate,
  sprint, readiness, and whether AC are present.
- Use the repo's reconciliation script if the workflow doc names one; otherwise a scratchpad
  script, not by eye.
- Classify: **conflict** (scope, dependency, priority, type) blocks the plan until the owner
  decides; **data gap** (empty estimate, sprint dates) is reported with a proposed fix.

A tracker that looks empty right after an import may still be indexing. Re-query before
reporting it empty, and do a direct key lookup (`ABC-1`) to tell "no issues" from "no
permission".

## No tracker tool: planning from an export

When nothing can reach the tracker, plan from a CSV export or a pasted list. It needs, per
ticket: key, title, type, status, priority, and whatever dependency column exists ("Blocked By",
"Depends on", "Linked issues").

- Read the file with the Read tool; do not assume a column order — find the columns by
  header.
- Say plainly that the plan was built from an export taken at a point in time, and that
  applying is not possible from here.
- Offer the result in a form the human can import or paste: the plan table, plus a two-column
  `key, wave` list.

## Shell notes for Windows

The user may be in PowerShell or Git Bash. To stay correct in both:

- `gh` and `git` arguments are the same in each. Prefer `--json` and read the JSON yourself
  over `--jq` expressions: a jq filter containing double quotes is mangled by Windows
  PowerShell's native-argument quoting. If you need `--jq`, wrap the filter in single quotes
  and keep double quotes out of it.
- For multi-line bodies use `--body-file <path>` with a file written by the Write tool,
  rather than a here-string or `echo` with escapes.
- Read repo files with the Read/Grep/Glob tools instead of `cat`, `grep` or `ls`.
- When applying many changes, issue them one command at a time (or a simple loop in the
  shell you are actually in) and stop on the first unexpected error instead of pushing
  through.
