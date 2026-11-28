# Requirements -> implementation -> evidence

### 28 November 2026 — Phase D / Slice D2

| Requirement | Implementation / evidence | Current status |
| --- | --- | --- |
| Session type shown by colour and text; institute toggle chips | `SchedulingTimetable.tsx`, `weekly-scheduling.css`; `PhaseD2.test.tsx` | VERIFIED by Vitest and harness render |
| No raw identifiers in draft dropdowns and lists; Edit preselects | `scheduling-labels.ts`, `SchedulingDraftPages.tsx`; same test | VERIFIED by Vitest |
| Advisor before/after pill | `SchedulingDraftPages.tsx`; same test | VERIFIED by Vitest with mocked advice; no live Gemini |
| Publish step, active step, polish totals, Open saved draft | `AcademicGenerationPage.tsx`, `PolishSummary.tsx` | Steps IMPLEMENTED-UNVERIFIED by automated test; checked in harness |
| `No conflicts` only after a clear server check | `ClassroomRequestsPage.tsx`; `PhaseD2.test.tsx` | VERIFIED by Vitest |
| Failed reads say what failed and offer Retry | Admin and Teacher pages; `NoDeadEnds.test.tsx` | VERIFIED by Vitest for ten routes; publication panel and issue restrictions IMPLEMENTED-UNVERIFIED |
| Server-side roster status filter, combined with other filters | `academic/app/main.py`, `postgres_repository.py`; `test_roster_postgres_runtime.py`, `test_roster_crud.py`, `test_roster_proxy.py`, roster page test | VERIFIED on disposable PostgreSQL (483 passed, no skips); hosted not verified |
| Teacher shortcuts and `?occurrence=` prefill | `RoleScheduleWorkspace.tsx`, `ClassSessionDetails.tsx`, `TeacherIssueReportPage.tsx`; `PhaseD2.test.tsx` | VERIFIED by Vitest (card and prefill) |
| Student Find room, Today/Week, `.ics` export | `StudentHome.tsx`; `PhaseD2.test.tsx` | VERIFIED by Vitest with mocked exporter; download not verified |
| Urgent changes distinct from announcements; no 360px overflow | `AlertsFeed.tsx`, `alerts-feed.css`; same test | VERIFIED by Vitest and harness render |
| Main entry at most 101,376 bytes | budget script | VERIFIED: 87,719 bytes |
| `npm run test:web` completes | `scripts/test-web.cjs` limit raised from 300 to 600 s | VERIFIED: 1064 passed in 357 s; the run before had 2 timing failures |

### 28 November 2026 — Phase D / Slice D1

| Requirement | Implementation / evidence | Current status |
| --- | --- | --- |
| Skip link hidden until keyboard focus | `styles.css`; `AppShell.phase-d.test.tsx` | VERIFIED by Vitest and harness render |
| Sidebar group opens and highlights on nested pages; breadcrumbs | `route-config.ts`, `AppShell.tsx`; same test | VERIFIED by Vitest |
| Branded access cards, waking skeleton | `RouteGuard.tsx`, `UniversitySessionPanel.tsx`; `RouteGuard.states.test.tsx` | VERIFIED by Vitest and harness render |
| Read failures worded apart from save failures, with Retry (setup, roster) | `academic-api.ts`, `publication-api.ts`, `institutional-api.ts`, `InlineError.tsx` | Academic and roster VERIFIED by Vitest; publication and institutional wording IMPLEMENTED-UNVERIFIED |
| Setup counter never exceeds 6; one primary action | `AcademicPeriodSetup.tsx`, `AcademicManagementPage.tsx` and test | VERIFIED by Vitest and harness render |
| Roster row actions, accessible names, bulk activation, page status filter | `AcademicStudentRosterPage.tsx` and test | VERIFIED by Vitest with mocked API |
| Main entry at most 101,376 bytes | `data/preview-profiles.ts`; budget script | VERIFIED: 87,595 bytes |
| No dead ends | `NoDeadEnds.test.tsx` | VERIFIED by Vitest |

### 28 November 2026 — Phase C / Slice C3

| Requirement | Implementation / evidence | Current status |
| --- | --- | --- |
| Migration 0030: two forced-RLS tables, least-privilege grants, upgrade, downgrade refusal | `0030_facility_issue_reports.py`; `test_facility_issues_postgres_runtime.py` | VERIFIED on disposable PostgreSQL; Neon not migrated |
| Teacher reports and reads only own; Admin reads tenant; transitions only by checked function | same migration and test | VERIFIED locally |
| Append-only issue history; linked active restriction of the same room | same migration and test | VERIFIED locally |
| Issue endpoints and Gateway routes | `facility_issues.py`, `gateway/app/main.py`; `test_facility_issue_proxy.py` | VERIFIED with test identity adapters |
| Teacher report page, Admin Issue reports tab, prefilled restriction link, Teacher updates | `TeacherIssueReportPage.tsx`, `IssueTriagePanel.tsx`, `ConnectedUpdatesPage.tsx`; `FacilityWorkflows.test.tsx` | VERIFIED by Vitest; no browser check |
| `.ics` export of the selected range for all three roles | `calendar-ics.ts`, `ExportIcsButton.tsx`; `calendar-ics.test.ts` | Serializer VERIFIED; button and download IMPLEMENTED-UNVERIFIED |
| Request detail honors `?id=` with honest not-found | `ClassroomRequestsPage.tsx`; `FacilityWorkflows.test.tsx` | VERIFIED by Vitest |
| Student and Teacher alerts merged with audience announcements | `AlertsFeed.tsx`, `StudentHome.tsx`, `ConnectedUpdatesPage.tsx`; `FacilityWorkflows.test.tsx` | Merge VERIFIED by Vitest; server isolation relies on existing announcement RLS tests |
| No institutional route shows "This service is not connected"; academic detail redirects | `RouteGuard.tsx`; `NoDeadEnds.test.tsx` | VERIFIED by Vitest |

### 28 November 2026 — Phase C / Slice C2

| Requirement | Implementation / evidence | Current status |
| --- | --- | --- |
| Migration 0029, non-superuser owner, upgrade, downgrade refusal, single head | `0029_restrictions_and_period_lifecycle.py`; `test_period_lifecycle_postgres_runtime.py` | VERIFIED on disposable PostgreSQL 18; Neon not migrated |
| No activity event dropped; three added | `test_0029_keeps_every_earlier_activity_event_and_adds_three` and the history test | VERIFIED locally |
| Any tenant Administrator revises or cancels a restriction, with acting-UID audit | 0029 trigger and policy; reports and occupancy runtime tests | VERIFIED locally |
| Cancelled restrictions release rooms | revised `room_restriction_windows`; occupancy, report runtime tests | VERIFIED locally |
| Reports and utilization (41 rooms, 57 instructors), formula-safe CSV | `reports.py`, `ReportsPage.tsx`, `csv.ts`; runtime and Vitest | VERIFIED locally; no browser check |
| Buildings, 41/12 separation, restriction CRUD and preflight | `BuildingsPage.tsx`, restriction routes; runtime and Vitest | VERIFIED locally; no browser check |
| Bulk status (<= 500, atomic) and CSV import (<= 2,000 rows / 1 MB) | `roster_operations.py`, `roster_import.py`, `RosterImportDialog.tsx`; roster runtime and Vitest | VERIFIED locally |
| Clone without enrollments or locks; one-way archive | `roster_operations.py`, `PeriodLifecycleControls.tsx`; lifecycle runtime and Vitest | VERIFIED locally |
| Continuing students enrolled into new/cloned periods without new identities | `create_roster_student`, `roster_import.py`; `test_continuing_students_join_a_cloned_period_without_new_identities` | VERIFIED locally; limited to students in the acting Administrator's own periods |
| Announcements work with read-only identity grants | `announcements.py`; `test_announcements_postgres_runtime.py` | VERIFIED locally; hosted grants not checked |
| Administrator-only Gateway routes | `test_roster_proxy.py` | VERIFIED with test identity adapters |

