# P4d Administrator workflow acceptance cases

Scope: local feature worktree only, using synthetic fixtures, a new disposable PostgreSQL cluster, the Firebase Auth Emulator, and owned loopback services. These cases are recorded before implementation. No live institutional data or hosted services are used.

## Preservation and boundaries

- Verify branch `feature/auth-onboarding-saas`, record HEAD, and preserve pre-existing dirty/untracked files. Do not stop or reconfigure the existing server on port 5173.
- Verify original SQLite hashes before and after. Mutation qualification uses an owned disposable cluster only.
- Use the row-derived November 2026 53-space catalog; 59 is stale. It remains provisional and does not establish actual availability, capacity, equipment, or institutional readiness.

## Connected Administrator lifecycle

1. Authenticate an emulator-backed synthetic Administrator; unauthenticated and non-Administrator protected calls are denied server-side.
2. Create/select an academic period and persist its configured catalog/records in PostgreSQL; verify revision increments and stale expected revisions fail.
3. Load readiness from FastAPI. Resolve a fixture blocker and observe the updated revision/readiness on dashboard without mock fallback.
4. Generate from the persisted snapshot using its revision. Verify solver status (`optimal`, `feasible`, `infeasible`, or `unknown`), diagnostics, and independent validation; `unknown` never enables save or publication.
5. Save a validated immutable PostgreSQL draft; reload list/detail and verify idempotency/replay and tenant/owner isolation.
6. Validate the exact saved input snapshot in Conflict Center. Conflicts identify assignments; a conflict-free result has zero hard conflicts.
7. Run pre-publication checks and publish with authorized identity, revision/hash binding, and idempotency. Reload the immutable published calendar and dashboard revision.
8. Read Administrator audit history for academic edits, draft saves, and publications. Wrong-role/cross-tenant reads fail, and audit events are append-only.
9. Draft changes are either unavailable and presented honestly, or selection-based, server-revalidated, revision-bound, and saved as a new immutable snapshot. Client-only mutation cannot masquerade as persistence.

## Contracts, integrity, and security

- Every mutation contract rejects unknown fields and malformed identifiers/enum values.
- Migrations upgrade on a clean disposable PostgreSQL cluster; new tenant-scoped tables have ENABLE and FORCE RLS. Cross-tenant, wrong-role, stale-revision, duplicate, invalid-status, and rollback cases are covered.
- Academic provenance and `synthetic-review` boundaries are preserved; synthetic inputs cannot publish to institutional scope.
- Errors are typed and do not expose secrets or unnecessary personal information.

## Required verification gates

- Serial full Python suite: `python -m pytest -q` from the repository root, using the feature worktree `.venv` and explicit feature package paths; preserve exact output/exit status.
- `ruff check services packages` and `python -m pip_audit` (or approved installed `pip-audit` CLI); report findings without suppressions.
- In `apps/web`: `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`.
- Run the owned Auth Emulator/PostgreSQL/Chrome connected harness on its own ports. Verify positive/negative Admin journeys. Never use the existing port 5173 process as a mutation target or stop it.
- Native Chrome 200% zoom on dashboard, academic setup, schedule generation, conflicts, and calendar; zero page horizontal overflow or clipped controls. Keyboard-only route menu, drawers, readiness, generation, validation, publication; visible focus and status announcements. Manual screen-reader testing remains separate.
- Preserve command outputs, counts, screenshots/measurements, database preservation evidence, and limitations in `docs/autonomy/evidence/p4d/` (ignored raw evidence may be linked; reproducible summaries belong in STATUS/TRACEABILITY).

## Exit decision

P4d is incomplete unless connected positive/negative journeys, all required automated gates, native 200% zoom, and keyboard/focus checks pass with fresh evidence. Missing credentials, dependency findings, pre-existing test failures, solver `unknown`, absent institutional inputs, or unavailable screen-reader/provider evidence remain open and cannot be called success.

## 18 November 2026 — fixture diagnosis and current closure evidence

The previously failing `ready.ready and offerings == 4` assertion in
`scripts/postgres_academic_repository_qualification.py` was a qualification-fixture mismatch.
It reuses `services/academic/tests/test_academic.py::complete`, which creates a SQLite
`development-entered` sandbox fixture. `PostgresAcademicRepository.create_period` uses the schema
default `data_mode='institutional'`, and `period_in` maps that to institutional readiness. The
fixture lacks Registrar/cohort, curriculum/contact-minute references, faculty verification,
approved offering references, room-availability verification, and verified operating/shared-scope
references. A disposable SQLite characterization confirmed 4 offerings, sandbox-ready, but
institutional mode correctly blocked with those requirements and `inputs=None`. The qualification
assertion now requires those blockers instead of pretending incomplete fixture data is ready. No
readiness/security rule was loosened. New regression:
`services/academic/tests/test_academic.py::test_sandbox_qualification_fixture_is_blocked_in_institutional_mode`.

