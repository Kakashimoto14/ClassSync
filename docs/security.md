# Security approach

Firebase ID tokens are verified through a shared verification port using the Firebase Admin SDK with explicit project/app binding and revocation checks. `ALLOW_UNAUTHENTICATED_DEVELOPMENT` no longer supplies an identity at `/auth/me` or any protected endpoint; it is retained only as a compatibility setting. Anonymous development activity belongs to the separately gated sandbox.

Protected scheduling, Academic and publication boundaries require verified Firebase identity plus fresh server-side membership for the configured `INSTITUTIONAL_TENANT_ID`. The membership port defaults to unavailable until an authoritative repository is qualified in P2b/P3. Firebase role/tenant/record claims and preview storage grant no authority. A client role header only selects among current grants; multiple roles have no implicit priority. Private Student/Teacher projections require explicit current student/faculty links, separate from Firebase UID. Existing SQLite owner scopes are retained for local tests and sandbox, not certified tenant isolation or institutional release. Publication is not available to anonymous preview roles.

`FIREBASE_AUTH_EMULATOR_HOST` disables institutional SDK verification. No synthetic/emulator identity provider is shipped in runtime packages. Injected test providers require both `CLASSSYNC_ENV=test` and `ENABLE_TEST_IDENTITY_ADAPTERS=true`; production/staging/development reject them even with the opt-in flag. These are local test composition controls, not institutional identity or provisioning policy. Configuration/provider/repository outages return generic typed 503; invalid identity returns 401 and denied membership returns 403. No fallback to claims/sample data occurs. Publication authenticates before opening its repository. Open institutional streams recheck identity/current membership before each read and terminate on denial, outage or changed projection binding; this conservative behavior still requires production load/cost qualification. Synchronous verification is offloaded from asynchronous request/stream handlers.

The current verifier supports project-level Firebase identity only. Tokens carrying a native Firebase Auth tenant are rejected so a UID from another identity realm cannot alias the project-level UID. Native Firebase Auth multi-tenancy needs a separately qualified tenant-aware verifier and identity-key mapping; it is not inferred from ClassSync's institutional tenant field.

The separate `/api/v1/scheduling/sandbox/*` pathway requires both `CLASSSYNC_ENV=development` and `ENABLE_SCHEDULING_SANDBOX=true` at each service. The original S1 raw-input endpoints require explicitly synthetic inputs and synthetic resource provenance. S2B's `/sandbox/academic/{period-id}/...` endpoints instead compile persisted development-entered records fetched from the Academic service; they accept no client-supplied solver input. They read no production academic records. Bind presentation services to loopback; do not expose this deliberately unauthenticated development experience publicly. Ordinary production frontend builds hide these sandboxes even when UI role previews are explicitly configured.

S2A allows an explicit save of a server-held successful run to an immutable SQLite
draft, after independent validation. Sandbox drafts use a separate shared local
scope with creator `development-sandbox`; protected drafts are scoped to the verified
Administrator UID. Lists and reads enforce the same boundaries as saves at both
services. Client assignments, validation flags, source/owner claims and preview
roles are not accepted as proof. Saved drafts do not activate personal schedules or
grant publication authority. Secure and back up the database as academic data;
checksums detect corruption but do not protect against a database administrator.

S2B Academic CRUD requires the same verified Administrator identity at Gateway and
Academic, with owner/period-scoped foreign keys and optimistic revisions. Its
development namespace requires both flags at all three services. Development-entered
runs/drafts use `academic-sandbox` / `development-academic-sandbox`; the original
synthetic namespace cannot read them. The development UI role grants neither scope
nor protected access. There is no delete endpoint, and existing draft snapshots are
not changed by source edits. Current-record provenance and verification notes record
administrator assertions; comprehensive academic-edit audit history remains future work. Local publication audit/version history already exists.

Scheduling bounds request size at Gateway, collection sizes/legal placement count, solver time and one generation per process. Local publication audit/version retention exists. Distributed jobs, institutional atomic publication across concurrent academic revisions and production abuse protection remain future work; see the reconciled production plan.

Firestore is unused by current academic/scheduling persistence. Existing intended deny-by-default rules are not a certification of deployed rules. No Firebase settings/rules are changed by P1. A separately authorized notification projection is conditional on the actual course rubric and privacy policy; PostgreSQL remains authoritative in the future architecture. Backend services must use least-privilege credentials, never source-controlled credentials.

P1 validates `presentation | sandbox | institutional` at build/dev configuration. Every distributable build rejects sandbox regardless of NODE_ENV. Frontend capabilities control affordances and prevent unintended requests; they are never backend authorization. Institutional UI does not accept preview roles as identities and remains unavailable. Historical 21 October advisory reports are retained as dated evidence. The 26 October local scan no longer reported braces; it reported Vitest/mocker and unused zod, remediated with Vitest 4.1.12 and removal of unused zod. The resulting full npm scan had zero findings; no advisory exception was granted. Follow `docs/autonomy/STATUS.md` for current evidence and release gates rather than treating historical reports as permanent guarantees.

Python scanning uses isolated pip-audit 2.10.1 against exact installed third-party versions from all four service manifests, including test/install tooling. Internal editable contracts require verified local provenance and are reviewed/tested as source. Missing coverage, skipped packages, malformed reports, scanner/network failures and any finding fail the check. `services/security-constraints.txt` pins the three remediated security targets; this is not a complete deployment lock. CI also runs an unsuppressed npm audit. No advisory exceptions have been approved. Local scans do not certify an unbuilt deployment image or hosted CI run.

The gateway supplies safe error envelopes and request IDs. It is also the planned enforcement point for rate limiting (per IP on public/auth-sensitive paths, per identity on authenticated paths); exact quotas require usage data and are intentionally not guessed. Local publication already records server-side audit information. Complete privileged academic-edit, request-decision and future override auditing remains a production requirement. No client success flag substitutes for server audit.
