# P3b first slice — isolated academic period metadata

Before implementation, 26 October 2026. Dependency: bounded local P3a exit PASS in STATUS. Owner local P2–P8 authorization only.

- Add an explicit Alembic migration and PostgreSQL period metadata adapter, leaving original SQLite, service routes and default providers untouched. This is not a complete academic snapshot/create-period replacement; constraints/catalog/calendar/records follow in later slices.
- Preserve current administrator owner isolation within an explicit server-bound tenant/project. Do not infer shared university administration policy. Accept only trusted VerifiedPrincipal from the verifier boundary, never an HTTP payload or cached role grant. Check current active administrator membership inside each SQL statement via FORCE RLS; Student/Teacher, missing context, wrong project/tenant/owner and revoked/inactive identities cannot read or insert private metadata.
- Validate title/id/revision and tenant/member foreign keys. Return existing AcademicPeriod metadata contract; no sample data on error. Use bounded existing shared driver transactions and pool. No migrations at constructor/startup.
- Prove actual disposable PostgreSQL create/list/restart, transaction rollback, duplicate/invalid constraints, direct SQL isolation, membership revocation and database outage/recovery. Prove upgrade/downgrade/re-upgrade on the disposable schema, preserving identity rows; do not claim original-data migration or complete P3b PASS.
- Portable negative adapter/migration tests, Ruff, independent security/data review and original hashes required. No new UI behavior; P3a rendered evidence remains applicable to unchanged UI.
