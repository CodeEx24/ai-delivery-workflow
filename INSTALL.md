# Install the AI delivery workflow

Two levels:

1. **Once per machine:** install the kit into `~/.claude`. Every project on that machine then has
   `/deliver`, `/factory`, `/plan-waves`, `/implement-ticket`, the agents and the live board.
2. **Once per project:** run `/delivery-init` inside the project. It adds a few small files
   (no kit code is copied into your repo).

## Before you start

| Need | Check | Why |
|---|---|---|
| Claude Code 2.1.296+ | `claude --version` | Agents use `autoCompactWindow` |
| git | `git --version` | Worktrees, branches |
| GitHub CLI, logged in | `gh auth status` | PRs, and cloning this repo while it is private |
| Python 3.10+ | `python --version` (Windows) / `python3 --version` | The live board |
| Node.js with `npx` | `npx --version` | Installs the third-party skills (optional: `-SkipThirdParty`) |
| Orca *(optional)* | `orca repo list` | Parallel worker sessions; without it `/factory` uses background subagents |
| PM tool connector *(optional)* | Atlassian / Linear MCP in Claude Code | Jira / Linear backlogs; GitHub Issues needs only `gh` |

## 1. Install on this machine

The repo is private, so clone it with `gh` (works on any machine where you are logged in to
GitHub with access to the repo).

**Windows (PowerShell):**

```powershell
gh repo clone CodeEx24/ai-delivery-workflow "$HOME\.ai-delivery-workflow"
powershell -ExecutionPolicy Bypass -File "$HOME\.ai-delivery-workflow\install.ps1"
```

**macOS / Linux / Git Bash:**

```bash
gh repo clone CodeEx24/ai-delivery-workflow ~/.ai-delivery-workflow
~/.ai-delivery-workflow/install.sh
```

Then **restart** any open Claude Code sessions so they load the new skills.

What the installer does: backs up anything it replaces into
`~/.claude/backups/ai-delivery-workflow-<timestamp>/`, copies `skills/`, `agents/`, the workflow
file, the board (`~/.claude/delivery-board/`) and the `/delivery-init` templates, and installs the
third-party skills with `npx skills add`. It never edits `settings.json` or any project.

| Option (PowerShell / bash) | Effect |
|---|---|
| `-DryRun` / `--dry-run` | Show every action, change nothing |
| `-SkipThirdParty` / `--skip-third-party` | Skip the `npx skills add` step |
| `-WithBlueprint` / `--with-blueprint` | Also install `delivery-blueprint` (normally synced from claude.ai) |
| `-ClaudeHome <path>` / `--claude-home <path>` | Install somewhere other than `~/.claude` |

**Check it worked:** in any Claude Code session type `/factory` or `/delivery-init`; they should
autocomplete. Then look at the board with sample data:

```bash
python "$HOME/.claude/delivery-board/board.py" serve --demo --open
```

## 2. Set up a project

Open Claude Code in the project's folder and run:

```text
/delivery-init
```

It detects the project key, tracker (Jira, Linear, GitHub Issues or a local backlog) and checks
command, shows what it will change, and on your yes:

- adds the workflow block to `CLAUDE.md` (import line + compact instructions, between markers so
  re-running updates instead of duplicating);
- creates `docs/workflow/README.md` (cap, merge path, type mapping, checks script);
- adds `.delivery/` to `.gitignore`;
- merges the recommended permissions into `.claude/settings.json` **only if you say yes**;
- with `--factory` (or a GitHub-Issues project), offers to create the `/factory` labels.

Options: `/delivery-init ABC` (set the key), `--tracker jira|linear|github|local`, `--factory`,
`--dry-run`. Commit the changed files when you are happy with them.

Then start working; see [`workflow/PLAYBOOK.md`](workflow/PLAYBOOK.md):

| Situation | Command |
|---|---|
| Jira / Linear backlog | `/wave-status` → `/plan-waves` (if no waves) → `/loop /deliver ABC` |
| One ticket | `/loop /deliver ABC --only ABC-42` (or `/implement-ticket ABC-42`) |
| GitHub issues | label them `factory` → `/loop /factory run` |
| New product from a spec | `/delivery-blueprint`, then the Jira row |

### Set up a project by hand (no `/delivery-init`)

1. Paste the block from `settings/claude-md-snippet.md` into the project's `CLAUDE.md`.
2. Copy `settings/docs-workflow-README.template.md` to `docs/workflow/README.md` and fill it in.
3. Add `.delivery/` to `.gitignore`.
4. Optional: merge entries from `settings/settings.recommended.json` into `.claude/settings.json`.

## Update

```powershell
git -C "$HOME\.ai-delivery-workflow" pull
powershell -ExecutionPolicy Bypass -File "$HOME\.ai-delivery-workflow\install.ps1"
```

```bash
git -C ~/.ai-delivery-workflow pull && ~/.ai-delivery-workflow/install.sh
```

Projects need no update: they import the workflow from `~/.claude`. Re-run `/delivery-init` only
if the release notes in `CHANGELOG.md` say the project files changed.

## Uninstall

Delete `~/.claude/delivery-board/`, the kit's folders in `~/.claude/skills/` (`deliver`, `factory`,
`delivery-init`, `plan-waves`, `wave-status`, `implement-ticket`, `verify-ticket`,
`merge-ticket`, `senior-pr-reviewer`), the eight agent files in `~/.claude/agents/`, and
`~/.claude/workflows/ai-delivery-workflow.md`. Restore anything you want from
`~/.claude/backups/ai-delivery-workflow-<timestamp>/`. Third-party skills:
`npx skills remove <name> -g`. In a project, remove the marked block from `CLAUDE.md`.

## If the repo becomes public later

Cloning then needs no GitHub login:

```bash
git clone https://github.com/CodeEx24/ai-delivery-workflow ~/.ai-delivery-workflow
```

and the rest is the same.
