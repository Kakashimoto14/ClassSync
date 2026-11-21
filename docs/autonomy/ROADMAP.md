# ClassSync — execution roadmap and dependency gates

## 15 November 2026 — current product direction and implementation start

The owner approved the audit/master implementation plan and directed local implementation
to begin on `feature/auth-onboarding-saas`. PostgreSQL is the authoritative relational
store for membership, academics, schedules and publication; Firebase Auth proves identity;
Firestore is optional unless a verified rubric or later owner decision requires it. This
supersedes the 10 November Firestore bridge directive. Start with authority-document
reconciliation and current README maintenance, then follow the dependency-ordered tasks in
[`docs/audit/MASTER_ROADMAP.md`](../audit/MASTER_ROADMAP.md). Preserve existing work and
qualification evidence. No commit, push, merge, real-data import, original DB migration,
hosted setting, spending, or deployment is authorized by this local implementation start.

## 4 November 2026 — functional MVP M1–M5

Owner authorizes the local five-milestone implementation sequence in APPROVALS.md.
M1 account lifecycle/onboarding PASS for bounded local acceptance,4 November23:24 SGT.
Owner-approved diagnosis retained all solver/model limits/constraints/guards; final
backend968/frontend768, security17/artifact4, static/build and real emulator/PG/browser
journey pass. See STATUS.md, MVP_M1_ACCEPTANCE.md, MVP_EVIDENCE.md and final qualification.
M2 scanner PASS for bounded local acceptance,5 November03:34 SGT. Full backend986,
frontend776, static/build/security17/artifact4 and actual scanner/emulator/PG/browser
journey pass; Windows OCR only, no cloud/manual-screen-reader certification.
M3 connected schedules PASS for bounded local acceptance,5 November: full backend1003,
frontend795, static/security17/builds/artifacts4 and actual three-role publication,
request/decision/room change/rollback/readiness/revocation/SQL/browser journey pass.
Original hash mismatch explained by owner-confirmed intentional Demo save; preserved.
M4 existing features PASS locally: backend1020/frontend804/static/security/builds/
artifacts4 and connected notices/rooms/profiles/recovery/SQL/browser journey.
M5 local implementation/delivery qualified: backend1048/frontend804/security19/builds/
artifacts4 and final actual connected journey. Cloud integration, container execution,
Postman runtime and remote Actions remain unqualified; npm audit release gate BLOCKED7
moderate findings. M5 overall PARTIAL pending approved staging configuration/credentials
and secure runner/platform qualification. See MVP_M5_TRACEABILITY.md; no production release.
Supplied PDFs have been read locally.
No cloud/Git/original-data authority is expanded.

Status at harness creation is a historical snapshot, not a new repository audit. Continue only authorized work. Keep a requirement-to-test evidence matrix in `STATUS.md` or a linked file.

