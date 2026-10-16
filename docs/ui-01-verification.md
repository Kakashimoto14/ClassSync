# UI-01 implementation and verification

## Scope and safeguards

- Soft Rouge Mobile tokens, shared controls/cards, light shell, and Student dashboard.
- React, routing, role guards, deterministic selectors, React Query, the ICS utility,
  backend infrastructure, and Teacher/Administrator dashboard compositions preserved.
- Initial branch: `main` at `f4dc085`, equal to cached `origin/main`. Live remote-head
  verification failed because GitHub was unreachable. No fetch/reset/commit performed.
- Pre-existing untracked `apps/web/src/styles/` contains inactive Sapphire work. It
  was neither imported nor edited. The active theme is `src/theme.css`.
- No isolated approved ribbon master was found. Plain product-name fallback remains;
  required assets are documented in `branding.md`. No board crop or substitute mark.

## Design decisions

Files changed in UI-01:

- Foundation: `apps/web/src/theme.css` (new), `apps/web/src/styles.css`.
- Shell/entry: `apps/web/src/components/layout/AppShell.tsx`,
  `apps/web/src/pages/AuthPage.tsx`, `apps/web/src/pages/OperationsPreviewPage.tsx`.
- Schedule presentation: `apps/web/src/components/scheduling/NextClassSummary.tsx`,
  `apps/web/src/components/scheduling/ScheduleEntry.tsx`,
  `apps/web/src/pages/dashboards/StudentDashboard.tsx`.
- Resource cards: `apps/web/src/components/scheduling/RoomDirectoryCard.tsx` (new),
  `apps/web/src/pages/ProductScreenPage.tsx` (targeted room-function changes).
- Tests: `apps/web/src/pages/dashboards/Dashboards.test.tsx`,
  `apps/web/src/pages/RoomNavigation.test.tsx` (new).
- Documentation: `docs/branding.md`, `docs/ui-ux.md`, this verification record (new).

White surfaces and cool-neutral canvas use the approved palette. Inter remains
self-hosted. Shared field rules retain specificity over Tailwind preflight; error
borders, disabled treatment, focus rings, and semantic status labels are consistent.
Mobile controls use 48px targets; desktop retains 44px density. Cards use 12px radii.
The sidebar remains 256px, with separately scrollable navigation and reserved account
space. Header/bottom-navigation sizing is tokenized, including content safe-area space.

Student's summary now owns the schedule action and prioritizes classroom location.
Featured records are excluded from the later agenda by stable ID, without suppressing
another simultaneous assignment. All existing empty and unavailable states remain.
The typed resource card removes demonstrated incorrect room destinations and labels
resource state separately from date/time availability.

## Verification record

Foundation: 9 focused tests passed. Shell/routes: 16 focused tests passed.
Student/selectors: 27 focused tests passed, including duplicate prevention, correct
destination, overlap retention, and all four non-ready Student states.

Calculated foreground contrast against white: primary ink 15.55:1, secondary ink
4.97:1, primary rouge 8.34:1; semantic foregrounds range 5.04:1 to 6.92:1. Secondary
ink on the canvas is 4.68:1. These calculations do not certify every UI combination.

Final validation (2026-10-16): `npm run lint`, `npm run typecheck`,
`npm run test:web` (62 tests across 12 files), and `npm run build` passed.
Production output: 38.38 kB CSS / 8.14 kB gzip and 453.12 kB JavaScript /
134.90 kB gzip. No dependencies were installed.

Rendered browser verification used the local Vite application and development role
chooser, not production authentication:

- Student dashboard inspected at 360, 390, 768, 1024, and 1440px widths. No horizontal
  overflow observed. At 360x640 and 390x640, the complete next-class summary and its
  action fit above the bottom navigation. Home, Schedule, Rooms, Alerts remain intact.
- Student schedule action operated by keyboard and reached `/student/schedule`;
  its disabled export treatment was inspected. Refresh clears preview access and
  returns to sign-in with the schedule destination preserved in `returnTo`.
- Mobile drawer keyboard opening, focus wrap, Escape closing, and trigger focus
  restoration were checked. Automated shell tests cover closing after navigation.
- Teacher and Administrator dashboards inspected at 390 and 1440px for shared-style
  regressions. Administrator sidebar inspected at 1024x480 with expanded sections:
  navigation scrolls independently (331px viewport / 872px content), ending at y=411;
  the account begins at y=421.25. Header starts at x=256; no horizontal overflow.
- Room directory inspected at 360 and 1440px after correcting its destinations.
  Only the existing Administrator SCI-218 detail route is offered. Resource status
  is not presented as verified time-window availability.
- Login inspected at 390 and 1440px. Visible keyboard focus and neutral disabled
  controls were inspected. Additional tinted-text token `#596273` provides 5.30:1
  on rouge tint and 5.44:1 on the stronger neutral surface.

Student mobile and desktop screenshots were saved outside the repository in the
task visualization directory as `classsync-ui01-student-mobile.jpg` and
`classsync-ui01-student-desktop.jpg`.

Browser zoom, physical-device safe areas, assistive-technology testing, and full
WCAG conformance were not verified. Viewport testing is not a substitute for those
checks. Older schedule-page fixtures still differ from dashboard fixtures; their
reconciliation is explicitly deferred below.

Affected-file formatting was checked. `ProductScreenPage.tsx` retains pre-existing
compact formatting outside the edited `RoomScreen` function; only that function
was formatted to avoid an unrelated full-file rewrite.

## UI-02 follow-up

- Dedicated Teacher/Administrator screen refinements; their compositions were not rebuilt.
- Reconcile older feature-page samples with dashboard fixtures and future authoritative data.
- Complete role-appropriate resource details; only SCI-218 currently has an admin detail route.
- Review remaining feature-page placeholder controls and detail records, including conflicts,
  buildings, reports, and their sample status claims. No operational calculations were added.
- Obtain approved isolated logo exports; broader screen-reader, physical-device, and zoom QA.

No production authentication, scheduling CRUD, backend integration, AI/OCR, automatic
calendar synchronization, new dependencies, or dark mode are included.
