# ClassSync UI/UX system

The Phase 2 direction is a role-aware university workspace: deep navy structure, restrained deep-red actions, light neutral surfaces, compact readable typography, practical information density, and mobile-first task flows. Tokens and components live in `apps/web/src/styles.css` and `apps/web/src/components/ui`.

## Shared system

`AppShell` supplies consistent role-derived workspace context, search, notifications, profile, desktop navigation, mobile bottom navigation, and a mobile drawer. Buttons, alerts, status badges, empty states, modal, drawer, schedule blocks, and room results share the same visual language. Status uses text and semantic iconography as well as color. Focus indicators and labelled controls are provided; dialogs still need production focus trapping/restoration and automated accessibility coverage.

Navigation and route metadata come from `apps/web/src/routes/route-config.ts`. Student, teacher, and administrator paths are distinct; see the complete [frontend audit and route/screen/role matrix](frontend-audit.md). The client-side role guard prevents preview-role route leakage, but is not an authorization boundary.

## Role-specific schedule intent

- Student schedule is read-only and focuses on the student's classes, teachers, sections, rooms, buildings, and updates.
- Teacher schedule focuses on teaching assignments and offers request/report paths; it does not edit the official schedule.
- Administrator Schedule Manager is the only schedule-management screen and carries filters, conflict context, and draft/publish-oriented controls.

All schedule and availability records are local sample content. Availability means scheduled reservation availability, not live physical occupancy. Draft validation and publishing require a future service.

## Responsive behavior

Desktop uses grouped role-specific side navigation and dense work surfaces. At phone sizes the sidebar is replaced by a labelled bottom navigation and role-specific drawer; schedules and room results use compact list/cards, and wide tables are replaced by record cards. Bottom navigation destinations are resolved against the route registry rather than separate URLs.

## Development-only routes

`/dev/role-preview` changes only the local simulated role and explicitly states that it does not authenticate or grant permissions. `/dev/design-system` is a separate component playground. These tools are outside normal product screens. Authentication screens are interaction previews only and do not use Firebase Authentication.

## Deferred production work

Firebase-derived identity and server-enforced access, real academic data, persistence, server-side validation, scheduling/conflict algorithms, production loading/error states, dialog focus management, accessibility automation, and testing against real devices remain future work. Representative names, rooms, metrics, and academic dates are not product commitments.
