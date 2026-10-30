# ClassSync — verification and evidence contract

Run scripts as defined by the *current checked-out repository*; investigate changed command names rather than blindly following this historical checklist. Record exact command, environment, stdout/stderr excerpt, exit status and evidence path. A non-run check is NOT VERIFIED.

## Baseline and static verification
- Confirm `git status --short`, branch/HEAD and current applicable repository instructions. Protect uncommitted work.
- Preserve original SQLite integrity and SHA-256 baselines before any touched-adjacent work. Use disposable copies/test databases. Do not rely only on comparing file sizes.
- From root, where applicable: `npm run lint`, `npm run typecheck`, `npm run test:web`, `npm run build`, `npm run build:presentation`.
- For Python, use the repo's activated isolated runtime, then `ruff check services packages` and `pytest`; run scheduling-sensitive suites serially, investigate intermittent failures, never weaken timeouts simply to hide defects.
- Inspect `npm audit` and a suitable Python dependency audit when available. Differentiate runtime exploit paths from build/test-only exposure; record unresolved findings and release impact.
- Check lockfile integrity, secret exposure, missing env failure handling and actual production-artifact mode.

## Browser and HCI verification
- Test at 360, 390, 768, 1024, 1440 px and native browser 200% zoom; no horizontal overflow or broken navigation. Use real Playwright/browser rendering if available rather than static JSX inspection alone.
- Confirm Student: next class, official calendar, room, timetable changes and unauthorized draft isolation.
- Confirm Teacher: assigned classes, conflicting proposals, request workflow and approval status.
- Confirm Administrator: choose period → readiness → generate → review/edit → independent validation → approve → publish → role views. Negative paths: missing data, conflict, stale revision, duplicate command, backend unavailable.
- Verify keyboard/focus, dialog containment/restore, accessible names, error messages, contrast and live status announcements. Manual assistive-technology tests remain PENDING unless actually performed.
- Test direct deep-link refresh, missing assets/API true 404 (not SPA HTML), release SHA/mode identification and zero unexpected requests in presentation mode.
- Use no synthetic data disguised as real institutional data.

## Backend security/data verification
- Firebase token invalid/expired/revoked tests; role/tenant/record-level unauthorized access, IDOR, public route boundaries, request validation and rate-limit/security header policies.
- Scheduling hard constraints and output independent validator; adversarial impossible/unknown cases; concurrent edits and publications; revision/hash-bound approvals; snapshot immutability; outbox delivery retry/idempotency.
- PostgreSQL schema migration upgrade/rollback and row counts/checksums on disposable rehearsals; transaction error handling, pooling, privilege/RLS or equivalent tenant enforcement; restore drill before deployment.
- Data protection tests for cross-role/cross-tenant leakage and log/secret redaction.

## Completion semantics
PASS = changed code reviewed + required automated gates green + representative real journeys demonstrated + unresolved risks disclosed + original data preserved. CONDITIONAL = external/manual evidence pending and cannot count as production pass. FAIL = broken security/integrity/hard scheduling invariant or failing required gate.

If static checks pass but browser/service verification cannot be run, report those items UNVERIFIED—not PASSED. Evidence must identify actual test counts and not reuse historic numbers as new results.
