# ClassSync operational authority contract — 10 November 2026

Status: target approved; local synthetic composition only. Firestore owns the tested
onboarding writes; timetable requests through the bridge are read-only.
The existing release has PostgreSQL membership and onboarding, in-process scanner state,
and optional coursework Firestore. Coursework documents do not qualify as access authority.

| Entity / operation | Target owner and stable key | Write / read boundary | Staleness, failure and recovery |
|---|---|---|---|
| Credentials, verified email, sessions | Firebase Auth; project + UID | SDK sign-in and action links; server verifies project, token and revocation | Deny invalid, disabled or revoked identity; no role inference from Auth |
| Membership, role and record grants | Firestore; project + tenant + UID, monotonic revision | Trusted review/provisioning or revocation transaction; fresh lookup in Gateway and every protected service | Missing/revoked denies. Unreachable, invalid or mismatched projection denies; recover by reconciling from Firestore, never SQL fallback |
| One-account record binding | Firestore; project + tenant + record kind + canonical record ID | Same transaction as grant; verify approved PostgreSQL record before accepting | Reserve deterministically; conflicts deny. Do not reuse a revoked reservation automatically |
| Account claim and decision | Firestore; project + tenant + UID, immutable decision event | Verified claimant submits; authorized current Administrator reviews; activation and reservation are atomic | Pending is no access. Replay with command ID; preserve decision and repair ambiguous links |
| Faculty invitation | Firestore; tenant + hashed invitation secret | Authorized issuance, expiry, and one-use acceptance in the same transaction as binding | Wrong account, replay, revoke and expiry deny. Never log secrets or use email alone as authority |
| OCR review and intake | Firestore; tenant + owner UID + scan ID, expiry/revision | Gateway only; ephemeral bounded extraction, then minimized reviewed fields | On failure discard raw files and derivatives, require retry/review; never grants membership or enrollment |
| Academic records and enrollment | PostgreSQL; tenant + period + stable record ID and revision | Approved Admin and academic APIs under FORCE RLS | Missing/unapproved inputs block readiness. Verified academic correction creates a new revision |
| Solver run, draft and review | PostgreSQL; tenant + period + immutable snapshot/hash, run/draft/review IDs | Existing validated generation, edit and review APIs | Invalid/stale/unknown results cannot publish; regenerate/review against current revision |
| Official timetable, history, restrictions and pointer | PostgreSQL; tenant + period + immutable publication version and idempotency key | Existing atomic publication transaction and authorized projections | Failure preserves last good pointer; rollback publishes a new version. No second writable schedule |
| Classroom requests and announcements | PostgreSQL; tenant + request or announcement ID | Existing scoped community APIs | On stale assignment or role deny; refresh from current authoritative state |