### 28 November 2026 — Phase C / Slice C1

| Requirement | Implementation / evidence | Current status |
| --- | --- | --- |
| Focus, visibility, resize and token refresh never unmount or wipe cache | `university-session.ts`, `UniversitySessionProvider.tsx`; session and provider Vitest | VERIFIED in jsdom; no real-browser check |
| Cold-start retry before "unavailable" | `university-session-driver.ts`, `transient.ts`; driver and API Vitest | VERIFIED by unit tests; no hosted cold start |
| Per-period day-shape preferences and 180-minute pattern policy | contracts, `academic_input.resolve_patterns`; `test_commuter_polish.py` | VERIFIED locally |
| Bounded deterministic commuter polish, at most 1.0 s | `polish.py` (validator re-run after every move in tests); campus runtime test | VERIFIED on Windows; 19 of the campus section-days still exceed 9 h |
| Administrator rules screen and polish summary | `SchedulingRulesPage.tsx`, `PolishSummary.tsx`; Vitest | VERIFIED by Vitest; no browser check |

### Canonical hard-constraint mapping (owner-confirmed 27 November 2026)

| Code | Constraint |
| --- | --- |
| H1 | Room overlap |
| H2 | Instructor overlap |
| H3 | Section overlap |
| H4 | Student (cross-section enrollment) overlap |
| H5 | Eligibility, including excluded-space locks: the 12 excluded campus spaces are never eligible |
| H6 | Room type, capacity, equipment, program and activity requirements |
| H7 | Operating hours |
| H8 | Instructor availability |
| H9 | Room availability and dated restrictions |
| H10 | Instructor subject readiness (eligibility for the subject) |
| H11 | Instructor weekly and daily workload |
| H12 | Maximum continuous teaching |
| H13 | Transition buffer |
| H14 | Locked assignments |
| H15 | Weekly minutes, permitted pattern and distinct days |

### 27 November 2026 — Phase B / Slice 4

| Requirement | Implementation / evidence | Current status |
| --- | --- | --- |
| H12 max continuous teaching | `max_continuous_minutes`; `constraint_model.add_continuous_limit`, `validation.teaching_blocks`, `PublicationRules.continuous_teaching`; `test_phase_b_constraints.py` | VERIFIED locally |
| H9 dated restrictions in generation | `restriction_windows.with_room_restrictions` in Administrator generation | VERIFIED by unit tests; generation route with stored restrictions IMPLEMENTED-UNVERIFIED |
| H13/H14 on Teacher requests | buffer padding in occupancy; `locked_warnings` in preflight | VERIFIED locally (unit + PostgreSQL 18) |
| Pre-flight capacity audit with setup links | `readiness.capacity_audit`, `action_path`, `readiness-navigation.ts` | VERIFIED locally |
| Deterministic campus solve in budget | `engine.configure`, exact model reductions; `test_seed_all_programs_postgres_runtime.py` | VERIFIED on Windows (4.89 s); Linux CI and RSS unverified |
| Soft rules | `objectives.py` terms | VERIFIED on small inputs; NOT applied to the full campus (soft phase skipped above 150 sessions) |
| Bounded two-step repair | `repair.Repair`, `main.deterministic_repair` | VERIFIED by unit test |
| All seven other degree programs seeded; TCP row only | `seed_program_catalog.py`; `test_seed_program_catalog.py`; PostgreSQL idempotency and edit preservation | VERIFIED locally; not applied to Neon |
| Institute/Program filters | `program-scope.ts`; setup tabs, draft and published timetables | Setup tabs VERIFIED by Vitest; timetables typecheck only; no browser check |
| Cross-scope room occupancy without leakage | Migration `0028`; `room_occupancy.occupied_rooms`; `test_room_occupancy_postgres_runtime.py` | VERIFIED on disposable PostgreSQL 18; NOT applied to Neon |

### 26 November 2026 — Request approval on PostgreSQL

| Requirement | Implementation / evidence | Current status |
| --- | --- | --- |
| Teacher request submission under the runtime role | Advisory lock replaces identity row lock; `test_request_approval_postgres_runtime.py` | VERIFIED on disposable PostgreSQL 18; hosted unverified |
| Atomic approval, conflict rollback, rejection, triggers and RLS | Same test | VERIFIED on disposable PostgreSQL 18; supersedes the "IMPLEMENTED-UNVERIFIED against PostgreSQL" rows below |
| PostgreSQL tests run in the Linux CI `python` job | `services/testing/postgres_cluster.py` | IMPLEMENTED-UNVERIFIED (not run on Linux / PostgreSQL 16) |


### 26 November 2026 — Roster 503 and archived periods

| Requirement | Implementation / evidence | Current status |
| --- | --- | --- |
| Admin roster list/search/filter works under the runtime role | Typed filter casts; `test_roster_postgres_runtime.py` | VERIFIED on disposable PostgreSQL 18; hosted page unverified |
| Admin roster create/activate/re-key/delete with audit | Migration `0027_roster_audit_events`; no row lock on identity tables; same test | VERIFIED on disposable PostgreSQL; `0027` NOT applied to Neon |
| Archived periods never listed or auto-selected, rows retained | `periods()`, publication `periods()`, `listAcademicPeriods`; PostgreSQL, unit and Vitest tests | VERIFIED locally |

Supersedes the "Admin roster reachable + Mark active" row below: writes could not succeed before `0027`.

### 26 November 2026 — Defense readiness Slices 1–3

| Requirement | Implementation / evidence | Current status |
| --- | --- | --- |
| Standalone seed CLI and stale-head regression | `seed_campus_data.py` adds repo root at import; `test_cli_help_runs_standalone_without_pythonpath`; head test derives the single head from migration files; `scripts/tests` added to `testpaths` | VERIFIED locally (32 scripts tests run in default pytest) |
| Live room occupancy on Teacher requests (41 schedulable, 12 excluded) | `catalog.schedulable_spaces`; `occupancy_in`; `options_in` occupancy labels; `create` 409 occupied / 422 excluded; `RoomSlotChecker` + `GET /timetables/rooms/{period}/slot` (room metadata + occupancy only) | IMPLEMENTED; unit/API tests pass with faked storage; PostgreSQL/RLS runtime IMPLEMENTED-UNVERIFIED; reservations visible to Administrators only |
| Conflict-validated atomic approval | `Requests.preflight`/`check_candidate`/`approve_in`; `publish_in` within the decision transaction; `request_exception` calendar move; real review detects an injected conflict (`test_request_exception_conflict_is_caught_by_real_publication_review`) | IMPLEMENTED; trigger compatibility reviewed by reading only — IMPLEMENTED-UNVERIFIED against PostgreSQL |
| Reject with reason, no schedule mutation | Existing decide path unchanged | VERIFIED by existing and new tests |
| Non-blocking Teacher email + in-app updates | Notification `/internal/v1/request-decision-email`; Gateway decision route schedules post-commit task (5 s, sanitized logs); `ConnectedUpdatesPage` decisions; students see changed occurrences | IMPLEMENTED; Resend/Firebase only mocked; no student email by approval |
| Admin roster reachable + Mark active | `RouteGuard` connected `/admin/students`; Gateway roster GET/POST/PUT/DELETE proxies; `markActive` | IMPLEMENTED; focused UI/Gateway tests pass; live provisioning not run |
| Teacher provisioning precondition | Seed creates `classsync_identity.people`/`faculty` identities for 12 seeded faculty (no users/memberships) | IMPLEMENTED-UNVERIFIED against Neon; owner must re-run `--apply` |
| Defense runbook | `docs/defense/RUNBOOK.md` | DOCUMENTED; commands not executed by assistant |