| Phase                                      | Definition of demonstrably done                                                                                                                                                                                                    | Requires                                                     |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| P1 Modes/release boundaries                | Presentation vs sandbox vs institutional resolver; no sandbox distributable builds; frontend API gating plus independent backend protection; compatibility matrix; artifacts/SPA tests; UI unchanged; original DB hashes preserved | Already approved local scope                                 |
| P2a Identity and membership contracts      | Explicit contracts, tenant/record membership model, typed error states, auth/authorization tests using disposable adapters, no fake production identities                                                                          | P1 pass + phase approval                                     |
| P2b PostgreSQL foundation                  | Local disposable PostgreSQL schema, relational constraints, migrations, test adapters, consistency and tenant isolation; pin versions from compatibility evidence                                                                  | P2a + phase approval; no original-data cutover               |
| P3a Firebase Auth and actual authorization | Verified ID token, current DB-backed membership, authenticated lifecycle and denied access, staging/emulator negative-path tests                                                                                                   | P2b and access/config approvals for any real external change |
| P3b Full repository adaptation             | Replace approved SQLite adapters with PostgreSQL adapters, deterministic migration rehearsal, checksums, indexes and rollback tests; live cutover separately gated                                                                 | P3a; original DB remains intact absent cutover permission    |
| P4 Academic inputs/readiness               | Periods, curriculum, offerings, faculty, rooms, availability, calendars and enrollment modeling; honest missing-info blockers and provenance; verified pilot scope required for live pilot                                         | P3b; actual institutional data only with permission          |
| P5 Durable generation                      | Real ready-period → OR-Tools run → independently validated durable draft, across restart/session; robust unknown/infeasible states, deduplication, scaling benchmarks                                                              | P4 readiness and solver correctness                          |
| P6 Review/approval                         | Admin edit/reassign/revalidate, optimistic revisions, scoped approval and conflict recovery, auditable change history                                                                                                              | P5                                                           |
| P7 Atomic publish                          | Transactional head/version publication, immutable snapshots and role projections, idempotency, concurrent publish/revoke/stale-input tests, outbox                                                                                 | P3b + P6                                                     |
| P8 Connected experience                    | Real student/teacher calendars, administrator state, faculty requests, version-aware realtime and alerts; premium Soft Rouge responsive UI, accessibility, dark mode if approved                                                   | P7, policy decision for approvals/notifications              |
| P9 Infrastructure/qualification            | Authorized staging, reproducible deploys, secrets, backups, restore, monitoring, audit/security/privacy/rate-limit/scale/accessibility and manual acceptance                                                                       | Cloud/privacy/budget approvals                               |
| P10 Supervised pilot                       | Real institutional identities and approved data, smoke/e2e for all three roles, release evidence, gradual cutover and rollback                                                                                                     | P9 + institutional release authorization                     |

## No skipped work rules

- UI quality, privacy/security, tests, docs and error handling are _cross-cutting_, not deferred until P8/P9.
- A partial phase is PARTIAL. A phase is PASS only when the acceptance criteria are proven by freshly run commands and real workflows (or labelled as awaiting unavailable external verification).
- No `UNKNOWN` solver solution, unresolved critical security path, database inconsistency, false-authenticated identity or missing institutional approval may be reclassified as PASS.
- If blocked by an external gate, work on an independent approved improvement or document the exact dependency; do not jump past the gate.

## Verified local checkpoint — 26 October 2026

P1, P2a and bounded local P2b passed with fresh code, actual isolated PostgreSQL/migration/RLS/audit/concurrency/restore/failure evidence, full relevant regressions and independent reviews. See STATUS and `docs/production/local-20261026/p2b-exit-gap-review.md` for exact results/limits. P3a local synthetic/emulator composition is next. No institutional policy, real accounts/data, live provider/configuration, original-data cutover or release approval follows from these local gates.

## Current local checkpoint — 27 October 2026

Bounded emulator/local P3a passes, including actual Auth Emulator/Gateway/current-PG browser lifecycle and negative paths. P3b remains PARTIAL: complete academic adapter/generated migration/provider/restore and immutable draft adapter/Scheduling owned provider now qualify locally. Latest bounded exit backend492/492, security16/16, Python68/0, actual SDK/current-PG HTTP plus owned postmaster/provider restart, independent review and unchanged originals. Same-session unchanged frontend709/40/build/artifact checks remain dated evidence. Next is generated-only Scheduling run/draft migration and backup/restore proof, then publication adaptation/provider and full P3b exit. Original SQLite/default production configuration are unchanged; publication is unavailable in PG mode. See STATUS for exact scope/limits; production NO-GO. This supersedes earlier next-task pointers, not historical results.

## Latest bounded P3b checkpoint — 28 October 2026

Generated Scheduling migration and complete identity/academic/draft restore now qualify locally: actual PG exact content/authority/rollback/owner/expiry/revocation proof, backend607/security16, portable63+52, independent review and unchanged originals/stopped clusters. Full P3b remains PARTIAL. Next: publication PostgreSQL schema/data-access boundary, then provider adoption and complete P3b exit. Keep PG publication unavailable until qualified; P4 cannot advance yet. See STATUS for command/evidence/limitations.

## Latest bounded checkpoint — 28 October 2026 02:40