The scanner review adapter uses the existing Gateway routes and stores reviewed academic fields
under a project, tenant, owner and scan scoped document ID. The student number and raw scan
evidence stay in temporary processing. The original scan deadline controls access even after a
Gateway restart. Explicit erasure overwrites the reviewed fields with a marker through that deadline
so a review already in flight cannot restore them. The saved fields never confer student access.
The TTL definition is prepared for physical cleanup. The Gateway enforces expiry immediately
because [managed TTL deletion](https://firebase.google.com/docs/firestore/ttl) is asynchronous.
Normal runtime keeps the current in-memory composition until the private database, deletion
requirements and authorization cutover are approved and qualified.

The first slice routes Student claims and Teacher invitations through the existing Gateway
account endpoints in an isolated qualification composition. Firestore transactions bind
approvals/one-use acceptance and the unique record reservation together. Invite replacement
uses a per-faculty head and acceptance rechecks the issuing Administrator. Verified actor and
record bindings are synthetic; the SQL projection is preloaded by the qualification fixture.
A fresh grant
must exactly match the stable SQL projection, including roles, state and revision. Firestore
is consulted first; a SQL row cannot independently admit a request. No production setting can
select this test-trust adapter. The local Scheduling listener exposes only the allowed
read operation while the bridge is attached. Data grants are reduced to read-only after
fixture setup. A request admitted before revocation may finish its already admitted read;
no subsequent request can use an old grant. The local slice admits no privileged SQL writes
after fixture construction.
This does not prove safe cross-store publication or onboarding projection writes after cutover.
The existing protected services remain on PostgreSQL membership for normal runtime operation.

For a production bridge, use an explicit writer fence and revisioned projection. For
privileged writes, pair admission with a durable scoped intent, and hold a SQL operation
fence through the commit or reject if the captured authorization epoch/revision changed.
Revocation must first deny new admissions, then drain or abort outstanding admitted writes
before acknowledging completion. A cached token, timeout lease without fencing, or a second
read followed by an unfenced commit is insufficient. Prove lock ordering, crash recovery,
reconciliation and revocation linearization before enabling that path.

## Migration and rollback gates

1. Export only an explicitly approved disposable snapshot first. Validate source role/tenant
   bindings, canonical keys, revisions, counts, orphaned links and deterministic redacted
   checksums. Compare the publication version/pointer without copying timetable rows to Firestore.
2. The bounded shadow rehearsal validates project/tenant/role/record bindings and builds
   a deterministic checksum without writes. It resumes from a Firestore checkpoint after
   an interrupted record commit, handles concurrent replay, and compares exact membership
   and reservation contents. A separate shadow namespace cannot grant access. Production
   source export, durable conflict quarantine, publication-history restore parity and
   full migration rollback are pending.
3. Under an approved write freeze or versioned replay, fence SQL access writers, reconcile
   Firestore and SQL projection, then switch access reads and writes together. Never enable
   both sources as authority. Abort on mismatches, unavailable dependencies or stale epoch.
4. Before rollback, fence both writers; replay or reverse all Firestore decisions through the
   approved journal, verify parity and re-enable SQL only at an approved consistent boundary.
   Preserve immutable schedule history and retain audit evidence. Rehearse restore first.

## Gates and operator handoff

- Local: synthetic verified account → Firestore grant → actual PostgreSQL publication via
  Gateway and direct Scheduling; SQL-only, contradictory, cross-tenant, revoked and
  unavailable authority denied. Rules deny authenticated and unauthenticated clients.
- Next local: implement and qualify the projection writer and privileged-operation fence,
  then migrate every protected entry point, including OCR, together with the write/read
  switch. Add cursor pagination and a complete supervised migration/reconciliation rehearsal.
- Staging: blocked on an approved isolated Firebase/GCP target, region, billing, operators
  and passing local/CI gates. Verify real Auth delivery, Firestore durability after app
  restart, indexes/IAM, contention/outage/recovery, Linux OCR and PostgreSQL/Firestore restore.
- Public release: NO-GO until the separate launch gate passes, including Registrar-confirmed
  ICS/IBE/ITE shared scheduling scope, approved privacy/retention and supervised role journeys.
  No staging URL or release identifier has been established.

See [Firestore transactions](https://firebase.google.com/docs/firestore/manage-data/transactions)
and [Security Rules](https://firebase.google.com/docs/firestore/security/rules-conditions).
Server SDK writes bypass Rules and require dedicated IAM, private services and API authorization.

## Reproduce the local slice

Use Node 22, the existing Python 3.12 worktree environment, Windows SSPI PostgreSQL and the
reviewed pinned Auth tool installation from [local connected development](../infrastructure/local-connected-development.md).
Set `PYTHONPATH` to the worktree's `packages/api-contracts` and `packages/persistence`, and
`CLASSSYNC_FIRESTORE_EMULATOR_JAR` to the existing official `cloud-firestore-emulator-v1.22.0.jar`.
Java must be on PATH. Run from the feature worktree:

```powershell
node scripts/auth_emulator_qualification.cjs --tools-root <owned-tools> --postgres-bin <bin> --output <new-private-receipt> --firestore-slice
```

The command creates and stops owned Auth, Firestore and PostgreSQL processes. It constructs
an independently validated publication in the disposable database before qualifying the
Student claim, Teacher invite and Administrator review APIs. It retains only redacted status,
counts and a shadow checksum in the receipt. It does not start a browser or create real users.

| Remaining gate | Next verifiable action |
|---|---|
| Authority cutover | Implement a scoped projection writer and admission fence; demonstrate an in-flight SQL publication finishing before revocation acknowledgment, or aborting without changing the official pointer. Prove no other writer path can bypass that fence. |
| Durable OCR and complete migration | Verify hosted Firestore review composition, active TTL policy, physical cleanup and restore behavior against the institution's retention requirements. Rehearse full backfill, restore and rollback using a marked snapshot. |
| Candidate security and platform | Resolve the locked advisory with a supported dependency fix or an explicit policy disposition. Qualify the exact approved candidate on Linux, including native OCR, and obtain actual remote CI evidence after a separately approved Git checkpoint/push. |
| Hosted staging | Select a separate project, approved region, budget and operators; prepare a specific private-ingress/IAM and same-origin routing proposal. After approval, test hosted account delivery, durable Firestore writes, outages/recovery, MFA and restores. |
| Institutional launch | Obtain Registrar-confirmed shared ICS/IBE/ITE inputs and named operator/privacy approval; run the supervised data and release gates before asking for traffic cutover. |
