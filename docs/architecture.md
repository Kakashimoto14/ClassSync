# Architecture

**10 November 2026 decision:** [the operational authority contract](production/firestore-authority.md)
supersedes older statements that Firestore is optional. Firebase Auth owns identity, Firestore
Native mode is required for operational access and onboarding, and PostgreSQL retains canonical
academic records and publication. This is the target; the current release checkpoint still
authorizes from PostgreSQL. No hosted or production cutover has been approved.

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
has separate capability and backend gates. The current connected local app uses synthetic
accounts and records. The isolated Firestore qualification composes real account endpoints
with the new store and read-only schedule access; the normal runtime remains on its
existing SQL authorization path until the complete authority switch is qualified.
