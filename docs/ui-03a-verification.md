# UI-03A — Classroom discovery and room details

Verified 17 October 2026 (Asia/Singapore). Implementation scope: Room Directory,
Find a Room, Room Availability, room details, and directly related navigation.

## Baseline and safeguards

- Started from a clean worktree at `b4c9caa` (UI-02). No reset, commit, dependency
  installation, backend change, or dashboard redesign was performed.
- Read UI-01/UI-02 verification records, current route/guard/shell implementation,
  fixtures, selectors, shared controls, room screens, and tests.
- Soft Rouge Mobile, self-hosted Inter, logo fallback, 256px sidebar, role separation,
  Student Home / Schedule / Rooms / Alerts, and calendar-export utility remain.
- The inactive Sapphire styles remain untouched and unimported.
- No applicable AGENTS.md or official ITHUMCI rubric was found. This is targeted
  HCI/accessibility verification, not full WCAG or course-rubric certification.

## Confirmed causes and corrections

| Confirmed source/runtime issue                                           | Correction                                                                                 |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| Room mode inferred from displayed title                                  | Explicit typed `roomMode` in the route registry                                            |
| Legacy adapter overwrote stable IDs with display names                   | Shared `RoomRecord` adapter preserves identity and resource metadata                       |
| Only SCI-218 could open details; detail view hardcoded that resource     | Query-selected record on registered, role-owned detail routes for all roles                |
| Missing room query silently selected SCI-218                             | Missing, unknown, empty, or repeated IDs show safe recovery states                         |
| Sign-in redirect discarded room ID on refresh                            | Preserve query in returnTo; validate ownership against the registered pathname             |
| Directory and availability visually/functionally conflated               | Separate inventory presentation and unavailable time-query state; no available-room claim  |
| One start time, invented default date, no end time                       | Disabled Date / Start / End grouped in an unavailable disclosure without invented defaults |
| Navigation could arrive scrolled below the new page heading              | Focus main without scrolling, then explicitly reset scroll on pathname change              |
| Building detail used the fixed room URL and inconsistent condition label | Reuse shared room cards and stable-ID detail links in that existing view                   |

## Data and access boundaries

- The catalog combines existing resource records with recorded schedule locations,
  keyed by stable room ID. SCI-218, ENG-204, LAB-04 retain their exact metadata.
- Room 405 has a known name/building/floor and assignment, but no invented capacity,
  equipment, type, or operational condition. The directory explicitly identifies
  missing fields; a capacity/type/facility filter cannot match unknown metadata.
- The directory therefore has four known room identities. Administrator condition
  statistics still count the three resources with recorded condition (2 active,
  1 maintenance); only the scope label was clarified, not the dashboard calculation.
- Details show chronologically ordered recorded assignments, including overlapping
  records. Administrator sees all publication states; Student/Teacher see published
  records only. This read-only view does not add editing or booking privileges.
- No assignments is explicitly different from a free room. Maintenance is a resource
  condition, not an availability result. Room suitability remains unverified.

### Availability decision: Option B

Existing occurrences form a partial sample, not a complete timetable/closure feed.
Institutional time zone, complete coverage, and suitability rules are not defined.
No availability calculation, fake search result, reservation, or service call was
added. Name/building/minimum-seat/type/facility filtering works on recorded metadata.
Time controls are disabled with an explanation. Their disclosure prevents inactive
controls from dominating the phone screen. Results say “Matching resources”.

## Implemented experience

- Name/identifier search, building, inclusive minimum capacity, room type, and facility
  filters combine. Invalid minimum capacity has an associated error. Active criteria,
  result count, clear filters, and no-results recovery are explicit.
- Filter state lives in the URL. In-app detail return preserves the originating
  room screen and filters; direct detail entry falls back to the role directory.
  Refresh deliberately clears demo access but retains the requested room ID.
- Compact cards prioritize identity/location, capacity/type, facilities, condition,
  and a uniquely named details link. No repeated per-card availability warning.
- Native disclosures, labeled inputs, semantic status labels, live result counts,
  visible focus styles, and minimum 44px action targets reuse the existing system.
- Teacher's existing `/teacher/find-room` is now clearly labeled Room Directory;
  its existing availability path remains separate. No existing paths were renamed.
- New read-only paths: `/student/rooms/detail?id=…`, `/teacher/rooms/detail?id=…`.
  Administrator retains `/admin/rooms/detail?id=…`. Detail parents remain active.

## Files

New:

- `apps/web/src/lib/room-discovery.ts` and `.test.ts`
- `apps/web/src/pages/RoomDiscoveryPages.tsx`
- `apps/web/src/components/scheduling/RoomFilters.tsx`
- `apps/web/src/room-discovery.css`
- This verification record

Updated:

- `components/scheduling/RoomDirectoryCard.tsx`: typed card and resource-status badge
- `pages/ProductScreenPage.tsx`: delegate room screens; targeted building-room link fix
- `pages/PreviewOperationsViews.tsx`: remove the superseded fixed SCI-218 view
- `routes/route-config.ts`, `routes/RouteGuard.tsx`, `auth/access.ts`: mode, details,
  parent ownership, and query-preserving demo return
