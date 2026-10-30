# Shared PostgreSQL foundation

Local P2b foundation with optional P3a Gateway identity-provider adoption. The Gateway defaults to unconfigured membership; institutional provisioning and Academic/Scheduling PostgreSQL adoption are not enabled. Original SQLite remains current local academic/scheduling storage. Production remains NO-GO.

`classync_persistence.database` provides the Psycopg/SQLAlchemy engine and transaction boundary. A trusted server configuration must supply the URL; never accept one from a browser. Transactions commit on success and roll back on exceptions. Parameters are hidden from SQLAlchemy errors/logs by default.

`classync_persistence.schema.migrate` runs checked-in Alembic revisions only on an explicitly supplied PostgreSQL connection inside the caller's transaction. It has no environment URL, automatic service-startup migration or original-data cutover. Downgrade is for authorized disposable rehearsals, not a backup substitute.

Revision identifiers are immutable. Revisions before 0009 must fit Alembic's
original `VARCHAR(32)` version column; 0009 widens `public.alembic_version.version_num`
to `VARCHAR(128)` before its 34-character identifier is stamped. Downgrade retains
that capacity. All new revision identifiers and parent links must be at most 128
characters, enforced by `test_migration_revision_capacity.py`; a longer identifier
requires a capacity migration before its stamp, never a rename or manual stamp.
The table remains owned by the migration role and the alteration shares its
caller-owned transaction with policy changes and Alembic's stamp.

`python -m scripts.postgres_revision_capacity_qualification --bin <installed-bin> --output <new-json>`
checks actual SQLSTATE 22001 at revision 0008, transactional rollback, incremental
0008 → 0009 → head, downgrade/re-upgrade retaining capacity, and clean base → head.
It uses only a newly marked disposable SSPI cluster. Portable tests check operation
ordering and the revision graph; they do not substitute for that PostgreSQL run.

Canonical namespaces are `classsync_identity` (0001), `classsync_academic` (0004),
and `classsync_scheduling` (0006). Revision 0010 adds its archive to the existing
scheduling schema and references the existing identity keys and 0006 immutability
function. It owns only that table, its constraints, policies and triggers; its
downgrade refuses nonempty archives and never drops the scheduling schema.
`test_migration_namespace_contract.py` checks schema references in both directions
against the ordered chain. Archive imports reuse 0008's constrained current-authority
locking helper, requiring its explicit EXECUTE grant and SELECT/INSERT on the archive;
they do not require runtime UPDATE or schema CREATE grants.
The revision-capacity qualifier also checks canonical schema/table ownership, ACLs,
archive RLS/identity denial, cross-schema FK and checksum failures, immutability,
0010 rollback and retained-evidence downgrade denial. It reproduces the former
misspelled-schema SQLSTATE `3F000` in a savepoint without creating that schema.
Earlier restore drills do not qualify the new archive; its backup/restore evidence
remains a P3b exit requirement.

Revision `0011_publication_policy_cycle` corrects the cycle introduced by the
combination of 0007's version INSERT policy and 0009's record-scoped head SELECT
policy. Version INSERT now checks only current active Administrator membership,
tenant/project and owner UID. It does not query heads. Version SELECT still checks
membership/record scope; head SELECT and writes may query versions. Existing unique
revision keys, owner-bound head FK, single-step head trigger and deferred
version/head constraint preserve atomic revision sequencing. RLS/FORCE RLS and
Student/Teacher projections are unchanged. This is a forward correction for existing
0010 schemas as well as new base-to-head databases. Downgrading to 0010 restores its
known recursive write policy and must not be treated as a usable publication state.
The publication qualifier reproduces old runtime SQLSTATE42P17 using EXPLAIN INSERT
RETURNING, captures pg_policy expressions/ownership/RLS before and after correction,
then runs the existing actual INSERT/commit/projection/negative/concurrency matrix.

`classync_persistence.memberships.PostgresMembershipLookup` binds a configured Firebase project to current tenant/UID membership. Callers must supply the server-selected tenant and a verified UID. It reads every time; DB failures propagate to the P2a typed unavailable boundary. The runtime role receives SELECT only. Provisioning, grant changes and institutional policy remain separate concerns. RLS context is defense in depth behind trusted application code, not an identity verifier or permission to expose arbitrary SQL.

