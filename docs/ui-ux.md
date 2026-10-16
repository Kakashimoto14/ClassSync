# ClassSync UI/UX system

The UI-01 direction is **Soft Rouge Mobile**: white surfaces, cool-neutral canvas, restrained rouge actions, readable Inter typography, and task-focused mobile layouts. Active tokens and the self-hosted font definition live in `apps/web/src/theme.css`; `styles.css` imports that file and retains explicit base, shared-component, shell, feature, and responsive sections. Existing untracked Sapphire styles are not imported or modified.

## Shared system

`AppShell` supplies role-derived workspace context, search, notifications, profile, desktop navigation, mobile bottom navigation, and a mobile drawer. Buttons, alerts, status badges, empty states, modal, drawer, schedule entries, and room cards share tokens. Controls are at least 48px high on mobile and 44px on desktop. Status uses text and semantic iconography as well as color. `DialogSurface` owns focus containment/restoration, inert background, and scroll locking; focused tests cover this behavior. This is not a full accessibility conformance claim.

The existing Tailwind build remains intact. Global component selectors deliberately override preflight; page-level Tailwind colors do not provide a second theme. Brand artwork colors are independent from UI tokens. No dark-mode or motion system was added.

Navigation and route metadata come from `apps/web/src/routes/route-config.ts`. Student, teacher, and administrator paths are distinct; see the complete [frontend audit and route/screen/role matrix](frontend-audit.md). The client-side role guard prevents preview-role route leakage, but is not an authorization boundary.

## Role-specific schedule intent

- Student schedule is read-only and focuses on the student's classes, teachers, sections, rooms, buildings, and updates.
- Teacher schedule focuses on teaching assignments and offers request/report paths; it does not edit the official schedule.
- Administrator Schedule Manager is the only schedule-management screen and carries filters, conflict context, and draft/publish-oriented controls.

All schedule and availability records are local sample content. Availability means scheduled reservation availability, not live physical occupancy. Draft validation and publishing require a future service.

## Responsive behavior

Desktop uses grouped role-specific side navigation and dense work surfaces. At phone sizes the sidebar is replaced by a labelled bottom navigation and role-specific drawer; schedules and room results use compact list/cards, and wide tables are replaced by record cards. Bottom navigation destinations are resolved against the route registry rather than separate URLs.

The desktop grid owns the 256px sidebar track. Branding, independently scrollable navigation, and the reserved account region remain separate. Mobile uses a 64px header, a 72px bottom-navigation allocation plus safe area, and matching content padding. Student bottom navigation is exactly Home, Schedule, Rooms, Alerts.

The Student dashboard features current/next assignments once, followed by a compact chronological list of other remaining classes. A typed optional action on `NextClassSummary` opens the registered Student schedule. Existing deterministic selectors and fixtures are unchanged. The smaller sample-day label and supporting note identify the demo without displacing the next-class information.

`RoomDirectoryCard` displays resource metadata, not sensed occupancy or calculated availability. Only the existing Administrator SCI-218 detail destination receives a detail link. Other rooms retain visible metadata rather than linking to the same page, another search, or the wrong resource. No new room-detail routes were added.

## Development-only routes

`/dev/role-preview` changes only the local simulated role and explicitly states that it does not authenticate or grant permissions. `/dev/design-system` is a separate component playground. These tools are outside normal product screens. Authentication screens are interaction previews only and do not use Firebase Authentication.

## Deferred production work

Firebase-derived identity and server-enforced access, real academic data, persistence, server-side validation, scheduling/conflict algorithms, service-driven loading/error states, broader accessibility automation, and testing against real devices remain future work. Feature pages still use older independent preview fixtures; UI-01 does not unify their data with the dashboard. Representative names, rooms, metrics, and academic dates are not product commitments. See `ui-01-verification.md` for executed checks and remaining limits.
