# Frontend presentation sprint

Baseline: clean worktree at `a85954c` (UI-03A). Verified 17–18 October 2026,
Asia/Singapore. No commits, dependency additions, backend changes, or theme changes.

## Completed checkpoints

1. **Journey consistency:** Student schedule and alerts now use the dashboard's
   typed assignments and updates. Removed the older Room 301 / Room 304 samples and
   fabricated relative notification times. Reused the existing schedule view,
   selectors, agenda, status, empty-state, and export controls.
2. **Calendar consistency:** Existing calendar paths show supplied October demo dates,
   counts derived from role-owned assignments, and the selected day's agenda. Month
   navigation and empty dates work. Administrator retains draft visibility; personal
   calendars show published assignments. Desktop places calendar beside agenda;
   mobile stacks them. No calendar subscription, mutation, or timezone claim.
3. **CDM inventory:** Integrated the exact product-owner list as 59 provisional spaces
   (PRRC 27, New Building 31, Court 1). See `cdm-room-inventory.md` for provenance,
   aliases, exclusions, and verification boundaries. No PRRC 304–306 or inferred
   capacities, equipment, condition, floors, reservations, or assignments were added.
4. **Resource presentation:** Directory defaults to provisional CDM records; the
   separate Demo scenario remains selectable. Search includes aliases; building/area
   filters work; results paginate in groups of 12 with focus returned to the results
   heading. Unsupported resource filters are omitted for provisional records.
   VGA remains explicitly unconfirmed. Building cards derive counts and open their
   own records; a building previews six spaces and links to its complete filtered list.
5. **Navigation and density:** Teacher Rooms now opens the working directory directly.
   Availability remains reachable through secondary navigation and its directory link.
   Student bottom navigation remains Home / Schedule / Rooms / Alerts. Search offers
   registered entry pages rather than record details with no selected record.
   Presentation-screen headings and provisional cards omit redundant text.

## Changed files

New under `apps/web/src/`:

- `data/cdm-room-inventory.ts` and `.test.ts`
- `pages/PreviewCalendarView.tsx`
- `pages/PreviewBuildingViews.tsx`
- `pages/PresentationRoutes.test.tsx`
- `presentation.css`

Updated under `apps/web/src/`:

- `data/schedule-preview.ts`, `lib/room-discovery.ts` and its tests
- `pages/ProductScreenPage.tsx`, `PreviewOperationsViews.tsx`, `RoomDiscoveryPages.tsx`,
  `RoomNavigation.test.tsx`, and `dashboards/ResourceOverview.tsx`
- `components/scheduling/RoomDirectoryCard.tsx`, `RoomFilters.tsx`
- `components/layout/AppShell.tsx` and its tests
- `routes/route-config.ts`, `styles.css` (scoped stylesheet import)

New documentation: `docs/cdm-room-inventory.md` and this verification record.

## Automated validation

- `npm run lint`: passed.
- `npm run typecheck`: passed.
- `npm run test:web`: **131 tests passed across 17 files** on the final run.
- `npm run build`: passed; 1,690 modules, CSS 46.62 kB / 9.34 kB gzip,
  JavaScript 462.73 kB / 138.16 kB gzip.
- Affected-file formatting checks and `git diff --check`: passed, with existing
  formatting exceptions noted below. No dependencies or design tokens changed.

Coverage includes exact inventory membership and missing PRRC numbers, source labels,
unknown metadata, aliases, maintenance, resource boundaries, pagination/focus,
all three roles' detail routes, building-to-room return paths, invalid building IDs,
Student dashboard-to-schedule consistency, alerts, calendar counts/selection/months,
role ownership, route registry, search, guards, shell, drawers, logo fallback, and ICS.

Affected new/extracted components, tests, and CSS pass Prettier. Existing formatting
in the compact legacy ProductScreenPage, route registry, global stylesheet, and
schedule-preview model was preserved rather than broadly rewritten.

## Actual browser QA

Used Vite at `http://127.0.0.1:5182/` with development role access.

- CDM directory and calendar measured/rendered at 360, 390, 768, 1024, and 1440px;
  no horizontal overflow in these inspected layouts.
- Student mobile dashboard, its real schedule action, cross-section records, and
  exact bottom-navigation labels were verified. Teacher dashboard and its direct
  Rooms destination were verified at 390px. Administrator at 390/1440px retains
  conflict-first ordering and the same scoped demo metrics.
- Alias search COMLAB returns four supplied labs. VGA opens PRRC 302 with its
  unconfirmed label and four Unverified resource fields. Keyboard pagination selects
  page 2, focuses Rooms & spaces, and resets scroll; filtering returns to page 1.
  Direct demo-room detail links return to the Demo inventory rather than the CDM list.
- Administrator drawer opens Buildings & Areas, showing Court 1 / New Building 31 /
  PRRC 27. New Building's complete-list link opens its filtered inventory; Function
  Hall opens the supplied 4th-floor location without assigning a room number.
- On the Administrator calendar, selecting 13 October replaces the four Monday
  records with the single Tuesday assignment. Draft remains explicitly labeled on
  Monday. Calendar, notifications, and export do not simulate backend success.
- At 360x480, focused pagination ends at y=384.23; bottom navigation begins at y=408.
  At 1024x480 the sidebar remains 256px, navigation has 331px visible height for 708px
  content, and navigation/account regions meet at y=411 without overlap.
- Screen-reader use, browser zoom, and physical-device safe areas remain unverified.
  This is targeted browser/accessibility QA, not full WCAG/ITHUMCI certification.

Selected screenshots are in
`C:/Users/lenovo/.codex/visualizations/2026/10/11/01a12c48-7444-7a13-ab87-ec5a7a058aa0/`:

- `classsync-presentation-cdm-390.jpg`, `classsync-presentation-cdm-1440.jpg`
- `classsync-presentation-student-390.jpg`, `classsync-presentation-student-schedule-390.jpg`
- `classsync-presentation-teacher-390.jpg`
- `classsync-presentation-admin-390.jpg`, `classsync-presentation-admin-1440.jpg`
- `classsync-presentation-calendar-390.jpg`, `classsync-presentation-admin-calendar-1440.jpg`
- `classsync-presentation-vga-unconfirmed-390.jpg`, `classsync-presentation-function-hall-390.jpg`
- `classsync-presentation-buildings-390.jpg`, `classsync-presentation-short-height-pagination.jpg`

## Presentation boundaries and remaining limitations

- CDM records are provisional; official inventory verification is still needed.
- Timetables, requests, and conflicts remain the declared fictional demo scenario.
  Their assignments were not fabricated onto CDM spaces. Existing demo Room 405 is
  separate from the supplied Function Hall.
- Availability, scheduling CRUD, decisions, notifications, AI/OCR, authentication,
  and synchronization require their future services. No successful operation was
  simulated. Coming Soon paths and existing access boundaries remain intact.
- Approved isolated ribbon exports are still unavailable; the existing legible logo
  fallback remains. No mark was approximated or presentation board embedded.
- Unrelated academic, reporting, announcement, profile, and audit samples were not
  rebuilt in this sprint. Their existing preview limitations remain.
