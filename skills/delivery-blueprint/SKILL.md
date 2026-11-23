---
name: delivery-blueprint
description: >
  Turn a product spec or feature list into a complete, development-ready delivery
  package — a project-artifact workbook, a wave-planned backlog (epics → features →
  stories with testable acceptance criteria), a Jira/Azure/Notion/ClickUp CSV import,
  and repo memory files (CLAUDE.md + AGENTS.md) — using a fixed structure and
  Agile/AI-assisted best practices. Use whenever the user wants to plan a build,
  "turn this spec/features into tickets/backlog", "create a wave/sprint plan",
  "scaffold a new project", "generate CLAUDE.md / AGENTS.md", "set up Jira tickets",
  or produce a repeatable engineering plan. ALWAYS ask the intake questions first
  (tech stack, deliverables, PM tool, depth) unless the user already answered them.
---

# Delivery Blueprint

Produces a consistent, dependency-ordered delivery package from a spec/feature list so
the user never has to re-prompt the whole workflow. Assume the features are already
defined (in a doc, message, or attached file); this skill turns them into artifacts.

## Operating rules
- **Never skip intake.** Ask the intake questions (Step 1) before generating anything,
  unless the answers are already explicit in the conversation. Use one batched
  `AskUserQuestion` call; supply sensible defaults and mark the recommended option.
- **Dependency-first, not popularity.** Sequence work by technical prerequisite. No item
  is scheduled before the work it depends on. Ship cost/abuse/security guardrails in the
  same wave as the risky feature they protect.
- **Everything traceable.** Every story maps to an epic, a wave, a workstream, a sprint,
  a priority, points, status, and dependencies.
- **Acceptance criteria are mandatory** on every ticket: specific, testable, measurable
  (Given/When/Then or checkbox form) + the standard Done gates (tests, no regressions,
  reviewed PR, docs).
- **Documentation discipline.** Generated repos treat CLAUDE.md as durable, project-wide
  knowledge only — updated at epic completion or when a decision becomes stable/reusable,
  never per ticket. Day-to-day detail goes to `docs/tickets/<KEY>-###-<slug>.md`. Bake a
  **reuse-first** rule into CLAUDE.md/AGENTS.md (evaluate shared component / utility /
  existing pattern before creating new) to prevent duplicate implementations.
- **Verify before delivering** (Step 5). Never hand over unverified counts or broken refs.
- Use `TaskCreate`/`TaskUpdate` to track the run. Use the `xlsx`, `docx`, or `pdf` skills
  for formatted deliverables. Reuse the format templates in `references/formats.md`.

## Step 1 — Intake (ask, then proceed)
Ask these with `AskUserQuestion` (batch; skip any already answered). Offer defaults:

1. **Tech stack** — framework, language, UI kit, DB/ORM, auth, hosting, async/jobs,
   payments, key vendors. (If the user says "you pick," propose a modern default stack
   and state it explicitly.)
2. **Deliverables** (multi-select): artifact workbook (.xlsx) · Jira/CSV import ·
   push live to a PM tool · CLAUDE.md + AGENTS.md · setup prompt · architecture notes.
3. **PM tool + mode** — Jira / Azure DevOps / Notion / ClickUp / Linear; and export (CSV)
   vs. push live via connector. (Project creation is usually admin-only via API — if so,
   produce a CSV that creates the project on import, or ask for an existing project key.)
4. **Backlog depth** — Comprehensive · MVP/Phase-1 focus · Lean/high-level.
5. **Team & cadence** — team size, sprint length, target velocity (for sprint math).
6. **Conventions** — confirm branch-naming (`feat/<key>-###/title`), commit style
   (Conventional Commits), and naming standards, or accept the defaults in `references/formats.md`.

## Step 2 — Analyze the spec
- Extract features; group into capability domains → **epics**.
- Flag **gaps, ambiguities, assumptions, missing NFRs** (uptime/latency/RTO-RPO, data
  retention, limits, compliance). Record them in a "Gaps & Assumptions" list; resolve
  blocking ones with the user or state the assumption explicitly.
- Identify the **critical path** and cross-cutting concerns (multi-tenancy, security,
  cost controls, compliance).

## Step 3 — Build the plan
- Derive **epics → features → user stories** (INVEST). Each story: AC, priority (P0–P3),
  points (Fibonacci), dependencies, status, epic + feature mapping.
- Assign **waves** (sequence bands: Wave 1 = foundations/identity, then guardrails, core
  value, retention, intelligence, platform/ecosystem) and **workstreams** (parallel squad
  tracks with minimal file overlap). Derive waves from the dependency-ordered sprint plan.
- Resolve cross-wave dependency conflicts (e.g., a feature needing billing can't precede it).
- Produce the **sprint plan** using the team/velocity answers; validate that
  Σ sprint points == Σ backlog points (nothing dropped).

## Step 4 — Generate artifacts (fixed structure)
Use the exact schemas in `references/formats.md`:
- **Artifact workbook** — the standard tab set (Overview, Roadmap, Epic/Feature/Product/
  Sprint/Technical backlogs, Architecture, Data Model, API Contracts, QA, DevOps, Risk
  Register, Future, PM Import, Agile & AI Practices incl. DoR/DoD, Gaps & Assumptions).
- **PM import file** — the fixed CSV column schema (Issue ID, Type, Summary, Description
  incl. AC, Epic Name/Link, Priority, Points, Status, Labels[wave/workstream/sprint/epic/
  phase/priority], Sprint, Wave, Workstream, Blocked By). Include an import guide.
- **CLAUDE.md + AGENTS.md** — from the templates in `references/formats.md`: product line,
  locked stack, folder structure (incl. `docs/tickets/`), naming-convention table,
  branch/commit rules, a **Skills section** listing best-practice skills to consult when
  building a feature, a **Reuse-first** rule, a **Documentation & knowledge management**
  section (CLAUDE.md updated only at epic completion / stable decisions; per-ticket detail
  in `docs/tickets/<KEY>-###-<slug>.md`), and short DoR/DoD. AGENTS.md mirrors the non-negotiables
  (incl. reuse-first + "don't bloat CLAUDE.md") so all agents comply.
- **Ticket-doc scaffold** — create the `docs/tickets/` folder and a `_TEMPLATE.md` with the
  fixed sections (Overview · Implementation details · API changes · Database changes ·
  Dependencies o