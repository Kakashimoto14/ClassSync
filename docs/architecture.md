# Architecture

```text
React web / future React Native
              |
              v
       API Gateway (/api/v1)
       /        |         \\
Academic   Scheduling   Notification
       \\        |         /
     local SQLite repositories
     Firebase token verification (protected API)
```

The gateway implements public HTTP conventions, Firebase token verification, request correlation, CORS and routing. Production rate-limit policy enforcement remains planned, not verified by the local P1 gate. Protected services independently enforce authorization; frontend route guards are UX only.

Academic implements programs, sections, subjects, faculty, offerings, period/calendar and resource records in local SQLite. Scheduling implements OR-Tools CP-SAT, independent validation, immutable drafts, publication versions, role projections and server-originated timetable events. Notification currently provides health endpoints; delivery orchestration remains future work. Public contracts live in `packages/api-contracts`. Local service success does not establish production hosting or institutional authorization readiness.

Scheduling constraints are implemented in Python, not React. P1 introduces a validated frontend operating mode and capability descriptions, not a new authorization system. Presentation uses a fixed versioned sample with no live requests. Sandbox requires a development server and independent backend gates. Institutional UI remains honestly unavailable until production identity/current-membership integration is complete. See [P1 execution contract](production/p1-execution-contract.md) and [reconciled production plan](production/reconciled-master-plan.md) for exact boundaries and future PostgreSQL sequencing. Firestore remains unused by current scheduling storage.
