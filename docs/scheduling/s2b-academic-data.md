# S2B — Persisted academic inputs

S2B adds Administrator-entered academic periods and source records to the existing
S1 solver/S2A draft workflow. No official curriculum, faculty, enrollment, capacity
or equipment data is synthesized. The original synthetic example remains a separate
development-only source. Student/Teacher schedules and draft publication are unchanged.

## Run locally

Use the existing Python 3.12 virtual environment and Node workspace. Install the
Academic service requirements from its service directory if not already installed:

```powershell
Push-Location services/academic
..\..\.venv\Scripts\python.exe -m pip install -r requirements.txt
Pop-Location
```

Run the Academic service as a fourth process alongside the S1/S2A Gateway,
Scheduling service and Vite. All three Python processes need explicit sandbox flags:

```powershell
$env:CLASSSYNC_ENV='development'
$env:ENABLE_SCHEDULING_SANDBOX='true'
.\.venv\Scripts\python.exe -m uvicorn services.academic.app.main:app --host 127.0.0.1 --port 8001
```

Gateway remains at 8000, Scheduling at 8002, and the current Vite preview at 5182.
`ACADEMIC_SERVICE_URL` defaults to `http://127.0.0.1:8001` in both Gateway and Scheduling.
`ACADEMIC_DATABASE_PATH` defaults to `var/academic.sqlite3`, rooted at the repository,
with no machine-specific path. `SCHEDULING_DATABASE_PATH` remains unchanged. Database
files, sidecars and local backups are Git-ignored.

Choose Administrator → Schedule Manager → Manage Academic Data. Create a period,
optionally including only the owner-supplied nine-program/59-space catalogs. Then
enter Subjects → Sections → Faculty → Resource Metadata → Subject Offerings →
Scheduling Constraints. Validate Readiness, generate from that saved period, review
the real solver result and explicitly Save as Draft. The generation source selector
can still open the separate S1 synthetic test scenario.

Ordinary production builds do not expose this unauthenticated development UI.
Protected production API operations require verified Administrator tokens; live
university sign-in/permissions/deployment are not claimed as complete.

## Academic records and scope

Records are scoped to the verified owner and selected academic period. This is a
small period-versioned input workspace, not an asserted master registrar database.
Different periods can have different subjects, sections, availability and constraints;
records and eligibility never silently carry over from another period.

| Record | Stored behavior |
| --- | --- |
| Programs | Stable ID, acronym/name/institute, aliases, active flag, degree/custom section naming policy and optional allowed years |
| Subjects | Stable ID, unique code, name, explicit program associations, contact minutes, exact permitted patterns, known classroom requirements |
| Sections | Stable ID, program, structured year/letter or custom label, period ownership, optional verified population |
| Faculty | Stable ID, optional unique institutional identifier, name, explicit subject eligibility, available/unavailable windows, optional daily/weekly teaching-minute limits |
| Resources | Stable ID, supplied location/type/capacity/equipment/condition, verified flags, availability/blocks, program restrictions and verification source note |
| Offerings | Subject/section references, assigned or eligible faculty, explicit room eligibility, optional contact/pattern/classroom/building restrictions |
| Constraints | Operating windows, transition buffer, explicit scope declaration, solver options, locked assignments and supplied cross-section enrollments |

IDs are independent of display labels. Subject codes and program acronyms are unique
within a period. Sections and offerings have meaningful composite uniqueness; faculty
institutional identifiers, when supplied, are unique in that period. Names alone are
not treated as a reliable person identifier. All source references use composite
scope/owner/period foreign keys, so cross-period references fail validation.

No program length or number of sections is assumed. TCP supports a custom section
label. The provided CdM catalogs contain no official subject/curriculum assignments.
The 180-minute requirement is an editable proposed default, not a verified universal
institutional rule or a credit-unit conversion. Both 180 and distinct-day 90+90
patterns work; nonstandard patterns must total the explicitly required minutes.

The 59 CdM spaces retain their supplied IDs, floors and labels, including the
unconfirmed PRRC 302 alias. PRRC 304–306 are not created. Their capacities, equipment,
operating state and suitability start unknown. Function Hall and Court are not
automatically eligible classrooms. New user-entered resources use separate
administrator-supplied provenance. Metadata assertions on a CdM resource require a
source note and preserve its supplied identity/location; they apply to the selected
period and never rewrite the canonical provisional inventory or existing drafts.

Only verified population/minimum-capacity requirements impose capacity constraints.
If none is supplied, readiness warns that capacity suitability is not asserted.
Required equipment/type/capacity cannot be satisfied by unverified metadata. Current
record provenance includes the server-side actor, timestamp and verification note;
it is not a complete historical audit trail.

## Persistence and migrations

Academic owns a separate SQLite database, following S2A's transactional local-storage
strategy. `services/academic/migrations/001_academic.sql` creates periods, typed JSON
record snapshots/checksums, uniqueness constraints and relational reference edges.
`002_faculty_identity.sql` adds institutional-identifier uniqueness without changing
record payloads. Academic database schema version is **2**. CRUD uses optimistic
record revisions; each committed change increments the period revision.

Scheduling `002_academic_scope.sql` upgrades its database to schema **2**, preserving
all prior runs/drafts, foreign keys and the immutable-draft trigger. It adds the
separate `academic-sandbox` realm. Draft snapshot schema stays version 1; existing
payloads are not rewritten. Backups were taken before the local upgrade. All six
pre-S2B draft payload checksums were verified unchanged and independently validated.