Shared publication rules/workload correction and PostgreSQL publication-state schema foundation now qualify locally. Latest backend678/security16/Python68-0/wheel15/actual PG ownership and atomic-state evidence; originals unchanged. Full P3b remains PARTIAL. Next: publication application repository/transaction/room restriction adaptation and actual failure/concurrency qualification, then guarded provider adoption/history migration/restore/full exit. Publication remains unavailable in PG mode; P4 cannot advance yet. See STATUS for precise limits and commands.

## High-priority UI/UX recovery — owner direction, 28 October 2026

PLANNED; implementation follows the unfinished PostgreSQL publication repository acceptance gate. Source: [owner screenshot audit](ClassSync_UIUX_Screenshot_Audit_2026-10-28.md). The requested shorter audit filename is absent; this existing file contains the supplied findings. Its screenshots are reported evidence, not a fresh browser inspection.

1. Diagnose the connected timetable failure through the actual request, proxy, identity and publication provider chain. Distinguish unavailable service, denied access and no published timetable; provide actionable accessible recovery without sample fallback. Do not bypass the PostgreSQL publication qualification gate to clear the message.
2. Correct presentation synchronization language: an offline read-only sample must not claim live reconnecting or synchronization. Add mode-boundary regression coverage.
3. Student Home: trustworthy next class, today's agenda, weekly overview and relevant published changes, backed by the authorized source. Verify loading, unavailable, empty, unassigned, no-classes, multiple-classes and stale-data states.
4. Teacher Home and requests: today's teaching, next assignment, actual pending requests and decisions, working contextual actions. Preserve server authorization and explicit unavailable states.
5. Administrator: simplify period selection, academic readiness/blockers and generate/review/approve/publish progression. Use actual counts and statuses; keep unavailable approval/publication actions honest.
6. Simplify shared navigation and copy: canonical destinations, concise persistent mode indicator, details by disclosure, useful desktop density and legible mobile Soft Rouge layouts. Remove prominent nonfunctional destinations rather than imply completion.

Execute bounded screen-family slices alongside the dependency-ready authorized roadmap after the backend gate; this track does not waive P3b–P7 dependencies or grant institutional authority. Each slice requires real before/after screenshots, working actions and negative paths, independent review, relevant regression tests, 360/390/768/1024/1440 widths, keyboard/focus and native 200% zoom. Manual screen-reader checks remain unverified until performed. No fake data, statistics, alerts or decorative widgets.

### Current Administrator entry-flow slice — 15 November 2026

Implemented locally with the current Phase 1.3 academic-input work: no-period Academic Setup now
shows its configuration map before selection; development mode and sample import are clearly
separated; period-scoped categories are consolidated under one sidebar entry and remain searchable;
generation is labeled as deterministic Schedule Generation; and Conflict Center empty states link
to setup/generation. Source-level route inventory and screenshot findings are in
[`docs/hci/admin-workspace-audit.md`](../hci/admin-workspace-audit.md). This is a partial
implementation only. The two supplied screenshots predate these changes; no new rendered browser
screenshots, responsive matrix, 200% zoom, manual keyboard, or screen-reader results are claimed.
Audit/visual acceptance for remaining preview-only Admin screens is open.

### Administrator dashboard command-center slice — 16 November 2026

The owner approved and the feature worktree now implements the connected dashboard hierarchy in [AdminSchedulingHome](../../apps/web/src/pages/AdminSchedulingHome.tsx): inline period selection, period-scoped KPI links, a unified readiness card with typed issue destinations, and separate publication/draft snapshots. [AppShell](../../apps/web/src/components/layout/AppShell.tsx) now presents an Administrator-only route picker; Student and Teacher destination search remains unchanged. Scoped dashboard/shell styles keep responsive layout, focus indication, reduced-motion behavior, and a thinner sidebar scrollbar. README and the detailed [file-by-file implementation plan](../hci/admin-dashboard-command-center-plan.md) are synchronized.

