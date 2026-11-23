# Bootstrap

Runs on the first `/deliver <KEY>` and quickly re-checks on every later start (not every
cycle). Idempotent: anything already recorded in `.delivery/orchestrator.json` and still true
is skipped. `--dry-run` runs all detection and prints the result without writing anything.

## 1. Resolve the project

| What | Where to look | Record as |
|---|---|---|
| Tracker kind + project key | `CLAUDE.md` / `AGENTS.md` ("PM project: … key `ABC`"), `docs/workflow/README.md`, issue keys in `git log --oneline -15` | `tracker.kind`, `projectKey` |
| No tracker at all | No tracker named in the docs and no connector loads | **Default: GitHub Issues** on the repo when it is on GitHub and `gh` works (`tracker.kind: "github"`). Otherwise — offline, private experiment, no forge — the **local backlog** `docs/tickets/backlog.md` (`tracker.kind: "local"`, IDs `T-001…`; format and rules in `import-tasks.md`). State the default in the setup table; the owner may pick the other. Record the choice in `tracker` |
| Tracker connector | Jira → Atlassian MCP (`getAccessibleAtlassianResources` for the cloud id); Linear → Linear MCP; GitHub Issues → `gh`. Tools are often deferred: load with ToolSearch before concluding they are missing | `tracker.site`, `tracker.cloudId` |
| Key exists | Direct lookup of one issue (`<KEY>-1` or a JQL `project = <KEY>` with `maxResults: 1`). "No issues" vs "no permission" must be told apart | — |
| Status names + transitions | The workflow doc's status table, else read transitions on one issue. Never hard-code ids | `tracker.statuses` |
| Readiness rule | Workflow doc ("carries the `ready` label", Definition of Ready) | `tracker.readyRule` |
| Critical bug rule | Workflow doc; default: type Bug and label `severity:critical` (the recommended signal), or priority Highest/Blocker | `tracker.criticalBugRule` |
| Type mapping | Workflow doc's mapping of tracker issue types to Feature / Bug / Chore / Spike. Jira "Task" with no mapping → propose the line **"Task → Chore"** for `docs/workflow/README.md` (info gap; the owner adds it) | `tracker.typeMap` |
| Repo, default branch | `gh repo view --json nameWithOwner,defaultBranchRef`; `gh auth status` | `repo.*` |
| Main checkout | `git rev-parse --show-toplevel`; must be on the default branch with a clean tree (`git status --porcelain`). If not: stop and report — the orchestrator never works on a feature branch | `repo.mainCheckout` |
| Orca | `ORCA repo list --json` (Orca running? repo registered? note its id), `ORCA worktree list --json` | `repo.orcaRepoId` |
| Workflow file | `~/.claude/workflows/ai-delivery-workflow.md` exists; `CLAUDE.md` imports it (`@~/.claude/workflows/…`) | gap if missing |

One-line report: `Detected: Jira ABC (acme.atlassian.net) · owner/repo @ main · main checkout /path/to/… · Orca repo id … · workflow file imported: yes`.

**File mode:** after this step and step 2, run the import (`import-tasks.md`) before step 3.

**Hard stops** (no cycle until fixed): Orca not running; tracker unreachable or key not
found (local backlog: file missing and not in file mode); `gh` unauthenticated; main checkout dirty or not on the default branch.

## 2. Project setup check (workflow step 1b)

Detect each item, classify it, and print one table: **Item · Found · Severity · Fix**.