### 26 November 2026 — Phase 3 local implementation slice

| Requirement | Implementation / evidence | Current status |
| --- | --- | --- |
| UUID-valid seeded IDs and stale legacy period recovery | `scripts/seed_campus_data.py` UUIDv5 helper; migration `0026_archived_period_audit.py`; archived row/audit event committed transactionally; `PostgresAcademicPeriods.list_for` hides the explicit archive marker | IMPLEMENTED-UNVERIFIED against Neon; immutable audit references preserved; no `--apply` |
| Seeded generation and independent hard-conflict detection | `test_seeded_defense_dataset.py`: owner-authorized local fixture, 54/54 generated assignments, 41 room metadata records, zero conflicts; override overlap regression | VERIFIED in-memory only; no PostgreSQL-backed period readiness or live generation |
| Admin draft edit and publication | Scheduling revision route saves a separate complete immutable draft after independent validator success while preserving the exact academic input/pin snapshot; current publish/review flow tests remain green | IMPLEMENTED-UNVERIFIED on institutional PostgreSQL; pins are managed in Academic Setup; no connected Admin publication performed |
| Gemini conflict and health advice | Scheduling backend `advisor.py`, Render env declarations, bounded REST call and 16 KiB response, 10s timeout, 120-assignment/24-candidate cap, opaque options and aggregate metrics; mock fallback/schema tests | IMPLEMENTED locally; provider/key/rate-limit behavior only mocked; UI candidates apply through deterministic revision validator |
| Admin → Teacher → Student workflow | Existing request, publish, teacher/student projection tests and room directory checks pass locally | SUPERSEDED by the Slices 1–3 rows above; connected live role journey still unverified |
| Admin period recovery and checklist | Period/detail fallback, request coalescing, six-step label/student count, responsive tab layout; focused and full Web tests | VERIFIED locally; production browser/session remains unverified |
| Full local gates | Python 1,220 passed including migration `0026`; web 898 passed; Ruff, lint, typecheck, build, contract check and diff check pass; focused seed/advisor/migration tests pass | Local checks VERIFIED; no live data or provider operation |

**Current authority decision (15 November 2026):** PostgreSQL is the authoritative
relational identity-membership, academic, scheduling and publication store; Firebase Auth
proves identity. Firestore is optional absent a verified rubric or later owner decision.
This supersedes the 10 November Firestore Native requirement. The Firestore-specific rows
below are historical local-qualification receipts only; they do not define current product
requirements or production readiness. See [STATUS.md](STATUS.md) and the
[current architecture](../architecture.md). Production remains NO-GO.

| Historical Firestore qualification              | Implementation and recorded evidence                                                                                                                                                         | Status / limit                                                                                                                                |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Superseded: Native Firestore operational access | Firestore access/claim/invitation adapters, actual Auth and Firestore emulators, Gateway and direct Scheduling on disposable PostgreSQL; `production-firestore-role-5.json`                  | Historical isolated local role slice only; not current architecture requirement. Production and hosted behavior remain unverified.            |
| Pending claim and one-use invitation            | Verified Student claim and Administrator approval, exact replay, Teacher invite head/reservation, concurrent accept 200/403, denied wrong email/expired/replaced/revoked/revoked issuer      | PASS locally with preloaded synthetic SQL projection; production roster verification, projection writer, MFA and real email delivery pending. |
| Fail-closed access and direct Rules             | SQL-only/pending/shadow/revoked 403 at both boundaries, mismatch/outage 503, matching recovery 200, direct Firestore client denials 403                                                      | PASS locally. Hosted outage recovery and in-flight privileged-write fencing are unverified.                                                   |
| Resumable dry run and shadow parity             | `firestore_shadow_import.py`; bounded plan, duplicate/orphan rejection, interrupted/concurrent replay, exact reservation parity; two synthetic rows and a redacted checksum                  | PASS for bounded rehearsal; full export/cutover/restore/rollback are pending.                                                                 |
| Scheduling and OCR                              | `production-directive-focused.log` 142 passes including synthetic shared institute locks, publication and parser/limit regressions; Windows OCR receipt for four input types                 | PASS for focused synthetic Windows checks. No native Linux image, real forms or institutional coverage claim.                                 |
| Private durable registration review             | Gateway review routes, Firestore Native emulator and a fresh Gateway/client; exact binding check on timetable responses; erase vs. in-flight review, expiry, outage, and user/tenant denials | PASS locally with synthetic identity. Hosted composition, physical TTL cleanup and authorization cutover remain pending.                      |
| Release security                                | Fresh npm audit: seven moderate dependency entries tied to GHSA-g3hv-75wg-m249; current lint dependency range excludes patched major                                                         | BLOCKED under the unchanged audit policy; resolve with a supported release or separately authorized policy disposition.                       |