Focused UI regression is **49/49 across 5 files**; frontend typecheck, lint, and production build pass. The full web suite has three room/building presentation expectation failures against the already-updated room catalog (two expected-card-count mismatches and one missing Court link label); these remain open and were not altered in this dashboard slice. Browser screenshot, viewport/zoom rendering, manual assistive-technology, and real API/provider acceptance remain unverified because the local ports were not listening and Playwright is not installed in this worktree. This slice is implemented locally but not marked visual/production PASS.

## Historical P3b checkpoint — 29 October 2026 (superseded below)

The PostgreSQL repository and 0008 rollback/reapply had actual disposable-PG acceptance. Institutional API composition and migration0009 route configured publication, calendar, period, availability and restriction operations through the PG repository and define current Student/Teacher record-level RLS projection; the synthetic sandbox stays unavailable. The verified-role route correction covers Student/Teacher/Administrator timetable routes in mocked HTTP composition tests (17 focused tests; 703 scheduling/persistence tests pass). Provider composition and migrations0009/0010 remain **IMPLEMENTED-UNVERIFIED** because Windows initdb/pg_ctl failed before startup while creating its restricted process token; the separately running local PostgreSQL service requires a password and is not the owned disposable cluster. Migration0010 now adds a separate append-only admin-scoped archive for legacy publication history; its generated SQLite fixture/import/rollback exercise is implemented but not executed. See the latest STATUS entry. P3b remains PARTIAL pending actual disposable-PG execution, archive backup/restore evidence, and remaining phase-exit checks. Preserve the UI/UX track above; do not claim screenshot verification or skip backend dependencies.

29 October update: the owner's saved `migration-chain-0010-schema-fixed.json`
verifies the complete migration/archive gate through0010, with the cluster stopped.
Publication then failed on a confirmed RLS cycle. Forward migration0011 removes
only the version INSERT policy's head dependency; targeted portable checks pass,
the actual correction and publication acceptance are now verified by the evidence
summarized below. Historical pending and failed checkpoints above remain history.

Current 29 October evidence: publication repository0011, full generated
publication/archive restore, and actual Auth SDK/current-PG publication HTTP and
three-role projections **PASS**. Final serial backend947, frontend712/40,
lint/typecheck/security/audits and internal wheels pass. The first restricted-token
web test timeout is retained; the unchanged approved retry passed. Both final builds
and all4 artifact checks also pass. The approved bounded local **P3b exit is PASS**;
see STATUS and `../production/local-20261029/p3b-exit-evidence.json`. This Goal stops
at P3b. UI/UX recovery remains the prioritized subsequent bounded milestone; no
P4–P8 work or production authority follows automatically.

## Current bounded Student recovery checkpoint — 30 October 2026

Owner's current task names **P4a connected application recovery / P4b Student experience**; this bounded UI priority follows the P3b PASS above and takes precedence over older numbered planning labels for this session only. Authorization and one consumed serial-retry limit are in APPROVALS.md.

| Milestone                      | Current evidence                                                                                                                                                                                                                     | Exit                                                                               |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| P4a connected recovery         | Actual Auth/current-PG/TCP Student journey including outage recovery, denied/revoked/unassigned, navigation/refresh/logout and native200; fixture setup pools released before service handoff; final patched Vite6.4.5 qualification | **PASS bounded local**; zero healthy503s; production/manual screen reader excluded |
| P4b Student product experience | Soft Rouge Home, readable period/full title, UUID disclosure, compact Next Class/event hierarchy, actual scoped class-room action, all five widths and safe navigation                                                               | **PASS bounded local**; Teacher/Admin redesign deferred                            |
| P4c Teacher                    | Compact teaching agenda, actual requests/decisions and role browser acceptance                                                                                                                                                       | PLANNED; not started                                                               |
| P4d Administrator              | Readiness/blocker and generate-review-approve-publish hierarchy; actual task and responsive browser acceptance                                                                                                                       | PARTIAL: local audit trail added; full connected lifecycle and accessibility gates remain blocked/unverified; see latest STATUS and P4D evidence |

