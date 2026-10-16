# UI-02 implementation and verification

Verified on 17 October 2026 (Asia/Singapore). Scope: Teacher and Administrator
dashboards, shared preview data, and their immediate linked views.

## Baseline and safeguards

- Initial workspace was clean at `bfe16bd`. On resumption, the implementation was
  already present in `1cb7164`; no commits were created by this task.
- UI-01 tokens, self-hosted Inter, Student composition, 256px shell, role guards,
  typed route registry, and calendar serializer remain intact. No dependencies,
  backend services, authentication, scheduling CRUD, or AI were introduced.
- The formerly untracked Sapphire directory now contains 22 tracked files. It is
  still inactive: `main.tsx` imports `styles.css`, which imports `theme.css`.
  Production CSS contains the approved rouge token and does not contain Sapphire's
  `--color-primary-600` token. No Sapphire files were changed or deleted.
- No applicable AGENTS.md or official ITHUMCI rubric was found in available project
  instructions/documentation. Rubric-specific compliance remains unverified.

## Checkpoints and behavior

### A: data ownership and reusable components

- The original deterministic scenario and stable assignment IDs are retained.
- Requests sort pending-first, then latest update; Teacher selection also checks
  assignment ownership. Approved, declined, pending, missing, and empty states are
  supported without inventing successful decisions.
- Administrator record metrics all cover the entire supplied demo dataset:
  4 published occurrences, 1 draft, 1 open conflict, 1 pending request. These are
  occurrence counts, not recurring course counts. Today's list separately contains
  4 occurrences (3 published, 1 draft) on 12 October.
- The three existing directory samples are centralized with stable room IDs:
  SCI-218 and ENG-204 are active resources; LAB-04 is under maintenance. This is
  explicitly a partial demo directory, not a campus inventory. Room 405 has schedule
  location data but no invented resource-condition record.
- Resource condition counts do not calculate availability or suitability.

### B: Teacher dashboard

- Next assignment owns one schedule action, publication state, time, section,
  instructor, and classroom location.
- Remaining agenda excludes assignments already featured by stable ID, retains
  simultaneous records, and preserves current, finished, empty, unpublished, and
  unavailable states through existing selectors.
- Requests and decisions appear pending-first with links to the correct record.
  Schedule updates, request creation, and issue reporting remain role-owned.
- Mobile stacks next assignment, remaining agenda, requests, then updates/actions.
  Desktop separates the teaching area from requests and updates.

### C: Administrator dashboard

- Blocking conflicts come first, followed by compact consistently scoped metrics.
- Pending decisions appear before the campus schedule on mobile and beside it on
  desktop. Requests are not duplicated in the conflict queue.
- Resource condition, maintenance context, and a Room Directory action are explicit.
- Empty conflicts do not imply that pending requests or other attention are cleared.
- Management links use registered role destinations; unsupported approvals remain
  disabled in their linked view with an explanation.

### Immediate destination corrections

`PreviewOperationsViews.tsx` provides small fixture-backed destination views rather
than duplicating operational arrays inside `ProductScreenPage.tsx`:

- Teacher schedule and Administrator Schedule Manager use the dashboard occurrences,
  sections, rooms, teachers, dates, and publication states. Search/date filters work.
- Conflict list/detail show the actual recorded SCI-218 database/network overlap;
  unrelated hardcoded SCI-108 and capacity warnings were removed from these views.
- Request list/detail show the same pending database request and declined Web Systems
  request. Query IDs select records on existing paths; unknown IDs show unavailable
  instead of substituting a different record. Return links reach the owning lists.
- Request creation and issue reporting reference Teacher-owned assignments. Room
  suggestions show resource condition, not unverified availability; submission stays
  unavailable. No persistence or approval simulation was introduced.
- Teacher/Admin notification previews use the existing schedule-update records.
- The existing SCI-218 detail view uses shared resource metadata and recorded
  assignments, replacing its unsupported no-reservation claim.
- The Student dashboard and its older feature-page timetable were not rewritten.

## Verification

- `npm run lint`: passed, including the final empty-state correction.
- `npm run typecheck`: passed after final source changes.
- `npm run test:web`: **84 tests passed across 14 files** after the final correction.
- `npm run build`: passed; 1,684 modules, CSS 41.70 kB / 8.63 kB gzip,
  JavaScript 456.20 kB / 135.78 kB gzip.