- `components/layout/AppShell.tsx`: navigation scroll correction
- `pages/dashboards/ResourceOverview.tsx`: condition-count scope wording only
- `styles.css`: import the scoped room stylesheet
- `pages/RoomNavigation.test.tsx`, `components/layout/AppShell.test.tsx`,
  `pages/dashboards/OperationsDashboards.test.tsx`, `test/setup.ts`: regression coverage

Paths in the updated list are relative to `apps/web/src/`.

## Automated verification

- `npm run lint`: passed.
- `npm run typecheck`: passed.
- `npm run test:web`: **113 tests passed across 15 files** on the final run.
- `npm run build`: passed; 1,687 modules. CSS 45.06 kB / 9.13 kB gzip;
  JavaScript 462.04 kB / 137.51 kB gzip.
- `git diff --check`: passed.

Tests cover all 12 role/room journeys, filters/reset/filtered returns, capacity
boundaries, invalid inputs, maintenance, unknown/missing/duplicate query IDs,
missing metadata, assignment reference consistency, publication visibility,
chronology/overlap retention, query-preserving demo return, role rejection,
unavailable availability controls, and navigation focus/scroll. Existing dashboard,
shell, guard, logo, drawer, and ICS tests remain in the suite.

One earlier combined four-room Administrator test exceeded the default 5-second
timeout under the full suite. It was split into independent role/room cases without
raising timeout limits or reducing assertions.

Formatting: new/extracted files, updated formatted components/tests, and scoped CSS
pass Prettier. `access.ts`, `RouteGuard.tsx`, `route-config.ts`, and `styles.css` have
pre-existing formatting failures, confirmed against HEAD; broad baseline rewrites
were avoided. Compact legacy `ProductScreenPage.tsx` formatting was also preserved.

## Actual browser verification

Vite was rendered in the in-app browser through development role access.

- Directory rendered at 360, 390, 768, 1024, and 1440px: one/two/three-column cards,
  correct room identity/condition, no horizontal overflow in measured layouts.
- Availability and room details measured at the same five widths. Screenshots were
  inspected for phone and desktop compositions; expanded time/resource controls fit.
- Date/Start/End were confirmed disabled. Native filter disclosure worked by Enter;
  its focused outline was solid/visible. Combined 42-seat + Projector filters selected
  SCI-218, and its link opened that record.
- SCI-218 refresh returned to demo entry with the full query; selecting Student
  restored SCI-218, rather than another record or the dashboard.
- Teacher Rooms opened its availability route, directory opened its existing
  find-room route, and LAB-04 details displayed maintenance and no recorded assignments.
- Administrator directory opened SCI-218 with its actual draft overlap and published
  records. Student/Teacher did not display that draft in the room detail checks.
- At 360x480, the maintenance detail's last empty-state content ended at y=384.36;
  bottom navigation began at y=408. No bottom-content overlap or horizontal overflow.
- At 1024x480, sidebar width was 256px; navigation had 331px visible height for
  708px content. Navigation ended at y=411 and account region began at y=411.
- Student drawer Find a Room navigation closed the drawer, selected the correct
  route, and focused main. Exact Student bottom labels remain unchanged.
- Student/Teacher 390px and Administrator 1440px dashboards were rendered for
  shared-style regression. No dashboard composition was rewritten.
- Browser zoom, physical-device safe areas, and screen-reader announcements were
  not verified. Automated DOM accessibility checks do not establish full compliance.

Screenshots are stored in
`C:/Users/lenovo/.codex/visualizations/2026/10/11/01a12c48-7444-7a13-ab87-ec5a7a058aa0/`:

- `classsync-ui03a-directory-{360,390,768,1024,1440}.jpg`
- `classsync-ui03a-detail-{390,1440}.jpg`
- `classsync-ui03a-availability-390.jpg`
- `classsync-ui03a-availability-expanded-{360,1440}.jpg`
- `classsync-ui03a-admin-detail-1440.jpg`
- `classsync-ui03a-admin-availability-390.jpg`
- `classsync-ui03a-{student,teacher}-regression-390.jpg`
- `classsync-ui03a-admin-regression-1440.jpg`

## Deferred to UI-03B or separately approved work

- Legacy Student timetable/calendar, building inventory summaries, and unrelated
  academic/report/notification samples still need their own reconciliation.
- Building overview still has older representative statistics and fixed building
  detail behavior. This stage corrected only its room-card integration.
- Complete institutional room metadata (including Room 405), authoritative room
  coverage, time zone, closures/maintenance periods, and suitability policy.
- Service-backed availability and scheduling validation, CRUD, requests, AI/OCR,
  production authentication, and calendar subscriptions are not implemented here.
- Official isolated ribbon master exports remain missing; existing branding is unchanged.