| Requirement                                                    | Implementation                                                                                                                         | Fresh evidence                                                                                                       | Status / limit                                                                                                                                                   |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P1 immutable mode and safe distributables                      | web config/app-mode, runtime-config, Vite                                                                                              | full web664/36; artifact4/4 groups; both builds                                                                      | VERIFIED local; no sandbox distributables or production identity                                                                                                 |
| P1 preview/API boundaries                                      | preview-session, RouteGuard, API wrappers, independent backend guards                                                                  | backend260/260 at P2b exit; security13/13; presentation15 journeys zeroAPI                                           | VERIFIED local negative paths; institutional authority separate                                                                                                  |
| P1 direct refresh/assets/API errors and release metadata       | artifact server/build metadata; hosted verifier                                                                                        | p2b-exit-artifacts.log; p2b-exit-browser.json; dirty release rejected                                                | VERIFIED local; hosted deployment unchanged                                                                                                                      |
| P1 supply chain                                                | pinned compatible npm/Python graph and exact provenance scanner                                                                        | p2b-exit-npm-audit.json zero; Python68/0; npm tree and pipcheck0                                                     | VERIFIED scanned graph; native libraries/production images separate                                                                                              |
| P1 responsive Soft Rouge three-role public experience          | existing UI, frontend test setup repairs only                                                                                          | P2b browser15 at360/390/768/1024/1440; native200%/keyboard; reviewed identical before/after images                   | VERIFIED checked public/unavailable screens; full institutional journeys/manual screenreader unverified                                                          |
| P2a identity-only verification and current membership contract | classync_contracts identity/token/request authorization                                                                                | acceptance and token specs; full backend at P2b exit                                                                 | VERIFIED local; default membership provider unavailable                                                                                                          |
| P2a real SDK crypto/revocation negatives                       | token_verification, offline synthetic transport tests                                                                                  | gateway crypto16/16 including newly added SDK setup cleanup                                                          | VERIFIED offline SDK; not Google/live/emulator acceptance                                                                                                        |
| P2a failclosed roles/tenant/record membership                  | shared request_identity; service guards; stream fresh membership                                                                       | backend260/260 P2b exit; p2a evidence in STATUS                                                                      | VERIFIED tested boundaries; no frontend-only grants                                                                                                              |
| P2b new disposable cluster safety                              | postgres_disposable harness; explicit SSPI loopback/runtime identity                                                                   | p2b-audit-qualification-final.json; p2b-exit-pg-stopped.log                                                          | VERIFIED ownedcluster stopped; no original target accepted                                                                                                       |
| P2b real relational foundation                                 | shared persistence driver; pinned SQLAlchemy/Alembic/Psycopg; migrations0001-0003                                                      | actual PG18.6; wheel9 sourcefiles byte-equal; driver commit/rollback/pool qualification                              | VERIFIED bounded local foundation; no service cutover                                                                                                            |
| P2b tenant/UID/project/record integrity                        | six FORCE-RLS tables; compositeFKs; current repository                                                                                 | 13 invalid constraints; owner/noctx/crosstenant tests; uid-a plus uid-admin all3roles                                | VERIFIED synthetic; actual enrollment/policy absent                                                                                                              |
| P2b current grant/state and audit integrity                    | revision CAS, immutable history, trustedactor provenance                                                                               | audit exact1-6; revoked/inactive; stale/rollback/auditfailure negative paths                                         | VERIFIED local; actor helper does not authorize; privilegedDDL separate                                                                                          |
| P2b concurrency                                                | revision guard and CAS                                                                                                                 | observed competing rowlock; winner3/staleloser; rollback unchanged                                                   | VERIFIED single-row concurrency; no future multirow lockorder claim                                                                                              |
| P2b unavailable and recovery                                   | no silent fallback; fresh transaction repository                                                                                       | real permissionoutage/missingDB/terminatedownedconnection; recovery currentrevoked6                                  | VERIFIED local                                                                                                                                                   |
| P2b migration/backup/restore                                   | explicit caller-owned migrations; owned restore rehearsal                                                                              | all3 up/down; atomicrollback; datahash and13 catalog categories; ACL semantics and tamper negatives                  | VERIFIED synthetic restore; no original migration                                                                                                                |
| P2b complete exit                                              | p2b-exit-gap-review.md and status11:01                                                                                                 | backend260; web664; security13; artifacts4; lint/types/Ruff/builds/audits; independent review; original hashes equal | PASS complete bounded LOCAL P2b; production NO-GO                                                                                                                |
| P3a offline SDK -> PG -> Gateway requests                      | postgres_identity_http_qualification.py; test-only helper                                                                              | p3a-identity-http-reviewed.json, stoppedtrue; crypto16; independent findings fixed                                   | Historical targeted VERIFIED; serial backend261/261 at that slice; bounded local P3a subsequently PASS with actual emulator/provider/browser exit evidence below |
| P3b authoritative academic/scheduling adapter rehearsal        | PostgreSQL academic repository/migrations0004-0005; shared record_rules; generated-only migration rehearsal; existing SQLite preserved | p3b-academic-repository-exit.json; p3b-academic-migration-reviewed.json; full backend358                             | PARTIAL: academic adapter/rehearsal qualified; service adoption/restore/scheduling/publication adaptation and full exit pending; originalcutover unauthorized    |
| P4 durable academic readiness                                  | roadmap bounded local work                                                                                                             | verified institutional inputs/rubrics unavailable                                                                    | PLANNED; do not invent records or policy                                                                                                                         |
| P5 durable independently validated solver drafts               | existing OR-Tools and validator; future PG integration                                                                                 | initial P3 regression UNKNOWN retained; isolated serial261/261 passed without setting/constraint changes             | NOT milestonePASS; UNKNOWN is failure                                                                                                                            |
| P6 review/approval; P7 publication                             | roadmap revision/hash approval, atomic immutable publication/outbox                                                                    | future phase gates                                                                                                   | PLANNED; no production authority                                                                                                                                 |
| P8 connected role journeys                                     | roadmap current published projections                                                                                                  | future phase gates                                                                                                   | PLANNED; actual roleacceptance unverified                                                                                                                        |
| Capstone actual rubrics                                        | ITHUMCI/ITIASE1/ADBMS/ITELECT/APPSDEV source verification                                                                              | authoritative rubrics not provided/verified                                                                          | BLOCKED external requirement; no guessed Firebase database mandate                                                                                               |

| P3a actual Auth Emulator lifecycle | test-only demo verifier; gated parser; owned Auth/PG harness | p3a-auth-emulator-reviewed.json; backend307; security14; cleanisolatedtoolsaudit; stopped ports/originalhashes | Historical bounded slice PASS; bounded local P3a later PASS via configured provider and frontend lifecycle; institutional provisioning separate |

| P3a configured Gateway provider/pool | gateway authorization.py/lifespan; optionalsecretURL; defaultverifiedTLS and test-onlySSPI; boundedfive-slotpool | p3a-provider-exit-qualification.json; actual lock/pool503/recovery; normal/exceptional/restartcleanup; backend333/security14; Python68-0; originalhashes/closedport | Bounded local slice PASS; bounded local P3a later PASS via frontend lifecycle exit; defaultunconfigured and real productiontransport/provider unverified |

| P3a frontend Firebase/current-membership lifecycle | institutional-only university-session controller/driver/provider/panel; existing data API gate retained | p3a-web-session-browser-exit.json actual SDK/Auth/Gateway/PG; 3roles/denied/revoked/offline/outages/signout; native200/5widths; web709/backend334/security15/artifact4; presentation15zeroAPI; independentreview/originalhashes | VERIFIED bounded emulator/local P3a PASS; real provisioning/provider/TLS/manualscreenreader/connected schedules unverified; production NO-GO |

| P3b isolated owner-scoped academic period metadata | migration0004, academic_periods.py; currentAdmin/tenant/project/owner samestatement/FORCERLS; no routeadoption | p3b-period-metadata-owner-reviewed.json actualPG twoactiveAdmins/constraints/rollback/restart/revocation/outage/down-up; persistence68; wheel11byteequal; independentreview | Bounded metadata slice VERIFIED/PASS; fullP3b PARTIAL; complete academic/scheduling repositories and data-preserving rehearsal/cutover unverified |