The schema stores synthetic-testable record keys and grants, not official enrollment/curriculum details. Composite tenant/person foreign keys enforce record binding. All six identity/history tables use ENABLE/FORCE RLS; membership/history visibility also binds UID. A missing context yields no rows. Qualified non-superuser runtime roles must never own tables or have BYPASSRLS.

Qualification commands from the repository root:

```powershell
.venv/Scripts/python.exe -m scripts.postgres_driver_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output <new-evidence-file.json>
.venv/Scripts/python.exe -m scripts.postgres_identity_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output <new-evidence-file.json>
.venv/Scripts/python.exe -m scripts.postgres_restore_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output <new-evidence-file.json>
.venv/Scripts/python.exe -m scripts.postgres_revision_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output <new-evidence-file.json>
.venv/Scripts/python.exe -m scripts.postgres_audit_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output <new-evidence-file.json>
```

Each command creates its own marked temporary Windows SSPI cluster, refuses ambient PG settings for driver connections, uses loopback/nondefault port, verifies server identity before DDL, and stops only its owned cluster in `finally`. No passwords or existing clusters are used. Output must be new, with an existing parent directory. No recursive cleanup is performed; disposable logs/data/archive remain for evidence. Portable tests live in `services/persistence/tests`; the real PostgreSQL scripts are explicit local checks, not a claimed remote CI run.

The second migration enforces immutable tenant/UID keys and exact revision increments on UPDATE. `membership_changes.change_membership_state` compares the expected revision inside an already authorized caller transaction; an absent/invisible/stale row returns a typed conflict. This helper does not authorize a change, provision grants or expose a route. The ordinary reader has no UPDATE privilege. The revision qualification observes two competing connections' actual row lock and proves the stale writer cannot overwrite the winner, with rollback and cross-tenant/UID negative cases.

The third migration appends membership INSERT/UPDATE history atomically with the change. State and grant helpers require an explicit `VerifiedPrincipal` actor from a trusted caller; constructing that contract does not verify identity or grant provisioning permission. Callers must already be authorized and set trusted tenant/subject context. History records the caller UID plus database session identity, old/new snapshots and revision. Missing actor/context or audit failure aborts the authority mutation. The nonlogin owner's fixed-search-path append function supports a maintenance role with membership UPDATE but no direct history-write permission. Ordinary service readers gain no write/audit access. DML edit/delete/truncate is denied; a privileged database owner can still change DDL, and authorized downgrade removes synthetic history. No tamper-proof-owner, production retention or retrospective actor/backfill claim is made. Institutional provisioning policy and real service adoption remain separately gated.

Fresh evidence and open phase gates are in `docs/autonomy/STATUS.md`, `TRACEABILITY.md` and `docs/production/local-20261026`. A successful disposable restore is not production disaster-recovery qualification.

The Gateway's optional `IDENTITY_DATABASE_URL` is secret-valued and requires an explicit PostgreSQL/Psycopg host, port, database and runtime user, configured Firebase project and server tenant. URL query overrides and ambient `PG*` settings are rejected. Default `verify-full` transport requires system-trusted TLS and SCRAM; its real deployment/provider path is not qualified by local SSPI tests. The separate `loopback-sspi-test` transport requires exact test environment, explicit loopback/high nondefault port and no password. It is not a production fallback. Leave the URL unset for current unconfigured behavior.

Gateway lifespan owns the identity-only read pool and removes/disposes it on shutdown. No startup migration or provisioning occurs. The pool has five physical slots, no overflow and a three-second checkout deadline; connections have five-second connect/statement and 1500ms lock deadlines. Database timeout/permission failures return generic unavailable errors, never cached membership or sample success. Production capacity and real TLS/provider qualification remain separate gates. Bounded local authenticated browser lifecycle now passes with actual owned Auth Emulator/Gateway/current PostgreSQL evidence; this does not establish institutional sign-in/provisioning or connected schedule acceptance. The explicit `scripts.postgres_provider_qualification` check proves local configured startup, current membership/revocation, actual lock/pool failure recovery and zero owned database sessions after normal/exceptional shutdown and restart.


