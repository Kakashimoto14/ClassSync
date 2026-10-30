# PostgreSQL publication/restriction conflict acceptance

29 October 2026. This is a separate guarded qualification after the bounded
publication repository qualification. It exercises two distinct race orders that
the repository qualification's non-overlapping writer test does not cover.

## Scope and fixture

- Run only through `scripts/postgres_publication_conflict_qualification.py`, which
  uses the existing marked fresh-cluster guard, least-privilege migration/runtime
  setup, and generated 0008 migration. The runner must stop its own cluster.
- Create two separately owned academic periods from plainly synthetic records.
  Each has one 30-minute offering, one eligible teacher, one synthetic eligible
  room, and a Monday 08:00–08:30 availability window. Save drafts only from the
  actual CP-SAT solver and independently validate them; no solver, repository
  validation, expansion, or database operation may be mocked.
- Publish each saved draft once for Monday 5 October 2026 only. Verify its next
  effective revision can be expanded for both 5 and 12 October; the competing
  room restriction is exactly 12 October 08:00–09:00 Asia/Manila.
- Two scopes run independently. The only test seam is a delegate-then-pause wrapper
  around the real publication `review_scope` or restriction `expanded` call after
  it returns. Observe the other PostgreSQL transaction in `pg_stat_activity` waiting
  on a lock before releasing the first transaction.

## Acceptance cases

1. **Publication wins:** hold publication after it has really reviewed the candidate
   for 5 and 12 October. Start the overlapping restriction writer and observe its
   PostgreSQL lock wait. Release publication. It must commit exactly revision 2;
   the restriction must then fail with `409 restriction_publication_conflict`.
   Across all six scheduling tables, only the immutable version append and the
   matching head advance are allowed. There must be no restriction, audit row, or
   losing idempotency key.
2. **Restriction wins:** hold the restriction after it has really expanded existing
   published occupancy. Start the candidate publication and observe its PostgreSQL
   lock wait. Release the restriction. It must commit restriction revision 1 with
   exactly one initial audit row; publication must then fail with
   `422 room_restricted`. Across all six scheduling tables, only the restriction
   and its audit row are allowed. There must be no published version, head change,
   or losing idempotency key.
3. Before/after table snapshots must show every pre-existing row byte/value stable,
   the exact expected winner rows, and no partial loser writes. Errors, missing lock
   observations, solver infeasibility, or unexpected additional writes fail the run.
4. Portable acceptance tests exercise both exact-state validators and prove they
   reject extra rows, wrong winner data, missing audit, head changes, or loser writes.

## Evidence and limits

Portable tests can establish that the state assertions reject incorrect evidence;
they do not prove transaction ordering, PostgreSQL locks, CP-SAT results, or adapter
behavior. Actual PostgreSQL and CP-SAT execution, stopped-cluster fingerprints,
original-database preservation hashes, full backend regression, and independent
review are recorded only after the parent run. This qualifier alone cannot establish
full P3b, HTTP/provider adoption, approval, outbox delivery, institutional readiness,
or production acceptance.