| P3b complete PostgreSQL academic repository | shared record_rules, postgres_repository, migration0005, explicit Academic persistence dependency; current verifiedAdmin/RLS/periodlocks/CAS/repeatableread | p3b-academic-repository-exit.json all7kinds/4offerings/twoAdmin/activewrongroles/2lockwaiters/exactwinner/corruption/provenance/outage; backend358/Ruff0/Python68-0/wheel12; independentreview | VERIFIED bounded adapter slice; not installed in default service routes; fullP3b PARTIAL |
| P3b deterministic academic SQLite->PG rehearsal | generated-only marked source; typed/reference/hash checks; explicitsyntheticmapping; UTCcanonical decoder | p3b-academic-migration-reviewed.json 81rows/fullsnapshot/rawchecksums/revisions equal; interruptionrollback/replay409/reconnect/sourcehashsame; guards2/UTC2 | VERIFIED synthetic rehearsal; no arbitrary/original source accepted; academic backuprestore/scheduling/fullP3b exit pending |

| P3b Academic source-owned PG/identity provider and routes | Academicauthorization/provider/main; shared explicitPGconfiguration; optionalSecretURL; no prodSQLitefallback/startupDDL | local-20261027/academic-provider-reviewed.json realownedAuthSDK/currentPG/ASGI CRUD/CAS/roles/owners/serverbindings/revocationrace/outage/pool/restartcleanup; backend372/security15/Ruff0/wheel13; hashes/closedports; independentreview | VERIFIED boundedlocal/emulatorprovider slice PASS; fullP3b PARTIAL; realTLS/provisioning/TCP/browser/privateacademicUX/restore/schedulingadaptation pending |

| P3b academic backup/restore | guarded migration0005 fixture/archive/new target; full raw-data/catalog/ACL fingerprints and restored repository checks | local-20261027/academic-restore-qualification.json; portable58; final backend441; independent review; source/archive unchanged; stopped cluster/original hashes | VERIFIED bounded same-cluster synthetic restore PASS; not cross-host disaster recovery or original-data migration |
| P3b PostgreSQL server runs/immutable drafts | shared draft_rules; migration0006; current active Admin/owner/project RLS; compositeFK/checksum/immutable DML; transaction owner lock/strict-key replay | postgres-drafts-reviewed.json: new backendPID/exact snapshot,2lock waiters/one create, strict conflicts, invalid/expired/corrupt/role/tenant/outage/revocation negatives; backend441; wheel14; review/preservation | VERIFIED bounded adapter PASS; Scheduling provider/routes/publication not adopted; legacy dev SQLite alternate-key behavior differs; fullP3b PARTIAL |
| Cross-cutting bounded frontend regression throughput | root wrapper honors existing Vitest maxWorkers2/default isolation; unchanged300s/assertions | actual root web709/40 in172.80s; diagnostic185.96s; prior timeouts retained; independent review; security15 | VERIFIED local runner; no product UI change/new browser or institutional acceptance |

| P3b Scheduling owned PG/identity provider and draft routes | scheduling authorization/provider/main; optional SecretURL/owned pool; verified owner/current membership; guarded unsupported publication | local-20261027/scheduling-provider-qualification.json actualSDK/currentPG/ASGI generation-draft-replay/roles/owners/forgery/revocation/permission/pool/restart/publication denial; backend492/security16/Python68-0/Ruff; review/source fingerprints/original hashes | VERIFIED bounded local/emulator provider PASS; real timed UNKNOWN/Academic forwarding/TCP/browser/production/publication/fullP3b unqualified |

| P3b generated Scheduling SQLite-to-PG migration and full restore | fixed generated source/current-owner transaction; guarded12-table/14-catalog restore and exact functional audit delta | local-20261027/scheduling-migration-qualification.json (2 stopped clusters), scheduling-restore-reviewed.json; portable63+52; backend607/security16; independent review/fresh original hashes/11 stopped roots | VERIFIED bounded local slices PASS; original cutover/cross-host recovery/publication/fullP3b unqualified |

| P3b publication shared validation/projection prerequisite | publication_rules + SQLite inheritance; strictest supplied teacher/bucket cap | portable43/initial8-case workload RED4; fullbackend650/security16/Ruff; independent review/fresh preservation | VERIFIED bounded local prerequisite PASS; PostgreSQL publication/provider/fullP3b and approval/P6/P7 incomplete |

| P3b PostgreSQL publication-state foundation | migration0007 immutable versions/stable owned heads/currentAdmin RLS/deferred atomic pair | publication-state-reviewed.json actual3optimal drafts/32negative guards/owner collision/reconnect/rollback/down-up; portable28/backend678/security16/Python68-0/wheel15/review/preservation | VERIFIED bounded schema prerequisite PASS; adapter/provider/restrictions/history rehearsal/approval/P6/P7/fullP3b incomplete |

| P3b publication application transaction qualification | PostgreSQL repository/0008 restrictions + shared rules; current authority locks, exact replay and immutable audit | publication-repository-locks.json actual PG18.6/helper denials/both compatible writer orders; backend829/security16/portable39/wheel16/Python68-0; independent review/original hashes | VERIFIED listed probes; full adapter PARTIAL pending resource/conflicting-writer/scale matrix; provider/history migration/restore/fullP3b and approval/outbox unqualified |

| P3b actual room/faculty/section/student conflict matrix | `scripts/postgres_publication_resource_qualification.py`; shared ISO-week/buffer and dated-room constraints | `publication-resource-final.json` actual optimal PG18.6 generated drafts; four isolated exact422s/all-six-table preservation; disjoint-resource control; pure `publication-invariant-final.log`67 passed | VERIFIED bounded matrix and invariant regressions; conflicting reservation/publication race and provider/history exit remain open |
| P3b publication representative workload | generated 25 offering/250 enrollment PG18.6 workload, 13 Monday occurrences each,25 restriction audits | `publication-scale-bounded.json`: optimal,325 occurrences/225 projection/25 audits; measured operations <1 sec; four fixture guards | VERIFIED bounded local workload only; 100/3,000 exploratory run interrupted after CPU nonprogress, no P/scale claim |
| P3b institutional PostgreSQL publication provider and role projection | `scoped_repo`, current membership/record scope, migrations0009/0011 nonrecursive policy and head/version guard | local-20261029/publication-repository-sqlite-scope-fixed.json + publication-provider-http.json: actual runtime SQL and emulator SDK/current PG ASGI HTTP review/publish/replay, three-role calendars/periods and authorization/revocation denials | VERIFIED bounded local PASS; no new TCP/browser or production acceptance |
| P3b legacy publication history compatibility and complete restore | migration0010 immutable admin archive, opaque hash/payload and explicit mapping, no active head/replay; complete generated publication/head/restriction/identity/academic/draft restore | local-20261029/publication-repository-sqlite-scope-fixed.json + publication-archive-restore.json: actual import/retry/collision/downgrade and 17-table/17-catalog/sequence equality, restored role views/grants/RLS/immutability and unchanged source | VERIFIED bounded local PASS; same-cluster restore and generated/caller-attested provenance only; no original migration or cross-host recovery |
| P3b final approved local exit | unchanged production behavior, full serial regression, current provider composition, migration graph/wheels, audits, preservation and independent review | local-20261029/p3b-exit-evidence.json: backend947, web712/40, security16, artifacts4, lint/types/builds/Ruff/pip-check, Python68/0 and npm0, original hashes,113 stopped marked roots, current source fingerprints | PASS bounded P3b; first web timeout retained and unchanged approved retry PASS; stop before P4-P8; no production release |

