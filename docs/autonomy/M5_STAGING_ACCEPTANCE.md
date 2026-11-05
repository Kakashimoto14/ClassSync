# M5 controlled staging prerequisites and acceptance

Preparation only. No resources, users, secrets, DNS, billing or deployment settings have
been created/changed. PostgreSQL retains academic, enrollment, membership and publication
authority. Existing presentation and original databases remain separate and preserved.

## Minimum resources and decisions before deployment

- An owner-approved staging project, region, billing account, monthly budget and alerts;
  approved data residency/retention and named Administrator provisioning authority.
- Separate Firebase staging project: email/password Auth, authorized staging domain,
  verification/reset delivery, trusted Admin provisioning and faculty invitation handling.
  No public role claims. Use managed service identities/ADC and Secret Manager, not keys
  copied into images. Qualify current membership checks and revocation with real Auth.
- Connected React hosting with same-origin `/api/v1` Gateway proxy. Institutional clients
  reject cross-origin API bases. Do not change the public presentation deployment.
- Three existing Cloud Run service images: Gateway, Academic, Scheduling/OR-Tools.
  Build immutable digests after Linux qualification; scan both Python and native packages.
  Proposed starting envelope for measurement: one instance maximum/service, scale to zero,
  one worker, conservative concurrency for CPU-heavy solver/scanner,1vCPU/service and
  Gateway/Scheduling1GiB each, Academic512MiB. These are test hypotheses, not capacity proof.
  Keep existing solver limits, the20s scanner deadline and hard constraints/guards unchanged.
- Resolve internal ingress/IAM routing before deployment. Current proxies forward Firebase
  bearer tokens; separate Cloud Run invoker-ID-token transport is not qualified. Approve
  and test the network/IAM arrangement that both prevents public internal-service access
  and preserves Firebase user identity. Liveness is not authorization or readiness.
- Managed PostgreSQL, independent migration identity, least-privilege service roles,
  verified TLS/root CA, RLS grants, migration0016 head, backups and disposable restore/
  rollback rehearsal. No startup DDL. Budget aggregate pools across all instances plus
  migration/operations headroom; no original SQLite migration or institutional roster.
- Scanner raw inputs are private ephemeral files deleted after processing. Extraction
  metadata is per-instance, owner/tenant scoped, expires within15minutes and disappears
  on restart. A private writable temporary filesystem is required. Start with one Gateway
  instance; verify restart/expired-review messaging before changing scaling. No durable
  raw-document bucket is required. No public URL or third-party document upload.
- Optional course-only Firestore database/collection, private Storage bucket with enforced
  public-access prevention/uniform access/lifecycle, and approved Gemini model/key/quota.
  Default off; no institutional records or registration documents in these integrations.
  Require provider quotas and budget monitoring: process-local counters reset on restart.
- Signed-off Linux/container acceptance, security disposition, authorized Git checkpoint,
  real Actions evidence, then explicit provisioning/deployment authorization. Production
  cutover is separately gated even after staging passes.

## Environment variable inventory — names and descriptions only

Values belong in approved deployment configuration/secret storage, never this document.

| Names | Purpose |
|---|---|
| `VITE_CLASSSYNC_MODE` | Connected institutional frontend mode |
| `VITE_API_BASE_URL` | Same-origin Gateway API prefix |
| `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID`, `VITE_FIREBASE_MESSAGING_SENDER_ID`, `VITE_FIREBASE_STORAGE_BUCKET` | Approved staging Firebase browser configuration; never backend secrets |
| `VITE_ENABLE_ROLE_PREVIEW`, `VITE_ENABLE_PRESENTATION_SAMPLE` | Preview/sample capabilities must be disabled for institutional acceptance |
| `CLASSSYNC_SERVICE`, `PORT`, `CLASSSYNC_ENV` | Existing image entrypoint/service/listener/runtime |
| `FIREBASE_PROJECT_ID`, `INSTITUTIONAL_TENANT_ID` | Backend identity project and approved tenant |
| `GOOGLE_APPLICATION_CREDENTIALS` | Optional mounted credentials only when managed ADC is unavailable; never image-copy |
| `FIREBASE_SERVICE_ACCOUNT_JSON`, `FIREBASE_CLIENT_EMAIL`, `FIREBASE_PRIVATE_KEY` | Legacy credential alternatives; prefer managed identities and avoid populating these |
| `IDENTITY_DATABASE_URL`, `ACADEMIC_DATABASE_URL`, `SCHEDULING_DATABASE_URL` | Distinct service-scoped secret connection strings |
| `IDENTITY_DATABASE_TRANSPORT`, `ACADEMIC_DATABASE_TRANSPORT`, `SCHEDULING_DATABASE_TRANSPORT` | Verified TLS transport; test-only SSPI is prohibited in staging |
| `DATABASE_POOL_SIZE` | Bounded per-service database pool; aggregate instance budget required |
| `ACADEMIC_SERVICE_URL`, `SCHEDULING_SERVICE_URL` | Internal service addresses |
| `CORS_ORIGINS` | Exact approved HTTPS origin allowlist |
| `ALLOW_UNAUTHENTICATED_DEVELOPMENT`, `ENABLE_SCHEDULING_SANDBOX`, `ENABLE_TEST_IDENTITY_ADAPTERS` | Development bypasses/test adapters must be disabled |
| `REGISTRATION_MAX_BYTES`, `REGISTRATION_MAX_PAGES`, `REGISTRATION_TIMEOUT_SECONDS`, `REGISTRATION_RETENTION_SECONDS` | Strict upload/processing/retention bounds |
| `COURSE_CLOUD_ENABLED`, `COURSE_STORAGE_BUCKET`, `COURSE_GEMINI_MODEL`, `GEMINI_API_KEY` | Optional non-authoritative course integrations; API key in Secret Manager |