Current commands, truthful pass/failure counts, screenshot provenance, one independent review and requirement traceability: [P4_EVIDENCE.md](P4_EVIDENCE.md), [P4_ACCEPTANCE.md](P4_ACCEPTANCE.md), and latest STATUS entry. All original DB hashes and61 P3b backend/package hashes unchanged; all new owned services stopped. The initial one-retry stop remains historical. The owner subsequently reopened bounded stability recovery. Current P4a/P4b exit is **PASS**; see [P4_STABILITY_EVIDENCE.md](P4_STABILITY_EVIDENCE.md) and latest STATUS. **Stop at P4a/P4b; no P4c/P4d, infrastructure redesign or production authority.** Never substitute presentation data for a failed connected request.

## Student refinement follow-up — 30 October 2026

**PASS bounded local; STOP.** Owner's preferred-mockup Student refinement completed after P4 stability exit. Home, Student Schedule, four-destination navigation, room/source separation, validated richer synthetic fixtures, connected recovery and all final gates are verified in [STUDENT_REFINEMENT_EVIDENCE.md](STUDENT_REFINEMENT_EVIDENCE.md). No Teacher/Admin redesign began.

Remaining separately approved backlog: P4c teaching agenda + real request/status usability and role acceptance; P4d period/readiness/blocker hierarchy + generate/validate/review/approve/publish task usability and role acceptance. Manual assistive technology and production/institutional acceptance remain open; unsupported push delivery and physical room availability remain honest unavailable states.

## Campus Companion visual milestone — PARTIAL, approval required

Student-scoped visual changes are implemented in part. A repeated institutional label test failure triggered AGENTS.md's persistent-failure stop gate; see latest STATUS entry and `../production/student-visual-20261030/` logs. The proposed correction is to restore ` · University` for institutional Student accounts in the formatted sidebar JSX, then verify the affected test and milestone gates. Do not mark this milestone PASS until completed; P4c/P4d remain deferred.

## Selected Claude Student implementation — PARTIAL

Prior sidebar recovery passed under explicit approval. Actual selected-design code now spans shell, Home, Schedule, Rooms and Alerts; see CLAUDE_STUDENT_IMPLEMENTATION.md and phase captures. A new month-navigation test failed twice and triggers the persistent-failure gate. Approval needed for bounded correction/retest before final fidelity and acceptance checks. This supersedes only the former unresolved sidebar blocker; no PASS claimed for the new design. Teacher/Admin redesign remains deferred.

## Student Rooms refinement — PASS locally, 30 October 2026

Search-first Student Rooms shipped locally with strict timetable-derived My rooms, preview-only59-space All rooms, honest Labs state and retained-context details. Full frontend752, affected backend125, security17, artifacts4; connected outage/recovery and five-width/native200 acceptance; all64 preservation hashes match. See STUDENT_ROOMS_EVIDENCE.md. Prior visual milestone history remains separate; this bounded Rooms checkpoint is accepted. No Teacher/Admin redesign or deployment. Future separately scoped work: qualified tenant directory/lab metadata/physical availability sources, manual assistive-technology and production acceptance; P4c/P4d require separate authorization. STOP at Student Rooms.

## Three-job CI repair — PARTIAL / dependency security BLOCKED, 31 October2026

Web test clock and Python module invocation corrections implemented. Focused6 pass;947 backend cases collected; clean npm ci/npm ls pass. Full qualification incomplete: frontend300s guard, fresh Python setup180s twice. Stop at gate; see CI_REPAIR_EVIDENCE.md for bounded continuation requiring owner approval. minimatch advisory remains12 moderate with no compatible stable parent upgrade; security policy unchanged. No GitHub pass/commit/deployment. Preserve accepted Student Rooms; no new product scope.

## 31 October 2026 — institutional schedule review checkpoint

Owner-confirmed green BSIT 3A priority correction and twelve-session isolated file staging COMPLETE; pink superseded,3B currency unconfirmed, NB107 separate/undated. See ../academic/review-20261031/README.md for current dataset/source register/missing information and STATUS for fresh checks. Contract validation/observed minutes/within-section overlaps VERIFIED; Registrar reconciliation, full scheduling acceptance and PG import BLOCKED on missing authorized inputs. STOP before institutional accounts/import/publication/deployment; CI repair gate remains separate and unchanged.

