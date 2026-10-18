# Local development

Prerequisites: Node 20+, Python 3.12+, and a Firebase project only when testing authenticated behavior.

## One-command local workspace

After installing the existing npm/Python dependencies, run `npm run dev` from the repository
root. The launcher uses `.venv` when present, enables only the explicit local sandbox,
starts Academic (8001), Scheduling (8002), Gateway (8000), and Vite (5173), then verifies
service health and sandbox API reachability before reporting Ready. Existing compatible
services are reused; incompatible ports produce an actionable error. Ctrl+C stops only
processes started by this launcher. There is no automatic import, database reset,
authentication bypass or publication.

For occupied ports: `npm run dev -- --base-port 8830 --web-port 5190`.
`ACADEMIC_DATABASE_PATH` and `SCHEDULING_DATABASE_PATH` remain configurable; defaults
continue to use the existing `var/` databases. Set alternate paths explicitly for QA;
never replace working records with samples. Academic migration v3 adds calendar metadata;
scheduling draft schema v2 and immutable publication tables retain existing records.

The browser must use the Vite URL printed by this command so its proxy reaches the
matching Gateway. `npm run dev:web` alone starts only the frontend and does not verify
the backend. If a service fails, retry after restarting the launcher; do not interpret
the unavailable timetable as a free day. Real publishing still requires verified
Administrator credentials even in the local synthetic dataset.

1. Copy `.env.example` to `.env`, and `apps/web/.env.example` to `apps/web/.env`. Leave Firebase values empty to run the neutral web shell and service health checks. The gateway reads the root `.env` regardless of its working directory.
2. Run `npm install`, then `npm run dev:web` for the Vite app.
3. For each service, create and activate a Python virtual environment, then from its directory run `pip install -r requirements.txt` and start it with `uvicorn app.main:app --reload --port <port>`.

Ports: gateway 8000, academic 8001, scheduling 8002, notification 8003. Check `GET /health` on each process. The gateway can proxy a health check at `/api/v1/services/{academic|scheduling|notification}/health`.

Quality commands: `npm run build`, `npm run lint`, `npm run typecheck`, `npm run test:web`, `pytest`, and `ruff check services packages` after installing `ruff` in the development environment.

## S1 scheduling sandbox

See [the runnable S1 instructions](scheduling/s1-engine.md#run-locally) for the Gateway → Scheduling → OR-Tools workflow. Both services must have `CLASSSYNC_ENV=development` and `ENABLE_SCHEDULING_SANDBOX=true`; the sandbox remains disabled by default. The Vite client uses the same-origin `/api/v1` proxy to Gateway port 8000. Run `pip install -r requirements.txt` from each service directory because the editable shared-contract dependency is relative to that directory.

After changing Python scheduling models, regenerate the checked-in browser contracts with `.\.venv\Scripts\python.exe scripts/export_scheduling_contracts.py` from the root. Run the root Python suite with `.\.venv\Scripts\python.exe -m pytest`; importlib collection keeps identically named service health tests independent.

S2A uses `SCHEDULING_DATABASE_PATH` (default `var/scheduling.sqlite3`, rooted at the
repository). Migrations run on database access. Keep the database on durable local
storage and outside Git. [Draft persistence details](scheduling/s2a-drafts.md) cover
schema checks, API scopes, idempotency and restart verification.

## S2B academic input management

Start Academic on port 8001 as well as Gateway (8000) and Scheduling (8002).
All three require both explicit sandbox flags for the local entry workflow.
Academic owns `ACADEMIC_DATABASE_PATH` (default `var/academic.sqlite3`). Both service
databases migrate transactionally to schema version 2; existing draft snapshots
remain unchanged. Back up databases before deployments or manual maintenance.

Open Administrator → Schedule Manager → Manage Academic Data. Create a period,
enter source records, then check readiness before generating. The original S1
synthetic example remains a separate development-only source. See
[S2B details](scheduling/s2b-academic-data.md) for endpoints, source classifications,
startup commands and limitations. Do not copy local QA records into institutional
data or infer room suitability from the provisional catalog.
