# Delivery Blueprint — Command Reference

One skill that turns a feature spec into a full, development-ready plan. Trigger it by asking naturally, or type the command directly in chat.

## `/delivery-blueprint` — Spec → Delivery Package

Turns a feature list or spec into a complete, dependency-ordered plan in one pass: a wave- & sprint-sequenced backlog (epics → features → stories with testable acceptance criteria), a PM-ready import CSV (Jira/Azure/Notion/ClickUp) + import guide, an artifact workbook (~18 tabs), and repo memory files (CLAUDE.md + AGENTS.md). Runs a quick intake first so nothing's assumed, sequences work so no item is scheduled before its prerequisites (guardrails ship with the feature they protect), and verifies every epic link and dependency before handing it over. Optionally pushes tickets live to your PM tool and writes a stack-specific setup prompt.

**What you get:** backlog + wave/sprint plan, PM import CSV, artifact workbook (.xlsx), and CLAUDE.md/AGENTS.md — optionally a setup prompt and a live board.

**What it needs:** your feature list or spec (paste, Markdown, PDF, or Word). Everything else it asks for — tech stack, deliverables, PM tool, depth, cadence — or answer up front to skip the questions.

**Say things like:** "Turn this spec into a wave-planned backlog and push it to Jira" · "Scaffold a delivery plan + CLAUDE.md for this new app" · "Make me tickets from these features"

## Tips

- Drop your feature plan when you start — that's the only required input; the intake covers the rest.
- Answer the intake inline to skip the questions; leave anything out and it'll ask before generating.
- Creating a brand-new PM project is admin-only via API — for a new project it delivers an importable CSV (or uses an existing project key).
- Re-runnable: regenerating from an updated spec reproduces the same structure, so plans stay consistent over time.