| Updated CdM room catalog and offering selection | November 2026 DOCX row map; `cdm-spaces.json`; activity-aware Python/TypeScript contracts; Admin `AcademicRecordEditor` filters by schedulability, activity and program; backend `eligible_room` requires operational status and verified type | 15 November local evidence: 66 frontend tests / 5 files, 14 backend tests, TypeScript, ESLint, Ruff; stale IDs rejected in inventory checks | PARTIAL / locally VERIFIED implementation: row source still has 37/16 summary conflict; Facilities verification, actual availability, full solver/input acceptance remain open |
| Student ID/email onboarding and student-number sign-in | `InstitutionalEntrance.tsx`, `AccountOnboardingPanel.tsx`, `account-actions.ts`, Gateway `/api/v1/auth/student-verification-challenges`, `/verify-student`, `/complete-student-onboarding`, `/student-password-login`, `onboarding_repository.py`, migrations `0019_student_email_challenges` and `0020_student_portal_password` | 19 Nov 2026 focused checks: Web 22 passed across 3 files; Gateway and migration regression 33 passed. Full serial suites and database migration/RLS execution are pending. | IMPLEMENTED-UNVERIFIED. Exact active roster/email match, HMAC OTP (5-minute expiry, 5 failures, 60-second resend), Firebase password-provider check, deferred membership grant, internal roster email resolution, generic student-number/password failure and custom-token response are implemented. Turnstile is enforced on Gateway lookup/OTP/completion routes; direct Firebase email/password and Google calls remain outside this enforcement boundary. Auth Emulator, Resend delivery, PostgreSQL migration/RLS and connected institutional acceptance are pending. |
| Phase 1.3 Administrator setup and task flow | `AcademicManagementPage.tsx`, `AcademicPeriodSetup.tsx`, `AcademicCalendarEditor.tsx`, `AcademicRecordEditor.tsx`, `AcademicGenerationPage.tsx`, `AdminSchedulingHome.tsx`, `ConflictCenterPage.tsx`, `AppShell.tsx`, `route-config.ts`, related CSS and component tests; `docs/hci/admin-workspace-audit.md` | Fresh focused web tests: 31 passed across 3 files; web typecheck and ESLint pass; production build pass with existing Firebase mixed-import and >500 kB chunk warnings. Browser visual/responsive rendering remains unverified. | PARTIAL: period entry explains setup before selection; sandbox/sample data is labeled and demoted; sidebar categories are consolidated but remain searchable; generation/conflicts have honest deterministic labels and actionable empty states. Catalog is not Registrar-verified. Live providers, preview route cleanup, visual browser acceptance and manual assistive-technology checks remain open. |
| Administrator dashboard command center | `AdminSchedulingHome.tsx`, `AppShell.tsx`, `readiness-navigation.ts`, `AcademicGenerationPage.tsx`, scoped dashboard/shell CSS, corresponding UI tests, README and approved plan | Focused UI 49/49 across 5 files; latest full web suite now 836/836; typecheck/lint/build pass with existing Firebase mixed-import and >500 kB chunk warnings. No live browser/API run. | PARTIAL: connected dashboard hierarchy, issue destinations, KPI links and selection-only Admin navigation implemented. Visual viewport/zoom, screen-reader and real provider acceptance remain unverified. |
| Administrator secondary screens density and laptop-width controls | `AcademicPeriodSetup.tsx`, `AcademicManagementPage.tsx`, `AcademicGenerationPage.tsx`, `ConflictCenterPage.tsx`, `ClassroomRequestsPage.tsx`, `PreviewOperationsViews.tsx`, `AppShell.tsx`, `styles.css`, `operational-ui.css`, UI tests and `README.md` | Full web suite 836/836 across 62 files; current typecheck/lint/build pass with existing Firebase mixed-import and >500 kB chunk warnings. Presentation tests use actual 53-space/four-location inventory. Browser viewport capture not performed because port 5173 is occupied by an unverified process. | PARTIAL: category selection, request/notification filtering and compact layout implemented; `/admin/requests` and `/admin/notifications` remain demonstration feeds. Exact viewport behavior, keyboard browser acceptance and manual assistive technology remain unverified. |

### Current local qualification evidence — 16 November 2026

The Administrator popover and active secondary screen dimensions have fresh follow-up evidence that supersedes the stale warning/browser-unavailable statements in the historical rows above. `operational-ui.css` plus `vite.config.ts` and consistent imports in `auth/account-actions.ts` / `auth/university-session-driver.ts`: real Chrome/Playwright measured the page-picker at 1366×768, 1440×900 and 1024×768 (64px header, all 23 labels fit, neutral inactive and burgundy active colors, focus ring and bottom item verified). Five target Administrator routes measured at 1366×768 and 390×844 without horizontal overflow. Lint/typecheck/build pass; frontend tests 837/837 across 62 files. Build chunks are all below 500 kB and emit no prior Firebase import warning. Connected provider/data, 200% zoom and assistive-technology status remain separate.

| P4d Administrator activity audit trail | `0017_administrator_activity_audit.py`; `postgres_publication_repository.py`; `publication_api.py`; Gateway proxy authorization; `PublicationAuditPage.tsx` | `var/p4d-evidence/activity-only-20261117.json`: fresh PG18.6 disposable cluster, 78 synthetic events, redacted trigger events, same-tenant Admin read, cross-tenant RLS denial, update/delete/truncate rejection, stopped cluster | VERIFIED bounded audit slice only. Whole academic PG qualification fails later at a pre-existing readiness fixture assertion; connected Auth/browser lifecycle, native 200%, keyboard E2E and production authority remain unverified |
| P4d automated regression and build | Backend all services, persistence migrations and Web | `var/p4d-evidence/pytest-20261118-post-fixture.log`: 1093 passed/0 failed/1 Starlette deprecation warning; web logs `web-{lint,typecheck,test,build}-20261117.log`: lint/typecheck/build pass, 838 tests across 63 files; `python -m ruff check services packages scripts` and `pip check` pass | VERIFIED local tests/build only. `pip-audit` finds CVE-2026-126360 (`opentelemetry-api` 1.45.1, fixed in 1.45.2); constraint added but install was approval-blocked and shared `.venv` is a junction into `main`; zero-finding rerun remains BLOCKED; npm audit not run |
| P4d PostgreSQL academic readiness qualification | `postgres_academic_repository_qualification.py`; readiness requirements in `academic_input.py` | SQLite characterization: `complete()` is ready as `development-entered`; after mapping mode to institutional, 4 offerings remain but readiness correctly blocks on cohort, curriculum/contact references, faculty/offering/room verification and operating/shared-scope references. Qualification now asserts blockers. Current non-elevated PostgreSQL attempt fails at `pg_ctl` before exercise (`could not create restricted token: error code 87`) | Root cause of old assertion VERIFIED at source/characterization level; corrected full PostgreSQL run UNVERIFIED until run under an authorized process that can start only the script-owned disposable cluster |
| P4d audit privacy and retention review | Migration 0017 / audit endpoint / audit UI | Independent read-only review: no critical RLS or endpoint authorization issue observed. Open findings: guessable unkeyed entity hash, destructive downgrade, nondeterministic timestamp ties, no cursor beyond 500 entries, actor UID display | PARTIAL; define before production and decide whether keyed references, reversible retention/archive, deterministic sequence, pagination, and UID masking are required |
| P4d connected Admin lifecycle and accessibility | Emulator-backed Admin, disposable PostgreSQL, Chrome/Playwright, `/admin/dashboard` through `/admin/calendar` | `node scripts/auth_emulator_qualification.cjs --development` → `Missing pinned Auth Emulator tools`; port 5173 intentionally left untouched; no 200%/keyboard E2E evidence | UNVERIFIED/BLOCKED. Do not claim draft generation, validation, publication, or dashboard/calendar update as freshly browser-qualified this phase |

