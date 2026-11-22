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

## Student verification and Turnstile boundary (19 November 2026)

Gateway verifies Turnstile before student-number lookup/sign-in, OTP issuance/confirmation, and
password-onboarding completion. Production Gateway fails closed if its secret is absent, and the
no-secret bypass is limited to development/test. Direct Firebase email/password and Google Auth
calls still originate in the browser and can bypass this Gateway check; this is not a global
Firebase authentication enforcement boundary. The production site key/secret and provider
acceptance have not been verified.

For roster-linked onboarding, `/api/v1/auth/student-verification-challenges` requires a verified
Firebase principal, an exact `YY-NNNNN` student ID and a matching active Registrar record, then
stores only a tenant/UID-scoped HMAC digest in the PostgreSQL challenge table from migration
`0019_student_email_challenges`. Codes expire after five minutes, are limited to five failures,
and have a 60-second resend cooldown. After OTP, the browser links a Firebase password provider;
the Gateway verifies current provider/email state before setting `password_configured` and granting
membership. Migration `0020_student_portal_password` records that gate. Student-number login
resolves roster email only inside the Gateway, authenticates with Firebase Identity Toolkit, checks
active membership, and returns a custom token without the email. Unknown IDs and invalid passwords
share a generic error, and the Gateway sends the Firebase credential request for unknown IDs too
to reduce a missing-roster timing signal. Notification delivery requires a private service token and configured
Resend credentials; no plaintext code fallback is enabled. Migration/RLS execution, real Resend
delivery, real roster handling, and Auth Emulator/browser end-to-end behavior are unverified. The
bootstrap seed remains local synthetic academic data only and does not create identity or official
publication data.

## Domain-neutral student email and COR self-verification (21 November 2026)

Student email addresses are normalized to trimmed lowercase and validated without a required institutional domain. Email possession is necessary but does not by itself grant student membership. Default `cor_or_roster` requires a verified Firebase email and either a matching active Registrar record or a server-stored, reviewed Registration Form confirmed by the signed-in student. New self-verified rows are marked `cor_self_verified`; student-number claims are unique per tenant and an existing claim cannot be rebound to a different UID. `strict_roster` keeps roster-only activation available when required by approved policy. These changes are represented in migration `0021_student_email_and_cor_source` and the Gateway repository transaction. The database migration and RLS behavior have not yet been executed against a disposable PostgreSQL instance in this work phase.

Firebase verification/reset action codes are rewritten to the branded frontend `/auth/action` route and sent through the existing notification service. The client keeps per-action/per-email cooldown expiry in `sessionStorage`, and Gateway returns retry metadata. Current server email/IP limiting is process-local; it is suitable only as local defense-in-depth and must be backed by shared coordination before horizontal/multi-instance deployment. Live Firebase, Turnstile, Brevo/Resend, and hosted checks remain unverified. See the 21 November implementation evidence in `docs/autonomy/STATUS.md`.

Gateway's in-process login and email cooldown maps are bounded and protect a single instance. They preserve unexpired lockouts when their key capacity is reached and reject new keys until capacity recovers. When Gateway runs multiple workers or replicas, pair these local checks with shared edge/proxy rate limiting; per-process maps do not provide a deployment-wide quota.
