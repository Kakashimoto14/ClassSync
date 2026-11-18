# Architecture

**15 November 2026 decision:** PostgreSQL is the authoritative relational store for identity
membership, academic records, schedules, drafts and publication. Firebase Authentication
proves identity; the backend checks current PostgreSQL membership and role/record grants.
Firestore is optional and must not become a second writable authority unless a verified
coursework rubric or later owner decision explicitly requires it. This supersedes the 10
November Firestore authority proposal in [the historical contract](production/firestore-authority.md).
The current project is not production-qualified; no hosted cutover is approved.

```text
Current connected runtime

React web -> Gateway (/api/v1) -> Academic and Scheduling
                 |                     |
         Firebase identity     Independent token and role checks
                 |                     |
         PostgreSQL membership, academic data and publication (FORCE RLS)
```

The gateway implements public HTTP conventions, Firebase token verification, request correlation, CORS and routing. Production rate-limit policy enforcement remains planned, not verified by the local P1 gate. Protected services independently enforce authorization; frontend route guards are UX only.

Academic implements period-scoped curricula, sections, offerings, enrollments, faculty,
calendar and resources. The connected providers use PostgreSQL; SQLite remains a separate
legacy local sandbox. Scheduling uses CP-SAT and independent validation, with persisted
drafts, immutable publication versions and role projections. Public contracts are in
`packages/api-contracts`. The notification service is not an established delivery path.

Presentation uses a fixed versioned sample with no live requests. The development sandbox
has separate capability and backend gates. Local connected acceptance uses synthetic
accounts and records. Historical Firestore bridge qualification remains historical evidence;
it does not change the selected PostgreSQL authority or justify a dual-writer design. Live
provider behavior, real institutional data and production recovery remain unverified.
