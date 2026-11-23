# Building the scenario matrix

Write the matrix before touching the app. A scenario with no expected result cannot pass.

## Scenario IDs

| Kind | ID | Question it answers |
|---|---|---|
| Positive | `AC1-P1` | Does the criterion work as written? |
| Negative | `AC1-N1` | Does it refuse what it should refuse, with a clear message? |
| Edge | `AC1-E1` | Does it hold at the boundaries: empty, longest, zero, first, last? |
| Regression | `AC1-R1` | Does the nearby behavior the diff touched still work? |
| Routed | `UI-1`, `FORM-1`, `AUTH-1`, `API-1`, `BILL-1`, `AI-1`, `PUB-1`, `PERF-1`, `STRESS-1` | Extra checks chosen from the diff |

Each row of the matrix:

```text
ID · AC · type · preconditions · steps · expected result · writes data? · role · priority
```

Mark `writes data?` honestly: it decides what `smoke-read-only` may run.

## Depth

| Depth | Runs |
|---|---|
| `smoke` | `P` scenarios for each AC, a page smoke, console and network |
| `standard` | `P`, `N`, `E` and `R` for each AC, plus the core of each routed type |
| `full` | Standard, plus every routed row below and a wider regression pass over linked features |

`--focus` adds these types at any depth. `--focus` with `--depth smoke` runs the smoke set plus
the named types.

## Routing from the diff

Read the changed files and pick every row that applies.

| The change touches | Signals in the diff | Test |
|---|---|---|
| **Any feature** | Always | Functional, negative, edge, regression |
| **UI** | Components, pages, styles | 375, 768 and 1440 px viewports; visual check; dark mode if supported; axe accessibility scan and a keyboard pass |
| **Forms** | Inputs, validation schemas, submit handlers | Validation messages, empty, very long, invalid format, double submit |
| **Permissions or tenancy** | Auth checks, roles, policies, row-level security, org IDs | Wrong role, wrong org, signed out; direct URL access to another QA tenant's record |
| **API** | Route handlers, server actions, contracts | Status codes, bad payloads, missing fields, retries and idempotency |
| **Billing or quota** | Plans, limits, checkout, webhooks | At, under and over the limit; failed payment; duplicate submit or webhook. **Test mode only** |
| **AI features** | Prompts, model calls, output parsing | Missing input, malformed model output, invented values in the result, a prompt-injection string as plain input |
| **Public endpoints** | Unauthenticated routes, forms, webhooks | Rate-limit and bot-protection behavior with the fewest requests that show it. Never hammer |
| **Performance-sensitive** | Queries, lists, heavy pages, caching | Page timing (LCP, CLS, INP where available), slow-network profile |
| **Stress** | Only with `--focus stress` | Capped load in an isolated environment. See `safety.md` |

If the routing is unclear, include the row and say why. If a routed test cannot run, it is
BLOCKED, not dropped.

## Regression picks

Choose from evidence, not at random:

1. Callers of changed functions and other pages using changed components.
2. Features in the same area's guide in `docs/features/`.
3. Past bugs in that area: tracker items labeled `qa:found`, or linked regressions.
4. The critical path of the product, such as sign in and the main action, as a short smoke.

## Worked example

Ticket `ABC-123`, AC1: "Given a signed-in owner, when they export tasks, then a CSV with all
visible tasks downloads." The diff touches an export button and an API route.

| ID | Type | Steps | Expected | Writes |
|---|---|---|---|---|
| `AC1-P1` | Positive | Open Tasks as owner, click Export | CSV downloads with every visible task | No |
| `AC1-N1` | Negative | Call export while signed out | 401, no data returned | No |
| `AC1-E1` | Edge | Export with zero tasks | Header-only CSV or a clear empty message | No |
| `AC1-E2` | Edge | Task title with commas, quotes and newlines | Columns stay intact | Yes, QA-marked |
| `AC1-R1` | Regression | Filter tasks, then export | Only filtered tasks are exported | No |
| `UI-1` | UI | Export button at 375, 768, 1440 px and in dark mode | Visible and usable | No |
| `AUTH-1` | Permissions | Sign in as a QA user in another org and request the export | 403, or that org's own data only | No |
| `API-1` | API | Send an invalid filter value | 400 with a clear error | No |

Under `smoke-read-only`, `AC1-E2` is marked BLOCKED: "needs a write".
