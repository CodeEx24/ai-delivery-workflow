# `/deliver <KEY> --mine`

Runs every ticket assigned to the person at the keyboard (the **operator**), with no ticket list.
Best as `/loop /deliver <KEY> --mine`. This file overrides the normal cycle only where it says so.
All hard rules still apply.

`--mine` cannot be combined with `--only` or file mode. If both are given, ask which one to use.

**Preview:** `/deliver <KEY> --mine --dry-run` runs one read-only cycle. It reads the operator's
assignments, blockers and PRs, then lists what would start, continue, wait or need them. It writes
no state files, starts no worker or board, claims nothing, and changes nothing in the tracker, Git
or GitHub. It runs once, so do not put `/loop` in front of it.

## 1. Who is the operator

Use the identity of the operator's own tracker connection:

| Tracker | Assigned-to-me query |
|---|---|
| Jira | `project = <KEY> AND assignee = currentUser() AND statusCategory != Done ORDER BY priority DESC, created ASC` |
| Linear | Issues in the team with assignee `me`, not completed or canceled |
| GitHub Issues | `gh issue list --assignee @me --state open` |
| Local backlog | Not supported. Say so and stop |

If the identity cannot be resolved, start nothing and report the connector problem. Never fall
back to the whole backlog. Do not store the operator's email or account ID in state files.

## 2. Refresh the queue every cycle (cycle step 1.4)

Re-run the query and write `policy.mine = { enabled, keys, refreshedAt, idleSince }`. Treat
`keys` as `policy.only` for step 5.

- **Startable:** assigned, and in the tracker's **to-do** status category.
- **Already moving:** assigned, in progress or in review, with a job folder on this machine or an
  open PR authored by the operator. Adopt it instead of starting it again.
- **Assigned and in progress with neither:** report it and do not start it. It may be running on
  another machine.
- **Past review** (for example merged and on staging): nothing to do.

## 3. Starting a ticket (cycle step 5)

Immediately before `worker-start`, re-read the ticket and confirm that **it is still assigned to
the operator**. Then run the normal checks, with one change to the window:

- A ticket **with a wave** follows the normal two-wave window.
- A ticket **with no wave** is not barred by the window, because the assignment is the decision to
  do it. It starts after critical bugs and window tickets, and it must still pass the blocker,
  entry-rule, collision and machine checks.

Never run `plan-waves` from `--mine`. If the project has no waves, the assigned tickets are one
queue ordered by critical bugs, tickets that unblock the most, priority, then oldest.

## 4. Stay inside the operator's work

Other developers may be running their own loops, and the orchestrator lock is local to one
machine. So a `--mine` run:

- **Adopts** only the operator's job folders and PRs at bootstrap.
- **Runs housekeeping** (`merged-not-closed`, stale worktrees, re-syncs) only for the operator's
  tickets and PRs. Everything else is one read-only line in the cycle output.
- **Never** comments on, transitions, pushes to, closes out or merges another person's ticket or PR.
- **Tells `merge-ticket`** that the scope is `--mine`, so it re-syncs only the operator's PRs.

**Reassigned while running:** do not advance the ticket. Park it as in `pause.md`, keep its branch
and worktree, and ask the operator one question: continue, or hand it over.

## 5. Keep watching instead of stopping

The normal stop condition does not apply. While under `/loop`, keep scheduling wake-ups when work
is blocked, waiting on the operator, or when the queue is empty.

| Situation | Delay |
|---|---|
| Work is active | The normal delay table |
| Only blocked, waiting or empty | `policy.loopMinutes` if it is a number, otherwise 1800 s |

**Idle check.** When no worker, gate or merge is active, run only the lock, inboxes, assigned query
and blocker re-read. If no ticket can start and nothing changed, write one line and schedule the
next wake-up. Skip the full `wave-status`.

**Idle limit.** Set `idleSince` when a cycle has nothing to start or advance, and clear it when
anything starts, advances, merges or is answered. After **8 idle hours**, send the normal stop
summary and stop with `stop: true`. Say how to resume: `/loop /deliver <KEY> --mine`.

A plain `/deliver <KEY> --mine` runs one cycle and then suggests the `/loop` form. The session and
machine must stay on for the loop to keep running.

## 6. Cycle line

```text
Mine · 5 assigned · 1 running · 2 blocked (ABC-12 on ABC-9) · 1 waiting on you · 1 started · next 30 min
```
