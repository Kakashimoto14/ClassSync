# ClassSync — Codex Engineering Instructions

These instructions apply to the entire repository. Inspect existing repository instructions before adding or replacing this file, and preserve any more specific nested instructions.

## Mission
Build a genuinely functioning, maintainable, accessible and secure university classroom scheduling, room-availability, conflict-prevention and publication system for Student, Teacher and Administrator roles. Meet verified capstone/course rubrics. Never substitute demonstration data or a successful build for live functional acceptance.

## Source of truth and honesty
- Actual current code, schema, contract and fresh tests outrank stale documentation. Reconcile disagreements and update docs as authorized.
- Distinguish VERIFIED / IMPLEMENTED-UNVERIFIED / PLANNED / BLOCKED. An earlier report is not current evidence.
- Never invent CdM policy, programs, curriculum, room equipment/capacity, teacher availability, enrollment, consent, costs, institutional delegation or hosting authorization.
- Inspect `docs/autonomy/STATUS.md`, `ROADMAP.md`, `QUALITY_GATES.md`, `APPROVALS.md` and `GOALS.md` at the start of every work session. Update status/evidence after each accepted milestone.
- Do not falsely report that tests, scans, screenshots, deployments or cloud checks happened.

## Architecture and existing behavior
- Preserve React + TypeScript + Vite frontend; Python FastAPI gateway/academic/scheduling services; OR-Tools CP-SAT plus independent validation; Firebase Auth direction; and existing three-role routing/workflows.
- PostgreSQL is selected as the future authoritative relational academic/scheduling datastore. Existing SQLite is current local storage until authorized, rehearsed migration. Prefer SQLAlchemy/Alembic when implementation conditions support them. Data access should be isolated, but Firestore is not automatically interchangeable.
- Firebase Authentication proves identity; backend authorization must check verified identity plus current institutional role/tenant/record membership. Preview role is NOT an institutional identity.
- Firestore is optional unless an approved coursework rubric requires it; any Firebase projection cannot be a second writable official timetable source.
- Preserve Soft Rouge design language unless redesign is approved. Optimize mobile-first and desktop teacher/admin workspaces. Reuse existing design system and meaningful interactions.
- Existing development sandbox and read-only presentation cannot be mistaken for production identity or schedule authority.

## Operational loop — run without routine user prompts
1. Read current scope, approvals, source, tests, and the latest working tree. Protect any user/uncommitted work; never reset, overwrite, stash, rebase or discard it.
2. Select the next *authorized*, dependency-ready, smallest demonstrable task from `ROADMAP.md`; write its acceptance cases before implementation.
3. Implement with targeted changes, tests, rollback awareness, and observable error states; do not perform major unnecessary rewrites.
4. Run relevant unit, integration, authorization, data-integrity, performance and UI checks. Use independent review: examine diff and test coverage as if you did not write it. For security-sensitive changes, use an independent reviewer/subagent when available, but do not treat its conclusion as proof.
5. Fix failures and retest; do not skip or relax gates, add `skip`/`xfail`, change hard constraints or fake data to achieve green status.
6. Append concrete evidence to `docs/autonomy/STATUS.md`: timestamp, base/current SHA, files, commands/results, coverage, new risks, data preservation, and next task. Maintain a requirements traceability matrix as deliverables emerge.
7. Advance automatically to the next *authorized* local task only after applicable gates pass. If blocked, pursue another independent authorized task if safe; never disguise a blocker as complete.
8. If continuing in a future session, re-read repository state and resume from evidence, not previous chat assumptions.

## Mandatory quality bars
- Frontend: WCAG 2.2 AA-oriented implementation, keyboard navigation/focus, labels and announcements, forms/error recovery, responsive 360/390/768/1024/1440px, native 200% zoom, light/dark if required by approved roadmap, actual 3-role task journeys. Test with rendered browsers when available. Report manual screen-reader/unverified checks as open.
- Schedule: enforce room/faculty/section/student overlap, verified eligibility, operating hours, resource capacity/equipment, contact minutes, calendars, publication revision state, constraints/optimizations. `UNKNOWN`/infeasible is never success. Independently validate solver output.
- Publication: server-side authorization; revision/hash-bound approval; atomic consistency, concurrency/idempotency, immutable published versions, audited changes, and post-commit delivery. No student/teacher private draft leakage.
- Database: integrity, constraints, transaction semantics, migrations with rehearsal/backups/rollback, tenant/record isolation, no silent read fallback to sample data.
- Security: input validation, OWASP ASVS-aligned coverage, secrets hygiene, least privilege, threat modeling, supply-chain audit, role/tenant IDOR tests, no browser-only authorization.
- Reliability: CI lint/typecheck/frontend and backend tests, build/prod artifact checks, representative E2E tests, actual negative-path checks, regression and scale tests, versioned docs.
- Capstone: link functionality to ITHUMCI, ITIASE1, ADBMS, ITELECT and APPSDEV using *actual* rubrics; verify whether a Firebase database product is required rather than assuming Firebase Auth is sufficient.

## Actions allowed without repeated confirmation
- Read, inspect and compare local repository; edit local application code/docs/tests in an approved milestone; run existing local builds and tests; generate disposable synthetic fixtures; write local status/review evidence. Local installation of required dependencies only if clearly compatible, within allowed environment, and not introducing a security or financial exposure.
- Create isolated temporary databases and validate them. Never modify original databases as part of a verification task.

## Must stop and request explicit approval
- Any source-change phase outside the currently approved scope recorded in `APPROVALS.md`.
- Commit, push, PR merge, release, production/staging deployment, hosted settings, GitHub Actions secret changes, Firebase settings/rules/custom claims applied to real tenants, cloud resource creation, spending, external services, live data import, original DB migrations/cutover, destructive action, or access to sensitive institutional records.
- Identity/institutional policy choices not covered by verified requirements, conflicts between authoritative requirements, or security/privacy decisions without a safe local option.
- Persistent test failures, unexplained data changes, exploitable critical vulnerabilities, loss of rollback path, major architecture deviation, or resource usage beyond defined budget.

Do not enable unrestricted approvals or disable safeguards to maintain autonomy. In Plan Mode, plan only; actual edits require execution mode. If a session Goal supports automatic continuation, keep within these constraints and budget.