- Affected-file Prettier checks passed except the intentionally excluded compact
  legacy `ProductScreenPage.tsx`; its unrelated baseline formatting was preserved.
- `git diff --check`: passed.

Tests cover role selection, all-record versus day scopes, request/conflict counts,
approved decisions, missing resources, no-data states, chronology, overlaps, unknown
record IDs, actual navigation into details, filter behavior, disabled submission,
Student regressions, role guards, shell navigation, drawer behavior, and ICS.

### Actual rendered browser checks

The local Vite app was opened through development role preview. Both operational
dashboards were rendered and inspected at 360, 390, 768, 1024, and 1440px widths.

- No horizontal overflow observed. Mobile content wraps without hiding assignments.
- Teacher at 360x640: next-card bottom approximately 509px, above the 568px bottom
  navigation boundary. Teacher schedule action worked by keyboard and showed the
  same SCI-218 / ENG-204 assignments.
- Administrator metrics use two columns on phones and four at wider widths.
  Desktop campus schedule sits beside decisions/resources; mobile ordering remains
  conflicts, metrics, requests, schedule, resources.
- Conflict action opened the same assignment IDs and room. Parent Conflicts remains
  `aria-current="location"`; main-content receives focus. Return action worked.
- At 1024x480, expanded sidebar navigation scrolls independently (331px viewport,
  696px content). Navigation ends at y=411 and the reserved account region begins
  at y=411. No overlap or horizontal overflow observed.
- At 390x640 after scrolling to the end, the last dashboard text ends at y=543.66,
  above the bottom navigation at y=568.
- Drawer keyboard opening, reverse-tab focus wrap, Escape, focus restoration, and
  closing after request navigation were verified. Request route became active and
  focus moved to main content.
- Student at 390x640 retains Home / Schedule / Rooms / Alerts, no horizontal
  overflow, and the next card ends at y=436.8 above the y=568 bottom navigation.
- Browser zoom, physical-device safe areas, and screen-reader use were not verified.
  This is targeted HCI/accessibility QA, not a full WCAG or ITHUMCI certification.

Screenshots are in:
`C:/Users/lenovo/.codex/visualizations/2026/10/11/01a12c48-7444-7a13-ab87-ec5a7a058aa0/`

- `classsync-ui02-teacher-390.jpg`
- `classsync-ui02-teacher-1440.jpg`
- `classsync-ui02-admin-390.jpg`
- `classsync-ui02-admin-1440.jpg`
- `classsync-ui02-admin-desktop-preview.jpg`
- `classsync-ui02-student-390.jpg`

Full-page captures can show fixed navigation at the original viewport position;
actual bottom-content clearance was checked separately while scrolling.

## Files affected across UI-02

- `apps/web/src/data/schedule-preview.ts`
- `apps/web/src/lib/schedule-preview.ts` and its tests
- `apps/web/src/components/scheduling/AttentionQueue.tsx`
- `apps/web/src/components/scheduling/NextClassSummary.tsx`
- `apps/web/src/components/scheduling/ScheduleEntry.tsx`
- `apps/web/src/components/scheduling/RequestSummary.tsx` (new)
- `apps/web/src/pages/dashboards/TeacherDashboard.tsx`
- `apps/web/src/pages/dashboards/AdministratorDashboard.tsx`
- `apps/web/src/pages/dashboards/ResourceOverview.tsx` (new)
- `apps/web/src/pages/dashboards/Dashboards.test.tsx`
- `apps/web/src/pages/dashboards/OperationsDashboards.test.tsx` (new)
- `apps/web/src/pages/OperationsPreviewPage.tsx`
- `apps/web/src/pages/PreviewOperationsViews.tsx` and its tests (new)
- `apps/web/src/pages/ProductScreenPage.tsx` (targeted data/view delegation)
- `apps/web/src/styles.css` (scoped operations composition rules)
- This verification record (new)

## Deferred to UI-03 / later approved work

- Reconcile the legacy Student timetable, calendar, announcements, academic details,
  building summaries, reports, and audit samples. These are not authoritative data.
- Broader ProductScreenPage decomposition and complete record-specific room details.
- Schedule creation validation, service-backed decisions, notifications, and exports
  need authoritative data/services; they were not implemented in this stage.
- Production ribbon logo exports remain missing; UI-01's legible fallback is retained.
- Broader keyboard/screen-reader, zoom, real-device, and performance profiling.