### P4d continuation evidence — 18 November 2026

| Requirement | Current evidence | Status / remaining gate |
| --- | --- | --- |
| Python regression and static checks | 1093 passed, 0 failed, 1 Starlette deprecation warning; Ruff passed; `pip check` clean | Local regression PASS; security scan remains separately open |
| Frontend quality | lint/typecheck pass; 838 tests / 63 files pass; build passes without chunk/import warning | Local automated PASS |
| Institutional PostgreSQL academic qualification | Corrected fixture contract is tested; isolated `pg_ctl` startup fails before qualification with restricted-token error 87 | UNVERIFIED; requires viable isolated execution context |
| Auth Emulator and connected Admin journey | Pinned tools missing; no connected API mutation/journey executed | BLOCKED / UNVERIFIED |
| Browser responsiveness and keyboard shell | Presentation preview shows 64px topbar/no page overflow and menu/drawer keyboard behavior; target Admin routes mostly rendered a one-control preview gate | Shell behavior partially verified; actual screen acceptance UNVERIFIED |
| Native 200% zoom | Temporary extension blocked by Chrome; no measurement produced | UNVERIFIED |
| Audit privacy/lifecycle | Independent review lists entity hash, rollback retention, timestamp ordering, pagination, and actor UID display concerns | Open before production |

| Follow-up environment claim | Fresh feature-worktree observation | Gate |
| --- | --- | --- |
| Isolated Python environment with clean vulnerability scan | `.venv` is still a junction to `C:\Projects\ClassSync\.venv`; `pip-audit` module missing; system Python is 3.14 and Python 3.12 launcher is unavailable | BLOCKED; do not install into shared `.venv` |
| Auth Emulator prerequisites installed | `node scripts/auth_emulator_qualification.cjs --development` exits 1: pinned tools missing; repo requires firebase-tools 15.34.1, @opentelemetry/core 2.8.0, uuid 11.1.1 | BLOCKED; latest CLI alone is insufficient |
| Disposable PostgreSQL qualification succeeded outside sandbox | No receipts or updated isolated runtime visible in feature worktree | UNVERIFIED; do not rerun under current restricted process and claim the external result |
| Connected Admin E2E | Not started because required environment evidence is absent | BLOCKED |

### 18 November 2026 — PostgreSQL qualification-script correction

| Requirement | Changed components and evidence | Result / remaining gate |
| --- | --- | --- |
| Migrations use a non-superuser, non-BYPASSRLS owner for the 0008 guard | `scripts/postgres_academic_period_qualification.py`; `scripts/tests/test_postgres_qualification_regressions.py` | Helper asserts effective role flags before migration; 11 focused tests pass. Actual disposable migration run is pending. |
| Provisional room qualification matches current canonical catalog and does not invent capacity | `scripts/postgres_academic_repository_qualification.py`; `services/academic/app/repository.py::catalog_data` | Exact canonical ID/count comparison and `capacity is None`; regression rejects missing/stale IDs and invented capacity. |
| Publication/provider migrations expose current schema before repository writes and preserve the 0008 privilege rejection/rollback assertion | `scripts/postgres_academic_restore_qualification.py`; `scripts/postgres_publication_repository_qualification.py`; `scripts/postgres_publication_provider_qualification.py`; `scripts/postgres_driver_qualification.py` | Migration flow now uses historical 0005 setup, 0007/0008 negative boundary, and current Alembic head before repository fixture writes. PG execution pending. |
| Emulator/provider identities retain unique institutional student bindings | `scripts/postgres_identity_qualification.py`; academic, emulator, scheduling and publication provider qualifications; `services/persistence/tests/test_publication_projection_fixture.py` | Synthetic IDs are distinct and tested; no uniqueness constraint was relaxed. Focused tests pass. |
| Scheduling provider scope follows current Alembic head | `scripts/postgres_scheduling_provider_qualification.py`; `current_migration_head()` | Static/regression check selects revision 0017 at this checkout; live PG check pending. |
| Python/Web static and automated regressions | `pytest -q` (full); focused 11-test command; Ruff; `npm run test` in `apps/web`; `pip check` | Focused 11/11; Ruff pass; Web 838/838; pip check pass. Full Python run: 1090 pass/3 fail before updating the related stale student fixture assertion; current targeted fixture then passed. Two existing solver-dependent failures remain (`unknown` at unchanged 8 s; draft rejection of incomplete result). |
| Dependency advisory status | isolated `.venv`; `.venv-main-junction` preserved | User reports external `python_audit.py` clean. In-sandbox `pip-audit --strict` was blocked by `WinError 10013` reaching `pypi.org`; no fresh audit receipt in this worktree. |
| PostgreSQL/Auth Emulator + connected P4d | pinned tools observed in temp root; no scripts launched in this turn | IMPLEMENTED-UNVERIFIED until owner reruns disposable qualifications and provides JSON receipts; connected E2E/200%/keyboard checks remain open. |

| Requirement | Implementation / evidence | Current status |
| --- | --- | --- |
| Domain-neutral student email validation | `packages/api-contracts/classync_contracts/email_address.py`; Gateway onboarding/registration and Notification; `scripts/provision_live_accounts.py`; Python and frontend email helper tests | IMPLEMENTED; relevant tests pass. No institutional-domain-only source matches remain; external Registrar/Firebase flows are not live-qualified. |
| Student-number format and COR review validation | `apps/web/src/auth/student-number.ts`; `RegistrationScannerPage.tsx`; `services/gateway/app/registration_schema.py`; focused scanner tests | IMPLEMENTED; 12 focused frontend tests pass. User-entered OCR content still requires server validation and confirmed review. |
| COR self-verification with provenance and duplicate-claim denial | `services/gateway/app/registration.py`, `onboarding_repository.py`; `0021_student_email_and_cor_source`; Gateway registration tests | IMPLEMENTED-UNVERIFIED against real PostgreSQL; tenant/RLS transaction has not run against disposable PG this phase. |
| Branded verify/reset action flow and resend limits | Gateway `onboarding.py`; Notification `main.py` and `email_templates.py`; frontend `EmailActionPage.tsx`, `account-actions.ts`, `cooldown.ts`; related tests | IMPLEMENTED locally; 101 focused Python and 31 focused auth frontend tests passed. Firebase/provider delivery and distributed cooldown qualification remain open. |
| Admin guided setup UX | `apps/web/src/pages/AdminSchedulingHome.tsx`, `operational-ui.css` | IMPLEMENTED against available readiness/draft/publication state; browser/accessibility qualification not freshly run this phase. |
| Full automated regression gates | Python: 1156 passed/1 solver-dependent failed; Web: 859/859; Ruff/lint/typecheck/build pass | PARTIAL. Solver `unknown` remains a release blocker; wrapper `test:web` exceeded its 300-second timeout, but direct Vitest completed successfully. |

### 25 November 2026 — owner-authorized defense dataset