| Item | Detect | Missing → severity | Fix to propose |
|---|---|---|---|
| Checks script | `scripts/workflow/checks.{sh,ps1}` (or the path the workflow doc names) on the default branch; note whether it supports `--report <path>` (workflow 1b) | **degraded** if CI / `CLAUDE.md` give the check commands (gate runs those in CI order and says so), or if it lacks `--report` (you write `checks.md` from its output); **blocking** if no check commands can be found at all | Propose (owner's yes) a small Chore ticket to add it **with the `--report` mode** (template: workflow section 6) |
| Agent files | `.claude/agents/{reviewer-code,reviewer-security,reviewer-ui,reviewer-ux,tester-functional,tester-device,approver,explainer}.md` in the repo, else `~/.claude/agents/` | **degraded** per missing role (worker falls back to a general-purpose subagent with the workflow's role row, noted on the PR); **blocking** only if `approver` *and* the workflow file are both missing | Install/copy the agent files (owner) |
| Merge path | `delivery-config show --json` (`mergePath`, `effectiveMergePath`, `mergePermission`); else the workflow doc / `CLAUDE.md` | **info**: no choice recorded means the default, owner merges; never block on it | To change it: `/delivery-config mergePath=agent`, and the owner allows `gh pr merge` themselves (via `/update-config`); this skill never edits settings. "Agent" without the command allowed → treat as owner and report the gap |
| Worker push policy | Recorded in `policy.workerMayPush` | **blocking** first time | Ask: workers may push their ticket branch and open **draft** PRs (recommended; nothing merges without the gates) — or every push waits for the owner |
| `.delivery/` ignored | `git check-ignore -q .delivery/orchestrator.json` | **blocking** | Ask: (A) add `.delivery/` to `.git/info/exclude` now (local, shared by all worktrees, no commit — recommended) and propose a Chore to add it to `.gitignore`; (B) owner adds it to `.gitignore` first |
| Concurrency cap | `delivery-config show --json` (`cap`); else the workflow doc line about tickets in flight / workers / slots (range → upper bound) | **info**: default **2** when none is written (the same default wave-status uses); 3 is fine on a desktop-class machine | `/delivery-config cap=N` |
| Local backend recipe | `docs/setup/local-backend.md` (ports, seed, test account, mail catcher) | **degraded**: device tests needing login/backend data escalate instead of running | Owner guide or Chore |
| Dev build registry | Native app (`app.json`/`app.config.*` with native modules, `ios/`, `android/`, `eas.json`) → `docs/setup/dev-builds.md` | **degraded**: device lane disabled for tickets that need a native build; `policy.deviceLaneEnabled` per case | Owner guide (building a dev client is an owner action) |
| Owner to-do list, generated | `docs/actions/*.md` front matter + a script that builds `docs/actions/README.md` | **degraded**: workers append guides; risk of merge conflicts on the list | Chore ticket for the generator |
| `needs-human` / `ready-to-merge` labels | Workflow doc names them; tracker has issues with them, or a saved filter | **info**: `needs-human` is applied on the first real escalation, `ready-to-merge` when a PR waits for the owner's merge (labels are ticket content). A saved filter is structure → only with approval | Offer to create the filters (approval) |
| Cost script | `scripts/workflow/cost` (the standard name; takes the ticket key, prints the total), or the path `docs/workflow/README.md` names | **info**: cost reported as "not tracked" | Chore ticket; record the name in `docs/workflow/README.md` |
| Context limits | Session window (`CLAUDE_CODE_AUTO_COMPACT_WINDOW`, `autoCompactWindow`), `# Compact instructions` in `CLAUDE.md`, `claude --version` | **info** | Recommend orchestrator 300k / workers 400k / subagents 200k and the compact instructions; no hook unless compactions lose state; write nothing without a yes (`context-limits.md`) |
| Gate / device capacity | Free disk (`Get-PSDrive` / `df -h`), RAM | **info**; warn under `policy.diskWarnGb` (default 15 GB) | Clean leftovers, lower `--cap` |

Then:

- **Ask only the blocking items**, in one AskUserQuestion (≤ 4 questions, recommendation first,
  labelled "(Recommended)"). Record answers in `policy` with `approvedAt`.
- Do the one local action the owner approved (e.g. append `.delivery/` to `.git/info/exclude`).
  Nothing else is changed: no settings, no permissions, no hooks, no committed files.
- Degraded and info items go into `setup.gaps` and into the final summary every run until
  fixed. Offer to write the matching `docs/actions/` guide or propose the Chore ticket; do not
  create tickets without a yes.

## 3. Waves

Run `wave-status` and parse its `wave-status/1` summary block.

| Finding | Action |
|---|---|
| `window` not null | Waves exist. Record `waves.source`, `waves.window`. Continue. |
| `window` null, `fallback_unit` set, and a wave plan doc exists | Tracker and doc disagree — report; ask whether to apply the doc's plan via `plan-waves` (it shows the exact changes). Do not cycle until settled. |
| No waves anywhere | Run `plan-waves`. Present its plan (it saves the PROPOSED doc itself) and ask for an explicit go. **End the turn** without scheduling a wake-up. |
| Owner says go (later turn) | Let `plan-waves` apply exactly what it showed; record `waves.planApprovedAt`; continue the bootstrap and run the first cycle (schedule the wake-up if in loop mode). |
| Owner changes the plan | Re-run `plan-waves` with the change; ask again. |

A prior instruction like "/deliver ABC and just apply the waves" is not approval of a plan the
owner has not seen.

## 4. Orca Run and state

1. `ORCA skills get orchestration` (once per session).
2. If `orca.runId` is recorded: `ORCA orchestration run-use --run <id>`; if that fails, report
   and create a new Run (never `orchestration reset`).
   Else: `ORCA orchestration run-create --objective "deliver <KEY>" --json`; store the id.
3. Take the lock (`state-files.md`, "Lock").
4. **Adopt work in flight** so nothing is started twice:
   - `ORCA worktree list --json` + `git worktree list`: any worktree with
     `.delivery/jobs/<KEY>-<n>/job.json` → a `tickets` entry with its stage; find its dispatch with
     `ORCA orchestration worker-list --json` (if it belongs to an older Run, `send` still
     reaches it; if no live worker, mark `waitingOn: "worker"` and resume it with a new
     `worker-start --worktree <exact selector> --agent claude --spec-file <resume brief>`).
   - `in_progress` tickets from wave-status with an open PR but no job folder (built by hand):
     record as stage `built` (orchestrator stage `dispatched`) with `holdsSlot: true`, and gate them in the first cycle —
     or, if their author is a human, leave them alone and list them.
   - PRs that are approved and waiting for the owner's merge → `awaiting_owner_merge` (label
     `ready-to-merge`).
5. Write `orchestrator.json` (atomic) and print the bootstrap summary: detection line, setup
   table, policy, window, in-flight adopted, what the first cycle will do.
