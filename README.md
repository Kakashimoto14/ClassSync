# ClassSync

ClassSync is a university classroom scheduling, availability, and conflict-management application. The repository contains the Phase 1 service/foundation architecture and a Phase 2 role-aware frontend prototype. The frontend uses local representative data; it is not connected to authenticated accounts or production academic records.

## Workspace

| Path | Purpose |
| --- | --- |
| `apps/web` | React, TypeScript, and Vite web client |
| `services/gateway` | Versioned API boundary and Firebase token verification foundation |
| `services/academic` | Planned academic reference-data and availability service |
| `services/scheduling` | Planned scheduling and conflict service |
| `services/notification` | Planned notification delivery service |
| `packages/api-contracts` | Shared Python transport contracts and Firebase bootstrap |
| `packages/shared-types` | Shared browser-facing types |
| `infrastructure/firebase` | Security rules baseline and setup notes |

## Frontend preview

Role-owned screens and navigation are defined in `apps/web/src/routes/route-config.ts`. Routes use `/student/*`, `/teacher/*`, and `/admin/*`; the administrator Schedule Manager is `/admin/schedule-manager`. The root route is a public sign-in entry. In this repository's local configuration, production authentication is not configured: `/dev/role-preview` provides an in-memory, explicitly labeled Student, Teacher, or Administrator UI demo that clears on refresh/sign-out and is not authentication or authorization. The component playground is at `/dev/design-system`.

See [the frontend audit and route matrix](docs/frontend-audit.md), [architecture](docs/architecture.md), [development](docs/development.md), [API conventions](docs/api-conventions.md), [security](docs/security.md), and [UI/UX system](docs/ui-ux.md). Copy `.env.example` before configuring local services; never commit credentials.

## Validation

Run `npm run lint`, `npm run typecheck`, `npm run test:web`, and `npm run build` from the repository root. Use `npm run dev:web` to start the client.

The UI prototype intentionally does not implement real Firebase authentication, CRUD persistence, production data access, or scheduling algorithms. Frontend route guards are not a security boundary; the future API must independently authorize every request.
