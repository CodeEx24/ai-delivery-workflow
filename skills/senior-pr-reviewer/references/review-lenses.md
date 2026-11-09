# Review lenses

Read only the lenses Phase 3 selected. Each item is a question to answer against the actual code,
not a box to tick. A "no" is only a finding once Phase 5 can name the concrete failure.

---

## Correctness (always on)

- **Boundaries:** empty collection, single element, zero, negative, max, null/undefined, missing
  optional field, duplicate input, unicode and very long strings.
- **Off-by-one and inclusivity:** ranges, pagination windows, slice bounds, `<` vs `<=`, cursor
  overlap or gaps at page edges.
- **Control flow:** early returns that skip cleanup, a `switch` with a new case unhandled, a
  condition inverted under negation, short-circuit that hides a needed side effect.
- **Error handling:** a swallowed `catch`, an error path that returns a success shape, a failure
  that renders as legitimate emptiness (a fake "no data" instead of an error state), a retry with
  no cap, a promise not awaited.
- **Async and concurrency:** interleaved requests, a race between read-then-write, a shared mutable
  module-level value, unstable ordering assumed to be stable, a missing transaction around a
  multi-step write, an idempotency gap on a retried operation.
- **Type-level lies:** a cast or `as any`/`unwrap` that hides a real nullable, an optional field
  read as required, a string union widened to `string`, a DTO mapped field-by-field where a rename
  silently produced `undefined`.
- **Serialization at the edges:** numerics arriving as strings from a driver or REST layer,
  `bigint`/`decimal` precision, a JSON round-trip losing a `Date`, a boolean arriving as `"false"`
  (which is truthy).
- **Regression surface:** every caller of a changed signature, every consumer of a changed shape,
  anything else that shares the code path.

## Security & authorization

- **The real enforcement boundary:** is the rule enforced where it cannot be bypassed (database
  policy, server handler, middleware) rather than only in the UI or a client-side check? A hidden
  button is not access control.
- **Every new read/write path** gets asked: who can reach this, and what stops the user in the
  next tenant/role/scope from reaching it? Is the caller's identity taken from the verified
  session, or from client-supplied input?
- **IDOR:** an id from the request used in a query without an ownership/scope predicate.
- **Privilege paths:** a service-role, admin, or RLS-bypassing client used outside its narrow
  purpose; a permission check that passes on `undefined`; a default that grants rather than denies.
- **Input validation** at every boundary (HTTP, form, webhook, job payload, env), with a schema
  rather than hand-rolled checks. Unvalidated input reaching a query, a shell, a path, a template,
  or a redirect.
- **Injection:** raw string interpolation into SQL, a template, a command, HTML
  (`dangerouslySetInnerHTML`), or a regex built from user input.
- **Secrets:** a key, token, password, connection string, or internal hostname in the diff; a
  secret exposed to the client bundle by a public-prefixed env var; credentials in a log line or
  error message.
- **Data exposure:** PII in a response, a log, an error, or an export that the caller's permissions
  do not cover; a `select *` that now carries a sensitive column; masking dropped by a refactor.
- **Auth mechanics:** session fixation, missing re-verification on a sensitive action, a token with
  no expiry, `redirect` to a user-supplied URL, CSRF on a state-changing non-idempotent route.
- **Dependencies:** a new package — is it maintained, correctly scoped (dev vs prod), and does it
  pull a known-vulnerable transitive tree? Does it run install scripts?

## Architecture

- **Boundaries:** does the change respect the layering the repo has (server-only code not imported
  by a client module, a domain layer not reaching into transport, a pure module staying free of
  framework imports)? A leaf module that must stay dependency-free gaining an import is a real
  defect, not a nit.
- **Duplication vs reuse:** is this a third copy of logic that already exists twice? Conversely, is
  a premature abstraction being introduced for a single caller?
- **Single source of truth:** two places now encode the same rule (a permission list, a column
  contract, a status enum, a default) and can drift. Name the drift scenario.
- **Coupling and blast radius:** what else must change when this changes next? Is a shared type or
  contract being widened for one caller's convenience?
- **Contract changes:** an API response, event payload, database column, or exported signature that
  other consumers (other services, n8n, mobile, a cached client) depend on — is the change additive
  and backward compatible, and is versioning or a deprecation window needed?
- **Data model fit:** is the shape being forced into the wrong table/JSON blob because the right
  change was harder? Is state duplicated where it could be derived?
- **Performance shape** (not micro-optimization): N+1 queries in a loop, a full scan where an index
  exists, unbounded result sets with no limit, work in application code that belongs in one SQL
  round-trip, a cache key that cannot invalidate, a payload that grows with the dataset.
- **Failure design:** does this fail closed (deny, error state) or open (allow, fake success)? What
  happens when the dependency is down or slow? Is there a timeout?

## Tests & QA (always on)

- **Coverage of the change, not the file:** each new branch, error path, and boundary the diff
  introduced — is any of it exercised? Which specific behavior would a revert of this diff leave a
  test passing on?
- **The mandated test for this class of change:** if the repo requires a particular test for a
  category (an isolation/policy test for data access, a migration test, a contract test, a snapshot),
  its absence is a Blocker, not a suggestion.
