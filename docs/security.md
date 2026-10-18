# Security approach

Firebase ID tokens are verified by the gateway with the Firebase Admin SDK. The general local bypass requires both `CLASSSYNC_ENV=development` and `ALLOW_UNAUTHENTICATED_DEVELOPMENT=true`. It never authorizes production scheduling operations.

S1 scheduling readiness, generation, and validation endpoints independently require a Firebase ID token with a verified `role=administrator` custom claim at both Gateway and Scheduling service. Verification checks revocation. Client role strings and frontend preview storage have no authority. There is no publishing endpoint.

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
administrator assertions; comprehensive audit/revision history remains S2C work.

S1 bounds request size at the Gateway, contract collection sizes and legal placement count, solver search time, and one concurrent generation per service process. This is not a distributed production job queue, full abuse protection, or a publishing/audit system. Those deployment controls remain future work.

Firestore starts deny-by-default. Future security rules will be drafted only after collection ownership and access patterns are approved. Backend services will use least-privilege credentials from a secret manager, never source-controlled credentials.

The gateway supplies safe error envelopes and request IDs. It is also the planned enforcement point for rate limiting (per IP on public/auth-sensitive paths, per identity on authenticated paths); exact quotas require usage data and are intentionally not guessed. Audit logging will be server-side for privileged changes, publishing, conflict overrides, and request decisions.
