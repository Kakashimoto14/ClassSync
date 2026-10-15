# Frontend routing and UX audit

## Findings and corrections

The initial defect was architectural: role-agnostic paths and duplicated navigation allowed a personal “My Schedule” action to open an administrator-oriented schedule screen. Shared shell/page defaults amplified this by making the administrator experience the implicit fallback. Mobile navigation and quick links also had destinations outside one source of truth.

The frontend now has one typed route registry (`apps/web/src/routes/route-config.ts`) containing the path, role, title, purpose, screen kind, icon, sidebar group, and mobile label. Router entries are generated from this registry. `RoleRoute` checks the development role before rendering a screen and sends mismatches to a clear forbidden state. Sidebar, search results, mobile links, and dashboard actions use the same role-owned paths. The three scheduling experiences are distinct: `/student/schedule`, `/teacher/schedule`, and `/admin/schedule-manager`.

The role context is only an in-memory local preview that begins without a role. It is not authentication; direct API access must later be protected by server-side authorization. All product data/actions remain local and non-persistent. Disabled controls and explanatory copy mark operations that need backend validation.

## Route, screen, purpose, navigation, and access matrix

Every registry route is included below. “Sidebar” means generated from role navigation metadata; routes without a sidebar item are reachable through their parent screen actions or role-filtered workspace search.

| Route | Screen and purpose | Navigation source / primary action | Allowed role |
| --- | --- | --- | --- |
| `/student/dashboard` | Student day overview, next class, updates | Sidebar Dashboard; view schedule / find room | Student |
| `/student/schedule` | Personal classes, instructors, section, room, building, status | Sidebar and mobile Schedule; view class details | Student |
| `/student/calendar` | Student classes and changes by date | Sidebar Calendar; move between months | Student |
| `/student/rooms` | Room directory and location/facilities | Sidebar and mobile Rooms; inspect room | Student |
| `/student/find-room` | Search rooms by planned availability and requirements | Sidebar Find Available Room; inspect option | Student |
| `/student/notifications` | Student schedule and room updates | Sidebar and mobile Alerts; review update | Student |
| `/student/announcements` | Academic notices | Sidebar Announcements; read notice | Student |
| `/student/profile` | Student account and academic context | Profile link/drawer; open settings | Student |
| `/student/settings` | Student notification preferences | Settings link/drawer; adjust preference | Student |
| `/teacher/dashboard` | Teaching day, room, requests, updates | Sidebar Dashboard; view schedule / request change | Teacher |
| `/teacher/schedule` | Teaching assignments, sections, rooms, updates | Sidebar and mobile Schedule; request room change | Teacher |
| `/teacher/calendar` | Teaching assignments and room changes by date | Sidebar Calendar; move between months | Teacher |
| `/teacher/room-availability` | Planned classroom availability for teaching | Sidebar and mobile Rooms; find room | Teacher |
| `/teacher/find-room` | Compare suitable rooms before a request | Sidebar Find Available Room; open change request | Teacher |
| `/teacher/change-requests` | Track submitted requests and decisions | Sidebar and mobile Requests; create request | Teacher |
| `/teacher/change-requests/new` | Submit a classroom change request for review | Parent request action; submit (disabled pending service) | Teacher |
| `/teacher/change-requests/detail` | Inspect request status and context | Parent request action; return to request list | Teacher |
| `/teacher/report-issue` | Report a classroom issue | Sidebar Report Issue; submit (disabled pending service) | Teacher |
| `/teacher/notifications` | Teaching, room, and request updates | Sidebar and mobile Alerts; review update | Teacher |
| `/teacher/announcements` | Academic notices | Sidebar Announcements; read notice | Teacher |
| `/teacher/profile` | Teacher account and teaching context | Profile link/drawer; open settings | Teacher |
| `/teacher/settings` | Teacher notification preferences | Settings link/drawer; adjust preference | Teacher |
| `/admin/dashboard` | Campus schedule, room, conflict, and request overview | Sidebar Dashboard; manage schedule / review conflict | Administrator |
| `/admin/schedule-manager` | Official schedule overview and management context | Sidebar and mobile Schedule; create schedule / review conflict | Administrator |
| `/admin/schedule-manager/create` | Prepare a schedule draft and required checks | Schedule Manager action; save draft (disabled pending service) | Administrator |
| `/admin/calendar` | Campus schedules and changes by date | Sidebar Calendar; move between months | Administrator |
| `/admin/conflicts` | Investigate schedule conflicts | Sidebar and mobile Conflicts; inspect conflict | Administrator |
| `/admin/conflicts/detail` | Inspect conflicting assignments and resolution context | Conflict action; review schedule / available room | Administrator |
| `/admin/requests` | Review teacher change requests and issue reports | Sidebar Requests; inspect request | Administrator |
| `/admin/requests/detail` | Review request context and decision options | Request action; approve/reject (disabled pending service) | Administrator |
| `/admin/teachers` | Inspect teacher records and schedule context | Sidebar Teachers; view record | Administrator |
| `/admin/students` | Inspect student records and schedule context | Sidebar Students; view record | Administrator |
| `/admin/subjects` | Inspect subjects and scheduling requirements | Sidebar Subjects; view record | Administrator |
| `/admin/sections` | Inspect section assignments and schedule status | Sidebar Sections; view record | Administrator |
| `/admin/academic/details` | Inspect academic record relationships | Academic list action; return to parent list | Administrator |
| `/admin/rooms` | Inspect room capacity, facilities, and status | Sidebar Rooms; view room | Administrator |
| `/admin/rooms/detail` | Inspect room location, resources, and scheduled classes | Room action; return to room list | Administrator |
| `/admin/buildings` | Inspect buildings and classroom resources | Sidebar Buildings; view building | Administrator |
| `/admin/buildings/detail` | Inspect building and rooms | Building action; view room | Administrator |
| `/admin/room-availability` | Find planned room availability by time/requirements | Sidebar Room Availability; inspect room | Administrator |
| `/admin/reports` | Review operational schedule summaries | Sidebar Reports; adjust period/filter | Administrator |
| `/admin/utilization` | Review scheduled room-use patterns | Sidebar Room Utilization; adjust period/filter | Administrator |
| `/admin/notifications` | Review schedule, room, request, and system updates | Sidebar Notifications; review update | Administrator |
| `/admin/announcements` | Review academic notices and communication context | Sidebar Announcements; inspect notice | Administrator |
| `/admin/audit-logs` | Review administrative action history | Sidebar Audit Logs; inspect event | Administrator |
| `/admin/settings` | Review system and notification preferences | Sidebar Settings; adjust preference | Administrator |
| `/admin/profile` | Administrator account context | Profile link/drawer; open settings | Administrator |

