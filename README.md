# ClassSync

ClassSync is a university scheduling system for academic records, conflict-aware timetable generation, room discovery and published schedules. It has Student, Teacher and Administrator workspaces. The connected application is under active development; a successful local build or synthetic journey does not establish production readiness.

## Project status and architecture

- **Web:** React 19, TypeScript, Vite and Tailwind CSS.
- **Services:** Python FastAPI Gateway, Academic and Scheduling services; OR-Tools CP-SAT generation with independent schedule validation.
- **Identity and data:** Firebase Authentication proves identity. PostgreSQL is the selected authority for current membership, academic data, schedules, drafts and publication; protected APIs must authorize against current server-side membership. SQLite remains in local sandbox/demo paths. Firestore is optional unless an approved rubric or later owner decision requires it.
- **Readiness:** local implementation is substantial, but production hosting, institutional identity, real Registrar data, backup/restore, security configuration and end-to-end provider behavior remain unverified. The current audit and ordered completion plan are in [docs/audit/](docs/audit/MASTER_IMPLEMENTATION_PLAN.md).
- **Vercel build:** the deployment build now runs `npm run build` in institutional mode; it does not publish the read-only sample entrance. Production sign-in still requires valid Firebase and Gateway configuration, and must not be considered operational until those provider-backed checks pass.

The previous Firestore authority document is retained as a [superseded proposal](docs/production/firestore-authority.md); its qualification receipts are historical evidence, not the current architecture decision.

The code catalog now reflects the uploaded November 2026 room rows: 53 physical spaces, 41 marked schedulable by the source and 12 excluded. Focused catalog, readiness, directory, and Administrator selector checks pass locally. The document summary still conflicts (37/16), and Facilities has not verified operation, type, capacity, equipment, or current availability; no room is made solver-eligible by the source designation alone. See [the room inventory mapping](docs/audit/ROOM_INVENTORY_UPDATE.md). Student registration and onboarding forms use ID format `12-12345` and the institutional email placeholder `juan.delacruz@student.pnm.edu.ph`. The Gateway now validates the ID and lowercase email format and binds only an active roster record with an exact Firebase-verified email match. Existing student rows remain unverified until authorized Registrar data is populated; this local code change does not itself provide or verify that roster. See the [master plan](docs/audit/MASTER_IMPLEMENTATION_PLAN.md).

