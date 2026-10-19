# Deployment decision — UX-06

## Confirmed deployment failure

Local clean baseline and pushed `main` were both
`409279e6a44df34097c3c854b1c46ac1bc5cb201`. GitHub's latest successful Production
deployment records that SHA and environment URL
`https://class-sync-bhiv-noq8fm7i0-aarons-projects-401d02e7.vercel.app`.
Authenticated Vercel project settings are unavailable. The unique environment URL redirects to Vercel login and therefore could not be
compared with the public alias artifact, so **the exact alias SHA is not certified**
from this comparison. The recorded successful GitHub deployment and the observed
public alias artifact are reported separately, rather than assuming parity.

Actual Chrome journeys through the welcome screen work via client-side navigation.
Student and Teacher then request:

`GET https://class-sync-bhiv.vercel.app/api/v1/timetables/periods`

Response: **404**, `text/plain; charset=utf-8`, beginning:

```text
The page could not be found

NOT_FOUND
```

The sandbox-period path also returns 404 plain text. Direct `/dev/role-preview`
navigation fails; refreshing nested workspaces is not reliable. Root homepage,
client routing and loaded logo images are separate successful observations.
The Administrator page makes no data request and presents a generic prompt because
the old production build disables development scheduling operations.

There is no deployed Gateway target configured in the repository, no serverless
Python API, no Vercel project-link metadata/CLI credentials, and no root SPA routing
configuration at baseline. Local `/api` works through Vite's development proxy;
that proxy is not shipped with `dist`. Firebase initialization cannot supply those
missing FastAPI routes or expose local SQLite records.

Gateway's current CORS allowlist contains only `http://localhost:5173`. A future
cross-origin production API also needs an approved exact frontend allowlist; no
security-policy change was made here.

## Decision

**Recommend Option A for the present presentation.** It is staged locally, with a
versioned approved synthetic timetable and explicit source selection. Do not deploy
until the owner approves the concrete read-only build and project settings.
Proceed to Option B only as a separately approved infrastructure/migration phase.

| | A — Read-only public presentation | B — Deployed authorized backend |
| --- | --- | --- |
| Frontend | Existing Vercel Vite site | Same frontend with reachable HTTPS API |
| Timetable source | Lazy bundled `classsync-presentation-v1`, synthetic, October–December 2026 | Authorized database projections of published schedules |
| Roles | Preview navigation; Student/Teacher projections of explicitly selected sample; Admin can review frozen sample | Verified Firebase identities, tenant/role/enrollment/faculty authorization |
| Generation / save / publish | Unavailable; no API requests or success simulation | Real FastAPI + OR-Tools + independent validation + immutable drafts + transactional publication |
| Realtime | Explicitly absent | Existing version-aware protocol, tested on deployed hosting with reconnect/recovery |
| Persistence | No database access/writes | Durable shared transactional database and backups |
| Risk | Misrepresentation if labels/flags removed; mitigate explicit role entry and visible source version | Identity, networking, concurrency, migration, data isolation and operational cost |
| Approval | Review/deploy this artifact; verify project root, environment and rewrite settings | Cloud budget, credentials/IAM, security policy, schema migration and deployment |

The sample was exported read-only from an existing validated, synthetic-only draft.
It has 1 section, 2 offerings, 4 weekly sessions and 53 dated occurrences. Teacher
display names are readable sample aliases; stable IDs remain. Change flags are
false because this frozen version has no live change stream. Its metadata records
the source input hash and validation **at export**, not current campus validation.
It neither overwrites server records nor impersonates an official publication.

## Staged Vercel configuration — not applied

`vercel.json` assumes **repository-root Root Directory**, `npm run build`, output
`apps/web/dist`. The owner must inspect the actual Vercel Root Directory before
applying it; this setting was not accessible to the audit. Explicit frontend route
prefixes rewrite to `index.html`; `/api/*` is deliberately excluded and must retain
a real HTTP error until a real API exists. Static logo/favicon paths stay static.

For the approved presentation build only:

```text
VITE_ENABLE_ROLE_PREVIEW=true
VITE_ENABLE_PRESENTATION_SAMPLE=true
```