## Approved CI qualification outcome — 31 October2026

WEB PASS754/46 in219.68s; web gates/security17/artifacts4/builds green. PYTHON PARTIAL934 pass/13 fail of947 in120.08s due runner's non-OS-temp basetemp; guards unchanged, no second full run. New local audit:4 pyasn1.6.4 advisories with.6.5 fix. minimatch remains separately BLOCKED; bounded assessment found no supported parent upgrade and no production dependency path. All70 hashes preserved. See latest CI_REPAIR_EVIDENCE.md appendix. Stop; next separately authorized work is compatible Python dependency remediation plus plain python-mpytest qualification; Node audit remains blocking until upstream support or explicit policy decision. No remote-green/commit/deployment claim.

## Cohort-aware curriculum and synthetic BSIT pilot — PASS locally, 3 November 2026

Implemented the versioned 39-source catalog, immutable entry-cohort bindings, structured sections, Administrator review/readiness, and synthetic-only BSIT Years 1–4 pilot using existing PostgreSQL, OR-Tools, independent validation and publication safeguards. Final serial backend suite **790 passed**; disposable PostgreSQL end-to-end synthetic qualification, frontend typecheck/lint/build, five-width/native200 browser fixture, focused/full frontend results, security suite and original-database preservation are recorded in [COHORT_PILOT_EVIDENCE.md](COHORT_PILOT_EVIDENCE.md). Green BSIT3A remains separately file-staged current evidence; pink is superseded; Registrar codes, active term/sections, Tuesday room, room identities, faculty, contact minutes and campus-wide locks remain unresolved. Stop at this first pilot. Do not promote it into institutional records or publication; later approved import requires the evidence listed in the pilot report. Existing dependency audit blockers remain separate.

## Real academic-data readiness — PASS bounded local, 3 November 2026

Administrator data capture, verification references, institutional readiness blockers, same-period ICS/IBE/ITE scope review, structured fixed assignments, and the BSIT Years 1–4 readiness report are complete. Final academic/scheduling regression: **395 passed**; focused Admin **11 passed**; typecheck/lint/build/Ruff and review-only source reconciliation passed. Migration `0013_synthetic_review_period_mode` keeps synthetic reviews isolated from institutional periods; final disposable PostgreSQL qualification passed with **54 independently validated sessions**, institutional synthetic-write denials, role/tenant/RLS/rollback checks, and synthetic-to-institutional publication denial. Evidence: [REAL_ACADEMIC_READINESS_EVIDENCE.md](REAL_ACADEMIC_READINESS_EVIDENCE.md), [BSIT readiness report](../academic/real-academic-readiness-20261103/BSIT_YEARS_1_TO_4_READINESS.md), and [PostgreSQL evidence](../production/real-academic-readiness-20261103/postgres-synthetic-mode-final.json).

Real scheduling remains BLOCKED pending the Registrar-approved cohort/source/code/minute decisions, actual period/calendar, sections/populations/offerings, authentic faculty, verified rooms, effective NB 107 date, cross-institute commitment inventory, and supervised-pilot authority listed in the report. No institutional import, account provisioning, publication, deployment, commit or push. STOP at this milestone; Teacher/Admin visual redesign is out of scope.

## Administrator workspace density and responsive repair — current slice

Owner-approved continuation on `feature/auth-onboarding-saas`: fix the active topbar command-menu overlay; keep Academic Setup to a compact period workspace with one selected setup category; add selection-based status/category filters; reduce generation and conflict-center vertical bloat; compact classroom-request and notification rows; prevent status/action labels from breaking. Preserve API behavior and be explicit that Notifications are still demonstration-only. The current November 2026 room catalog has four grouped locations, so directory regression expectations must follow that source instead of the former three-group/59-space assumptions.

