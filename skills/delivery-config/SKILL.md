---
name: delivery-config
description: >-
  Show or change delivery settings: personal machine settings (how many tickets this computer
  runs at once, loop pacing, worker engine) and team rules in docs/workflow/delivery.config.json
  (review rounds, auto-accept, who merges, merge strategy, PR target branch). Shows allowed values, this computer's
  suggested cap and how to change each one. Use when the user types /delivery-config.
argument-hint: "[show | [--me] key=value ... | reset [--me] <key>... | reset [--me] --all]"
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
python "$HOME/.claude/skills/delivery-config/config.py" --repo . set --me cap=4
python "$HOME/.claude/skills/delivery-config/config.py" --repo . reset --me cap
```

| Arguments | Do |
|---|---|
| none or `show` | Run `show` and print both tables, this computer's suggested cap and the change commands |
| `--me key=value ...` | Run `set --me` and print the result. Changes only this computer |
| `reset --me <key>...` or `reset --me --all` | Run `reset --me` and print the result |
| `key=value ...` | Team setting. Apply the confirmation rule below, run `set`, print the result |
| `reset <key>...` or `reset --all` | Team setting. Run `reset`, print the result |

**Personal settings:** `cap`, `loopMinutes`, `idleReleaseMin`, `engine`, `diskWarnGb`. They are
stored in `~/.claude/delivery.machine.json`, outside the repo, and win over the project's values.
Every other setting is a team rule. The script refuses `--me` for them, so do not work around it.

If the user asks to raise the cap with no `--me` ("my computer is faster"), use `--me`. Use a team
setting only when they say it is for everyone.

## Base branch

`baseBranch` is where tickets start and PRs point. `releaseBranch` is production. Both are team settings, so they cannot be set with `--me`.

```text
/delivery-config baseBranch=staging
/delivery-config baseBranch=main releaseBranch=main
python "$HOME/.claude/skills/delivery-config/config.py" --repo . branch
```

A branch must exist before it can be saved. If the repo has `.engineering/config.json`, its `baseBranch` and `productionBranch` are read as the current values, and saving here updates them too, so PR checks agree. Tell the owner to commit both files so everyone uses the same target.

## Confirm these two changes first

Typing the command is the owner's request, but these change what happens without them. State the
effect and get a yes (AskUserQuestion) before running `set`:

- **`mergePath=agent`**: agents will merge approved PRs with no human click. Also needs
  `Bash(gh pr merge:*)` in `permissions.allow`. Never edit permissions from this skill: `show`
  prints the gap, and the owner applies it (`/update-config` or by hand).
- **`autoAcceptRecommended=on`**: routine questions get the recommended answer without the owner.
  List the exclusions from `~/.claude/skills/deliver/references/cycle.md`, step 6.

## After a change

Say that a running loop applies it on its next cycle. For a team setting, do not commit; suggest
committing `docs/workflow/delivery.config.json` so every checkout and worktree shares it. A
personal setting needs no commit.
