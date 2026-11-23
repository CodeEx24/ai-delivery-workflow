# Delivery workflow guide

How to set up the workflow in a new project, run it, and change how it behaves.

Commands starting with `/` go in Claude Code. The others go in PowerShell.

## 1. Set up a new project

### Before you start

You need Claude Code, Git, the GitHub CLI (`gh auth login`), Python 3 and Orca. Without Orca, use `--engine subagents`.

### Step 1: install or update the kit

Run this once per machine, and again whenever the kit changes:

```powershell
cd "D:\Orca Project Folder\ai-delivery-workflow"
git pull
.\install.ps1 -SkipThirdParty
```

On a first install, leave off `-SkipThirdParty`. Restart any open Claude Code sessions afterwards.

### Step 2: connect the project

Open Claude Code in the project and run:

```text
/delivery-init <KEY>
```

`<KEY>` is the tracker prefix, such as `EST` or `PP`. The command shows its plan and waits for your yes. It then:

- adds the workflow to `CLAUDE.md`
- creates `docs/workflow/README.md`
- adds `.delivery/` to `.gitignore`
- updates `.claude/settings.json` only if you say yes

Commit those files.

### Step 3: choose your settings

```text
/delivery-config
```

The defaults are safe: two tickets at a time, nothing auto-accepted, and you do the merging. See [Settings](#3-settings).

### Step 4: start

Start the loop. It also starts the board and prints its address:

```text
/loop /deliver <KEY>
```

On the first run, it checks the project and asks you to approve the wave plan if there isn't one.

## 2. Everyday commands

### Run the work

| I want to | Command |
|---|---|
| Choose what to run from a prompt (mine, specific tickets, or all available) | `/loop /deliver <KEY>` |
| Run everything assigned to me, and keep watching | `/loop /deliver <KEY> --mine` |
| Run only certain tickets | `/loop /deliver <KEY> --only <KEY>-12,<KEY>-13` |
| Run one cycle | `/deliver <KEY>` |
| Run the loop in its own Orca chat | `/deliver <KEY> --watcher` |
| Preview without changing anything | `/deliver <KEY> --dry-run` |
| Build tickets from a document | `/loop /deliver docs/spec.md` |
| Create a ticket from a description | `/new-ticket` |
| Work from GitHub issues labeled `factory` | `/loop /factory run` |

### Check and control

| I want to | Command |
|---|---|
| See where things stand | `/deliver <KEY> --status` or `/wave-status` |
| Open the board | `/deliver <KEY> --board` |
| Pause after the current step | `/deliver <KEY> --pause` |
| Pause right now | `/deliver <KEY> --pause --now` |
| Pause one ticket | `/deliver <KEY> --pause <KEY>-12` |
| Resume | `/deliver <KEY> --resume` |
| Use fewer agents for this run | `/loop /deliver <KEY> --cap 1` |

### See what a ticket changed

```powershell
python "$HOME\.claude\delivery-board\board.py" report --repo . --ticket <KEY>-12 --open
```

The board's ticket drawer also has a **Change report** link.

## 3. Settings

There are two levels of settings. A running loop picks up changes on its next cycle.

| Level | Stored in | Affects | Shared? |
|---|---|---|---|
| **Your machine** | `~/.claude/delivery.machine.json` | Only you, in every project | No |
| **Team rules** | `docs/workflow/delivery.config.json` | Everyone on the project | Yes, commit it |

Your machine settings win over the project's. Only `cap`, `loopMinutes`, `idleReleaseMin`, `engine` and `diskWarnGb` can be personal. Merging, review rounds, auto-accept, pushing and browser testing stay team rules.

```text
/delivery-config                       show all settings, this computer's suggested cap, and how to change them

/delivery-config --me cap=4            just for me: run 4 tickets at once
/delivery-config --me engine=subagents just for me: run workers without Orca
/delivery-config reset --me cap        remove my personal value
/delivery-config reset --me --all      remove all my personal values

/delivery-config cap=3                 team default for everyone
/delivery-config cap=3 maxRounds=4     change several team settings
/delivery-config reset cap             put a team setting back to its default
/delivery-config reset --all           put all team settings back to defaults
```

| Setting | Default | Options | What it controls |
|---|---|---|---|
| `cap` | `2` | 1-10 | Tickets, each with its own worker agent, running at once |
| `maxRounds` | `3` | 1-6 | Fix-and-review rounds before a ticket comes to you |
| `loopMinutes` | `auto` | `auto`, 1-60 | Time between loop check-ins |
| `idleReleaseMin` | `60` | 5-1440 | Minutes a worker waits for you before it is released (it can resume) |
| `autoAcceptRecommended` | `off` | `on`, `off` | Accept the recommended option on routine questions |
| `mergePath` | `owner` | `owner`, `agent` | Who merges an approved PR |
| `mergeStrategy` | `squash` | `squash`, `merge`, `rebase` | How PRs are merged |
| `workerMayPush` | `on` | `on`, `off` | Workers push ticket branches and open draft PRs |
| `deviceLane` | `on` | `on`, `off` | Run the browser or device tester |
| `engine` | `orca` | `orca`, `subagents` | How workers run |
| `diskWarnGb` | `15` | 1-1000 | Warn when free disk space falls below this |

### How many agents

`cap` limits tickets, not every agent. Each ticket has one worker, and that worker briefly starts its own testers and reviewers. Only one ticket uses the browser or device at a time, and only one merges at a time.

| Machine | Suggested `cap` |
|---|---|
| Laptop | `1` or `2` |
| Desktop | `3` |
| Large workstation | `4` or more |

A higher cap uses more memory and usage limits, and tickets are more likely to touch the same files.

### Auto-accept recommended options

This is **off by default**, so every question waits for you under **Needs you**.

```text
/delivery-config autoAcceptRecommended=on
```

When it's on, the orchestrator accepts the recommendation only for routine design decisions and spec approvals on tickets that aren't high risk. Each one is logged and listed in the cycle output.

These **always come to you**:

- anything about auth, permissions, data access, secrets, billing, personal data, deletion, production, or migrations on live data
- high-risk tickets
- escalations, blocked tests and tickets that hit the round limit
- requests to change scope, missing information, and things only you can do
- dropping or deferring an acceptance criterion
- ticket lists, wave plans and setup decisions
- merges, which follow `mergePath`

### Who merges

Every PR must pass the checks, testers, reviewers and approver first, whichever option you choose. Nothing merges on a failing check.

| | You merge (default) | Agents merge |
|---|---|---|
| After approval | The ticket is labeled `ready-to-merge` and waits | The agent re-checks and merges it |
| Your part | Merge on GitHub | Nothing |
| Afterwards | The loop sees the merge and closes out the ticket | Same |

**To let agents merge, make both changes:**

1. Run `/delivery-config mergePath=agent` and confirm.
2. In the project's `.claude/settings.json`, move the merge rule from `ask` to `allow`:

   ```json
   {
     "permissions": {
       "allow": ["Bash(gh pr merge:*)"]
     }
   }
   ```

   Make sure it no longer appears under `ask` or `deny`.

Run `/delivery-config` and check the **Who merges right now** line. If only one change was made, it still says `owner`, so an agent can't merge by accident.

**To go back to merging yourself:**

```text
/delivery-config mergePath=owner
```

Also move the rule back to `ask`.

### Common setups

| Style | Command |
|---|---|
| Full control (default) | `/delivery-config reset --all` |
| Fewer interruptions, you still merge | `/delivery-config autoAcceptRecommended=on` |
| One careful ticket at a time | `/delivery-config cap=1 maxRounds=2` |
| Mostly hands-off | `/delivery-config cap=3 autoAcceptRecommended=on mergePath=agent`, plus the permission above |

## 4. QA

`/verify-ticket` proves a ticket works before merge. `/qa` tests what is **deployed**, goes wider than the acceptance criteria, and leaves evidence for a person to sign off. It never moves a ticket to Done.

### Set it up once per project

```text
/qa-config init --project ABC --staging-url https://staging.example.com
```

Commit `docs/workflow/qa.config.json`. Put the QA account's login in the gitignored `.env.qa.local`, never in chat:

```text
QA_OWNER_EMAIL=qa-owner@example.com
QA_OWNER_PASSWORD=<the QA account's password>
```

Then run `/qa-config check`. To use `/qa ABC --ready`, set the `QA testing status` line in `docs/workflow/README.md`.

### Run it

| I want to | Command |
|---|---|
| See the test plan without changing anything | `/qa ABC-123 --dry-run` |
| Test one ticket | `/qa ABC-123` |
| Test my tickets in the testing status | `/qa ABC --mine` |
| Test all tickets in the testing status | `/qa ABC --ready` |
| Test a release | `/qa ABC --release` |
| Choose how deep | `/qa ABC-123 --depth smoke`, `standard` or `full` |
| Add test types | `/qa ABC-123 --focus ui,a11y,api` |
| Test a PR's preview | `/qa ABC-123 --pr 42` |
| Report a bug by hand | `/report-bug-ticket "Export drops rows" --ticket ABC-123` |
| Retest after a fix | `/qa ABC-123 --retest --env local` (add `--from-run <run-id>` to pick the run) |

### Results

| Result | Label | Meaning |
|---|---|---|
| `✅ QA PASSED` | `qa:passed` | Everything planned passed on a verified build |
| `⚠️ QA PASSED WITH NOTES` | `qa:passed-with-notes` | No criterion failed, with minor findings |
| `❌ QA FAILED` | `qa:failed` | A criterion failed or a serious defect was found |
| `🚫 QA BLOCKED` | `qa:blocked` | Something could not be verified. It is not a pass |

Improvements are flagged `💡` and labeled `qa:improvement`. Evidence is saved in `.delivery/qa/<KEY-n>/<run-id>/` and attached to the tracker, which is the shared copy. If an upload fails, the bug says `Evidence incomplete` and gets `qa:evidence-missing`.

Every QA bug has an **Engineering handoff**, so an AI on another machine can reproduce, fix and retest it. A retest reports what is fixed, still failing, newly failing and not run. Anything required that did not run makes it BLOCKED.

### Where QA may test

| Access | What QA may do |
|---|---|
| `full` | Any journey with QA accounts |
| `qa-data-only` | Write only QA-marked data |
| `smoke-read-only` | Look, but never write |
| `blocked` | Refuse |

Production can only be `smoke-read-only` or `blocked`, and always asks first. An unknown URL also asks first and stays read-only. Stress tests run only with `--focus stress`, your confirmation and an isolated environment, never on production.

Your personal settings can change only your local URLs, default environment, browser and headed mode:

```text
/qa-config --me local.url=http://localhost:3100
/qa-config --me defaultEnv=local browser=firefox headed=on
```

## 5. Troubleshooting

| Problem | Fix |
|---|---|
| `can't open file ...~\.claude...` | PowerShell doesn't expand `~`. Use `"$HOME\.claude\..."` |
| Board answers aren't picked up | Check that the loop is running, or run `/deliver <KEY>` |
| New settings or skills aren't used | Re-run the installer and restart the orchestrator and board |
| An agent didn't merge | Run `/delivery-config` and read **Who merges right now** |
| A ticket is stuck | Run `/deliver <KEY> --status`, then check **Needs you** on the board |
| `/qa` says BLOCKED | Read the reason, then run `/qa-config check`. A fix that isn't deployed yet is a common cause |