Exit gates: verify current branch and preserve existing dirty changes; topbar is capped at 64px and command popover is absolutely positioned in the loaded stylesheet; active academic category switches and retains CRUD forms; role/API requests and publication semantics stay unchanged; responsive controls fit 360–1024 and desktop dimensions without forced word splitting; web typecheck, lint, build and full frontend tests pass; real browser rendering at target widths and keyboard/reduced-motion checks are recorded or marked UNVERIFIED. No backend, data, branch, provider or deployment changes.

### Command-menu visual and build qualification follow-up — PASS local, 16 November 2026

Owner-authorized follow-up corrected neutral/current/focus menu colors, two-column category layout with single-column links, scroll-bottom breathing room, consistent Firebase app imports, and Vite `react-vendor` / `firebase-vendor` / `ui-vendor` splitting. Real local Chrome/Playwright verified the topbar and all destination labels at 1366×768, 1440×900 and 1024×768, then verified Academic Setup, Schedule Generation, Conflict Center, Requests and Notifications at 1366×768 and 390×844 without horizontal overflow. `npm run lint`, `npm run typecheck`, `npm run test` (837/837, 62 files), `npm run build` and `git diff --check` pass. Bundle chunks are 319 kB, 243 kB, 47 kB and 321 kB; no Vite chunk-size or mixed Firebase import warning remains. Preview browser evidence is local UI only; connected provider/data, 200% zoom and assistive technology gates remain open. See latest `STATUS.md` for exact measurements.

### P4d Administrator workflow completion — PARTIAL, 18 November 2026

Local implementation and checks on `feature/auth-onboarding-saas` added PostgreSQL-backed, append-only redacted Administrator activity events for academic period/record/calendar changes, draft saves and publications; a tenant-scoped Administrator-only read endpoint and UI; and a disposable-PostgreSQL qualification mode. The complete fresh serial Python suite passes 1092 tests, web gates pass 838 tests, Ruff passes and the production build has no chunk-size/Firebase mixed-import warning. The activity-only PostgreSQL slice passed same-tenant Admin read, cross-tenant RLS denial and append-only checks (78 synthetic events). P4d is not complete: one current Python advisory remains (CVE-2026-126360 in opentelemetry-api 1.45.1; compatible fixed version 1.45.2 is constrained but could not be installed after the approval service usage limit), complete academic PostgreSQL qualification later fails its readiness fixture contract, the pinned Auth Emulator harness cannot start, and no connected browser, native 200% zoom or keyboard-only end-to-end evidence exists. Exact outputs, paths, and limits are in the latest `STATUS.md` entry and `docs/autonomy/P4D_ADMIN_ACCEPTANCE.md`.

18 November continuation diagnosed that assertion as a harness mismatch: the SQLite `complete()` fixture is ready only as `development-entered`, while PostgreSQL creates `institutional` periods and correctly requires verification references. Added a regression characterization and changed the qualification to require the exact institutional blockers; full suite is now **1093 passed**. This corrected full PostgreSQL qualification remains unverified because the non-elevated Windows `pg_ctl` startup fails before the assertion with restricted-token error 87. The worktree `.venv` is a junction to the main worktree's environment, so dependency installation there is not safe. Independent review found no critical RLS/authorization defect; five medium/low audit privacy/retention/order/pagination/actor-display concerns are recorded in P4D acceptance and must be decided before production. Other dependency scan, Auth Emulator, connected browser and 200%/keyboard gates remain open.

### P4d continuation — 18 November 2026

The readiness-fixture mismatch correction is covered by a regression test and the full Python suite (1093 passed); frontend lint, typecheck, 838 tests and production build pass, and Ruff is clean. No vulnerability-free claim is made: the installed OpenTelemetry advisory could not be remediated in the shared `.venv`, and a fresh scan is pending. The corrected full disposable PostgreSQL qualification is blocked before test execution by Windows `pg_ctl` restricted-token error 87. A separate presentation preview confirms shell dimensions and keyboard menu/drawer behavior only; most target routes rendered a preview gate, so actual Admin screen acceptance is still open. Native 200% zoom was not measured. P4d remains PARTIAL pending isolated dependency/PG qualification, Auth Emulator tools, connected create-to-publish browser journey, workspace zoom/accessibility checks, and audit-history privacy/retention decisions.

