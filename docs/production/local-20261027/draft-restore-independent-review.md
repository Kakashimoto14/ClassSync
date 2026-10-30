# PostgreSQL academic restore and immutable drafts — independent review

27 October 2026. Local HEAD `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`; dirty working tree preserved.

The independent security reviewer (`/root/p2a_security_review`) inspected the PostgreSQL draft adapter, migration 0006, shared snapshot rules, academic restore harness and acceptance/tests. The reviewer did not run tests, solvers or servers. Its initial usage-limit interruption was retained in the conversation; a later retry completed the review.

Findings and corrections:

1. A second key for an already saved run returned success without binding that key, allowing later reuse for a different run. PostgreSQL now returns 409 before reporting success. The portable regression explicitly rejects that path; actual PostgreSQL proof checks the original remains unchanged and a rejected key is not a successful alias. Legacy development SQLite behavior remains unchanged and differs here; it is not an institutional adapter acceptance claim.
2. Creating another repository around the same Engine did not prove a physical reconnect. The final draft qualifier captures `pg_backend_pid()`, disposes the pool, requires a different physical session, then compares the exact snapshot.
3. The checksum probe also mismatched payload run identity. The final probe uses a new matching run ID/payload and only an invalid checksum, isolating the intended database check.

The reviewer inspected all three corrections and reported no further actionable issue. It also reviewed root's restore-harness fixes: omit exactly one archive `SCHEMA - public` entry because template0 already has that schema, retaining all objects and ACLs; target one synthetic reference row for the foreign-key probe so uniqueness does not mask the intended failure. Source/target/archive/cleanup boundaries and the migration-0005 pin remained intact.

Review is evidence of source examination, not proof of execution or production certification. Actual runs, regressions, original-file hashes and cleanup evidence are separately recorded in STATUS and the qualification outputs. No service routing/cutover, browser or institutional workflow acceptance follows from this review.

The same reviewer separately inspected the regression-runner change after the full two-worker diagnostic passed 709 tests/40 files in 185.96 seconds. Removing the wrapper's one-worker override honors the already configured two-worker bound; default file isolation, assertions, verbose output, failure propagation and the 300-second limit are retained. No gate weakening was found. The actual root command and remaining regressions still require their own execution evidence.