Transactions use foreign keys, bounded SQLite lock waits and rollback on failure.
Invalid references, duplicate identities and stale record revisions fail explicitly;
no optimistic success is shown. Reads verify checksums and typed snapshots. Future
database schemas are rejected instead of reset. No record/period deletion API exists;
active flags retain source identities. Source changes cannot cascade into immutable
draft snapshots stored by the Scheduling service.

Migrations run on repository access. Explicit checks from the repository root:

```powershell
.\.venv\Scripts\python.exe -c "from services.academic.app.main import repository; repository(); print('Academic migration/integrity passed')"
.\.venv\Scripts\python.exe -c "from services.scheduling.app.main import repository; repository(); print('Scheduling migration/integrity passed')"
```

SQLite remains a single-host local/presentation solution. Back up with SQLite's
backup mechanism or stop the service before copying it. Protect academic databases
with OS permissions; snapshots can contain supplied enrollment information.

## Readiness and solver input construction

The Scheduling service retrieves one transactional `AcademicSnapshot` through the
Academic API, forwarding the verified authorization header when protected. It builds
the existing `GenerationInput` from saved records only. The client sends period ID
and expected period revision for generation, never a fabricated teacher/subject
batch. A stale revision returns 409 and asks the user to recheck readiness.

Blocking issues include missing sections/offerings/teaching windows, sections with
no offerings, missing/inactive/inconsistent references, missing subject/program
associations, invalid faculty eligibility, absent availability, missing minutes or
patterns, unsatisfied room requirements, provably insufficient individual workload
or weekly time and patterns with no legal placement. Warnings distinguish unverified
population/capacity coverage, inactive records, and an undeclared complete scope.
Readiness does not claim that all interacting constraints are feasible; CP-SAT must
still establish a full timetable.

The compiler preserves exact contact requirements, valid patterns, teacher/section/
room/student exclusivity, teacher and resource availability, verified resource
requirements, building/program eligibility, locked assignments and buffers. It does
not infer availability from missing data. S1's CP-SAT model remains in place, extended
only with optional supplied faculty daily/weekly workload bounds. The independent
validator separately checks these bounds.

Optional workload fields are omitted from normalized hashing when absent, preserving
S1 hashes for legacy snapshots. New constraints participate in the hash when present.
Generation records `data_version=academic:{period-id}:revision:{revision}` and captures
the exact compiled input. An edit after snapshot capture does not mutate that run;
saved drafts retain the earlier input/assignments. Full historical academic-record
revisions are deferred to S2C; the saved solver input itself is immutable.

## API

Gateway wraps responses in the existing `{data: ...}` convention and preserves status
codes and structured errors. Shared contracts are in `classync_contracts/academic.py`;
the existing exporter generates browser types and JSON schemas from Python models.

| Method/path | Purpose |
| --- | --- |
| `GET/POST /api/v1/academic/sandbox/periods` | List/create development-entered periods |
| `GET /api/v1/academic/sandbox/periods/{id}` | Load a consistent saved period snapshot |
| `PUT /api/v1/academic/sandbox/periods/{id}/records/{kind}/{record-id}` | Create/edit a typed record with `expected_revision` |
| `GET /api/v1/scheduling/sandbox/academic/{id}/readiness` | Compile and validate saved inputs |
| `POST /api/v1/scheduling/sandbox/academic/{id}/generate` | Real CP-SAT generation with `expected_revision` |
| `POST/GET /api/v1/scheduling/sandbox/academic/drafts` | S2A save/list in the separate development-entered realm |
| `GET /api/v1/scheduling/sandbox/academic/drafts/{id}` | Reopen a saved development-entered draft |

Protected equivalents for academic CRUD/readiness/generation omit `/sandbox` and
require a verified Administrator at Gateway and each service. Protected results save
through existing `/api/v1/scheduling/drafts`, scoped to the verified creator UID.
Another Administrator cannot read that owner's period/drafts in this phase. Browser
preview roles and the general development authentication bypass grant no authority.

All sandbox services require both development environment and enabled sandbox flag.
Academic source records use owner `development-academic-sandbox`; generated runs use
Scheduling realm `academic-sandbox`. The original S1 `sandbox` realm still requires
synthetic input/resources and cannot load academic drafts. Production academic
records, development-entered records and seeded synthetic test data stay distinct.

## Files and verification

Core changes: Academic contracts/repository/service/migrations; Scheduling
`academic_input.py`, scoped APIs, migration, optional workload model/validator and
compatible hashing; Gateway routes; generated DTOs; AcademicManagementPage,
AcademicRecordEditor, AcademicGenerationPage, API/label helpers, typed routes,
existing S2A source-aware draft views and scoped CSS. No dependencies were upgraded;
Academic adds the already-used httpx test dependency.

See [S2B browser/HCI evidence](../hci/s2b-academic-inputs.md) for actual inputs,
results, screenshots and final checks. No screen-reader or physical-device study
and no complete production/authentication/deployment validation are claimed.

S2C remains deferred: authorized revisions/audit history, organization-wide sharing
policy, approved institutional source reconciliation, production identity UX and
deployment/scale hardening. No schedule editing, publication, notifications or
AI/OCR work is included.
