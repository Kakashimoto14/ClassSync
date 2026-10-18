# S2A persistent scheduling drafts

S2B subsequently adds an isolated academic-input draft scope and migrates the
scheduling database to version 2 without changing existing snapshot payloads.
The version-1 description below records the S2A baseline; see
[S2B migration and source details](s2b-academic-data.md) for the current extension.

S2A extends the local S1 engine with durable, immutable, unpublished drafts.
The existing OR-Tools constraints, provisional CdM catalog, and Student/Teacher
representative schedules are preserved. No publication or notification is added.

## Architecture and storage

The repository had Firebase token bootstrap and deny-by-default Firestore rules,
but no implemented academic/scheduling persistence. The Scheduling service now owns
a standard-library SQLite repository at `SCHEDULING_DATABASE_PATH`, defaulting to
`var/scheduling.sqlite3` relative to the repository root. Absolute paths can also be
configured through the environment; there are no machine-specific paths in code.
The database and SQLite sidecars are ignored by Git. No seeded database is shipped.

`services/scheduling/migrations/001_drafts.sql` creates `solver_runs` and
`scheduling_drafts`, with primary/foreign keys, source-scope checks, unique run IDs,
per-owner idempotency keys, JSON integrity checks and an update-prevention trigger.
Each API repository initialization applies missing migrations inside a write
transaction and checks the schema version, database integrity and foreign keys.
`PRAGMA user_version=1` records the migration. Future database versions are rejected
explicitly rather than reset or guessed. The migration is idempotent.

Successful generation stores a server-held input/result snapshot before the API
confirms the run. The public generation response remains an unsaved candidate.
Saving accepts only run ID, expected input hash, title and idempotency key. It does
not accept assignments, validation counts or a client-reported optimality claim.
The repository reloads the owned run, checks its checksum and typed snapshot,
reruns the independent validator, checks exact complete coverage and all hard
constraints, and writes one complete draft transactionally. Infeasible, invalid,
unknown and incomplete runs cannot become validated drafts.

The draft stores a schema-v1 structured input snapshot, the exact original
generation result (including assignments, minute coverage, options/weights, solver
version/status/objective/bound), independent validation, title, UTC timestamp,
creator, source classification and stable UUID. SHA-256 checksums detect accidental
snapshot corruption; they are not a defense against an attacker with database write
access. Original `generation_result.persisted=false` describes the candidate at
generation time; the enclosing saved draft is the persisted record.

Reopening reads the saved snapshot and independently validates it; it does **not**
rerun CP-SAT. Saved drafts do not expire. Unsaved server runs can be saved within
24 hours; expired candidates return 410. There is no automatic deletion of saved
drafts. Storage retention and cleanup of expired unsaved runs remain operational
follow-up work.

`BEGIN IMMEDIATE` serializes writes with a five-second busy timeout. Exceptions roll
back the transaction. Concurrent identical saves return the same draft; a unique
run constraint prevents duplication even with another key. A reused key/run with
different title or hash returns 409. New generation produces a new run and draft,
never overwriting the earlier timetable. Titles need not be unique; UUIDs identify
records. Draft list pagination is 25 by default, maximum 100.

## API and authorization

Gateway and Scheduling service expose:

| Endpoint | Successful response |
| --- | --- |
| `POST /api/v1/scheduling/sandbox/drafts` | 201 for a new draft, 200 for an identical retry |
| `GET /api/v1/scheduling/sandbox/drafts?limit=25&offset=0` | Paged summaries and `has_more` |
| `GET /api/v1/scheduling/sandbox/drafts/{id}` | Complete saved draft, input, original result and validation |

The same endpoints without `/sandbox` require a verified Firebase Administrator
token at **both** services. Their scope is the verified creator UID; another
Administrator cannot list/load that creator's drafts in S2A. Tokens are revocation
checked. No client role, preview selection, UID or source-scope argument grants
access. The general development authentication bypass does not authorize drafts.

