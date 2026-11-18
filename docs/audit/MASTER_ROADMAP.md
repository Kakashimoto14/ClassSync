# ClassSync master implementation roadmap

This is the execution source of truth for the audit findings in `docs/audit/`. It does not authorize deployment, real-data import, cloud resource creation, provider spending, Git publication or production cutover. PostgreSQL is the sole target authority for identity membership, academic data, schedules and publication; Firebase Auth proves identity only. Firestore is optional unless an approved rubric later establishes a requirement.

## Phase 0 — Establish safe candidate and requirements

### 0.1 Reconcile authority documents

- **Problem / impact:** `docs/architecture.md` and `docs/production/firestore-authority.md` conflict with `AGENTS.md` and owner-selected PostgreSQL authority, creating risk of dual authority.
- **Outcome / likely files:** align `docs/architecture.md`, `docs/production/firestore-authority.md`, `docs/autonomy/TRACEABILITY.md`, `README.md`; describe Firestore as optional and non-authoritative.
- **Depends / priority / complexity:** none; CRITICAL; SMALL.
- **Acceptance / tests:** all architecture/security/approval docs consistently name PostgreSQL authority; search and review every auth adapter for a second writer; doc-contract test if existing tooling supports it.

### 0.2 Requalify exact current candidate

- **Problem / impact:** historical receipts can be mistaken for current proof; current focused checks show a solver failure.
- **Outcome / likely files:** audit/evidence docs only initially; use current `git status`, commit SHA and test wrappers.
- **Depends / priority / complexity:** 0.1; CRITICAL; SMALL.
- **Acceptance / tests:** current commit and clean/dirty state recorded; controlled auth, scheduling, full regression, typecheck/lint/build and security results captured; original DB checksums preserved; no broad tests touching originals.

### 0.3 Define accepted institution scope and provenance

- **Problem / impact:** curricula, cohort, enrollment, staff, calendar and room facts are not fully Registrar/facilities verified; solver guarantees only supplied scope. The November 2026 room DOCX has 53 physical rows, but its summary conflicts with row counts (37/16 vs 41/12).
- **Outcome / likely files:** requirements/evidence in `docs/academic/`, `docs/audit/ROOM_INVENTORY_UPDATE.md`, `packages/api-contracts/classync_contracts/academic.py`, `packages/api-contracts/classync_contracts/catalogs/cdm-spaces.json`, `apps/web/src/data/cdm-room-inventory.ts`, Academic readiness/catalog contracts. Preserve each room's row designation; mark 12 non-schedulable and restrict the 8 specialized/activity spaces (4 computer labs, 1 BSEd Science lab, Function Hall, Court, Oval) to their stated activity. No capacities/equipment/availability inferred.
- **Depends / priority / complexity:** authorized Registrar/facilities source and DPO review; CRITICAL; LARGE.
- **Acceptance / tests:** source/version/owner/approval for each required dataset; completeness gates block readiness when missing; synthetic fixtures clearly segregated. Inventory fixture proves 53 distinct stable IDs, 41 schedulable/12 excluded, PRRC 27/18/9, New Building 24/21/3, Court/Oval 2/2/0, category counts 33 lecture/4 computer labs/1 restricted science lab/3 activity spaces, exact row-to-ID mapping and rejection of stale catalog IDs. “Schedulable” means activity eligibility, never current availability.

## Phase 1 — Correctness, data and scheduling foundation

### 1.1 Diagnose and close solver UNKNOWN regression

- **Problem / impact:** existing synthetic multi-program case can return UNKNOWN within its existing 8-second guard.
- **Outcome / likely files:** `services/scheduling/app/engine.py`, `constraint_model.py`, `objectives.py`, `readiness.py`, `validation.py`, `services/scheduling/tests/test_engine.py`.
- **Depends / priority / complexity:** 0.2; CRITICAL; LARGE.
- **Acceptance / tests:** capture deterministic input hash/model/solver status and profile; pass existing regression on unchanged constraints/time policy or document actionable resource gate; no UNKNOWN can save/review/publish; test repeated serial and concurrent service limits.

### 1.2 Complete institutional input/readiness provenance

