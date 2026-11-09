# Delivery Blueprint — Fixed Formats & Templates

The skill produces artifacts in these exact structures so output is consistent every run.

---

## 1. Artifact workbook — standard tabs

1. README / Index — how to use, legends (status, priority), conventions
2. Project Overview — summary, objectives, target users, KPIs, assumptions, constraints, risks
3. Product Roadmap — MVP/Phase 1–N, priority, dependencies, release targets
4. Epic Backlog — Epic ID, Name, Description, Business Value, Priority, Dependencies, AC, Status
5. Feature Backlog — Feature ID, Epic, Name, Description, Priority, Complexity, Dependencies, Status
6. Product Backlog (stories) — Story ID, Epic, Feature, User Story, AC, Priority, Points, Dependencies, Status
7. Sprint Backlog — Sprint #, Goal, Stories, Est. Points, Dependencies, Deliverables
8. Technical Backlog — Infra, DB, API, FE, BE, Security, DevOps, Monitoring tasks
9. Architecture & Decisions — architecture, components, stack, API/auth/z, data design, AI integration
10. Data Model — entities, relationships, tables, migrations, seed data
11. API Contracts — endpoint, method, description, request, response, auth, status
12. QA & Testing — per feature: unit/integration/E2E/regression/UAT, edge cases, error + security cases
13. DevOps & Deploy — repo, branching, CI/CD, environments, monitoring, logging, backup, DR
14. Risk Register — risk, impact, probability, mitigation, owner
15. Future Improvements — nice-to-have, scalability, performance, security, AI, mobile
16. PM Import — Initiative → Epic → Feature → Story → Task → Sub-task, importable columns
17. Agile & AI Practices — DoR, DoD, ceremonies, AI-assisted dev/test/docs/review workflows
18. Gaps & Assumptions — missing requirements, ambiguities, assumptions with impact + recommendation

Formatting: professional font, frozen header row, autofilter, zebra rows, status color-coding,
no formula errors.

## 2. Status & priority legends
- Status: Draft → Ready → In Progress → Blocked → Code Review → QA Testing → UAT → Done
- Priority: P0 critical/critical-path → P1 high → P2 medium → P3 nice-to-have
  (map to PM tool: P0=Highest, P1=High, P2=Medium, P3=Low; if no Priority field, use a label)

## 3. PM import CSV — column schema
```
Issue ID | Issue Type | Summary | Description | Epic Name | Epic Link | Priority |
Story Points | Status | Labels | Sprint | Wave | Workstream | Blocked By
```
- Issue ID = stable external key (EP-xx / US-xxx) used to resolve links on import.
- Epics carry Epic Name; stories reference it via Epic Link. Sub-tasks use Parent.
- Description embeds the user story + AC checklist + Wave/Workstream/Sprint/Epic mapping.
- Labels duplicate wave/workstream/sprint/epic/phase/priority so the plan works without custom fields.
- Blocked By lists only real, importable IDs (strip feature-only refs).
- Deliver an import guide (field mapping + steps) alongside the CSV.

## 4. Wave model (default)
- Wave 1 — Foundations & Identity (repo, data layer, tenancy, auth/roles)
- Wave 2 — Core engine + Guardrails (the risky primitive + its cost/abuse/security controls)
- Wave 3 — Core value layer (the headline features + their data)
- Wave 4 — Retain & Engage (jobs, follow-ups, notifications, compliance)
- Wave 5 — Channels & Intelligence (extra channels, analytics, QA scoring)
- Wave 6 — Platform & Ecosystem (billing, API/integrations, marketing, white-label)
Waves are sequence bands; within a wave, workstreams run in parallel. Derive from sprints.

## 5. Definition of Ready / Done (default)
- Ready: AC written & testable; prerequisites done; sized ≤ 8 pts (split if larger);
  design/API contract linked; tenant-isolation/security/compliance implications noted.
- Done: AC met & demoed; reviewed PR merged, CI green; unit+integration pass (E2E on
  critical paths); security/isolation tests pass where relevant; no new errors;
  docs/runbook updated; migrations reversible.

