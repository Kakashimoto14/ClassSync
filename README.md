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

P4d local qualification status (18 Nov 2026): latest in-process gates pass with 1115 Python tests,
843 Web tests, Web lint/typecheck/build, and Ruff. The activity-only PostgreSQL audit qualification
was previously verified with disposable data; this turn did not rerun external PostgreSQL or Auth
Emulator qualification. The connected schedule-to-publication browser flow, native 200% zoom, and
keyboard-only end-to-end journey remain open. The student verification code is fail-closed when no
matching active Registrar roster record exists; roster ingestion/population and institutional
acceptance remain required. External qualification scripts and dependency scans are deferred to
CI/pre-release and are not a manual PowerShell prerequisite for local development. See [P4d
acceptance](docs/autonomy/P4D_ADMIN_ACCEPTANCE.md) and the [current evidence ledger](docs/autonomy/STATUS.md);
local checks do not establish production readiness.

P4d qualification scripts that require disposable PostgreSQL process creation, hosted providers, or
network-based dependency scans are CI/pre-release gates. Their current local evidence and limitations
are recorded in [STATUS](docs/autonomy/STATUS.md); they are not a reason to block fast in-process
development checks.

## Optional backend hosting blueprint

The root `Dockerfile` keeps the existing single-service mode used by Cloud Run CI and adds an
opt-in-by-default multi-service image for the root `render.yaml` blueprint. That mode runs the
three internal APIs on loopback and exposes only the Gateway. It performs no migrations or seeding;
Neon runtime-role DSNs, Firebase service credentials, institutional tenant, and exact CORS origins
must be supplied through the hosting provider's secret settings. The Notification API remains a
health-only stub. This Render Free blueprint is for qualification or preview only: its documented
cold starts, ephemeral local disk, resource limits, and Render's stated non-production guidance do
not satisfy ClassSync's production reliability gates. It is not deployed, and `vercel.json` remains
the presentation build. See [Render qualification setup](docs/infrastructure/render-free-qualification.md).