- **Problem / impact:** provisional room data and incomplete roster/calendar/availability can create false-feasible schedules.
- **Outcome / likely files:** academic contracts/repository/readiness; `packages/api-contracts/classync_contracts/catalogs/cdm-spaces.json`; `apps/web/src/data/cdm-room-inventory.ts`; import/preview pages.
- **Depends / priority / complexity:** 0.3; CRITICAL; VERY LARGE.
- **Acceptance / tests:** allowlist CSV/JSON importer previews row errors and provenance; duplicate/reference/term/enrollment completeness cases; only verified room eligibility is schedulable; incomplete scope returns blocked readiness.
- **Progress (15 November 2026):** room catalog portion implemented and focused locally verified: 53 row-mapped IDs, 41/12 source designations, activity/program-aware UI choices, backend readiness requiring operational/type verification, and generated Python/TypeScript contracts. Remaining: resolve DOCX aggregate discrepancy, review exact source mapping with Facilities, verify all institutional inputs, and test importer/complete readiness and solver lifecycle. This task remains PARTIAL.

### 1.3 Selection-first academic and schedule forms

- **Problem / impact:** free-text IDs/names permit invalid relationships and increase operator error.
- **Outcome / likely files:** `apps/web/src/pages/AcademicManagementPage.tsx`, `AcademicRecordEditor.tsx`, `AcademicCalendarEditor.tsx`, `AdminSchedulingHome.tsx`, `SchedulingDraftPages.tsx`, shared API contracts and catalog types.
- **Depends / priority / complexity:** 1.2; HIGH; LARGE.
- **Acceptance / tests:** Programs/year/section/subjects/offerings/rooms/days/time patterns use searchable canonical selectors and structured checklists; free text retained only for approved labels/notes; keyboard and validation tests reject stale/unknown IDs.
- **Progress (15 November 2026):** the `/admin/academic` overview presents the period calendar and all seven academic data areas together, with in-page jumps, saved-record summaries, inline record create/edit, and full category-list links. New program records select from the shared supplied catalog without duplicate period entries; creation is disabled when all catalog rows are already present. The catalog remains unverified by the Registrar. Degree section year and letter selectors use fixed menus; offering room choices filter by catalog schedulability, activity and program. Faculty, room, and operating-hour windows use day checkboxes and blank 30-minute interval menus; fixed-assignment end-time options follow the chosen offering's durations. Fresh Admin tests (17 across two files), web typecheck, ESLint and production build pass. The task remains PARTIAL: browser-rendered responsive/accessibility acceptance was unavailable; curriculum/source verification and backend-contract gates remain required.
- **Progress (15 November 2026, Admin task-flow follow-up):** no-period routes now present the setup work map before period selection; synthetic scenario import is demoted to Development Tools; category links are consolidated under Academic Setup while retaining search/direct routes. The generator is labeled Schedule Generation because it uses CP-SAT and the conflict center identifies deterministic independent validation; both empty states provide next actions. Source-only route inventory is documented in `docs/hci/admin-workspace-audit.md`. Focused verification: Academic Setup, Conflict Center and sidebar acceptance. Remains PARTIAL pending browser screenshots at required widths, keyboard/zoom/assistive-technology acceptance, accurate institutional sources and end-to-end API/provider workflows.

### 1.4 Secure contract validation (not “injection-proof” claims)

- **Problem / impact:** strict shape validation alone does not prevent SQLi/XSS/SSTI/prompt injection.
- **Outcome / likely files:** `packages/api-contracts/classync_contracts/{academic,scheduling,identity}.py`, request schemas, `services/*` repositories/routes, import parsers.
- **Depends / priority / complexity:** 1.2; CRITICAL; LARGE.
- **Acceptance / tests:** `extra="forbid"` on mutation models; enums/UUID/catalog IDs where domain values are truly closed; bounded strings where legitimate; SQL bound parameters, output encoding and authorization; adversarial strings cause 422 or safe rejection before side effects; test query counts/database unchanged.

## Phase 2 — Authentication, roster verification and account security

### 2.1 Complete Firebase lifecycle and PostgreSQL authorization acceptance

- **Problem / impact:** actual project, recovery completion, persistence and provider behavior are not proven.
- **Outcome / likely files:** `apps/web/src/auth/*`, `AuthPage.tsx`, `services/gateway/app/{main,authorization,onboarding}.py`, identity contracts/migrations.
- **Depends / priority / complexity:** 0.1; CRITICAL; LARGE.
- **Acceptance / tests:** Auth Emulator + disposable PostgreSQL for email signup, Google only if institution enables it, verification, refresh, logout, reset completion, revoked/disabled token, membership changes and 401/403/503. No preview identity grants access.