Auth/Firestore emulator variables must be absent in real staging. Do not configure
`ACADEMIC_DATABASE_PATH`/`SCHEDULING_DATABASE_PATH` as an institutional SQLite fallback.
Do not populate `NOTIFICATION_SERVICE_URL` unless an actually supported consumer needs it.

## Cost review — estimate, not spending approval

Checked5November2026, USD, illustrative us-central1 list pricing,730hours/month; region,
currency, taxes and actual usage remain unapproved. Prefer one region for services/data.
[Cloud Run](https://cloud.google.com/run/pricing) request-based CPU is$0.000024/vCPU-second
and RAM$0.0000025/GiB-second before shared free-tier credits. An illustrative10,000requests
using an aggregate3CPU-seconds/3GiB-seconds each costs about$0.80 compute before requests,
network and free credits. Solver/OCR workloads must be measured; this is not a forecast.
[Cloud SQL](https://cloud.google.com/sql/pricing) shared-core examples are$0.0105/hour
micro(~$7.67/month) or$0.035/hour small(~$25.55/month), plus storage/backups/network.
Shared cores have no Cloud SQL SLA and micro memory may be inadequate. A dedicated
1vCPU/3.75GiB illustrative floor is~$49.31/month at listed$0.0413CPU-hour+$0.007GiB-hour,
before disk/backup/HA. Confirm actual eligible machine size and selected-region quote.

Planning envelope: roughly$15–40/month for a tiny short-lived shared-core test environment,
or$60–100/month with a small dedicated database, plus actual optional AI/API usage.
These ranges are assumptions requiring a provider calculator quote and owner budget
approval. Include Artifact Registry/builds, logging retention, Secret Manager, frontend,
Storage operations/egress, Firestore operations, Auth usage and Gemini tokens; optional
services can add charges even if Cloud Run is idle. No free-tier entitlement is assumed.
Set maximum instances, enforceable provider quotas, limited log retention and alerts;
budget alerts are not hard spend caps. No subscriptions/commitments are authorized.

## Complete synthetic provider acceptance — execute only after deployment approval

Retain release SHA/image digests, configuration version, timestamps, HTTP status/assertion
counts and redacted receipts. Never retain ID/refresh tokens, personal forms or raw private
response exports. Use a new disposable staging tenant and invented records only.

1. Trusted Administrator signs in through actual staging Firebase, verified email/current
   server membership; browser role changes cannot grant access. Reject missing token401.
2. Select/create a clearly synthetic period with explicit term/calendar/cohort version;
   verify current and historical period navigation and missing-period404.
3. Configure synthetic sections/offerings/eligible faculty/rooms/availability/enrollments;
   readiness names blockers. Student/Teacher cannot change institutional inputs403.
4. Generate with existing OR-Tools. Require feasible/optimal, zero hard conflicts and
   independent validation; UNKNOWN/infeasible cannot become a publishable timetable.
5. Review exact draft/calendar/revision; alter input to prove stale approval rejection409,
   then regenerate/review. Missing inputs must block generation/publication.
6. Publish as authorized Admin using current revision/version and unique idempotency key.
   Verify replay consistency, immutable history, concurrency conflict and audited receipt.
7. Test Student signs up, verifies real email, remains pending; submits record claim.
   Admin verifies against authorized synthetic roster/process and approves. ID/email/image
   alone cannot activate membership; duplicate record claims cannot steal another account.
8. Admin selects existing faculty, issues scoped expiring email-bound invitation. Teacher
   verifies account/accepts. Invalid, expired, redirected, revoked/replayed tokens fail.
9. Student and Teacher view the same published classes through separate projections;
   multiple classes/day, next class, weekly rooms/instructors, no schedule/unassigned,
   cross-user/tenant denial, draft isolation, refresh/session restoration and secure logout.
10. Student uploads invented digital PDF, scanned PDF, PNG/JPEG; review/correct fields,
    evidence and code ambiguity. Reject unsupported415, malformed422, oversized413,
    excess pages, active PDF and another user's scan404; test throttling and cleanup.
11. Match reviewed courses only to verified enrollment and published term/offerings.
    Wrong term/unmatched remains pending; numeric section2 never becomes an invented
    institutional section, class time, classroom or authorization.
12. Teacher submits classroom-change request for assigned published class; test duplicate
    idempotency and foreign-class/role denial. Student cannot submit Teacher decisions.
13. Admin reviews/decides, validates a room-change draft and publishes before fulfillment;
    reject stale request/publication versions and preserve decision evidence.
14. Student/Teacher see relevant changes and audience-scoped announcements; history/
    rollback publishes a new version while retaining immutable previous versions.
15. Revoke Student/Teacher membership and repeat old-token reads: immediate institutional
    denial. Exercise invalid/expired token401, wrong role/tenant403, not-found404, conflict409,
    invalid body422, unavailable dependency503 and recovery without sample fallback.
    Verify private logs, retention/restart handling, mobile5widths/desktop/native200zoom,
    password recovery and any remaining manual accessibility checks.

If course integrations are enabled, separately run actual Firestore GET/POST/PATCH/DELETE,
CAS/recreation/foreign-owner denial, private bucket CRUD/retention/IAM, and fixed-topic
Gemini success/timeout/quota denial. Stub tests cannot close provider acceptance.
