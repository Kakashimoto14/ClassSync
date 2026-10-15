# Local development

Prerequisites: Node 20+, Python 3.12+, and a Firebase project only when testing authenticated behavior.

1. Copy `.env.example` to `.env`, and `apps/web/.env.example` to `apps/web/.env`. Leave Firebase values empty to run the neutral web shell and service health checks. The gateway reads the root `.env` regardless of its working directory.
2. Run `npm install`, then `npm run dev:web` for the Vite app.
3. For each service, create and activate a Python virtual environment, then from its directory run `pip install -r requirements.txt` and start it with `uvicorn app.main:app --reload --port <port>`.

Ports: gateway 8000, academic 8001, scheduling 8002, notification 8003. Check `GET /health` on each process. The gateway can proxy a health check at `/api/v1/services/{academic|scheduling|notification}/health`.

Quality commands: `npm run build`, `npm run lint`, `npm run typecheck`, `npm run test:web`, `pytest`, and `ruff check services packages` after installing `ruff` in the development environment.