### 2.2 Student ID and registered-email verification

- **Problem / impact:** account claim review exists but proposed strict roster matching and uniform anti-enumeration contract are not implemented as specified.
- **Outcome / likely files:** new student roster contract/repository/API under `services/gateway/app/` and Academic repository; `apps/web/src/pages/AuthPage.tsx`; migration after current 0016 (next revision is 0017, not 0012).
- **Depends / priority / complexity:** 0.3, 2.1; CRITICAL; LARGE.
- **Acceptance / tests:** browser and Pydantic pattern `^[0-9]{2}-[0-9]{5}$` with placeholder `12-12345` and examples `24-98096` / `22-98095` (prefix is enrollment year); email pattern `^[a-z]+(?:\.[a-z]+)*@student\.pnm\.edu\.ph$` with placeholder `juan.delacruz@student.pnm.edu.ph`. Reject uppercase, hyphenated local parts, wrong domain and malformed IDs. Verify active roster ID + exact normalized registered email after Firebase token/revocation verification; submitted email, verified token email and Registrar email must match; formatting alone never authorizes. Missing ID/inactive/mismatch return identical status/schema/generic configured message and bounded timing distribution; throttling, replay and race tests; no PII in logs/URLs. Exact copy constant: “Student ID or registered email could not be verified. Please check your information or contact the Registrar.”

### 2.3 OTP/challenge and transactional email

- **Problem / impact:** notification service is health-only; OTP is not implemented.
- **Outcome / likely files:** `services/notification/app/main.py`, new outbox/provider modules, Gateway auth routes, migration 0017+ if accepted after schema review.
- **Depends / priority / complexity:** 2.2, approved provider/privacy policy; HIGH; LARGE.
- **Acceptance / tests:** OTP generated with cryptographic RNG; keyed HMAC digest, UID/purpose binding, expiry, atomic one-time consume, attempt/resend limits, rate limits, secret redaction and provider outage/replay tests. Resend primary only if current terms/limits and institutional email domain qualify; Brevo alternative separately evaluated; Firebase action email remains preferred for normal verification/reset if it meets requirements.

## Phase 3 — Durable schedule lifecycle and connected workflows

### 3.1 Revision-safe draft editing and correction

- **Problem / impact:** create/list/detail exist but generic edit/delete/correction workflow is not established.
- **Outcome / likely files:** `services/scheduling/app/main.py`, draft repositories, API contracts and `SchedulingDraftPages.tsx`; migration only if current schema cannot express revisions/audit.
- **Depends / priority / complexity:** Phase 1 gates; CRITICAL; LARGE.
- **Acceptance / tests:** each edit revalidates complete candidate, uses expected revision/hash, records actor/audit, and stale/unauthorized edits do not mutate; deletion/retention policy explicit and tested.

### 3.2 Publication/recovery qualification

- **Problem / impact:** historical local publication receipts do not qualify this exact commit or hosted recovery.
- **Outcome / likely files:** `publication_api.py`, `postgres_publication_repository.py`, migrations 0007–0011 and test/qualification scripts.
- **Depends / priority / complexity:** 1.1–1.4, 3.1; CRITICAL; VERY LARGE.
- **Acceptance / tests:** atomic immutable publish, revision-bound review, idempotency/replay, concurrent publication, stale academic revision, rollback as a new version, Student/Teacher projection isolation, restore parity and outage recovery.

### 3.3 Route completion and accessible role journeys

- **Problem / impact:** some route kinds remain disconnected and dashboard/notifications coverage is partial.
- **Outcome / likely files:** `apps/web/src/routes/{route-config,RouteGuard}.tsx` (actual extension verify), `AppShell.tsx`, role pages, API hooks and tests.
- **Depends / priority / complexity:** Phase 3.2; HIGH; LARGE.
- **Acceptance / tests:** all visible Student/Teacher/Admin links work or are clearly unavailable; 3 real role journeys; 360/390/768/1024/1440 and 200% zoom; keyboard, focus, announcements, reduced motion and no cross-role leakage.

### 3.4 Interactive schedule move precheck

- **Problem / impact:** UI drag/move needs immediate correct feedback and no mutation before validation.
- **Outcome / likely files:** `services/scheduling/app/validation.py`, route in scheduling `main.py`, structured frontend calendar editor.
- **Depends / priority / complexity:** 1.1–1.3; MEDIUM; MEDIUM.
- **Acceptance / tests:** `POST /api/v1/scheduling/check-move` is advisory, scoped and bounded; calls `validate_timetable(..., partial=True)`; validates resources/authorization/revision and has measured p95 target defined from environment before setting a 50ms SLA.