The institutional login uses a CdM campus access layout with a white sign-in surface and a soft-tinted campus panel. Production/institutional `/auth/login` always renders the real credential form even if legacy preview flags remain in deployment settings; sample role selection is kept at `/dev/role-preview`. Motion for React provides restrained entrance transitions and honors the operating system's reduced-motion setting. First-time students verify a Registrar roster match with a five-minute single-use email code, then link a Firebase password provider; the Gateway records password setup and grants the student membership only after checking Firebase's current provider state. Migration `0020_student_portal_password` adds that membership gate. Returning students may submit their student number and password to `POST /api/v1/auth/student-password-login`; the Gateway resolves the roster email internally, authenticates against Firebase Identity Toolkit, checks the active membership, and returns only a Firebase custom token. Unknown student IDs and invalid passwords share the same response, and shaped IDs follow the Firebase credential-request path to reduce the missing-roster timing signal. Configure `FIREBASE_WEB_API_KEY` (Firebase's public web API key), `TURNSTILE_SECRET_KEY`, `OTP_HMAC_SECRET` (32+ random bytes), `NOTIFICATION_SERVICE_TOKEN`, `RESEND_API_KEY`, and `RESEND_FROM_EMAIL` in ignored environment settings before provider-backed use. The Gateway enforces Turnstile for student lookup, OTP challenge, OTP verification, password completion, and student-number sign-in; the direct Firebase email/password and Google provider calls still cannot be forced through that Gateway check by this code alone. Provider delivery, migration/RLS execution, Auth Emulator, live roster matching, and connected browser acceptance remain unverified. The local bootstrap remains synthetic and does not create an institutional roster, verified room capacity, or official timetable.

Sign-up, OTP password setup, and password-reset completion use the same six-rule password checklist (12+ characters, upper/lowercase, number, special character, and matching confirmation). Forgot Password sends the email and single-use Turnstile token to Gateway `POST /api/v1/auth/request-password-reset`; Gateway creates a Firebase Admin reset action code, then asks Notification to deliver a branded ClassSync email linking directly to `/auth/reset-password?oobCode=…`. The generic success response does not reveal whether an account exists, and the reset email does not display Firebase project IDs or raw URLs. Configure `CLASSSYNC_WEB_URL` to the exact approved frontend origin in Gateway and Notification, plus an authorized Firebase continue URL and the matching internal Notification service token. The reset page validates/completes Firebase's `oobCode` through the Auth SDK. The notification service renders branded table-based HTML and plain-text OTP/reset emails using `EMAIL_PROVIDER` (`resend` or `brevo`); supply the matching sender/key variables in service settings. These integrations are locally tested only; Firebase project authorization, sender approval, provider acceptance, and live delivery still require configuration and external verification.

The login entrance is responsive across narrow phones, tablets, and laptop screens: below 768px it uses a single-column card and hides the campus showcase; 768–959px keeps a centered single-column card; 960px and above uses a two-panel card capped at 980×600px. Fresh Chrome layout checks at 1366×640 (the tested laptop usable viewport), 1440×900, and 390×844 confirmed no page overflow and that the complete desktop login content fits within the card. These local UI checks do not verify Firebase, Turnstile, or Registrar services.

An operator-only account provisioning utility is available at `scripts/provision_live_accounts.py`. It requires a TLS-protected remote PostgreSQL `DATABASE_URL`, `FIREBASE_SERVICE_ACCOUNT_JSON`, an existing tenant tied to the same Firebase project, and explicit tenant/write confirmation. It applies Alembic through head and grants memberships only for a matched active student row in `classync_identity.students` or an existing faculty identity; it does not create a `student_roster` table, infer enrollment, or invent faculty assignments. An initial administrator can be explicitly bootstrapped with a recorded `bootstrap:provision_live_accounts` audit actor; later grants require an active administrator UID. Generated or supplied passwords are printed to the operator's terminal only after provisioning succeeds. **Do not run this against hosted data until the target tenant, operator authority, backups, and release approval have been verified.** No live PostgreSQL or Firebase provisioning was performed for this local change.

## Workspace

| Path                      | Purpose                                                                                |
| ------------------------- | -------------------------------------------------------------------------------------- |
| `apps/web`                | React, TypeScript, and Vite web client                                                 |
| `services/gateway`        | Versioned API boundary and Firebase token verification foundation                      |
| `services/academic`       | Persistent period-scoped academic records, availability and verified resource metadata |
| `services/scheduling`     | CP-SAT weekly batch generation, readiness checks, and independent conflict validation  |
| `services/notification`   | Planned notification delivery service                                                  |
| `packages/api-contracts`  | Shared Python transport contracts and Firebase bootstrap                               |
| `packages/shared-types`   | Shared browser-facing types                                                            |
| `infrastructure/firebase` | Security rules baseline and setup notes                                                |

## Frontend preview

Role-owned screens and navigation are defined in `apps/web/src/routes/route-config.ts`. Routes use `/student/*`, `/teacher/*`, and `/admin/*`; the administrator Schedule Manager is `/admin/schedule-manager`. The root route is a public sign-in entry. `/dev/role-preview` provides an explicitly labeled Student, Teacher, or Administrator UI preview with bounded same-tab session continuity and explicit Exit Preview. It does not authorize backend operations. The component playground is at `/dev/design-system`.

For the original synthetic example, follow [S1 setup and verification](docs/scheduling/s1-engine.md), then select that source under Administrator → Schedule Manager → Generate Weekly Schedule. Its raw-input sandbox requires explicit development flags and accepts synthetic inputs only. Generated candidates require an explicit draft save and are never automatically published.

Start the complete local workspace with `npm run dev` from this worktree. Its launcher resolves shared Python packages from the active worktree before any older editable installs. If starting Uvicorn manually on Windows, set `PYTHONPATH` to the active worktree's `packages/api-contracts`, `packages/persistence`, and repository root first; otherwise a shared `.venv` can import contracts from a different checkout and fail with a missing module such as `classync_contracts.cloud_run`.

S2A adds explicit **Save as Draft → Saved Drafts → Open Draft** with SQLite persistence
across refreshes and backend restarts. Drafts remain unpublished; Student and Teacher
schedules are unchanged. See [S2A setup, API and storage](docs/scheduling/s2a-drafts.md).

S2B adds **Manage Academic Data → Check Readiness → Generate → Save Draft**.
Saved academic periods are the default generation source. Start the Academic service
as well as Gateway and Scheduling, following [S2B setup, contracts and migrations](docs/scheduling/s2b-academic-data.md).
Administrator-entered development records use a separate sandbox scope from the
original synthetic example. No official subjects, teachers or classroom facts are
invented. See [the verified academic-entry workflow](docs/hci/s2b-academic-inputs.md).

The Administrator **Academic Setup** entry explains the period-scoped work before a period is
selected. Once a period is chosen, its calendar, programs, subjects, sections, faculty,
offerings, resource metadata, and scheduling rules appear in one workspace. The sidebar groups
these categories under one destination; category routes remain searchable. Records can be added
or edited inline, with quick jumps, saved-record counts, and links to full category lists. New
program records are selected from the supplied catalog, with duplicates in the period hidden; the
catalog still needs Registrar verification. Counts are informational; use **Validate Readiness**
to check scheduling inputs.
Availability and operating windows use day checkboxes and
30-minute time menus; fixed assignment end times follow the selected offering's approved
meeting durations. New windows start unselected to avoid implying campus hours. Existing
category routes remain available for focused review. The development sandbox label is visible;
synthetic scenario import is separated into Development Tools below setup. The program action
closes when all supplied catalog entries are already present for that period. Schedule
Generation and Conflict Center are labeled as deterministic OR-Tools and independent validation;
no language-model copilot is connected. Their empty states link to the next required action.
Inline form and selection transitions respect the browser's reduced-motion preference.

For local review of the owner-provided bootstrap scenario, run
`python -m scripts.seed_bootstrap_cdm --database-path var/bootstrap-sandbox/classsync.bootstrap-sandbox.sqlite3`.
The script is idempotent and refuses database filenames without the isolated sandbox suffix. It
creates synthetic program/subject/section/faculty/offering inputs in SQLite, leaves the supplied
53-room catalog at its current provisional state, and writes an `owner_bootstrap_seed` manifest.
It does not create student identities, apply the owner-proposed room capacity of 40, verify room
eligibility, or publish a timetable. Those production operations require authorized Registrar
and Facilities data and verified tenant configuration.

Several Administrator routes are still previews or placeholders, including student record lists,
building views, operational reports, and sample communications. Their contents are not live campus
records. See the [Administrator workspace audit](docs/hci/admin-workspace-audit.md) for the
screen-by-screen source review and remaining visual QA gates.

The Administrator dashboard is organized as a period-scoped command center: readiness blockers link
to their relevant setup areas, summary cards open the corresponding management screens, and
publication status is kept distinct from saved drafts. Room counts are schedulable candidates only;
they do not confirm availability or per-offering suitability. The Administrator topbar page picker
uses the existing role-authorized route list. These client interactions do not replace backend
authorization. See the [dashboard redesign plan](docs/hci/admin-dashboard-command-center-plan.md)
for acceptance coverage and remaining browser/accessibility checks.

Administrator operations now use a compact counted selector for period setup, with only the active
academic category expanded; period records and their inline editors remain backed by the existing
academic API. The shared Administrator page picker is a scrollable, grouped selection menu anchored
to a locked 64px topbar. Neutral links, a single active-route accent, full-width labels, and a
theme-matched focus ring keep destinations readable. Mobile uses the navigation drawer in place of
the desktop page picker. Schedule Generation, Conflict Center, and Classroom Requests use denser
command bars, status controls, and non-stretching action layouts. Notifications remain a demonstration
feed with selection filters; delivery is not connected. Production builds split React, Firebase, and
UI vendors; the latest measured chunks were 319 kB, 243 kB, and 47 kB, with no chunk-size warning.
A real local Chrome/Playwright preview check covered the menu at 1366×768, 1440×900, and 1024×768 and
all five secondary Administrator routes at 1366×768 and 390×844. This is UI preview evidence only;
live data/provider, 200% zoom, and assistive-technology acceptance remain separate.

The P4d Administrator workflow slice adds a PostgreSQL-backed, append-only activity audit for
academic period/record/calendar changes, draft saves, and publications. A protected audit endpoint
and `/admin/audit-logs` view expose redacted event metadata to institutional Administrators; preview
mode remains explicitly non-authoritative. The isolated PostgreSQL activity qualification passed
its tenant/RLS and immutability checks. The complete Administrator generate-to-publish browser
journey, Auth Emulator run, native 200% zoom, and keyboard-only workflow remain unverified, so this
slice is not a production-readiness claim. See [P4d acceptance](docs/autonomy/P4D_ADMIN_ACCEPTANCE.md)
and the latest [local qualification record](docs/autonomy/STATUS.md).

See [the frontend audit and route matrix](docs/frontend-audit.md), [architecture](docs/architecture.md), [development](docs/development.md), [API conventions](docs/api-conventions.md), [security](docs/security.md), and [UI/UX system](docs/ui-ux.md). Copy `.env.example` before configuring local services; never commit credentials.

## Validation

Run `npm run lint`, `npm run typecheck`, `npm run test:web`, and `npm run build` from the repository root. Use `npm run dev:web` to start the client.

Academic and scheduling endpoints independently enforce authorization. The S1/S2 examples above describe historical sandbox milestones. Connected local sign-in and publication use isolated synthetic records; hosting, approved academic inputs and institutional release remain separately gated. See [rules and assumptions](docs/scheduling/rules-and-assumptions.md) before supplying institutional data.

P4d remains PARTIAL. The latest local full runs on 19 November passed the Python suite (1,128 tests)
and Web suite (846 tests across 63 files); Web lint, typecheck and build passed, with no mixed Firebase
import or oversized-chunk warnings (largest JavaScript chunk 330.19 kB). On 20 November, the new
provisioning CLI's focused suite passed (13 tests), full Ruff passed, and the production artifact
matrix passed all 5 checks after updating legacy-preview expectations. PostgreSQL migration/RLS,
Firebase Auth Emulator, live provider login, real browser connected workflow, native 200% zoom and
keyboard-only journeys remain open. The CLI is an operator-only tool and was not run against hosted
data. Student verification still requires a matching active Registrar record; roster population and
institutional acceptance remain required. See [P4d acceptance](docs/autonomy/P4D_ADMIN_ACCEPTANCE.md)
and the [current evidence ledger](docs/autonomy/STATUS.md); local checks do not establish production
readiness.

P4d qualification scripts that require disposable PostgreSQL process creation, hosted providers, or
network-based dependency scans are CI/pre-release gates. Their current local evidence and limitations
are recorded in [STATUS](docs/autonomy/STATUS.md); they are not a reason to block fast in-process
development checks.

## Optional backend hosting blueprint

The root `Dockerfile` keeps the existing single-service mode used by Cloud Run CI, sets
`PYTHONPATH=/app` for the container entrypoints, and adds an
opt-in-by-default multi-service image for the root `render.yaml` blueprint. That mode runs the
three internal APIs on loopback and exposes only the Gateway. It performs no migrations or seeding;
Neon runtime-role DSNs, Firebase service credentials, institutional tenant, and exact CORS origins
must be supplied through the hosting provider's secret settings. Notification now exposes a private
verification-email endpoint, but real delivery requires the private service token and verified
Resend sender configuration; no provider delivery has been qualified. This Render Free blueprint
is for qualification or preview only: its documented cold starts, ephemeral local disk, resource
limits, and Render's stated non-production guidance do not satisfy ClassSync's production reliability
gates. It is not deployed, and `vercel.json` remains the presentation build. See [Render
qualification setup](docs/infrastructure/render-free-qualification.md).
