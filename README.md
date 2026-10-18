# ClassSync

ClassSync is a university classroom scheduling, availability, and conflict-management application. The role-aware React frontend retains representative dashboard data. S1 adds a real Python OR-Tools weekly batch generator, independent timetable validator, and an Administrator development sandbox through the API Gateway. Production academic records and university sign-in are not configured.

## Workspace

| Path | Purpose |
| --- | --- |
| `apps/web` | React, TypeScript, and Vite web client |
| `services/gateway` | Versioned API boundary and Firebase token verification foundation |
| `services/academic` | Persistent period-scoped academic records, availability and verified resource metadata |
| `services/scheduling` | CP-SAT weekly batch generation, readiness checks, and independent conflict validation |
| `services/notification` | Planned notification delivery service |
| `packages/api-contracts` | Shared Python transport contracts and Firebase bootstrap |
| `packages/shared-types` | Shared browser-facing types |
| `infrastructure/firebase` | Security rules baseline and setup notes |

## Frontend preview

Role-owned screens and navigation are defined in `apps/web/src/routes/route-config.ts`. Routes use `/student/*`, `/teacher/*`, and `/admin/*`; the administrator Schedule Manager is `/admin/schedule-manager`. The root route is a public sign-in entry. `/dev/role-preview` provides an explicitly labeled Student, Teacher, or Administrator UI preview with bounded same-tab session continuity and explicit Exit Preview. It does not authorize backend operations. The component playground is at `/dev/design-system`.

For the original synthetic example, follow [S1 setup and verification](docs/scheduling/s1-engine.md), then select that source under Administrator → Schedule Manager → Generate Weekly Schedule. Its raw-input sandbox requires explicit development flags and accepts synthetic inputs only. Generated candidates require an explicit draft save and are never automatically published.

S2A adds explicit **Save as Draft → Saved Drafts → Open Draft** with SQLite persistence
across refreshes and backend restarts. Drafts remain unpublished; Student and Teacher
schedules are unchanged. See [S2A setup, API and storage](docs/scheduling/s2a-drafts.md).

S2B adds **Manage Academic Data → Check Readiness → Generate → Save Draft**.
Saved academic periods are the default generation source. Start the Academic service
as well as Gateway and Scheduling, following [S2B setup, contracts and migrations](docs/scheduling/s2b-academic-data.md).
Administrator-entered development records use a separate sandbox scope from the
original synthetic example. No official subjects, teachers or classroom facts are
invented. See [the verified academic-entry workflow](docs/hci/s2b-academic-inputs.md).

See [the frontend audit and route matrix](docs/frontend-audit.md), [architecture](docs/architecture.md), [development](docs/development.md), [API conventions](docs/api-conventions.md), [security](docs/security.md), and [UI/UX system](docs/ui-ux.md). Copy `.env.example` before configuring local services; never commit credentials.

## Validation

Run `npm run lint`, `npm run typecheck`, `npm run test:web`, and `npm run build` from the repository root. Use `npm run dev:web` to start the client.

University sign-in, schedule publication, and deployment with approved institutional data remain outside S2B. Academic and scheduling endpoints independently verify administrative authorization; frontend route guards and preview selections are not a security boundary. See [rules and assumptions](docs/scheduling/rules-and-assumptions.md) before supplying institutional data.