- **Test quality:** does it assert the behavior or just that nothing threw? Is it asserting on a
  mock's call rather than a real outcome? Would it still pass if the implementation were wrong?
  Are error cases asserted with the specific error?
- **Test level:** is this a slow end-to-end test doing what a pure unit test could prove, or a
  mocked unit test claiming to prove an integration?
- **Fragility:** a dependence on wall-clock now, on timezone, on ordering, on network, on a shared
  mutable fixture, on a sleep. Flaky tests get merged and then ignored.
- **Fixtures:** does the test data resemble production (unicode, nulls, large values, the weird
  legacy row), or only the happy shape?
- **Manual check:** what is the one thing a human should click to confirm this? Name it in the
  review.

## Data & migrations

- **Reversibility:** can this migration be rolled back, and is a down path or a recovery plan
  needed? Is it destructive (dropping a column, rewriting rows) and is the data recoverable?
- **Order of deploy:** does the code depend on the migration, or the migration on the code? Under a
  rolling deploy, does the old code survive the new schema for the overlap window? An
  expand/contract split may be required.
- **Locks and scale:** will this rewrite a large table, take an exclusive lock, or add an index
  without the concurrent option? What is the row count in production?
- **Constraints and defaults:** a `NOT NULL` added without a default or a backfill; a unique
  constraint added over data that may already violate it; a foreign key with the wrong cascade
  behavior; a check constraint that existing rows fail.
- **Backfills:** batched or one giant statement? Idempotent if it dies halfway? Does it respect the
  same rules the application enforces?
- **Timestamps, ordering, and collisions:** migration filenames ordered correctly against what has
  already been applied, especially with parallel branches.
- **Drift:** does the live database actually match what is merged? Verify rather than assume — a
  merged-but-unapplied migration fails pages closed on a column mismatch.
- **Policies travel with the table:** a new table or view created without the access policies the
  repo requires is a Blocker.

## Frontend

- **Client/server split:** a server-only module (secrets, admin clients, database access) imported
  into a client component; a hook or browser API used in a server component; `"use client"` added
  to a boundary that drags a subtree into the bundle.
- **State correctness:** stale closure over changing props, an effect with a wrong or missing
  dependency, an effect that should be derived state, a fetch with no cancellation on unmount, a
  key that is an array index over a reorderable list.
- **Loading, empty, and error states** all present and distinguishable from each other — an error
  that renders as "no results" is a correctness bug.
- **Accessibility:** a clickable non-button without a role and keyboard handler, an input with no
  label, an image with no alt, a modal with no focus trap or escape, focus lost after a mutation,
  color as the only signal, a contrast regression.
- **Forms:** validation on the server as well as the client, submit disabled during submission
  (double-submit), server and permission errors actually surfaced to the user.
- **Perf:** a large dependency pulled in for one helper, an unmemoized expensive render in a hot
  list, an unbounded list rendered without virtualization, an image with no dimensions causing
  layout shift, a waterfall of sequential awaits that could be parallel.
- **Consistency:** does it use the repo's component library and design tokens, or hand-roll a
  one-off variant of something that exists?

## Numeric & temporal correctness

- **Money:** integer minor units or decimal — never float arithmetic; consistent rounding with a
  stated direction; currency carried alongside the amount; no accumulation of rounding error
  across a sum.
- **Units:** seconds vs milliseconds, bytes vs kilobytes, percent vs fraction — especially across a
  boundary where the name does not say which.
- **Timezones:** storage in UTC and display in the business timezone, converted exactly once and in
  one place. Any hour arithmetic added to "fix" a display is a symptom of a bug elsewhere.
- **Calendar dates vs instants:** a date-only column is a literal calendar date and must not be run
  through a timezone conversion (the day shifts); an instant must not be truncated with a string
  slice to get its business day.
- **Day boundaries:** a "today"/MTD window must be built from the business timezone's midnight
  converted to an instant, never a date string concatenated with `T00:00:00`. Bucketing belongs in
  one place — ideally the query — not re-derived per call site.
- **Aggregation:** the denominator excludes what it should (cancelled, test, deleted rows); a
  division with a possible zero denominator; a percentage of an empty set; double counting from a
  join fan-out; an average of averages.
- **DST and leap cases:** a duration spanning a DST change, a 23- or 25-hour day, Feb 29, a week
  boundary that differs by locale.

## Ops & rollout

- **Config:** a new env var documented in the example file, validated at startup, and present in
  every environment that needs it — otherwise the deploy fails at request time instead of boot.
- **Feature flags:** default off, safe to flip either way, and the removal path noted.
- **Observability:** can you tell from logs or metrics that this broke in production? Does the new
  failure path log enough context — without logging secrets or PII?
- **Blast radius of the deploy:** does anything here require a coordinated release with another
  service, a job, an ingestion pipeline, or a scheduled task?
- **Resource limits:** a new external call without a timeout or retry cap, a job with no
  concurrency bound, an endpoint with no pagination or rate limit.
- **Docs and runbooks:** does this change make an existing README, runbook, or doc page untrue? A
  doc that now lies is a Minor finding, not a nit.