P3b begins with the isolated `academic_periods.PostgresAcademicPeriods` metadata adapter and Alembic revision0004. It is not installed in service routes and does not replace complete academic snapshots, default constraints, calendars or catalog imports. Current administrator owner isolation is preserved under an explicit server tenant/project; shared institutional administration is not inferred. Every read/create checks current active Administrator membership in the same SQL statement, with matching FORCE RLS SELECT/INSERT policies. Missing/revoked/wrong-role authority yields typed denial; SQL/database errors propagate without empty/sample fallback. The revision0004 metadata-only runtime needs identity SELECT plus academic schema USAGE and metadata SELECT/INSERT only. Revision0005 adds the period UPDATE policy required for complete academic edits; its qualified runtime receives UPDATE(revision), not a blanket metadata update grant. The metadata-only qualifier explicitly targets revision0004; it is historical slice evidence, not a current-head no-update claim. No constructor migration or provider cutover occurs.

The metadata-only qualification uses a fresh disposable cluster and two active synthetic Administrators, proves independent owned reads and direct cross-owner insert denial, non-superuser table-owner FORCE RLS, rollback/constraints, membership revocation/reactivation, real permission outage/recovery and explicit downgrade/re-upgrade preserving identity rows. Downgrade removes disposable academic metadata; it is not data-preserving rollback or a backup. Complete academic/scheduling adapter parity, original-data migration rehearsal, checksums/restore and cutover remain separate P3b work.

```powershell
.venv/Scripts/python.exe -m scripts.postgres_academic_period_qualification --bin 'C:/Program Files/PostgreSQL/18/bin' --output <new-evidence-file>
```


P3b's complete academic adapter is `services/academic/app/postgres_repository.py`. It remains uninstalled in default routes. Revision0005 adds owner/tenant/period-scoped records, references and calendars, checksum/payload-identity checks, label/faculty uniqueness and reference indexes. Both adapters use `record_rules.py` for eligibility, reference validation, provisional catalog identity, serialization and initial records. Current verified Administrator membership/project/owner predicates apply in SQL/RLS; repeatable-read snapshots keep metadata/records/calendar coherent. Period row locks serialize saves, with record/calendar expected revisions and a checked period bump. Database/pool failures produce generic unavailable errors, and stale/constraint failures remain explicit. UTC timestamp strings preserve the existing SQLite contract independently of the database display timezone. No constructor/startup migration or SQLite fallback occurs.

The generated-only rehearsal takes no source-path argument. It creates a new SQLite fixture inside the owned marked cluster root, validates its payloads/references, explicitly maps the synthetic owner/tenant, transfers all81 records including revisions/checksums, and compares the complete mapped snapshot and canonical raw rows. Interrupted imports roll back atomically; duplicate import conflicts preserve the destination; source bytes remain unchanged. This is not authorization or tooling for institutional/original-data import. DDL downgrade tests remove disposable academic children; full backup/restore and data-preserving rollback qualification are still pending.

```powershell
.venv/Scripts/python.exe -m scripts.postgres_academic_repository_qualification --bin 'C:/Program Files/PostgreSQL/18/bin' --output <new-evidence-file>
.venv/Scripts/python.exe -m scripts.postgres_academic_migration_qualification --bin 'C:/Program Files/PostgreSQL/18/bin' --output <new-evidence-file>
```


Academic service provider adoption (bounded local/emulator qualification): institutional routes select the complete PostgreSQL adapter only when explicit `ACADEMIC_DATABASE_URL` is configured and its lifecycle-owned engine exists. Missing production configuration returns unavailable, never an original SQLite fallback. The existing isolated SQLite identity fixtures are available only with exact test environment, explicit test-adapter flag and an absolute path inside OS temporary storage; development sandbox remains separately gated. No `.env`, production tenant, credentials or original data is changed by this implementation.

`classync_persistence.configuration.postgres_configuration` now holds the existing reviewed libpq target/transport rules shared by Gateway and Academic. Each service owns its adapters/pool independently. Academic uses one five-slot/no-overflow pool with three-second checkout, five-second connect/statement and1500ms lock limits for current membership and owner-scoped academic transactions. Default verified TLS/SCRAM still needs real provider qualification; exact-test SSPI is not a deployment alternative. Runtime privileges and migrations are explicit operator/rehearsal work, never startup DDL.

Academic rechecks current membership both at the HTTP guard and inside repository transactions. If a grant is revoked between them, the HTTP boundary maps the repository denial to generic403 (unavailable503), never unhandled500 or raw SQL/identity details. The reviewed owned Auth Emulator/current PG qualification uses actual SDK identity and FastAPI TestClient ASGI HTTP create/list/snapshot/record/calendar routes, owner/role/server-tenant/project denials, stale saves, revocation races, real permission/pool exhaustion recovery and normal/exceptional/restart cleanup. This is not TCP/browser or institutional-production acceptance. Full P3b scheduling/publication adaptation remains open.

