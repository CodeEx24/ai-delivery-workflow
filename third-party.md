# Third-party skills, plugins and MCP servers

The kit does not ship these. Skills marked **installed by the installer** are added with `npx -y skills add <package> -g -y` unless you pass `--skip-third-party` / `-SkipThirdParty`. Everything else is optional and depends on your stack; install only what the project needs (every extra hook or MCP server costs context).

## Skills (installed by the installer)

| Skill | Install | Used by / why |
|---|---|---|
| `security-review` | `npx skills add getsentry/skills@security-review -g -y` | `reviewer-security` agent (preloaded) and `senior-pr-reviewer`'s security lens: OWASP-based, high-confidence checks for auth, injection, secrets and data leaks. |
| `test-driven-development` | `npx skills add obra/superpowers@test-driven-development -g -y` | `implement-ticket` (Bug tickets: reproduce with a failing test first) and `senior-pr-reviewer` / `reviewer-code` (judging whether new tests are any good). |
| `playwright-cli` | `npx skills add microsoft/playwright-cli@playwright-cli -g -y` | `verify-ticket` / `tester-device`: first-choice browser driver for web apps, records Playwright E2E flows. |
| `webapp-testing` | `npx skills add anthropics/skills@webapp-testing -g -y` | `verify-ticket` / `tester-device`: the other preferred web driver (Python Playwright scripts, server lifecycle helpers). |
| `find-skills` | `npx skills add vercel-labs/skills@find-skills -g -y` | Workflow step 1 (tooling): finds skills that fit the project's stack. |

## Plugins and MCP servers (optional, per stack)

| Tool | Install | Role |
|---|---|---|
| **Orca** (worktrees + orchestration) | Install the Orca app; its skills (`orca-cli`, `orchestration`) come from `npx skills add stablyai/orca -g -y` | **Required for `/deliver` parallel workers**: one worktree session per ticket, messages between orchestrator and workers, embedded browser. |
| PM tool MCP, e.g. **Atlassian** (Jira) | Connect the Atlassian connector in claude.ai, or add the Atlassian MCP server | Read tickets, transition statuses, labels, links, comments. Linear, ClickUp, Notion etc. work the same way. |
| **GitHub CLI `gh`** | <https://cli.github.com> then `gh auth login` | PRs, checks, merges; also the fallback tracker (GitHub Issues) when no PM tool is connected. |
| **Claude in Chrome** or **Playwright MCP** | Claude in Chrome extension, or `claude mcp add playwright npx @playwright/mcp@latest` | Device/browser checks on web apps; uploading screenshots to a PM tool whose API can't attach files. |
| **Context7** | Connect the Context7 connector, or add its MCP server | Current library docs for builders and reviewers (instead of relying on memory). |
| **Expo plugin** (stack example) | `claude plugin install expo@claude-plugins-official` | Framework best practices for React Native / Expo projects. |
| **Supabase agent skills** (stack example) | `npx skills add supabase/agent-skills` | Row-level security, auth and database best practices for Supabase backends. |
| **ecc plugin** (optional) | Install from its marketplace if you want its hooks | Extra hooks such as GateGuard (fact-check prompts before edits / Bash). Not required; if you use it, tune it so routine source and docs folders aren't gated (workflow step 1b, "Hook tuning"). |
