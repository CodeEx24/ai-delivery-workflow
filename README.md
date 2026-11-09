# AI delivery workflow kit

A Claude Code kit that takes a project from tickets to merged, verified code. It installs a workflow file, seven skills and eight subagents into `~/.claude`. Together they plan the backlog into waves, build each ready ticket in its own git worktree, run checks, testers and reviewers on every pull request, ask you only for real decisions, and close out each merge (proof on the ticket and PR, ticket moved to Done, worktree cleaned up). It works with any stack and any PM tool; stack names in the files are only examples.

Private — all rights reserved. Third-party skills are not included; the installer fetches them from their own sources.

## What's inside

| Path | What it is |
|---|---|
| `workflow/ai-delivery-workflow.md` | The workflow itself. Installed to `~/.claude/workflows/` and imported by each project's `CLAUDE.md`. |
| `workflow/AI-Delivery-Workflow.pdf` | The same workflow as a readable PDF guide. |
| `skills/deliver/` | `/deliver` — the orchestrator: runs steps 3–7 in a loop (manual-only command). |
| `skills/plan-waves/` | `/plan-waves` — orders the backlog into dependency-correct waves. |
| `skills/wave-status/` | `/wave-status` — what is open, ready, out of sync or waiting on you. |
| `skills/implement-ticket/` | `/implement-ticket` — builds one ticket up to a draft PR. |
| `skills/verify-ticket/` | `/verify-ticket` — runs the app and walks every acceptance criterion with screenshots. |
| `skills/merge-ticket/` | `/merge-ticket` — re-checks, merges (or hands you the merge), posts proof, cleans up. |
| `skills/senior-pr-reviewer/` | Senior code review; used by the `reviewer-code` agent. |
| `skills/delivery-blueprint/` | Mirror of the claude.ai-synced `/delivery-blueprint` skill (new projects). Skipped by the installer unless asked. See its `NOTE.md`. |
| `agents/` | The review and test loop: `tester-functional`, `tester-device`, `reviewer-code`, `reviewer-security`, `reviewer-ui`, `reviewer-ux`, `approver`, `explainer`. |
| `settings/` | Templates to merge by hand: recommended `settings.json` permissions, a `CLAUDE.md` snippet, a `docs/workflow/README.md` template. |
| `third-party.md` | Skills, plugins and MCP servers the workflow uses but this kit does not ship. |
| `docs/changelog/` | Detailed change notes per release. Summary in `CHANGELOG.md`. |
| `install.ps1`, `install.sh` | Installers for Windows and macOS/Linux. |

## Prerequisites

- **Claude Code 2.1.296 or later** (the agents use `autoCompactWindow` in their frontmatter).
- **Node.js with `npx`** (installs the third-party skills through the skills CLI).
- **git** and the **GitHub CLI `gh`**, logged in (`gh auth status`).
- **Orca** for parallel ticket workers: `/deliver` starts one Orca worktree session per ticket. Without Orca you can still run each skill by hand.
- A **PM tool connection** (for example the Atlassian MCP for Jira). With none, `/deliver` falls back to GitHub Issues, or to a local `docs/tickets/backlog.md`.

## Install

Windows (PowerShell 5.1 or 7):

```powershell
pwsh ./install.ps1            # or: powershell -ExecutionPolicy Bypass -File .\install.ps1
```

macOS / Linux:

```bash
./install.sh
```

Options (both scripts):

| PowerShell | bash | Effect |
|---|---|---|
| `-DryRun` | `--dry-run` | Print every action, change nothing. |
| `-WithBlueprint` | `--with-blueprint` | Also install `skills/delivery-blueprint` (normally synced from claude.ai). |
| `-SkipThirdParty` | `--skip-third-party` | Don't run `npx skills add` for the third-party skills. |
| `-ClaudeHome <path>` | `--claude-home <path>` | Install somewhere other than `~/.claude` (for testing). Third-party skills still go to the skills CLI's global location, so add `-SkipThirdParty` when testing. |

