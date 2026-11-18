# Testing strategy

Use synthetic records and owned disposable databases/emulators. Never point qualification at original SQLite files or real Registrar records. Record SHA/base commit, exact commands, versions, output, artifact paths, coverage and remaining gaps. Historical `STATUS.md` evidence is context only.

## Required layers

1. **Contracts/unit:** Pydantic bounds/`extra="forbid"`, enum/catalog ID, calendar/timezone, CSV/JSON allowlists, identity-state transitions, OTP lifecycle, input provenance and deterministic solver model construction. Validate student ID `^[0-9]{2}-[0-9]{5}$` (valid `24-98096`, `22-98095`; invalid malformed lengths/separators) and email `^[a-z]+(?:\.[a-z]+)*@student\.pnm\.edu\.ph$` (accept lowercase dotted names; reject uppercase, hyphenated local-part, wrong domain and empty segments).
2. **Repository/integration:** Alembic fresh upgrade and supported upgrade path; FK/check/unique constraints; transaction rollback; FORCE RLS for no context, each role, tenant/record isolation; CAS/revisions; pool timeout/outage recovery; backup/restore comparison.
3. **API/security:** Firebase invalid/expired/revoked/disabled/unverified token; current membership and revocation; unauthenticated, wrong-role, wrong-tenant, wrong-record, replay, stale request, malformed payload, oversized upload, SQLi/XSS strings, rate limit, CORS and safe error/request ID. For student verification, missing ID, inactive record, wrong email and malformed values must not reveal roster membership; assert identical generic response status/schema and rate-limiting behavior using synthetic records. Verify all role/tenant routes on Gateway and downstream services.
4. **Scheduling:** inventory fixture has exactly 53 unique IDs, 41 schedulable/12 excluded, category totals 33 lecture/4 computer labs/1 restricted science lab/3 activity spaces, correct PRRC/New Building/Court/Oval counts, row-to-ID mapping, and rejects stale IDs from the old catalog. Only activity-eligible schedulable rooms can be selected; excluded spaces cannot enter general scheduling; no capacity or equipment is assumed without source data. Test verified room eligibility, faculty/section/student overlap, operating windows, enrollment completeness, contact minutes, recurrence/holidays, buffers, locked assignments, incomplete input, invalid model, UNKNOWN and infeasible. Independently validate every solver output. Test revision races, concurrent save/review/publish, idempotency, rollback and projections.
5. **Frontend:** Vitest/API contracts, mocked unit tests plus actual Gateway/Auth/PG journeys. Test Student, Teacher and Administrator direct links, keyboard/focus, announcements, forms/error recovery and no private-draft leakage. Browser viewports 360/390/768/1024/1440, native 200%, reduced motion, color contrast and manual screen reader as an explicit open gate.
6. **Operational:** clean production artifact, env validation, deep-link/404 behavior, security headers, rate-limit behavior, cold start/DB resume, migration/restore, monitoring alerts, provider outage/recovery and cost-limit alarms.

## Commands

Run from feature worktree after dependencies are provisioned; use serial scheduling tests:

```powershell
npm ci
npm run typecheck --workspace=@classync/web
npm run lint --workspace=@classync/web
npm run test:web
npm run build --workspace=@classync/web
npm run build:presentation
npm run test:security
npm audit --audit-level=moderate
.venv/Scripts/python.exe -m ruff check services packages
.venv/Scripts/python.exe -m pip_audit --strict
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m pytest services/scheduling/tests -q
```

`pip-audit` invocation must match the repository’s maintained scanner workflow and include installed service/runtime dependencies; confirm the command against current CI before running. Playwright qualification scripts are under `scripts/*browser*.cjs` and `scripts/postgres_*_browser_qualification.py`; run only the current documented owned-emulator/disposable-PG wrapper, with a new output directory and preservation receipt. Confirm flags from `--help`/current script before execution. Never issue a “retry until green.”

## Current evidence available for this audit

Fresh on `7165fa130e413f8dc8893b85d30ecbe530ef8173`: six focused frontend files, **55 passed**; combined Gateway auth/onboarding and Scheduling engine, **67 passed / 1 failed**, with one Starlette TestClient deprecation warning. The failure `test_complete_multi_program_batch_and_independent_minutes_check` returns `unknown` at the unchanged 8-second limit. Frontend typecheck, lint and build passed; build reports Firebase dynamic/static import and a 692.33 kB minified chunk warning. No current full suite, live provider/browser journey, dependency scan or migration rehearsal is claimed.

## 15 November 2026 implementation evidence

After the feature-branch catalog and activity-aware room selector changes: focused frontend inventory, room discovery, dashboard regression, and Academic editor suites passed **66 tests across five files** (`npm run test:web -- src/data/cdm-room-inventory.test.ts src/pages/StudentRooms.test.tsx src/pages/RoomNavigation.test.tsx src/pages/dashboards/OperationsDashboards.test.tsx`, plus `src/pages/AcademicManagementPage.test.tsx`). Signup/claim form placeholder tests passed **8 across two files**. Focused backend catalog/readiness/API checks passed **14 tests**; TypeScript, full web ESLint, and targeted Ruff checks passed. The production build passed with a Firebase dynamic/static import warning and a 701.26 kB minified chunk warning. One backend Starlette TestClient deprecation warning remains. These tests verify source designation, selection filtering, and displayed hints, not the correctness of Facilities data, ID/email format enforcement, or roster verification. Full suites, browser rendering, live services and provider behavior remain unverified; the prior solver UNKNOWN remains open.

**15 November 2026 Admin input acceptance:** after adding the one-period setup overview, supplied-catalog program selection and duplicate guard, blank-by-default day-checkbox windows, 30-minute time menus and pattern-bound fixed-assignment end choices, `npm run test:web -- src/pages/AcademicManagementPage.test.tsx src/pages/LockedAssignmentsEditor.test.tsx` passed **17 tests across two files**. Web typecheck, ESLint, production build and targeted Prettier/diff checks passed. Build warnings remain: mixed Firebase imports and a 710.86 kB minified chunk. These are frontend component tests over synthetic fixtures; no browser-rendered/responsive/accessibility journey, institutional catalog validation, backend persistence or live provider acceptance was performed.