### External environment handoff — verification result, 18 November 2026

The claimed setup was not visible to the current feature worktree: `.venv` remained a junction to the main environment, pip-audit was absent, no system Python 3.12 was registered, and the pinned Auth Emulator runner exited before starting. The repository pins the emulator toolchain rather than accepting `firebase-tools@latest`. No setup, PostgreSQL or connected E2E PASS is recorded. Continue only after the isolated Python 3.12, pinned tools, and disposable qualification receipts are available.

### PostgreSQL qualification-script synchronization — IMPLEMENTED, awaiting disposable qualification, 18 November 2026

The environment statement immediately above is superseded by the latest STATUS addendum: the
feature worktree now contains Python 3.12.10 and the pinned Auth Emulator package versions in an
isolated temp root. Five qualification defects were corrected: non-BYPASSRLS migration-owner use
in the academic-period qualification; exact current provisional-catalog assertion without inferred
capacity; migration ordering/current-head alignment before `period_metadata.data_mode` writes;
unique synthetic account-to-student records across emulator/provider fixtures; and dynamic current
Alembic-head checking in the scheduling provider qualification. Focused regression tests pass 11/11,
Ruff passes, pip check is clean and Web tests pass 838/838. The serial Python suite still has two
solver-dependent failures (the existing 8-second multi-program `unknown` and a draft test dependent
on complete solver output); neither was altered. The sandbox's strict pip-audit invocation was
blocked from reaching PyPI, while the owner reports a clean external scan that is still awaiting its
receipt. Next task: owner reruns the five corrected disposable PostgreSQL qualifications and Auth
Emulator qualification in normal PowerShell; then attach receipts and continue connected P4d E2E.
Do not mark P4d complete from unit tests alone.

### Local feature continuation — active; external qualification deferred, 18 November 2026

Owner direction supersedes earlier manual-receipt prerequisites for local feature development:
do not block on external PowerShell qualification receipts, disposable PostgreSQL `pg_ctl` runs,
or isolated `pip-audit` tool environments. These remain CI/pre-release gates. Current fast local
gates are fresh: full Python 1115 passed, Web 843 passed across 63 files, Web lint/typecheck/build
pass, Ruff passes. Student ID and lowercase institutional email validation now lead to an exact,
active Registrar roster match at Gateway; no roster import or migration was executed. Continue with
small authorized application features and their in-process tests, while keeping PostgreSQL/RLS,
dependency scan, Auth Emulator, connected lifecycle E2E, native 200% and keyboard gates explicitly
open. Do not commit, switch branches or merge until the entire dirty diff and target worktree are
reviewed and staging paths are grouped safely.

## 21 November 2026 — email-neutral onboarding / COR work

This local implementation adds domain-neutral normalized email validation, a configurable `cor_or_roster` onboarding mode, a strict-roster option, verified-email/COR account activation, duplicate student-number protection, branded Firebase action-email routing, resend cooldowns, student-number formatting, compact COR review and a four-step Admin setup journey. Current evidence and exact files are recorded in [STATUS.md](STATUS.md).

Dependency-ordered remaining work:

1. Diagnose the scheduling draft regression that returns CP-SAT `unknown` under the existing 8-second limit; preserve constraints, timeout, and the repository's rejection of nonvalidated output.
2. Apply migration `0021_student_email_and_cor_source` to a disposable PostgreSQL database and verify upgrade/downgrade refusal, tenant RLS, COR activation transactionality, duplicate claim conflicts, and rollback behavior.
3. Replace process-local email/IP cooldown coordination with shared storage before multi-instance deployment.
4. Verify Firebase Admin action-code generation, Brevo/Resend delivery, Turnstile, and registered-roster/COR matching in isolated provider/emulator fixtures.
5. Re-run full suites and connected browser/accessibility acceptance. Current local full Python run is 1156/1157 due solver `unknown`; direct web run is 859/859, lint/typecheck/Ruff/build pass. These local checks do not qualify production providers or deployment.

No hosted deployment, original database migration, institutional import, or release is authorized by this entry.
