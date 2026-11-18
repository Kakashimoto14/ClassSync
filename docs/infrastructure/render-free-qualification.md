# Render free-tier backend blueprint — qualification only

This configuration is an importable **$0 qualification/preview path**, not a production
deployment approval. Render currently documents that Free web services are not for
production use: they spin down after 15 minutes without inbound traffic, may take about a
minute to wake, have an ephemeral filesystem, and may restart at any time. Render also
recommends running applications in separate services instead of combining them because of
resource isolation and performance. ClassSync deliberately keeps the requested single
container option isolated from the existing per-service Cloud Run build mode. See the
[Render Free instance limitations](https://render.com/docs/free) and
[Render FAQ](https://render.com/docs/faq).

## What the blueprint does

- `render.yaml` describes one Docker web service, uses `main`, disables automatic deploys,
  checks `/health`, and prompts for secrets without storing values in Git.
- The default Docker build installs Gateway, Academic, Scheduling, and Notification. Existing
  CI and Cloud Run builds continue to pass `--build-arg SERVICE=gateway|academic|scheduling`
  and retain the original one-service entrypoint.
- `scripts/render_entrypoint.py` starts Academic, Scheduling, and Notification on loopback
  ports 8001–8003, waits for their health endpoints, then starts Gateway on Render's `$PORT`.
  An internal process exit stops the whole container so Render can restart a coherent instance.
  Access logs are disabled, all processes run as the non-root `classsync` user, and startup
  never migrates or seeds a database.
- Gateway accepts exact allowlisted origins from either `CORS_ALLOWED_ORIGINS` (preferred) or
  the existing `CORS_ORIGINS` JSON-array environment variable. The blueprint defaults to the
  existing Vercel origin. Add any custom frontend origin explicitly in Render's settings.
- The existing presentation-only `vercel.json` is unchanged. After a separately authorized
  backend deployment, Vercel must be configured with the approved `VITE_API_BASE_URL` for the
  connected build; do not replace its presentation build with a connected deployment by default.

## Operator prerequisites before importing

Render does not create a Neon database through this blueprint. Prepare the Neon project, schema
upgrade/restore rehearsal, and three least-privilege runtime DSNs separately:

| Render environment variable | Required value |
| --- | --- |
| `IDENTITY_DATABASE_URL` | Gateway-only PostgreSQL role and approved database endpoint |
| `ACADEMIC_DATABASE_URL` | Academic-only PostgreSQL role and endpoint |
| `SCHEDULING_DATABASE_URL` | Scheduling-only PostgreSQL role and endpoint |
| `INSTITUTIONAL_TENANT_ID` | Owner-approved tenant key |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Restricted Firebase Admin service identity for the approved project |
| `CORS_ALLOWED_ORIGINS` | JSON array of exact HTTPS Vercel/custom origins |

The three database URLs must use verified TLS supported by the target database, match the
existing `verify-full` configuration, and have pool capacity for the configured two connections
per service. Do not paste secrets into this repository or a public issue. Existing users and
memberships, current database head, Firebase allowed domains, email verification policy, and
separate API authorization must be qualified before real accounts are admitted. The deployment
does not create the Registrar roster, run Alembic, import data, or establish a published timetable.

The Notification service is currently a `/health` stub; this container does not send email or
verification codes. The single-instance free plan also places three database clients and the
CP-SAT solver in a 0.1 CPU / 512 MB service, so memory, solver latency, concurrency, cold-start,
recovery, and institutional workflow acceptance are not established. Render Free Postgres is not
used: its documented expiry and backup limits do not meet ClassSync's recovery needs. If the free
configuration cannot meet privacy, recovery, responsiveness, and availability gates, do not use it
for live university scheduling; keep production blocked instead of silently upgrading or relaxing
requirements.

## Local checks

The supervisor's configuration and routing plan have in-process unit coverage. Parse `render.yaml`
with a YAML parser and build/run both the default multi-service image and each explicit single-
service image in CI before import. Native Docker build/runtime, Render blueprint import, Neon TLS,
Firebase credential validation, real migration/recovery, connected browser workflows, and cost
behavior are **UNVERIFIED** until performed in separately authorized environments.
