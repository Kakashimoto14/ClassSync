# Controlled staging — configuration and approval required

6November: publication/Postman core acceptance PASS39/39assertions. Existing workflow now
contains Linux image/native OCR/communication/outage/recovery checks for a later approved
push. Owner confirms no runner available and prohibits local Docker/WSL/firmware changes;
native runtime remains UNVERIFIED. See ../autonomy/M5_PUBLICATION_QUALIFICATION.md.

No service has been deployed by this milestone. Docker is absent on the qualification
machine, so image build/run is IMPLEMENTED-UNVERIFIED. Cloud APIs, IAM, billing, secrets,
networking and staging data must be configured only after separate owner approval.

## Container contract

`Dockerfile` builds the existing `gateway`, `academic` or `scheduling` service using
`--build-arg SERVICE=...`. The entrypoint validates the service and Cloud Run `PORT`,
runs one worker as a non-root user, and never migrates/seeds a database. `.dockerignore`
excludes originals, PDFs, credentials, environment files and development artifacts.
`compose.yaml` publishes only the loopback Gateway; Academic/Scheduling have no host
ports. All services still verify tokens/current membership. Do not enable the sandbox
or test identity adapters in staging. Compose forces cloud demonstrations off.

After Docker availability and appropriate configuration, build each image locally and
run health/401/protected-read checks. Copy `.env.gateway.example`, `.env.academic.example`
and `.env.scheduling.example` to their respective ignored `.env.container.gateway`,
`.env.container.academic` and `.env.container.scheduling` files. Each container receives
only its own database credential and approved service identity; cloud keys are Gateway-only.
Use verified TLS (`verify-full`), bounded pools matched to the approved DB connection
budget, and independently granted runtime roles for migrations0014–0016. No startup
schema privileges, original database cutover or automatic institutional provisioning.
Never export populated secrets or share provisioning credentials with the other services.
The scheduling service also needs the Academic service URL. The Gateway needs both
service URLs. CORS_ORIGINS is a JSON array of exact HTTPS origins (loopback HTTP only
for local development); an empty list allows same-origin access only.

The Gateway image now installs Poppler, English Tesseract and fonts for bounded local
Linux image/scanned-PDF OCR. Native container execution remains UNVERIFIED: this host has
firmware virtualization disabled and no Docker/usable WSL. Portable boundary tests are
not native OCR evidence. Windows OCR remains supported. No cloud OCR fallback exists.
Run the image-local `scripts.linux_runtime_probe` before staging approval. POSIX512MiB
address-space/15CPU-second limits are per process; the20s parent deadline and process-group
termination bound elapsed processing. Set an independently reviewed container memory/
CPU budget; do not describe POSIX limits as aggregate process-tree memory enforcement.

## Optional course cloud configuration

Default `COURSE_CLOUD_ENABLED=false`. Enabling is an operator action after explicit
approval, not proof of qualification. Provide approved ADC/workload identity with least
privilege, the Firebase project ID, `COURSE_STORAGE_BUCKET`, a currently supported
approved `COURSE_GEMINI_MODEL`, and Secret Manager-managed `GEMINI_API_KEY`. Never use
frontend `VITE_` variables for backend secrets or store key JSON in images/repository.
Check auth-emulator/Firestore-emulator variables are absent from actual cloud staging.

Firestore contains only the separately scoped `classsync_course_preferences` collection:
calendar-view enum, compact boolean, revision and opaque generation. PostgreSQL retains
all academic, identity-membership, enrollment, timetable and publication authority.
Backend SDK access bypasses client rules: use deny-by-default client rules and restrict
the service identity's database privileges. No browser SDK writes are required.

Storage must have **enforced public-access prevention and uniform bucket-level access**;
the adapter reads and verifies these before uploads/downloads. Grant bucket metadata read
and narrowly scoped object create/read/delete, with no public IAM or ACL grants. Use a
dedicated bucket/prefix and approved one-day object lifecycle/retention policy. Only
synthetic UTF-8 course text is supported here; registration evidence remains local/private
in the scanner and is never sent to this adapter. Verify foreign-owner and expired/revoked
credentials cannot download. No signed/public URL is returned.

Gemini has two fixed non-sensitive topics, no personal inputs/tools or scheduling writes.
Its total request deadline is10s; response bytes/output are bounded. Per-process limits
are20 requests/user/minute,6 advisories/user/day,100 advisories/process/day and2 concurrent
provider operations. These counters reset on restart and do not coordinate instances.
Before approval, configure enforceable provider quotas/budget monitoring and an edge
limit; a single-instance cap alone does not enforce a durable daily spend cap. Do not
claim deployment-wide cost enforcement from process-local counters.

## Cloud Run staging checks, after approval

1. Build/scan immutable images and record digests. Resolve the recorded npm audit blocker;
   keep the existing low audit threshold and all CI guards.
2. Configure approved Cloud SQL connectivity/TLS, secrets, service identity and internal
   routing. Review Cloud Run ingress/IAM for Gateway-to-service invocation; the current
   proxy forwards Firebase identity but has no separately qualified Cloud Run IAM token
   transport. Qualify the selected network/IAM setup before claiming deployability.
   Stage an institutional frontend separately with its approved same-origin `/api` proxy
   to the Gateway; the institutional clients deliberately reject cross-origin API bases.
   Preserve the currently deployed read-only presentation and its hosting settings.
3. Rehearse migrations/rollback on a new staging database with backups and approved
   runtime grants. Provision only authorized synthetic qualification memberships.
4. Check liveness,401, current role/tenant isolation, readiness blocking, valid publication,
   matching Student/Teacher views, request decisions, rollback and revocation. Liveness
   alone is not readiness or acceptance.
5. Execute the Postman cloud folder with approved credentials; retain redacted HTTP/status
   evidence for Firestore CRUD/CAS, private Storage/foreign-owner denial and Gemini timeout/
   quota/failure cases. Verify IAM/public-access/retention configuration separately.
6. Verify original data preservation, dependency/CI status, browser widths/native200,
   logs/secret hygiene and explicit release authorization. No production cutover is approved.

API shapes were checked against [Firestore DocumentReference](https://docs.cloud.google.com/python/docs/reference/firestore/latest/google.cloud.firestore_v1.document.DocumentReference),
[Storage Blob](https://docs.cloud.google.com/python/docs/reference/storage/latest/google.cloud.storage.blob.Blob)
and [Gemini generateContent](https://ai.google.dev/api/generate-content). Documentation and
offline interface tests do not substitute for the cloud checks above.

The final environment inventory, budget assumptions, approval dependencies and15-step
acceptance procedure are in `../autonomy/M5_STAGING_ACCEPTANCE.md`.
