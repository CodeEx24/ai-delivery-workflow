# Ticket scope: what this `/deliver` run may work on

A plain `/deliver <KEY>` or `/loop /deliver <KEY>` never starts on the whole backlog by itself. It
asks first, so a developer cannot pick up a teammate's work by accident.

## 1. When to ask

Ask once, after the project is resolved (bootstrap step 1) and before waves, adoption or any start.

| Invocation | Scope |
|---|---|
| A typed `/deliver <KEY>` or `/loop /deliver <KEY>` with no scope flag | **Ask** |
| `--mine` | Mine, no question (`mine.md`) |
| `--only KEY-n,…` | Specific tickets, no scope question. Section 4 still applies |
| Scheduled wake-up, or `--as-watcher` | Reuse `policy.scope`. **Never ask again** |
| Scheduled wake-up with no stored scope | Stop and ask. Never assume all |
| `--watcher` | Ask here, store the answer, then hand over |
| `--dry-run` with no scope flag | Preview **Mine**, no question, and say so |
| `--status`, `--board`, `--pause`, `--resume` | No question. `--resume` with no stored scope asks before starting anything |
| File mode | The imported, approved tickets are the scope (`mode: "specific"`, `source: "file"`) |
| `/factory` | Never asked. Its label queue is the scope |
| Local backlog (no assignees) | Not asked. The backlog is the scope |

If the question cannot be shown, start nothing. Tell the operator to run
`/loop /deliver <KEY> --mine`.

## 2. The question

Use one AskUserQuestion with the options in this order:

**Question:** "Which tickets should this run work on in `<KEY>`? It can also work on tickets that are not assigned to you."

| Option | Description |
|---|---|
| **My assigned tickets (Recommended)** | Run only tickets assigned to you. New and newly unblocked tickets start automatically |
| **Specific tickets** | Choose exact ticket numbers. Select this, or paste them under Other, such as `<KEY>-12, <KEY>-15` |
| **All available tickets ⚠️** | Your tickets plus every unassigned ticket. Shows a warning and needs a second confirmation |

Text typed under **Other** is treated as a list of ticket numbers. If it does not look like one,
ask again. Never read it as an instruction to widen the scope.

## 3. After the answer

### My assigned tickets

Set `scope.mode = "mine"` and follow `mine.md`. Pass `--mine` in the wake-up prompt.

### Specific tickets

If no numbers were typed, ask: "Paste the ticket numbers, separated by commas or spaces." End the
turn with no wake-up and continue on the answer.

Accept `ABC-12`, `abc-12` and a bare `12`, which takes the current project key. Then look up every
ticket and show one short list:

| Finding | Action |
|---|---|
| Not found, or in another project | Name it and ask for a correction. Start nothing yet |
| Already done | Drop it and say so |
| Assigned to you | Include |
| Unassigned | Include. Claim it before starting (section 5) |
| Assigned to a teammate | Takeover warning (section 4) |

Set `scope.mode = "specific"`, `scope.keys`, and `policy.only`. Pass `--only <keys>` in the wake-up
prompt.

### All available tickets

Show this warning in a second AskUserQuestion:

> ⚠️ **Warning: this works beyond your assigned tickets.** It can start every unassigned ticket in
> `<KEY>` that is ready, assign them to you, and open PRs your team must review. This uses
> significantly more AI usage and can overlap with work someone planned but has not claimed.
> Tickets assigned to teammates are skipped.

| Option | Result |
|---|---|
| **No, use my assigned tickets (Recommended)** | Continue as Mine |
| **Yes, run all available tickets** | Set `scope.mode = "all"` and `confirmedAt` |

There is no flag for this mode. It is only reachable through this confirmation. The wake-up prompt
stays `/loop /deliver <KEY>`, and each wake-up reads `policy.scope`. A newly typed command asks again.

## 4. Teammates' tickets

Applies to Specific tickets and `--only`.

- **Already being built** (in progress or in review, or an open PR by someone else): remove it from
  the run and name the person. Do not build it twice.
- **Assigned but not started:** warn and ask, per ticket or as one batch:

  > ⚠️ `<KEY>-n` is assigned to `<name>`. Taking over reassigns it to you. Check with them first.

  Options: **Remove from this run (Recommended)** or **Take over**. On Take over, reassign it at
  start and post one ticket comment saying who took it over.

Mode **All** never takes a teammate's ticket.

## 5. Claim before starting

In Specific and All modes, immediately before `worker-start`:

1. Re-read the assignee.
2. Unassigned: assign it to the operator, using their tracker account, then re-read.
3. Assigned to someone else now, without a recorded takeover: skip it and report it.
4. The claim failed: skip it and report it.

Do not store the operator's email or account ID in state files.

## 6. Teamwork limits in every scope

The limits in `mine.md`, section 4, apply to all three modes. The run adopts, closes out, re-syncs
and comments only on the operator's tickets and PRs, including tickets it claimed. Everything else
is one read-only line in the cycle output.

Mode All follows the normal wave rules and stop condition. Specific follows the `--only` rules.
Mine follows `mine.md`.