Sandbox operations require both `CLASSSYNC_ENV=development` and
`ENABLE_SCHEDULING_SANDBOX=true` on each service. The explicit creator is
`development-sandbox`; synthetic records are shared within this one local sandbox,
not represented as personal authenticated accounts. They remain isolated from the
protected Administrator scope. The generation path accepts only synthetic inputs
and synthetic rooms. These flags do not grant access to institutional records.

Gateway responses use `{data: ...}` or structured `{error: {code, message,
requestId}}`, preserving 201/200 and service errors. Errors include 401/403 for
authorization, 404 for unavailable scoped IDs, 409 for conflicting versions/keys or
corrupted/incompatible snapshots, 410 for expired runs, 422 for invalid submissions,
and 503 for database failures. Publication remains unimplemented (404 in sandbox).

## Run and verify

Use the [S1 three-process setup](s1-engine.md#run-locally). The new environment
variable is documented in the root `.env.example`; its default needs no setup.
Choose Administrator → Schedule Manager → Generate Weekly Schedule → load the
synthetic example → Generate → inspect validation → Save as Draft. Open Saved Drafts,
select Open Draft, then refresh or restart the Python services and reopen its URL.
Changing inputs and regenerating creates a separate candidate.

To apply/check migrations explicitly from the root:

```powershell
.\.venv\Scripts\python.exe -c "from services.scheduling.app.main import repository; repository(); print('Scheduling database migration/integrity checks passed')"
```

Migrations also run on repository access. Tests use a temporary database per test;
they never write into the presentation database.

## Files changed for S2A

- `services/scheduling/app/draft_repository.py`, `migrations/001_drafts.sql`, and
  Scheduling `main.py`: persistence, authoritative save validation and APIs.
- Gateway `main.py`: scoped draft routes, safe errors and response statuses.
- Python scheduling contracts, generated TypeScript/JSON schema, and contract
  exporter: typed save/list/detail records.
- `SchedulingDraftPages.tsx`, `SchedulingTimetable.tsx`, `WeeklySchedulingPage.tsx`,
  `scheduling-api.ts`, `scheduling-labels.ts`, `ProductScreenPage.tsx`, scoped CSS and
  route registry: real Save/list/detail workflow and shared timetable rendering.
- Route ownership handles the new parameterized draft path, keeping Saved Drafts
  active on desktop and Schedule active on mobile. P0 session storage is unchanged.
- Repository/API/UI/navigation tests, `.gitignore`, `.env.example`, and documentation.

## Verification and deployment limits

See [the S2A workflow evidence](../hci/s2a-scheduling-workflow.md) for actual command
results, browser scenarios and screenshot locations. Protected authorized requests
are covered using mocked verified Firebase claims; no live university identity or
production deployment is claimed. The Python suite retains an upstream
TestClient/httpx deprecation warning.

SQLite is a local/presentation database, not distributed production persistence.
Use durable local storage with restricted OS permissions; the database can contain
administrator-supplied academic/enrollment snapshots in protected use. Never commit
it or place it in a public static directory. Back up using SQLite's backup mechanism
or stop the service before copying the complete database; verify restores. Do not
run this demonstration on an ephemeral or shared network filesystem and assume
durability or multi-host coordination. Sandbox servers should remain loopback-bound.

Reads currently validate each returned snapshot, and initialization checks database
integrity; this favors defensive local behavior over large-list throughput. Large
institutional datasets and multi-process/multi-host loads need profiling. There is
no encryption-at-rest configuration, retention UI, deletion/edit/revision endpoint,
publication, activation or audit history in S2A.

S2B should define approved immutable revision/optimistic-concurrency and audit
requirements before adding authorized editing. A PostgreSQL migration can preserve
UUIDs, owner/scope boundaries, schema-versioned JSONB snapshots and unique
idempotency/run constraints, using explicit database migrations and row locking.
Back up and verify every snapshot/count during import; do not silently reinterpret
S2A data or relax independent validation. Publication needs a separate approval and
distribution design.
