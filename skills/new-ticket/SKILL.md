---
name: new-ticket
description: >-
  Turn a one-line request or a short free-text description into a proper, buildable ticket:
  draft the title, type, description, testable acceptance criteria, out of scope, risk and size,
  ask only the questions that block it, show the draft, and on the owner's yes create it — in
  the project's PM tool (Jira, Linear, GitHub Issues) when one is connected, otherwise as a local
  ticket file `docs/tickets/T-<nnn>.md` with a colour status (🔴 to do / blocked, 🟡 in progress
  / in review, 🟢 done), the PR link and a log. Then offer to build it right away with
  implement-ticket. Use whenever the user gives a task as plain text with no ticket ("add CSV
  export to the tasks page", "fix the login redirect bug", "create a ticket for …", "make a
  ticket from this", "/new-ticket …"), or when implement-ticket is handed a description instead
  of a key.
argument-hint: "\"<description>\" [--type feature|bug|chore|spike] [--tracker jira|linear|github|local] [--build] [--loop]"
user-invocable: true
---

# /new-ticket — from a description to a ticket

Arguments: `$ARGUMENTS`

One description in, one ticket out. Nothing is created until the owner approves the draft.

## Step 1 — Find the tracker (read-only)

Same order as the delivery workflow: `--tracker`; else what `CLAUDE.md` /
`docs/workflow/README.md` / `.delivery/orchestrator.json` name; else Jira or Linear if their MCP
tools load (ToolSearch for deferred tools before deciding they are missing); else **GitHub
Issues** only if the project already tracks work there (open issues, or `CLAUDE.md` says so) and
`gh` works; else the **local tracker** (files in `docs/tickets/`). Say in one line which one you
picked and why; the owner can switch.

Also read: the project key, the type mapping (e.g. Jira Task → Chore), and the repo enough to
ground the ticket (where the feature would live, what exists already). Check for a duplicate: an
open ticket with the same intent → show it and ask whether to use it instead.

## Step 2 — Draft

From the description and what the repo shows, draft:

| Field | Rule |
|---|---|
| **Title** | Imperative, ≤ 70 characters ("Export tasks as CSV") |
| **Type** | Feature / Bug / Chore / Spike (`--type` wins). A broken behaviour is a Bug |
| **Description** | Problem, who it is for, desired outcome, in 2–5 sentences. Bug: steps to reproduce, expected vs actual, severity. Spike: the question, options, time box |
| **Acceptance criteria** | 2–6 criteria, each testable: `AC1: Given …, when …, then …`. No vague words ("fast", "nice") without a number |
| **Out of scope** | What a reader might assume is included but is not |
| **Risk** | Low / Medium / High (high: auth, data access rules, payments, migrations on live data, AI surfaces) |
| **Size** | 1 / 2 / 3 / 5 / 8 points; ≥ 8 → propose a split into two tickets |
| **Assumptions** | Every guess you made, so the owner can correct it |

Ask (one batched AskUserQuestion, recommendation first) only what blocks a testable ticket: a
product decision the description leaves open, a missing fact. Everything else goes under
Assumptions.

## Step 3 — Show and approve

Show the draft as it will be created, plus where it will go ("Jira ABC", "GitHub issue in
owner/repo", "local file docs/tickets/T-013.md"). **Wait for the owner's explicit yes.** Edits →
redraft and show again.

## Step 4 — Create

### With a PM tool

- **Jira:** `createJiraIssue` (issue type from the mapping; description in the project's format
  with the AC as a checklist; labels `type:<name>` where the issue type cannot carry it). Re-read
  it with `getJiraIssue` to confirm.
- **Linear:** its create-issue tool, the same fields.
- **GitHub Issues:** body to a file, then `gh issue create --title "…" --label type:<name>
  --body-file <file>`; add `--label factory` only if the owner wants `/factory` to pick it up.

Report the key and URL. The ticket record (`docs/tickets/<KEY>-<n>-<slug>.md`) is written later by
implement-ticket, as usual.

### Without a PM tool — local ticket file

1. **ID:** the next `T-<nnn>` after the highest in `docs/tickets/` and `docs/tickets/backlog.md`.
2. **Write `docs/tickets/T-<nnn>.md`** with the template below. This file is both the ticket and
   its record: implement-ticket fills Design, Decisions and the PR link in it; merge-ticket fills
   Outcome. No second record file.
3. **Index it** in `docs/tickets/backlog.md` (create the file with its header if missing; format
   in the deliver skill's `references/import-tasks.md`) as a short entry, so `/wave-status` and
   `/deliver` see it:

   ```markdown
   ## T-013 — Export tasks as CSV
   - Type: Feature · Size: 2 · Risk: Low · Status: To Do · Wave: — · Labels: from-description
   - Blocked by: — · Blocks: —
   - PRs: —
   - Record: docs/tickets/T-013.md (description and acceptance criteria live there)
   ```

4. **Get it onto the default branch**, because tickets start only from the default branch:
   - a tiny commit `docs(tickets): add T-013 — <title>` on the default branch, **only if the
     owner says so** in the approval (solo repos), or
   - a branch `docs/ticket-T-013` with a draft PR the owner merges (team repos, protected `main`).

   If the owner wants to build right now (Step 5), the ticket file may instead travel on the
   ticket's own branch: implement-ticket commits it there first, and it reaches the default
   branch with the merge (the backlog entry then appears there only after the merge; say so).

#### Local ticket template

```markdown
# T-013 — Export tasks as CSV

**Status: 🔴 To do**
Type: Feature · Risk: Low · Size: 2 · Created: 2026-11-11 (from a one-line request)
Ticket: local (no PM tool) · PRs: (none yet) · Branch: (none yet)
Related: —

> Status key: 🔴 To do / blocked · 🟡 In progress / in review · 🟢 Done
> The copy on the default branch shows 🔴 or 🟢; 🟡 lives on the ticket's branch and PR while it is built.

## Description
<problem, who it is for, desired outcome>

## Acceptance criteria
- [ ] AC1: Given …, when …, then …
- [ ] AC2: …

## Out of scope
- …

## Assumptions and open questions
- …

## Design
(filled by implement-ticket)

## Decisions
| Decision | Options | Choice | Who / when |
|---|---|---|---|

## Outcome
(filled at merge: what shipped, deviations, follow-ups)

## Log
- 2026-11-11 🔴 created from: "<the owner's original sentence, verbatim>"
```

**Status values** (always emoji + words, so it reads well and stays searchable):

| Status line | When | Who sets it, where |
|---|---|---|
| `🔴 To do` | Created, not started | new-ticket, on the default branch |
| `🟡 In progress` | Branch exists, building | implement-ticket, on the ticket branch (Phase 1) |
| `🟡 In review` | Draft PR open, review loop running | implement-ticket, on the branch (Phase 8), with the PR link |
| `🔴 Blocked — <reason>` | Escalated, waiting on the owner, or blocked by another ticket | implement-ticket / the loop, on the branch |
| `🟢 Done` | PR merged | merge-ticket, on the PR branch before merge, with the merge date |
| `⚪ Won't do` | Dropped by the owner | whoever drops it, on the default branch |

Every status change also appends a Log line (`- 2026-11-12 🟡 draft PR #57`). The default
branch only ever shows 🔴 or 🟢 (and ⚪), because workers never edit the default branch; the live
🟡 state is on the PR and on the live delivery board.

## Step 5 — Build it?

Ask once: **build it now?**

| Answer | Do |
|---|---|
| Yes, here (`--build`) | Run `implement-ticket <KEY>` in this session (it creates the branch, sets 🟡, opens the draft PR, then offers the review loop) |
| Yes, with the full loop (`--loop`) | Tell the owner to run `/loop /deliver <PROJECT-KEY> --only <KEY>` (gate, testers, reviewers, approver, merge, board) |
| GitHub + factory | Label it `factory`; `/loop /factory run` picks it up |
| Later | Done. Report the key / file and how to start it |

## Will not

- Create anything before the owner's yes, or several tickets from one description without
  showing the split.
- Invent acceptance criteria that decide product behaviour silently: those go under Assumptions
  or become a question.
- Put secrets, credentials or personal data in a ticket.
- Edit the default branch for status changes after creation (🟡 lives on the ticket branch).
