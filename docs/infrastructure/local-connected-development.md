# Local connected development

Run from the feature worktree with Node 22, Python 3.12 and Windows PostgreSQL with SSPI.

```powershell
npm run dev:connected
```

The command checks dependencies and the requested frontend port, creates a new marked disposable PostgreSQL cluster, applies the existing migrations, starts the owned Firebase Authentication Emulator, then starts Gateway, Academic, Scheduling and Vite. It checks all three service health endpoints and the Gateway's unauthenticated 401 boundary before reporting readiness.

The default frontend is http://127.0.0.1:5191/. The terminal prints the dynamically allocated Gateway, Academic, Scheduling and Auth URLs. The browser uses /api/v1 through Vite's same-origin proxy. Other existing servers are left running. An occupied port produces an explicit error. Set CLASSSYNC_DEV_PORT in your terminal to choose another frontend port.

This is synthetic connected development. It uses real Firebase SDK and Auth Emulator requests, real FastAPI services and PostgreSQL membership checks. A persistent visible label identifies the local test environment. The supplied academic fixture is synthetic and published only inside that disposable database.

## Accounts and verification

The terminal prints the path to a private dev-accounts.json file containing the session's generated password, Admin and Teacher emails, and the synthetic record IDs. Open that file locally. Its contents belong outside Git. Credentials are generated per session and do not appear in launcher logs.

Create a Student account using a synthetic email address. Claim the supplied Student record. The Admin can approve that claim using a synthetic verification reference. An approved faculty record can receive an invitation that the provisioned Teacher account accepts.

The terminal also prints the Auth Emulator /oobCodes URL. Open it locally to obtain the email action link for a test account's verification or password reset. The emulator sends no real email.

Each launch has a distinct emulator project and browser persistence key. Browser refresh restores a session within the running environment. A new launch starts with new disposable accounts and records.

## Shutdown and data lifecycle

Type stop and press Enter in the launch terminal, or use Ctrl+C. The printed alternate stop command writes the owned session's stop marker. The launcher closes Vite and all three APIs, stops its Auth Emulator, and stops its marked PostgreSQL cluster. It also detects loss of the supervising process.

There is no evaluation timer. The environment stays usable until intentionally stopped. Temporary database files remain in the marked session directory for diagnostic evidence. Restarting creates a fresh isolated environment. Original SQLite files and institutional databases are never selected by this command.

## Prerequisites

- Run npm ci from the repository root if node_modules is absent.
- Create the worktree .venv with Python 3.12. Install the existing Gateway, Academic and Scheduling requirements from their service directories so their relative editable dependencies and constraints resolve correctly.
- Install PostgreSQL for Windows and add its bin directory to PATH, or set CLASSSYNC_POSTGRES_BIN to that directory.
- The launcher discovers the existing pinned Auth tooling in a classsync-auth-tools-* direct child of the system temporary directory. Its required versions are firebase-tools 15.34.1, @opentelemetry/core 2.8.0 and uuid 11.1.1. CLASSSYNC_AUTH_TOOLS_ROOT can explicitly select that installation. Missing or mismatched versions stop startup before services are launched.
- The current disposable database adapter requires Windows SSPI and the current Windows principal. Linux container qualification is a separate release check.

## Modes and configuration

| Entry | Behavior |
| --- | --- |
| npm run dev:connected | Owned persistent synthetic environment, default port 5191 |
| Plain Vite, including a server on 5190 | UI only unless explicitly configured for institutional providers |
| npm run dev | Existing scheduling sandbox and its existing startup policy |
| npm run build:presentation | Separate read-only public sample build |

Port 5173 is Vite's default port, not an authentication mode. Ports 5190, 5191 and 5192 have no authorization meaning. The mode and provider configuration determine capabilities. The earlier 5192 process was a separately served presentation artifact, not a required backend.

A plain Vite launch cannot locate configuration from another worktree. For an authorized real-provider development environment, set the existing client-safe Firebase variables in this worktree and explicitly select institutional mode. Configure the Gateway and its current PostgreSQL memberships separately. A missing Firebase setup or failed local Gateway auth probe withholds credential controls. Developer console diagnostics list missing variable names and provider stages without keys, passwords or token contents.

## Environment inventory

Names and descriptions only follow. Actual secrets belong in ignored local files or managed secret storage.