The academic restore qualifier pins migration0005 and accepts only its own new marked cluster, generated synthetic fixture, new archive and newly created empty target database in that same cluster. It compares all10 identity/academic tables and14 catalog components before functional checks, including ACLs, default privileges, FORCE RLS and raw academic payload/checksum/revisions/references/calendar. Exactly one archive entry creating `public` is omitted because template0 already contains it; objects and ACLs remain in the restore list. No existing target is reused or replaced. Source/archive preservation, reversible tamper detection, restored owner/role isolation, revocation, CAS and actual outage/recovery were qualified. This is not cross-host disaster recovery or permission to restore original data.

Migration0006 adds owner-scoped immutable scheduling runs and drafts. `services.scheduling.app.postgres_draft_repository.PostgresDraftRepository` requires an explicit engine, server tenant/project and trusted `VerifiedPrincipal`; constructing that contract does not verify a token. Both transactions and FORCE RLS require a current active Administrator. Shared SQLite/PostgreSQL snapshot rules independently validate complete solver results; UNKNOWN/infeasible/incomplete results never become saved timetables. An owner transaction advisory lock serializes save/run/key replay, and the database enforces composite owner/run FKs, checksums, metadata, uniqueness and ordinary DML immutability. Privileged DDL remains privileged; synthetic downgrade removes draft data and is not a production rollback plan.

The PostgreSQL adapter rejects changing the save key for an existing run with409. Legacy development SQLite behavior still accepts an alternate key without creating an alias; no institutional compatibility claim is made for that behavior. The new PG adapter is qualified across physical reconnect, two competing save waiters with exactly one creation, expiry, malformed snapshots, current authority, actual outage recovery and negative constraints. Scheduling run/draft provider routing is now locally qualified as described below; PostgreSQL publication remains pending. Original SQLite is unchanged.

Additional explicit generated-only qualification commands:

```powershell
.venv/Scripts/python.exe -m scripts.postgres_academic_restore_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output <new-evidence-file.json>
.venv/Scripts/python.exe -m scripts.postgres_draft_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output <new-evidence-file.json>
```

Current evidence is under `docs/production/local-20261027`; phase status and limitations remain in `docs/autonomy/STATUS.md` and `TRACEABILITY.md`.

Scheduling now supports an optional secret-valued `SCHEDULING_DATABASE_URL` and `SCHEDULING_DATABASE_TRANSPORT`, using the same explicit configuration/default verified TLS/test-only SSPI policy. Its lifespan owns one five-slot pool (no overflow, three-second pool wait), Firebase verifier and current PostgreSQL membership lookup. Institutional generation and draft routes bind the verified UID to server tenant/project. Missing configuration/owned lifespan fails closed; only isolated exact-test fixtures may use temporary SQLite. Explicit development sandbox behavior is separate. Missing bound storage on an institutional generation call fails before acquiring the solver slot; persistence failure never returns a confirmed candidate.

Institutional publication, history, calendar, periods, restrictions, availability and
event routes select the configured PostgreSQL repository with no SQLite fallback.
Current migration0011 repository acceptance, generated publication/archive backup
and restore, and actual Auth Emulator SDK/current-PG ASGI HTTP publication and
three-role calendar composition now pass. See the three qualification JSON files
under `docs/production/local-20261029/` and STATUS for exact gates. Restored content,
opaque archive hash/payload, grants, FORCE RLS, functions, policies, triggers and
sequence state match. Archive evidence stays non-current and non-replayable.
Synthetic sandbox publication remains unavailable in PostgreSQL mode; unconfigured
production has no institutional SQLite fallback. Same-cluster restore and ASGI HTTP
are bounded local evidence, not cross-host recovery, new browser acceptance,
production TLS/identity provisioning, institutional approval or release authority.

The fixed Scheduling emulator entry uses the same reviewed pinned temporary tools root and accepts no arbitrary qualification module:

```powershell
node scripts/auth_emulator_qualification.cjs --tools-root <reviewed-owned-temporary-tools-root> --postgres-bin "C:/Program Files/PostgreSQL/18/bin" --output <new-evidence-file.json> --scheduling
```
