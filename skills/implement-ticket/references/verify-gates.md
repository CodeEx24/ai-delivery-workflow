# Verification gates

Read at Phase 7 (and skim during Phase 6). The goal is simple: **run everything the gate and
CI will run, locally, before the draft PR opens** — and when a gate genuinely cannot run on
this machine, say so out loud instead of hoping. The review loop's gate re-runs the checks
from the main branch's copy; a red gate there costs a whole round.

## 0. The project's checks script comes first

If the repo has a checks script — default `scripts/workflow/checks` (`.sh` / `.ps1`), or
whatever the workflow doc names — **run that**. It is the same command the gate runs, and it
typically covers install with a frozen lockfile, lint, typecheck, tests, build, migration and
database checks, and the ticket-record check (record exists, links block, AC, decisions).

```bash
# local mode — no --report, so it only prints the result (use whatever the repo actually has)
bash scripts/workflow/checks.sh
pwsh scripts/workflow/checks.ps1
```

The convention (workflow stage 1b): with `--report <path>` the script writes a round file
(`VERDICT: PASS|FAIL` + log tail); that is how the loop's gate runs it. A builder run is not a
gate round, so **never pass `--report`** and never write into `round-N/`. If the script fails
on the ticket-record check, fix the record (usually the links
block) rather than the script. **Never edit the checks script to make your branch pass**; if
it is genuinely wrong, say so and raise it separately.

Only if there is no checks script, fall back to §1–2.

## 1. Discover the gates (no checks script)

CI is the authority on what "green" means, so start there and work back to local commands.

```bash
# What CI runs, in order
cat .github/workflows/*.yml 2>/dev/null || cat .gitlab-ci.yml 2>/dev/null

# What the project exposes as commands
sed -n '/"scripts"/,/^  }/p' package.json   # Node
grep -E '^[a-zA-Z_-]+:' Makefile            # Make
cat justfile Taskfile.yml 2>/dev/null
sed -n '/\[tool\./,$p' pyproject.toml       # Python
```

Note the package manager from the lockfile (`package-lock.json` → npm,
`pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `bun.lockb` → bun) and use it consistently;
mixing them rewrites the lockfile and pollutes the diff.

Record the ladder you found before running anything, so later phases are not re-deriving it.

## 2. Run them in CI order

Order matters because each gate is cheaper than the next and failures cascade:

| Stage | Typical commands | Why this order |
| --- | --- | --- |
| Format | `npm run format` / `prettier --write .` / `ruff format` / `gofmt -w .` / `cargo fmt` | CI usually only *checks* formatting; write first so a whitespace diff never fails the PR |
| Lint | `npm run lint` / `ruff check` / `golangci-lint run` / `cargo clippy` | Catches the cheap class of mistake before the slow gates |
| Types / compile | `npm run typecheck` / `tsc --noEmit` / `mypy` / `go build ./...` | Fast, and a type error makes test output noise |
| Tests | `npm test` / `pytest` / `go test ./...` / `cargo test` | The substance |
| Build | `npm run build` / `cargo build --release` | Catches what unit tests cannot — bundling, server/client boundaries, dead imports |
| Extra CI jobs | migrations, contract tests, isolation suites, smoke scripts, e2e | Project-specific; see §4 |

Report the outcome as a compact list of command → pass/fail. On failure, paste the real error
text (trimmed to the useful part), not a summary of it.

## 3. Failure recipes

**Generated code out of date.** ORM clients, GraphQL types, protobufs, and OpenAPI clients are
often gitignored and must be regenerated after a schema change (`prisma generate`,
`graphql-codegen`, `buf generate`, `sqlc generate`). A wave of "cannot find name" or "module
has no attribute" errors right after touching a schema is almost always this, not your code.

**Fresh worktree or clean install.** Missing-module errors and phantom test failures usually
mean dependencies were never installed here, or a postinstall step did not run. Install with
the project's package manager, then rerun.

**Formatting fails in CI but passed locally.** Different tool version, or the formatter ran on
a subset. Run the repo's *check* command (`format:check`, `--check`, `--diff`) rather than the
write command to see exactly what CI sees.

**A test fails that you did not touch.** Confirm it fails on a clean checkout of the base
branch before debugging your change — a pre-existing failure is worth reporting, not
absorbing. `git stash push -u -m "<unique-tag>"` is risky in shared worktrees; prefer a
temporary WIP commit, or test the base branch in a scratch clone.

**Flaky or order-dependent test.** Run it alone, then the file, then the suite. If it only
fails in the suite, something leaks state — and a test you "fixed" by rerunning is not fixed.

**Build fails only in production mode.** Server/client boundary violations, missing
environment variables, and tree-shaking problems surface in `build`, never in unit tests.
Read the first error, not the last.

## 4. Gates that cannot run on this machine

Every project has a few: a database-backed test suite, a container-only integration harness,
a cloud smoke test, a paid API. Two rules make this safe:

1. **Still write the artifact.** If the repo mandates a test for this class of change, author
   it even when you cannot execute it — CI will, and the human needs to see it in the diff.
2. **Name the gap explicitly** in your Phase 7 report: which gate, why it cannot run here
   (missing Docker, no psql, no credentials), and that CI is the one who will run it. Never
   let an unrun gate read as a pass.

Before pushing, re-read the CI config once more and confirm every job either ran locally or
appears in that named-gap list.

## 5. Single-test shortcuts during Phase 6

Fast loops keep implementation honest. Typical forms:

```bash
npx vitest run path/to/file.test.ts      # one file
npx vitest run -t "name of the test"     # by test name
npx jest path/to/file -t "name"
pytest path/to/test_file.py::test_name
go test ./pkg/... -run TestName
cargo test test_name
```

## 6. Changes that carry extra obligations

Check these against the repo's own rules — several projects make them non-negotiable:

- **Migrations / schema.** Which directory or tool owns them, the naming or timestamp scheme
  (timestamp collisions across parallel branches are a classic), whether the migration is
  reversible, and whether a generated client must be refreshed afterwards.
- **Data access and authorization.** Many repos require a test proving a user cannot read
  outside their scope. Find the existing examples and add yours next to them.
- **Contracts and shared shapes.** API responses, event payloads, exported types, and column
  contracts often have a guard test that parses a source of truth. Update the source of truth,
  not just the consumer.
- **Public surface.** Exported functions, CLI flags, and config keys are someone's dependency;
  a rename is a breaking change unless proven otherwise.
- **Dates, times, and money.** If the repo documents a timezone or rounding discipline, treat
  a display shift or a rounding drift as a failing test, not a cosmetic issue.