| Name | Purpose |
| --- | --- |
| CLASSSYNC_DEV_PORT | Optional frontend port for owned local development |
| CLASSSYNC_AUTH_TOOLS_ROOT | Optional pinned Auth Emulator tool installation |
| CLASSSYNC_POSTGRES_BIN | Optional installed PostgreSQL binary directory |
| VITE_CLASSSYNC_MODE | Explicit institutional, presentation or sandbox mode |
| VITE_API_BASE_URL | Browser Gateway base, normally /api/v1 |
| VITE_CLASSSYNC_PRESENTATION_URL | Optional separate read-only sample origin |
| VITE_FIREBASE_API_KEY | Client-safe Firebase web app key |
| VITE_FIREBASE_AUTH_DOMAIN | Approved Firebase Auth domain |
| VITE_FIREBASE_PROJECT_ID | Client Firebase project identity |
| VITE_FIREBASE_STORAGE_BUCKET | Client Firebase storage configuration |
| VITE_FIREBASE_MESSAGING_SENDER_ID | Client Firebase messaging configuration |
| VITE_FIREBASE_APP_ID | Client Firebase web app identity |
| FIREBASE_PROJECT_ID | Backend verifier's approved project |
| INSTITUTIONAL_TENANT_ID | Current institutional membership scope |
| GOOGLE_APPLICATION_CREDENTIALS | Backend credential file where workload identity is unavailable |
| IDENTITY_DATABASE_URL | Gateway membership database connection |
| ACADEMIC_DATABASE_URL | Academic authoritative database connection |
| SCHEDULING_DATABASE_URL | Scheduling authoritative database connection |
| IDENTITY_DATABASE_TRANSPORT | Gateway TLS transport policy |
| ACADEMIC_DATABASE_TRANSPORT | Academic TLS transport policy |
| SCHEDULING_DATABASE_TRANSPORT | Scheduling TLS transport policy |
| ACADEMIC_SERVICE_URL | Private Academic service endpoint |
| SCHEDULING_SERVICE_URL | Private Scheduling service endpoint |
| CORS_ORIGINS | Exact approved frontend origins as a JSON allowlist |
| DATABASE_POOL_SIZE | Per-service bounded database pool |

FIREBASE_AUTH_EMULATOR_HOST, test identity adapters and local SSPI transport are controlled only by the owned local launcher. Hosted production or staging settings must use real token verification and approved database TLS.

## Hosted staging boundary

The parent workspace's existing client configuration identifies classsync-f444c. That does not establish its staging designation, Email/Password provider state, authorized domains or backend administrative identity. This feature worktree has no authenticated Vercel project link. Confirm the staging project and supply an authenticated provider connection before changing hosted settings.

Use the existing scoped environment templates, container configurations and staging checklist. Verify provider health and migration head in an approved staging database. Rehearse upgrades and rollback on a separate copy before cutover. Preserve current publication revisions and RLS. Restore the prior service revision for application rollback, and follow the existing backup/restore procedure for database rollback. Hosted provisioning and deployment require separate approval.

## Hosted target confirmation and inspection status — 7 November 2026

The owner confirms classsync-f444c as the existing Firebase project and class-sync-bhiv as the Vercel project currently serving the public presentation. Neither confirmation establishes that Firebase is staging-exclusive. The owner has approved read-only configuration inspection only.

Local client configuration identifies classsync-f444c, but authenticated provider state, authorized domains, billing/resource inventory and environment isolation remain unverified. The available in-app browser has no signed-in console tabs. Native browser inspection stopped because the computer-use safety layer could not determine its current URL. No hosted changes or Firebase user reads were performed. Do not infer staging suitability from a client project ID or a public presentation URL.

Before approving hosted changes, inspect Firebase project/environment designation, web app registration, enabled sign-in providers, authorized domains and existing resource dependencies without reading user records. Inspect the Vercel production branch, per-environment build command and environment-variable names, preview deployment policy and deployment protection. Preserve the existing presentation build and production branch. Use an authenticated provider connection or owner-supervised console review; never send credentials in chat.

Unless this review establishes that classsync-f444c is isolated for staging, use a separate staging Firebase project, subject to explicit provisioning approval. Proposed later staging changes are: enable the approved Email/Password provider, allow only approved frontend domains, configure the frontend's client-safe project registration and same-origin Gateway, configure private backend identity and managed PostgreSQL with TLS, and provision synthetic authorized memberships through the existing trusted process. No real institutional accounts or imports are required for acceptance. Keep emulator trust variables absent from hosted environments.

The connected staging target also needs approved service origins, private service communication, narrowly scoped service identities, managed secret references, scanner retention/storage configuration and a migration/rollback rehearsal. Firestore/Gemini remain separately scoped and require their own provider qualification. Review costs against actual resource choices before provisioning; no cloud budget or resource availability is assumed here.
