# Real academic-data readiness — bounded milestone evidence

Date: 3 November 2026. Base/current HEAD: `aea9494db46153672a31a2161070e5e4ff713966` (work remains local and uncommitted). Owner authorization: [APPROVALS.md](APPROVALS.md). Acceptance: [REAL_ACADEMIC_READINESS_ACCEPTANCE.md](REAL_ACADEMIC_READINESS_ACCEPTANCE.md).

## Deliverables and traceability

| Requirement | Result | Evidence |
|---|---|---|
| BSIT cohort/source reconciliation | 39 versions and 2,062 extracted rows across 8 programs reconcile structurally; five BSIT cohort candidates retained, none Registrar-approved; 36 adjacent code changes remain candidate-only. | [BSIT Years 1–4 report](../academic/real-academic-readiness-20261103/BSIT_YEARS_1_TO_4_READINESS.md), cohort CSVs, source review catalog |
| Requirements versus term offerings | 27 first-semester BSIT course rows remain prospectus-only review inputs. Printed lec/lab hours are not meeting minutes. No offering or equivalent code was promoted. | `bsit-first-semester-requirements-review-only.csv`, `green-bsit3a-curriculum-reconciliation.csv` |
| Current/superseded timetable evidence | Green BSIT3A remains owner-confirmed operational reference (12 sessions); Tue ITOPSYS is tentative with null room. Pink is superseded; BSIT3B currency is unknown. NB 107 is separate from PRRC 107; room-image effective date is unknown. | [31 October source-priority register](../academic/review-20261031/README.md), preserved source images/hashes, current CSV/JSON |
| Administrator data entry/readiness | Existing period, curriculum, section, faculty, resource, offering and constraints forms now collect verification references. Calendar starts blank; fixed assignments use structured offering/faculty/room choices; scope review covers same-period ICS/IBE/ITE commitments. Changed verified values clear the related review flag. | `AcademicCalendarEditor.tsx`, `AcademicRecordEditor.tsx`, `LockedAssignmentsEditor.tsx`, `academic_input.py`, generated API/shared contracts |
| Shared institute conflicts | Cross-institute programs in one period share stable faculty/room identities and fixed assignments. Solver plus independent validator accept nonoverlapping locks and reject colliding shared-resource locks. Separate periods are not compared. | `test_independent_validation_feasible_infeasible_and_cross_institute_locks` |
| Isolated PostgreSQL pilot | PostgreSQL 18.6 disposable SSPI cluster: 39 versions, 27 hypothetical offerings, 81 synthetic candidates, 54 feasible sessions, independent validation, draft replay/revision, tenant/RLS/role checks, rollback, and rejected synthetic-to-institutional publication with unchanged publication state. Institutional periods default to institutional mode; synthetic faculty/room writes are denied there; synthetic-review periods are separately persisted and hidden from the institutional period list. Cluster stopped; `real_publication=false`. | [PostgreSQL evidence](../production/real-academic-readiness-20261103/postgres-synthetic-mode-final.json), `scripts/postgres_cohort_pilot_qualification.py`, migration `0013_synthetic_review_period_mode` |
| Original database preservation | Qualification compared academic, scheduling and backup SQLite SHA-256 values to the existing P1 baseline; all match. | PostgreSQL evidence JSON and baseline `docs/production/p1-database-preservation.json` |

## Fresh verification

- `.venv/Scripts/python.exe -m pytest services/academic services/scheduling -q` — **395 passed**, one existing Starlette/httpx deprecation warning, 81.67 seconds.
- `npm run typecheck --workspace=@classync/web` — passed.
- `npm run lint --workspace=@classync/web` — passed.
- `npm run test --workspace=@classync/web -- --pool=threads src/pages/AcademicManagementPage.test.tsx` — **11 passed**.
- `npm run build --workspace=@classync/web` — passed; existing Firebase dynamic-import/chunk and >500 kB bundle warnings remain.
- `.venv/Scripts/ruff.exe check services/academic/app services/scheduling/app scripts/postgres_academic_restore_qualification.py scripts/postgres_cohort_pilot_qualification.py` — passed after final formatting.
- `.venv/Scripts/python.exe scripts/build_real_academic_readiness_review.py` — `PASS_REVIEW_ONLY`; 39/39 versions, 2,062/2,062 course rows, 0 structural differences, 27 pilot requirement rows, 36 unresolved code-change candidates, 12 green sessions.
- `git diff --check` — passed (Git reports existing line-ending conversion notices).

An earlier broad test attempt exposed the interaction between synthetic test fixtures and population verification. The scope was corrected so complete synthetic scenarios remain simulation-only; institutional scopes still require verified population and institutional references. Final PostgreSQL qualification exposed that the shared restore fixture intentionally begins at migration 0005; the cohort test now defers its fixture until after the production migration authorization check and the 0013 upgrade/downgrade/reapply cycle. The final run verified migration revision and column, synthetic write isolation, period visibility and publication denial on a new, stopped cluster. No test gate or solver limit was relaxed.

## Remaining blockers before supervised real-data pilot

The application is prepared to accept reviewed data; real institutional scheduling is **not ready**. Obtain the Registrar-approved source/version for each cohort and exact code/equivalency decisions (including `ITASE1`/`ITIASE1`, `ITELECT3`/`ITELEC3`, and `ITDMATH`); approved contact minutes/patterns; the actual term/calendar; real section IDs, cohort bindings and aggregate populations; confirmed term offerings; authentic faculty eligibility, availability and workload; physical room IDs, status, capacity, equipment, operating windows and blocks; effective date/authority for NB 107; current BSIT3B evidence if needed; and the full shared ICS/IBE/ITE room/faculty/fixed-commitment scope. Name an authorized Administrator and provide supervised-pilot, data/privacy, rollback and publication-stop procedures.

Synthetic candidates and provisional rooms remain disallowed for institutional readiness/publication. No real roster, faculty, room or timetable was imported. No institutional account, production provisioning, cloud change, deployment, commit, push or real publication occurred. Stop here; Teacher/Admin visual redesign and later production work are outside this milestone.