| Requirement | Implementation / evidence | Current status |
| --- | --- | --- |
| Owner authorization and boundary | `docs/autonomy/APPROVALS.md`: defense records, dates 2026-08-01–2026-12-31, 41 catalog schedulable spaces / 12 excluded; `AGENTS.md` carries the narrow exception | APPROVED for local implementation; no live data operation or deployment authorized here |
| Bulk room verify preserves inventory boundary | `AcademicManagementPage.tsx` intersects candidates, verified count, and completion count with canonical schedulable catalog IDs; regression includes an unverified ad hoc row and excluded catalog row | IMPLEMENTED; focused frontend file passes 23 tests. Actual institutional room records not inspected/changed |
| Academic record edit/delete | `AcademicRecordEditor.tsx`; Academic DELETE routes/repositories; migration `0024_academic_record_deletion_audit.py`; revision/reference checks and audit | IMPLEMENTED-UNVERIFIED against PostgreSQL/RLS; no live database exercise |
| Seed script and defense dataset | `scripts/seed_campus_data.py`; deterministic dry-run/apply gate, stable records, exact tenant confirmation, 41/12 room boundary, unverified roster statuses; seed regression tests | IMPLEMENTED-UNVERIFIED; 12 seed and migration regression tests pass. No Neon connection or `--apply`; curriculum/room/faculty defense defaults are not Registrar/Facilities verified |
| Student roster search/filter/pagination and Admin CRUD | `AcademicStudentRosterPage.tsx`, Academic roster endpoint/query and CRUD routes, migration `0025_student_roster_crud.py`, `test_roster_crud.py` | IMPLEMENTED locally; focused backend and UI tests pass. PostgreSQL/RLS migration runtime qualification remains open; no live database used |
| Python, contracts and Web quality gates | 1201 Python tests pass; seed/migration focused set 12 pass; Ruff, contract check, lint, typecheck, final Web 891 tests pass, build 97.62 kB raw / 26.19 kB gzip, `git diff --check` pass | Local checks VERIFIED; PostgreSQL migration/RLS runtime qualification remains open |

### 28 November 2026 — Phase E, Slice E0 seeded logins

| Requirement | Implementation / evidence | Current status |
| --- | --- | --- |
| Dry-run default; explicit confirmed apply; tenant, project, role, operator and emulator gates | `scripts/provision_seeded_logins.py`; argument, gate and wrong-target tests | VERIFIED locally |
| Only seed-provenance rows; program/section/count targeting; explicit faculty domain | `select_targets`; selection tests over 432 students and 57 teachers | VERIFIED on disposable PostgreSQL |
| Idempotent single-role binding with audit actor; Admin and conflict protection; compensating delete | `test_provision_seeded_logins_postgres.py` with fake Firebase | VERIFIED locally; live Firebase IMPLEMENTED-UNVERIFIED |
| Credentials only in git-ignored `.local/`; never printed | `.gitignore`, `CredentialFile`, output and ignore tests | VERIFIED locally |
| Provisioned Student/Teacher resolves a Gateway session and reads the published schedule with `verification_source='unverified'` | Real Gateway and Scheduling routes, runtime role | VERIFIED locally |
| Live-account script keeps its behaviour on shared helpers | `scripts/lib/identity_provisioning.py`; 13 existing tests | VERIFIED for tested paths; live path not run |
| Owner runbook | `docs/production/SEEDED_LOGINS.md` | IMPLEMENTED; not executed against hosted services |

### 28 November 2026 — Phase E, Slice E1 design system, entrance and shell

| Requirement | Implementation / evidence | Current status |
| --- | --- | --- |
| Skill palette and unified geometry; legacy variables inherit it | `tokens.css`, `theme.css`; token and no-override assertions in `AppShell.phase-e.test.tsx` | IMPLEMENTED; un-migrated pages not visually reviewed |
| Mode switching keeps input; first-field focus; show/hide; default-button submit; blur validation; mapped errors | `InstitutionalEntrance.tsx`, `PasswordInput.tsx`; `InstitutionalEntrance.phase-e.test.tsx` | VERIFIED in jsdom; sign-in and sign-up rendered |
| Three-step onboarding, resend cooldown, continue, prefilled locked claim email; existing OTP backend step kept | `AccountOnboardingPanel.tsx`; onboarding tests | VERIFIED in jsdom; not rendered or run live |
| One active sidebar item and open group on every nested route; top bar contents | `AppShell.tsx`, `app-shell.css`; `AppShell.phase-e.test.tsx` | VERIFIED in jsdom and sample render |
| Page-shaped loading skeleton | `ClassSyncPageSkeleton`, `RouteGuard.tsx` | VERIFIED in jsdom |
| Main entry within 98,000 / 101,376 bytes; no new package | `check_bundle_budget.mjs`: 87,119 bytes; `package.json` unchanged | VERIFIED locally |
| WCAG 2.2 AA | Existing accessible-name and focus tests pass; solid focus outline | PARTIAL: zoom, screen reader and coarse-pointer checks open |

### 28 November 2026 — Phase E, Slice E2 Administrator workspaces

| Requirement | Implementation / evidence | Current status |
| --- | --- | --- |
| Shared page header, command bar, KPI strip, collapsed metadata, table and meter in lazy chunks | `components/layout/*`, `components/ui/DataTable.tsx`, `Meter.tsx`; bundle budget 87,264 bytes | VERIFIED locally |
| One week matrix and agenda list with text-labelled session accents, keyboard movement, names, phone default | `WeekGrid.tsx`, `week-grid.css`; `WeekGrid.phase-e.test.tsx`; sample render | VERIFIED in jsdom and sample render; screen reader open |
| Draft and published timetables use the matrix, institute chips and one-click Edit | `SchedulingTimetable.tsx`, `PublishedTimetable.tsx`; existing draft tests | VERIFIED locally; live published data IMPLEMENTED-UNVERIFIED |
| Dashboard and academic setup fit 1280x720; hairline record tables | `AcademicPeriodSetup.tsx`, `AcademicRecordTable.tsx`; sample render | VERIFIED with sample data |
| Roster command row, server status filter, sticky bulk activation | `AcademicStudentRosterPage.tsx`; roster tests including bar order and single solid action | VERIFIED in jsdom and sample render |
| Generation progress, before/after polish cards, advisor diff | `scheduling.css`, `PolishSummary.tsx`, `SchedulingDraftPages.tsx` | VERIFIED locally; live advisor not contacted |
| Utilization and faculty load meters with green/amber/red thresholds | `Meter.tsx`, `ReportsPage.tsx`; threshold tests (rooms 70/90, load 85/100) | VERIFIED locally; thresholds are a design choice, not CdM policy |
| 41 schedulable / 12 excluded directory and restriction timeline | `BuildingsPage.tsx`; existing restriction tests | VERIFIED locally |
| Triage layout, audit table, one h1 per redesigned page | `triage.css`, `PublicationAuditPage.tsx`; `NoDeadEnds.test.tsx` | VERIFIED in jsdom and sample render |
| RBAC and optimistic revision checks unchanged | No service, API or route-guard authorization change; 1,127 web tests | VERIFIED by existing tests |
| WCAG 2.2 AA | E1 tokens retained | PARTIAL: zoom, screen reader, coarse-pointer checks open |