Leave `VITE_API_BASE_URL` at `/api/v1` for the ordinary connected build. The
presentation does not call it. Never point a public build to localhost/private QA
ports. Sample mode is not an automatic fallback when an institutional API fails.
Both flags are opt-in; ordinary production builds keep preview disabled. Existing
backend sandbox flags stay false in public hosting. Do not upload server secrets.

After owner approval: deploy the reviewed revision, confirm its SHA in Vercel,
verify root/deep-route refresh and all three roles on the public URL, inspect logo/
favicon, confirm zero API/mutation requests in sample mode, and retain rollback.
Local production emulation cannot certify unapplied Vercel project configuration.

## Full-backend target and tradeoffs

Recommended later target: Vercel frontend; Gateway, Academic and Scheduling as
Cloud Run Linux services; managed PostgreSQL for transactional academic/draft/
publication state; Firebase Auth for verified identities. Service contracts and
OR-Tools remain. SQLite remains local development storage.

- OR-Tools Linux/container compatibility is viable in principle; pinned Python and
  wheel versions require an actual container build and benchmark. Start solver
  sizing experiments at 1–2 vCPU and 2 GiB, concurrency 1 per scheduling instance,
  with explicit maximum instances and bounded queues. This is a proposed baseline,
  not a measured cloud capacity claim.
- Existing solver limit is at most 30 seconds and Gateway proxy timeout 45 seconds.
  Measure cold starts, validation and database overhead; align client/Gateway/Cloud
  Run timeouts and move longer future workloads to jobs rather than inventing
  progress. Do not share solver concurrency limits with long-lived SSE clients.
- Cloud Run supports Linux containers but instance-local filesystem data is
  ephemeral. Do not host authoritative SQLite there. Runtime/timeouts are described
  in the [container contract](https://docs.cloud.google.com/run/docs/container-contract)
  and [request-timeout guidance](https://docs.cloud.google.com/run/docs/configuring/request-timeout).
- Preserve version ordering, reconnect, foreground refetch and server-originated
  events. Test SSE proxy buffering, timeout/reconnect and multiple instances.
  An in-process semaphore does not coordinate all instances.
- Private Academic/Scheduling ingress requires service-to-service identity in
  addition to forwarded end-user Firebase identity; the current proxy does not
  implement Cloud Run IAM tokens. Approve and test that adapter, exact CORS
  allowlists, TLS, workload identities, Secret Manager and log redaction.
- PostgreSQL needs a separately approved adapter/migration: immutable JSON/checksums,
  foreign keys, atomic optimistic publication checks, scope uniqueness and outbox
  behavior must survive. Export, rehearse, checksum, restore and test rollback before
  any production migration. No migration was implemented here.
- A single durable VM/persistent-disk SQLite deployment is an alternative with less
  adapter work, but requires single-writer ownership, backups and operations and
  does not solve horizontal scaling. Firestore is not a drop-in relational migration.
- Co-locate services/database in an approved region after latency, residency and
  product availability review. Singapore is a candidate for measurement, not an
  automatically selected database location.

## Cost envelope and approval

No paid resource was provisioned and no new cost was authorized. Option A adds no
backend/database service; existing Vercel plan eligibility and bandwidth limits
still need owner confirmation.

Illustrative compute demand for Option B: 20 solver runs/day × 30s × 30 days at
1 vCPU is **18,000 vCPU-seconds**, and 2 GiB is **36,000 GiB-seconds**. This is
arithmetic, not a benchmark. The request-based free tier lists 180,000 vCPU-seconds,
360,000 GiB-seconds and 2 million requests, shared across the billing account with
region/billing qualifications. Cold starts, API reads and active SSE add usage;
build/artifact/network costs are separate. See [Cloud Run pricing](https://cloud.google.com/run/pricing).

For a scale reference only, the pricing page lists shared `db-f1-micro` at
$0.0105/hour in its selected default context: 730 hours is about **$7.67/month for
instance compute alone**. It excludes storage, backups, networking, HA, regional
differences and taxes; shared CPUs have no Cloud SQL SLA and are not a production
recommendation. Obtain a region/size-specific quote before approving an always-on
database. See [Cloud SQL pricing](https://cloud.google.com/sql/pricing?hl=en).

Required approval for B: chosen region and maximum budget; billing account;
production data/identity ownership; credential/IAM policy; database and rollback
plan; public API/CORS/ingress policy; deployment and ongoing operations. Until then,
**public live timetable generation/publication is NOT DEPLOYED**.