Fresh full Python regression after the correction: 1093 passed, 0 failed, one Starlette deprecation
warning; Ruff passes; `pip check` reports no broken requirements. The corrected full PostgreSQL
qualification has not been verified: default `pg_ctl` startup under the current non-elevated process
fails with Windows restricted-token error 87 before the new assertion runs. The feature worktree's
`.venv` is a junction to `C:\Projects\ClassSync\.venv` shared with `main`; do not install the
security dependency into that shared environment. A separate properly isolated environment and
an elevated disposable-PG run are needed to finish the dependency/PG gates.

The independent audit review found no critical authorization/RLS defect in the added endpoint, but
left these production concerns open: the unkeyed SHA-256 entity reference can be guessed for
predictable IDs; the migration downgrade drops all activity history; events within a transaction
can tie on timestamp and sort by random UUID; the 500-row maximum has no cursor pagination; and
the UI displays stable Firebase actor UIDs. Decide the pseudonymization, retention/rollback,
ordering, pagination, and actor-display policy before production adoption. No live audit history
exists; downgrade was not run against production data.

### 18 November continuation — preview and closure status

The presentation-only browser probe and its limitation are recorded in `docs/autonomy/STATUS.md` with raw receipt `var/p4d-evidence/admin-preview-qa-20261118.json`. It verified the shared shell and keyboard route-menu/mobile-drawer behavior, but the five principal workspace routes (dashboard, academic, generation, conflict, audit) each exposed only one main control; this is insufficient to establish that their target content rendered. Calendar exposed its controls. Native 200% zoom did not run because Chrome blocked the isolated extension. Do not count this as the connected E2E or actual workspace visual gate.

Current local regression is 1093 Python tests passed, Ruff clean, and 838 frontend tests across 63 files with lint/typecheck/build passing. Full PostgreSQL academic qualification still stops before assertions because non-elevated Windows `pg_ctl` fails to create its restricted token (error 87). The shared `.venv` is a junction to the main worktree and must not be modified to apply the OpenTelemetry constraint. The pinned Auth Emulator tools remain unavailable. P4d remains **PARTIAL** until those environmental blockers are resolved and connected lifecycle/browser gates pass. Audit event pseudonymization, retention on downgrade, deterministic ordering, pagination, and actor UID display also need disposition before production.

### External environment handoff check — 18 November 2026

The proposed outside-sandbox setup is not reflected in the active feature worktree: `.venv` remains a junction to the main worktree's `.venv`; no `pip-audit` module is installed there; `py -0p` finds no system Python installations and `python` is Python 3.14, not the required 3.12; and the connected qualification exits before startup because pinned Auth Emulator tools are missing. Repository-pinned tools are `firebase-tools 15.34.1`, `@opentelemetry/core 2.8.0`, and `uuid 11.1.1`, so `npx firebase-tools@latest --version` alone is not qualification. No packages or services were changed/started. P4d remains blocked on the isolated environment and emulator/PG receipts; see STATUS for exact outputs.

### Qualification-script correction follow-up — 18 November 2026

The environment observation above is historical and superseded by the latest STATUS addendum. The
active feature worktree now has an isolated Python 3.12.10 `.venv`, retains `.venv-main-junction` to
the main worktree's environment, and has a temp root with the pinned Auth Emulator packages. All five
qualification-script defects are corrected and the focused qualification/projection suite passes 11
tests. No RLS policy, uniqueness rule, migration guard, solver constraint or domain assertion was
weakened. Ruff and `pip check` pass; frontend tests pass 838/838.

The full Python suite reported two solver-dependent failures: one multi-program result was `unknown`
at the existing 8-second limit and a draft test rejected that incomplete result. The in-sandbox
`pip-audit --strict` could not connect to PyPI; the user reports a clean external scan, but its receipt
is not yet in this worktree. The PostgreSQL/Auth Emulator scripts were deliberately not run in this
step. P4d remains **PARTIAL** until the owner reruns the disposable qualifications and supplies their
JSON receipts; connected Admin E2E, workspace browser acceptance, 200% zoom, keyboard workflow and
audit-history policy decisions remain open afterward.
