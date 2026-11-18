# Definition of Done — ClassSync MVP

Do not call the application production-ready until every applicable item is evidenced against the exact release commit. `UNKNOWN`, unavailable provider state, incomplete scope, mock data, frontend guards, historical receipts and successful builds alone do not pass a criterion.

## Identity and access

- [ ] Firebase registration/sign-in/verification/recovery completion/refresh/logout work in approved configuration and are tested after reload and revocation.
- [ ] Server verifies token issuer/project/expiry/revocation, current PostgreSQL membership, tenant, role and record link on every protected request.
- [ ] Student verification matches active authoritative roster record and institutional email; missing ID and mismatch share response body/status and bounded timing behavior.
- [ ] Student ID accepts only `^[0-9]{2}-[0-9]{5}$` (form placeholder `12-12345`, examples `24-98096` and `22-98095`; prefix means enrollment year); email accepts only lowercase dot-separated local-name segments at exact `student.pnm.edu.ph` (placeholder `juan.delacruz@student.pnm.edu.ph`). Formatting alone never grants identity or authorization.
- [ ] Student, Teacher, Admin and cross-tenant negative cases pass at API and database layers; no preview role grants access.

## Data and scheduling

- [ ] Registrar-approved catalogs, records, enrollment, faculty availability, period/calendar and source provenance are complete for declared scope. The room fixture reconciles the November 2026 row data to 53 unique spaces (41 schedulable/12 excluded), with 33 lecture classrooms, 4 computer labs, 1 BSEd Science-only lab, and 3 activity-only spaces; every row maps to a stable ID and obsolete IDs are rejected. No undocumented capacity/equipment or current availability is inferred.
- [ ] PostgreSQL migrations upgrade from the supported base, enforce FK/check/unique/FORCE RLS, and are rehearsed with backup and restore.
- [ ] Generation reports `optimal`/`feasible` only with complete independently validated assignments; `unknown`, invalid, missing input or infeasible blocks draft/review/publication.
- [ ] Room/faculty/section/student overlap, availability, operating hours, room eligibility, contact minutes, recurrence/holidays, locked assignments and current revisions are tested.
- [ ] Draft mutation, review, publication and rollback are authorized, revision/hash-bound, atomic, idempotent, immutable/versioned and concurrency-safe.
- [ ] Student/Teacher views show only authorized current published data; no private draft leakage.

## Product quality and security

- [ ] Each visible control is connected or explicitly unavailable; errors, loading, empty, retry and recovery states are usable.
- [ ] WCAG 2.2 AA-oriented manual/browser checks cover keyboard, focus, labels, status announcements, contrast, 360–1440px widths, 200% zoom and reduced motion; manual screen-reader results are recorded.
- [ ] SQL uses bound parameters; imports reject extra/invalid columns and malformed rows; XSS, unsafe paths, prompt injection and authorization abuse tests pass.
- [ ] CSP/security headers, TLS, exact CORS, IP/UID rate limits, request IDs, secret handling, redacted logs, dependency scans and least-privilege roles are verified on the deployed configuration.
- [ ] Privacy notice, lawful purpose, consent if required, retention/deletion, breach response, AI/provider policy and data-subject handling are approved by authorized CdM stakeholders.

## Operations and release

- [ ] Current exact-commit CI, frontend/backend tests, typecheck/lint, builds, security scans and representative three-role E2E pass without skipped/relaxed gates.
- [ ] Hosted provider limits, pause/cold-start behavior, storage, connections, backups, restore, monitoring, alerting, recovery and cost controls are tested and accepted.
- [ ] Monthly operating cost remains at or below the hard $0 cap and actual privacy, availability, backup, restore, and reliability gates pass. If no free provider meets these gates, production launch is explicitly BLOCKED; free-tier quotas are not treated as an SLA.
- [ ] Production configuration, migration and rollback runbooks, operator access, data ownership, support and incident responsibilities are documented.
- [ ] Registrar/privacy/security owner signs off on real data and supervised pilot; deployment/release approval is separately recorded.
