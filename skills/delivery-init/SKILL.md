---
name: delivery-init
description: >-
  Set up the current project for the AI delivery workflow in one step: add the workflow import
  and compact instructions to CLAUDE.md, create docs/workflow/README.md with the project's key,
  tracker and merge path, add .delivery/ to .gitignore, and (only on an explicit yes) merge the
  recommended permissions into .claude/settings.json. Shows every change before writing, is safe
  to re-run (it updates its own marked block instead of duplicating), and never touches product
  code. Use when the user says "/delivery-init", "set up this project for the workflow",
  "install the delivery workflow in this repo", "onboard this project to /deliver or /factory",
  or "add the workflow to CLAUDE.md".
argument-hint: "[<PROJECT-KEY>] [--tracker jira|linear|github|local] [--factory] [--dry-run]"
user-invocable: true
---

# /delivery-init — set up this project

Arguments: `$ARGUMENTS`

The kit itself is installed once per machine in `~/.claude` (skills, agents, workflow file,
board). This skill wires **one project** to it. It writes only the files below, shows the plan
first, and asks once.

Templates live beside this file in `templates/` (the installer copies the kit's `settings/`
folder there): `claude-md-snippet.md`, `docs-workflow-README.template.md`,
`settings.recommended.json`. If `templates/` is missing, say the kit is not fully installed and
point to `INSTALL.md` in the kit.

## Step 1 — Detect (read-only)

| What | How |
|---|---|
| Repo root, default branch | `git rev-parse --show-toplevel`, `gh repo view --json nameWithOwner,defaultBranchRef` (no GitHub → note it) |
| Kit installed | `~/.claude/workflows/ai-delivery-workflow.md`, `~/.claude/skills/deliver/`, `~/.claude/delivery-board/board.py` exist |
| Project key | argument; else `CLAUDE.md` / `AGENTS.md` ("key `ABC`"); else issue keys in `git log --oneline -30`; GitHub-only projects use `GH` |
| Tracker | `--tracker`; else what `CLAUDE.md` names; else Jira / Linear if their MCP tools load (ToolSearch first); else GitHub Issues if `gh` works; else local backlog |
| Already set up | `CLAUDE.md` contains `@~/.claude/workflows/ai-delivery-workflow.md` or the `ai-delivery-workflow:start` marker; `docs/workflow/README.md` exists; `.gitignore` has `.delivery/` |
| Checks command | `scripts/workflow/checks*`, else the package scripts / Makefile targets for test, lint, typecheck (for the README and the settings placeholders) |

Ask (one batched AskUserQuestion) only for what detection could not settle: the project key,
the tracker, the merge path (default: **owner merges**), and whether to merge the recommended
permissions into `.claude/settings.json` (default: **no**, show them instead).

## Step 2 — Show the plan

A short table: file · action (create / add block / update block / skip, already done) · what
changes. Then wait for a yes. `--dry-run` stops here.

## Step 3 — Write (idempotent)

1. **`CLAUDE.md`** (create it if missing, with a one-line title). Insert near the top the block
   from `templates/claude-md-snippet.md` between markers, with `<KEY>` filled:

   ```markdown
   <!-- ai-delivery-workflow:start -->
   @~/.claude/workflows/ai-delivery-workflow.md
   … (the snippet's body, including "# Compact instructions") …
   <!-- ai-delivery-workflow:end -->
   ```

   If the markers exist, replace only what is between them. If an unmarked import line already
   exists, leave it and add only the missing compact section, wrapped in the markers.
2. **`docs/workflow/README.md`** from `templates/docs-workflow-README.template.md`: fill
   `<Product>` (repo name), the PM link, `<KEY>`, the main branch, the merge path, and the
   checks command found in Step 1. Existing file → do not overwrite; list the values that differ
   and offer to update them one by one.
3. **`.gitignore`**: append `.delivery/` under a `# AI delivery workflow` comment if missing.
4. **`.claude/settings.json`**, only on an explicit yes: merge `templates/settings.recommended.json`.
   Add missing `allow` / `ask` / `deny` entries (never remove the project's own), replace the
   `<test-runner>` placeholders with the real commands from Step 1 (drop those that do not
   apply), keep `gh pr merge` under `ask` unless the owner chose "agent merges", add `env` only
   if the key is absent. Show the resulting diff before writing. No yes → print the entries to
   add and stop. If the owner chose "agent merges", also run
   `python "$HOME/.claude/skills/delivery-config/config.py" --repo . set mergePath=agent`.
5. **`--factory`** (or tracker = GitHub): list the labels `/factory` uses and offer to create
   them now (`gh label create …`, see the factory skill's `references/github-queue.md`).

Do not commit. Report the files changed and suggest committing `CLAUDE.md`,
`docs/workflow/README.md` and `.gitignore` together.

## Step 4 — Next steps (print)

```
Project ready for the delivery workflow.
  Live board (sample data):   python "$HOME/.claude/delivery-board/board.py" serve --demo --open
  Jira / Linear backlog:      /wave-status  →  /plan-waves (if no waves)  →  /loop /deliver <KEY>
  One ticket:                 /loop /deliver <KEY> --only <KEY>-<n>    (or /implement-ticket <KEY>-<n>)
  GitHub issues:              label them `factory`  →  /loop /factory run
  New product from a spec:    /delivery-blueprint first
  See or change settings:     /delivery-config
The first /deliver or /factory run checks the rest (checks script, agents, labels) and offers fixes.
```

## Will not

- Touch product code, CI, or anything outside the four files above.
- Write `.claude/settings.json` without an explicit yes, or remove any existing setting.
- Overwrite an existing `docs/workflow/README.md` wholesale.
- Commit or push.
