---
name: delivery-config
description: >-
  Show or change one project's delivery settings in docs/workflow/delivery.config.json: how many
  tickets run at once, review rounds, loop pacing, whether routine questions auto-accept the
  recommended option (default off), who merges (owner by default, or agents after approval), and
  the merge strategy. Use when the user types /delivery-config.
argument-hint: "[show | key=value ... | reset <key>... | reset --all]"
user-invocable: true
disable-model-invocation: true
---

# /delivery-config

Arguments: `$ARGUMENTS`

Run the script from the project; never edit the JSON by hand:

```text
python "$HOME/.claude/skills/delivery-config/config.py" --repo . show
python "$HOME/.claude/skills/delivery-config/config.py" --repo . set cap=3 maxRounds=4
python "$HOME/.claude/skills/delivery-config/config.py" --repo . reset cap
```

| Arguments | Do |
|---|---|
| none or `show` | Run `show` and print the table |
| `key=value ...` | Apply the confirmation rule below, run `set`, print the result |
| `reset <key>...` or `reset --all` | Run `reset`, print the result |

## Confirm these two changes first

Typing the command is the owner's request, but these change what happens without them. State the
effect and get a yes (AskUserQuestion) before running `set`:

- **`mergePath=agent`**: agents will merge approved PRs with no human click. Also needs
  `Bash(gh pr merge:*)` in `permissions.allow`. Never edit permissions from this skill: `show`
  prints the gap, and the owner applies it (`/update-config` or by hand).
- **`autoAcceptRecommended=on`**: routine questions get the recommended answer without the owner.
  List the exclusions from `~/.claude/skills/deliver/references/cycle.md`, step 6.

## After a change

Say that a running loop applies it on its next cycle. Do not commit; suggest committing
`docs/workflow/delivery.config.json` so every checkout and worktree shares it.