Shared routes outside the role registry: `/` and `/auth/login` provide the public sign-in entry; `/forbidden` presents the access-denied state; `/dev/role-preview` is the clearly labeled in-memory development role selector; `/dev/design-system` is the component playground; all unmatched paths show Not Found. Production authentication is not configured in this frontend prototype.

## Interaction and responsive audit

- Sidebar and mobile drawer destinations originate from `navigationForRole`; profile/settings destinations and header controls use the same role namespace.
- Mobile bottom-navigation is limited to each role's primary destinations. For Students it is exactly Home, Schedule, Rooms, and Alerts; the top-left hamburger opens the full role-owned destination set, including profile and settings.
- Dashboard links use `rolePath` and are differentiated for student, teacher, and administrator. Student schedule is view-only; teacher schedule links to change requests; only administrators see schedule creation/conflict management.
- Workspace heading, avatar, search corpus, and notifications derive from current role. A mismatched registered route cannot render its page.
- The app uses a sticky, compact top bar and content begins directly beneath it; there is no nested authenticated header. Breakpoint rules collapse the shell to a single column and replace wide tables with cards.
- Loading and server-error states cannot be meaningful until API data is integrated. The current screens use role-relevant empty states and clear prototype/server-required messages where actions are unavailable.

## QA coverage and residual risks

`route-config.test.ts` checks unique paths, role-owned dashboards/navigation, and the administrator-only schedule manager. Lint, typecheck, tests, and build are run as part of this audit; exact results are reported with the change. Full browser/device and assistive-technology QA remains outstanding. The development-role guard is intentionally not security: future authenticated route context and backend authorization must replace/supplement it. Representative data, academic year, filters, report/export controls, notification preferences, and forms are illustrative and not persisted; some filter controls are presentation-only. Route detail screens currently use fixed sample records rather than route parameters.
