---
name: qa-config
description: >-
  Show, check or change where and how /qa may test a project: environments, URLs, access levels,
  allowed hosts, GitHub deployment names, QA account variable names and personal local settings.
  Secrets stay in the gitignored .env.qa.local and are never printed. Use when the user types
  /qa-config.
argument-hint: "[show | check [--env E] | init --project KEY --staging-url URL | [--me] key=value ... | reset [--me] <key>... | reset [--me] --all | resolve ... | deployed ...]"
user-invocable: true
disable-model-invocation: true
---

# /qa-config

Arguments: `$ARGUMENTS`

Run the script from the project. Never edit the JSON by hand, and never open `.env.qa.local`.

```text
python "$HOME/.claude/skills/qa-config/qa_config.py" --repo . show
python "$HOME/.claude/skills/qa-config/qa_config.py" --repo . check --env staging
python "$HOME/.claude/skills/qa-config/qa_config.py" --repo . init --project ABC --staging-url https://staging.example.com
python "$HOME/.claude/skills/qa-config/qa_config.py" --repo . set staging.access=qa-data-only
python "$HOME/.claude/skills/qa-config/qa_config.py" --repo . set --me local.url=http://localhost:3100
python "$HOME/.claude/skills/qa-config/qa_config.py" --repo . reset --me local.url
python "$HOME/.claude/skills/qa-config/qa_config.py" --repo . resolve --pr 42 --json
python "$HOME/.claude/skills/qa-config/qa_config.py" --repo . deployed --env staging --sha abc1234 --json
```

| Arguments | Do |
|---|---|
| none or `show` | Run `show` and print it |
| `check [--env E] [--url U] [--pr N]` | Validate the config, probe the URL and report each account's variable names as present or missing. Non-zero means blocked |
| `init ...` | Create `docs/workflow/qa.config.json` and add `.env.qa.local` to `.gitignore`. Refuses to overwrite |
| `key=value ...` | Team setting. Apply the confirmation rule below, run `set`, print the result |
| `--me key=value ...` | Personal setting. Run `set --me`, print the result |
| `reset [--me] <key>...` or `--all` | Run `reset`, print the result |
| `resolve`, `deployed` | Run it and print the result. `/qa` uses these with `--json` |

## Files

| What | Where | Shared |
|---|---|---|
| Team rules | `docs/workflow/qa.config.json` | Yes, commit it |
| Personal settings | `~/.claude/qa.machine.json`, keyed by project (`QA_MACHINE_CONFIG` overrides the path) | No |
| Secrets | `.env.qa.local` at the repo root. A linked worktree falls back to the main worktree's copy | No, gitignored |

The secrets file holds the variables the config names:

```text
QA_OWNER_EMAIL=qa-owner@example.com
QA_OWNER_PASSWORD=<the QA account's password>
```

## Settings

- **Team:** `defaultEnv`, `allowedHosts` (comma separated), `<env>.url`, `<env>.authUrl`,
  `<env>.access`, `deployment.stagingEnvironment`, `deployment.previewEnvironment`,
  `accounts.<role>.emailEnv`, `accounts.<role>.passwordEnv`. `<env>` is `local`, `preview`,
  `staging` or `production`.
- **Personal (`--me`):** `local.url`, `local.authUrl`, `defaultEnv` (never `production`),
  `browser`, `headed`. Personal local URLs must point at this computer. Any other key in the
  personal file is ignored with a warning, so it can never widen access.

| Access | Meaning |
|---|---|
| `full` | Any QA journey with QA accounts |
| `qa-data-only` | Writes only to QA-marked data with a run ID |
| `smoke-read-only` | Reads only, no writes |
| `blocked` | `/qa` refuses to test |

`production` may only be `smoke-read-only` or `blocked`, and can never be a default environment.

## How a target is resolved

Order: `--url`, then `--env`, then personal `defaultEnv`, then team `defaultEnv`. No URL
configured is an error, never a guess.

For `--url`, hosts are compared exactly (wildcards by proper suffix):

| The host | Result |
|---|---|
| Is production, or a subdomain of it that is not a configured environment | Production's access, needs confirmation |
| Is a configured environment | That environment's access |
| Matches `allowedHosts` | `qa-data-only` |
| Anything else | `smoke-read-only`, `requiresConfirmation: true` |

URLs containing a username, a password or a credential-like query parameter are refused.

`deployed` reports `true`, `false` or `unknown`. Staging passes when the newest successful
deployment is the commit or contains it. Preview needs a successful deployment of the exact
commit, because previews share one environment across PRs.

## Confirm these changes first

State the effect and get a yes (AskUserQuestion) before running `set`:

- Any change to `production.*`.
- Raising access on any environment (for example `smoke-read-only` to `qa-data-only`).
- Widening `allowedHosts`.

## After a change

For a team setting, do not commit; suggest committing `docs/workflow/qa.config.json`. A personal
setting needs no commit. Never print a secret value, and never ask the user to paste one in chat.