### What the installer does

1. Backs up anything it is about to replace — `~/.claude/skills/<name>/`, `~/.claude/agents/<name>.md` and `~/.claude/workflows/ai-delivery-workflow.md`, only those that exist — into `~/.claude/backups/ai-delivery-workflow-<timestamp>/`.
2. Copies `skills/*` to `~/.claude/skills/`, `agents/*.md` to `~/.claude/agents/` and the workflow file to `~/.claude/workflows/`.
3. Installs the third-party skills globally with `npx -y skills add <package> -g -y` (see `third-party.md`).
4. Prints the next steps.

It never edits `settings.json` or any project. Running it again is safe: it takes a fresh backup and copies the same files again.

## Update

```bash
git pull
./install.sh          # or: pwsh ./install.ps1
```

## Uninstall / roll back

Each run leaves a backup folder `~/.claude/backups/ai-delivery-workflow-<timestamp>/` with the same layout as `~/.claude` (`skills/`, `agents/`, `workflows/`).

- **Roll back to what you had before:** copy the contents of that backup folder back over `~/.claude`.
- **Remove the kit:** delete the kit's skill folders (`deliver`, `plan-waves`, `wave-status`, `implement-ticket`, `verify-ticket`, `merge-ticket`, `senior-pr-reviewer`), the eight agent files and `~/.claude/workflows/ai-delivery-workflow.md`, then restore anything you want back from the backup. Third-party skills are removed with the skills CLI (`npx skills remove <name> -g`).

## Quick start

In a project that already has tickets:

| Command | What it does |
|---|---|
| `/deliver <PROJECT-KEY>` | Checks the project setup, plans waves if there are none (you approve), then builds, tests, reviews and merges ready tickets. |
| `/loop /deliver <PROJECT-KEY>` | **Recommended.** Same, but keeps going without you prompting each cycle. |
| `/deliver <path-to-doc>` | Starts from a spec, PRD or notes: turns it into tickets (you approve the list), then runs as above. |
| `/deliver <KEY> --dry-run` | Shows what one cycle would do. Writes nothing. |
| `/deliver <KEY> --status` | Read-only: what is running, waiting and ready. |
| `/deliver <KEY> --watcher` | Runs the loop in its own Orca chat so this one stays free. |
| `/deliver <KEY> --cap N` | Fewer tickets in flight for this run (raising it above the project's cap asks you first). |

New project? Run **`/delivery-blueprint`** first (PRD, tickets, `CLAUDE.md`, docs layout), then `/deliver`.

You can also run any step on its own: `/plan-waves`, `/wave-status`, `/implement-ticket <KEY>-<n>`, `/verify-ticket <KEY>-<n>`, `/merge-ticket <KEY>-<n>`.

## Per-project setup

1. Add the import line to the project's `CLAUDE.md`, plus a `# Compact instructions` section — copy from `settings/claude-md-snippet.md`:

   ```
   @~/.claude/workflows/ai-delivery-workflow.md
   ```

2. Create `docs/workflow/README.md` from `settings/docs-workflow-README.template.md` (concurrency cap, merge path, ticket type mapping, checks and cost script names, device lane).
3. Merge the parts of `settings/settings.recommended.json` you want into the project's `.claude/settings.json` by hand (replace the placeholder commands with your real test / lint / typecheck commands).
4. Add `.delivery/` to the project's `.gitignore`.

The first `/deliver` run checks the rest (checks script, agent files, local backend recipe, dev build registry, labels) and offers to set up what is missing; it writes nothing without your yes.

## More

- Full workflow: [`workflow/ai-delivery-workflow.md`](workflow/ai-delivery-workflow.md)
- PDF guide: [`workflow/AI-Delivery-Workflow.pdf`](workflow/AI-Delivery-Workflow.pdf)
- Third-party tools: [`third-party.md`](third-party.md)
- Changes: [`CHANGELOG.md`](CHANGELOG.md)