---

## 6. CLAUDE.md template

```markdown
# CLAUDE.md — <Product> Engineering Guide
Working memory for the <Product> codebase. Read before writing code.
> PM project: <Name> (key <KEY>). Every branch/commit/PR references <KEY>-###.

## 1. Product (one paragraph)
<what it is, who it's for, the core constraint>

## 2. Tech stack (locked — no swaps without an ADR)
<framework, UI, forms/validation, state, auth, ORM/DB, key vendors, async, observability>

## 3. Folder structure
<feature-first tree; routes thin; data access centralized/scoped; provider abstractions>
Rules: routes stay thin; all data access through the scoped data layer; server-only code
isolated; vendors hidden behind interfaces.

## 4. Coding standards & naming conventions
| Thing | Convention | Example |
| Component files | PascalCase .tsx | LeadTable.tsx |
| Hooks/utils/actions files | kebab-case | use-leads.ts, rate-limit.ts |
| Components | PascalCase | LeadTable |
| Hooks | camelCase use-prefix | useLeadScore() |
| Functions | camelCase verb-first | createLead() |
| Variables | camelCase | activeAgent |
| Booleans | is/has/should/can | isBlocked |
| Constants | UPPER_SNAKE_CASE | MAX_CALL_SECONDS |
| Types/interfaces | PascalCase, no I-prefix | Lead, AgentConfig |
| Schemas | camelCase + Schema | createLeadSchema |
| Env vars | UPPER_SNAKE_CASE | DATABASE_URL |
| DB models/fields | PascalCase / camelCase (+ tenantId) | model Lead { tenantId } |
| Routes | kebab-case | /phone-numbers |
| Tests | *.test.ts(x) | lead-score.test.ts |
General: strict types, no `any`; validate external input at the boundary; prefer server
components/actions; no secrets client-side; small single-purpose functions; enforce any
multi-tenancy/cost/security invariants on every relevant path.
Reuse-first: before creating a component/util/pattern, check whether it should be a shared
component, a utility/helper, or an existing pattern to follow — avoid duplicate solutions.

## 5. Git: branches, commits, PRs
Branch: `<type>/<key>-<ticket>/<short-kebab-title>` (feat/fix/chore/refactor/docs/test/perf/build/ci).
Commit (Conventional Commits): `feat(scope): summary (<KEY>-###)`.
Trunk-based: short branch → PR → ≥1 review + green CI → squash-merge; PR restates AC.

## 6. Best-practice skills (consult when building features)
Install: `npx skills add <org>/skills/<name>` (list each).
When developing any feature, load and follow these as the authority for language/framework
best practices. If a skill and a ticket AC conflict: AC wins for behavior, skill wins for how it's coded.

## 7. Definition of Ready / Done (short)
<mirror section 5 above>

## 8. Documentation & knowledge management
CLAUDE.md is NOT updated per ticket/feature — only for durable, project-wide knowledge:
best practices, architectural patterns/decisions, validation & sanitization standards,
coding conventions, shared workflows, reusable UI/API patterns, anti-duplication rules.
Cadence: update only when an Epic completes or a decision becomes stable/reusable.
Reuse-first: evaluate reuse before building (shared component? utility? existing pattern?
standardize it?). Per-ticket detail lives in docs/tickets/<KEY>-###.md, never in CLAUDE.md.
Ticket doc template: Overview · Implementation details · API changes · Database changes ·
Dependencies on other tickets · Known limitations · Testing notes · Follow-up tasks.

## 9. Commands
<dev/build/lint/typecheck/test/migrate>
> Note: keep CLAUDE.md canonical; mirror critical rules into AGENTS.md.
```

## 7. AGENTS.md template (mirror)

```markdown
# AGENTS.md — <Product>
Rules for all coding agents. CLAUDE.md is canonical; this mirrors the must-follow rules.

## Non-negotiables
- Follow the folder structure and naming conventions in CLAUDE.md.
- <core invariant 1, 