## Phase 4 — Security, reliability and optional assistance

### 4.1 Rate limits, headers, dependency gates and audit

- **Problem / impact:** distributed abuse limits, complete security headers, current dependency findings and comprehensive academic mutation audit are open.
- **Outcome / likely files:** `services/gateway/app/main.py`, shared middleware, `.github/workflows/quality.yml`, audit migrations/services.
- **Depends / priority / complexity:** 2.1; HIGH; LARGE.
- **Acceptance / tests:** exact CORS, HSTS only on HTTPS, CSP/frame-ancestors/nosniff/referrer/permissions policy, shared IP+UID limits, request IDs and redacted errors; fresh npm/pip audits; immutable actor/action/target/revision audit and tamper/retention tests.

### 4.2 Motion and bundle performance

- **Problem / impact:** motion not installed and previous build emitted large-chunk/import warning; motion is not a functional prerequisite.
- **Outcome / likely files:** `apps/web/package.json`, app root, `AuthPage.tsx`, role dashboards, `Drawer.tsx`, `Modal.tsx`, `DialogSurface.tsx`, Vite config. Follow clean, restrained visual hierarchy with purposeful minimal icons; avoid glassmorphism and non-functional decoration.
- **Depends / priority / complexity:** 3.3 and accessible design review; LOW; MEDIUM.
- **Acceptance / tests:** evaluate latest compatible `motion`; use `LazyMotion`/`domAnimation` strict and `MotionConfig reducedMotion="user"`; `AnimatePresence mode="wait"`, shared `layoutId`, small stagger and spring variants; reduced-motion has no essential motion; keyboard/focus stays correct; route code splitting improves measured budget. Keep the UI clean and restrained, with purposeful minimal icons; avoid glassmorphism and conspicuous decorative effects.

### 4.3 AI explanation copilot (optional, non-authoritative)

- **Problem / impact:** free-text AI proposals risk privacy, arbitrary constraint changes, cost and nondeterminism.
- **Outcome / likely files:** new structured constraint contract/UI; isolated service adapter; `readiness.py`/`validation.py` diagnostic codes.
- **Depends / priority / complexity:** all scheduling gates and explicit institution/privacy/provider approval; LOW; VERY LARGE.
- **Acceptance / tests:** CP-SAT remains sole decision authority; model only explains opaque, redacted diagnostics; JSON schema validated; suggestions map to existing structured options and require human approval plus re-solve/independent validation; provider 429/503 fallback is bounded, no-PII and kill-switchable. Do not commit to named free model quotas; reverify terms/limits at implementation time.

## Phase 5 — Production readiness and supervised pilot

### 5.1 Provider, migration, backup and cost qualification

- **Problem / impact:** free-tier platforms may pause, lack backups/SLA or exceed quotas; $0/month cannot be guaranteed for a real service.
- **Outcome / likely files:** `docs/production/*`, env examples, Docker/Compose/CI, persistence configuration and restore scripts.
- **Depends / priority / complexity:** prior phases; CRITICAL; VERY LARGE.
- **Acceptance / tests:** hard recurring-cost ceiling is $0/month. Provider owner/security review; TLS and pooled connection limits; migration from approved export only after separate approval; pre/post counts/checksums, restore and rollback rehearsal; pause/cold-start/outage tests, spend controls, backup retention and operator runbook. No real records or cutover in this plan. If a free service cannot satisfy privacy, availability, backup, recovery and reliability gates within $0, production launch remains BLOCKED; do not weaken requirements or silently add paid spend.

### 5.2 Real institutional pilot and release

- **Problem / impact:** no Registrar, facilities, privacy, hosting or release authorization is established by local code.
- **Outcome / likely files:** supervised pilot evidence under `docs/production/` and runbooks.
- **Depends / priority / complexity:** 5.1 plus written approvals; CRITICAL; VERY LARGE.
- **Acceptance / tests:** approved roster/curriculum/room/calendar scope, role training, privacy/legal sign-off, production-like rehearsal, all tests in `DEFINITION_OF_DONE.md`, rollback rehearsal and separately approved deployment. No public release until every gate is evidenced.
