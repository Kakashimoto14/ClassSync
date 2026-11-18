# Administrator workspace audit

**Date:** 15 November 2026
**Scope:** Administrator routes in `apps/web/src/routes/route-config.ts`, current page dispatch,
and the two owner-supplied screenshots of `/admin/academic` and `/admin/offerings`.
**Evidence rule:** the screenshots directly show the initial no-period experience only. Other
findings below are source inspections, not fresh browser verification. Tests establish component
behavior, not institutional data or production readiness.

## Findings from the supplied screens

Both screenshots show a large, mostly empty page when no period is selected. The only path forward
is a period dropdown and a secondary-looking “New Academic Period” action. The page gives no
visible outline of what setup entails. A collapsed “Data source” disclosure hides the development
data qualification, and the Academic Setup sidebar expands into many separate links even though
the period overview already places most of those tasks in one workspace.

The `/admin/academic` screenshot also shows a prominent “Sample Academic Scenario” card. That
synthetic import is useful for local solver evaluation, but its placement competes with real setup
and could be mistaken for the normal entry flow. The screenshot header says “Administrator demo”
and “Preview workspace”; neither is institutional authorization.

## Administrator route inventory

| Screen or route family                                                                                                                                                          | Actual implementation and evidence                                                                                                                                                     | Current status and UX/product gap                                                                                                                                                                                                                     |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/admin/dashboard`                                                                                                                                                              | `AdminSchedulingHome.tsx` reads periods, readiness, drafts and publication state; `OperationsPreviewPage.tsx` supplies a distinct presentation mode.                                   | **PARTIAL.** The connected local sandbox has actionable readiness state. With no period it needs an explicit setup path and configuration outline. Production/provider behavior is unverified.                                                        |
| `/admin/academic`, `/admin/programs`, `/admin/subjects`, `/admin/sections`, `/admin/teachers`, `/admin/offerings`, `/admin/academic/resources`, `/admin/scheduling-constraints` | `AcademicManagementPage.tsx`, `AcademicPeriodSetup.tsx`, `AcademicCalendarEditor.tsx`, and `AcademicRecordEditor.tsx` share period-scoped records and one-screen setup.                | **PARTIAL.** The overview and structured selectors are implemented. Before a period is chosen the screens previously hid the work map; category navigation duplicated entry paths. Supplied catalog/inventory still needs institutional verification. |
| `/admin/ai-scheduling` and `/admin/schedule-manager/create`                                                                                                                     | `AcademicGenerationPage.tsx` calls the readiness API and deterministic generation path; `/admin/ai-scheduling` and the legacy create route share this view.                            | **PARTIAL.** This is OR-Tools constraint-based generation. No LLM copilot is connected. The old “AI-Powered” title overclaimed the implementation. Generation, draft save, and publication are separate operations.                                   |
| `/admin/conflicts`, `/admin/ai-conflict-detection`, `/admin/conflicts/detail`                                                                                                   | All dispatch to `ConflictCenterPage.tsx`, which loads saved drafts and runs `IndependentValidation` against each exact saved input snapshot.                                           | **PARTIAL.** Deterministic validation exists; the two “AI” paths did not provide AI. Empty state needed clear links to generation and setup. Provider validation remains unverified.                                                                  |
| `/admin/schedule-manager`, `/admin/schedule-manager/drafts/*`, `/admin/calendar`                                                                                                | `ProductScreenPage.tsx`, `SchedulingDraftPages.tsx`, and `StructuredCalendarPage.tsx` expose schedule review, saved drafts and calendar views.                                         | **PARTIAL.** Local draft and calendar paths exist. Review and publication readiness must be distinguished, and institutional authorization/data are not established by preview mode.                                                                  |
| `/admin/students`, `/admin/academic/details`                                                                                                                                    | `ProductScreenPage.tsx` renders `AcademicListScreen` and `AcademicDetailScreen` with source-defined example rows and values.                                                           | **UI ONLY.** These records are hardcoded presentation content, not database-backed Registrar data. Do not use them for decisions or display them as live student records.                                                                             |
| `/admin/rooms`, `/admin/room-availability`, `/admin/rooms/detail`                                                                                                               | `RoomDiscoveryPage.tsx`, `ConnectedRoomsPage.tsx`, and `StudentRooms.tsx` select directory or availability behavior by route/mode.                                                     | **PARTIAL / UNVERIFIED.** Inventory mapping and room filtering exist; the source inventory does not verify operational status, equipment, capacity or availability. Live role/provider checks were not performed in this audit.                       |
| `/admin/buildings*`                                                                                                                                                             | `PreviewBuildingViews.tsx` renders preview directory/detail screens.                                                                                                                   | **UI ONLY.** The route labels do not make the content an authoritative facilities registry.                                                                                                                                                           |
| `/admin/reports`, `/admin/utilization`                                                                                                                                          | `ProductScreenPage.tsx` renders `ReportScreen`, which explicitly says operational data is not connected and reports are coming soon.                                                   | **UI ONLY / PLANNED.** No metrics should be synthesized to fill the page.                                                                                                                                                                             |
| `/admin/requests*`, `/admin/notifications`, `/admin/announcements`                                                                                                              | `PreviewOperationsViews.tsx` and `ProductScreenPage.tsx` provide preview or sample operations views.                                                                                   | **UI ONLY / PARTIAL.** Review actions and delivery are not demonstrated as connected institutional workflows.                                                                                                                                         |
| `/admin/audit-logs`, `/admin/profile`, `/admin/settings`                                                                                                                        | `ProductScreenPage.tsx` routes to local screen components; connected audit evidence belongs to publication-specific paths and should not be conflated with a complete admin audit log. | **PARTIAL / UNVERIFIED.** Confirm each action persists, is authorized server-side, and has audit coverage before relying on it.                                                                                                                       |

## Changes made in this implementation slice

- The no-period Academic Setup view now describes the period-scoped work areas before an admin
  chooses a period, keeps period selection explicit, and opens the create form when no period exists.
- The development sandbox qualification is visible. The synthetic scenario remains available under
  a separate development-tools area after the primary setup content.
- The Administrator sidebar exposes one Academic Setup entry for period-scoped categories. Direct
  category routes remain reachable from destination search and the selected-period workspace.
- Generation is labeled **Schedule Generation** because current generation is deterministic CP-SAT;
  the Conflict Center uses **Independent Conflict Validation** as its method note. No AI capability
  is claimed.
- The empty Conflict Center and no-period generation view explain what must happen next and expose
  direct setup/generation actions.

## Acceptance evidence and open work

Fresh focused tests cover the Academic Setup no-period work map, development-tool placement,
category search after navigation consolidation, and Conflict Center empty-state links. TypeScript,
ESLint, and the production build are run for this slice; exact output is recorded in
`../autonomy/STATUS.md`.

Rendered visual review at 360, 390, 768, 1024 and 1440 pixels, keyboard-only walkthrough, native
200% zoom, focus behavior in a real browser, and manual screen-reader checks remain **UNVERIFIED**.
Current institutional provider behavior, API errors under real credentials, live data accuracy,
reporting, and production readiness also remain **UNVERIFIED**. A future screen-family pass should
connect the explicitly preview-only student, building, report, request and announcement routes or
remove their visibility from operational accounts after the required approval and tests.

## 16 November 2026 — secondary-screen density follow-up

The Administrator command menu now uses the loaded `operational-ui.css` overlay rules and the
active `styles.css` topbar is fixed at 64px. Academic Setup uses a counted seven-area selector and
renders one area at a time; calendar entry is disclosed separately, and the existing inline
record editor and API saves are preserved. Category record filtering uses status selections rather
than a text-search field.

Schedule Generation uses a compact step/status workspace, while Conflict Center has an inline
draft selector and a balanced empty state. Its checklist is limited to checks currently present in
`services/scheduling/app/validation.py`; it does not claim building-specific travel-time checks.
Classroom Requests and Notifications were traced to `PreviewRequestsView` and
`PreviewUpdatesView` in `PreviewOperationsViews.tsx`, not to a live admin API. Both remain clearly
identified as demonstration data; their selection filters and compact rows are presentation-only,
and disabled decisions or notification delivery were not connected as a side effect of this visual
task. The separate API-backed `ClassroomRequestsPage.tsx` also gained status filtering but is not
the component currently mounted by `/admin/requests`.

The updated room-directory regression uses the current four groups in the November catalog
(PRRC, New Building, Campus Grounds, Montalban Sports Complex) and the 53 catalog records. The
full frontend suite passes 836 tests across 62 files; typecheck, lint and production build pass.
Build still reports the existing Firebase mixed static/dynamic import warning and a 734.29 kB
minified chunk. Browser rendering at the requested pixel sizes remains **UNVERIFIED**: an
unidentified process already owns port 5173, and its command line could not be inspected, so it
was not terminated or treated as the feature worktree. A frontend-only server on 5174 redirected
`/dev/role-preview` to the sign-in screen because university sign-in was unavailable, so no Admin
preview was accessible; that server was stopped. Manual keyboard, reduced-motion and
assistive-technology acceptance also remain open.

## 18 November 2026 — P4d activity audit trail and remaining acceptance

The connected PostgreSQL activity view now has a server-side Administrator-only endpoint and
append-only, tenant-scoped activity table (migration `0017_administrator_activity_audit.py`).
Its disposable PostgreSQL qualification records 78 synthetic events and verifies metadata
redaction, same-tenant Administrator access, cross-tenant RLS isolation, and rejection of
updates/deletes/truncation. Preview mode still labels its publication-only list as non-authoritative.

Fresh frontend lint/typecheck/build pass and 838 unit tests pass across 63 files; the build emits
no prior chunk-size or Firebase import warning. The 1092-test serial Python suite passes. These
are local automated results, not an end-to-end connected Admin workflow. Auth Emulator tools are
missing, the full academic PostgreSQL qualification currently stops at a readiness-fixture
contract, and no browser workflow, native 200% zoom, keyboard-only lifecycle, or screen-reader
acceptance was completed. P4d remains PARTIAL. See `../autonomy/STATUS.md` and
`../autonomy/P4D_ADMIN_ACCEPTANCE.md`.

## 18 November 2026 — P4d browser evidence qualification

A separate presentation-only preview on port 5193 was stopped after inspection. The route-menu and mobile-drawer keyboard checks passed in preview (keyboard open/arrow navigation/Escape/focus restoration/Tab cycling and visible Soft Rouge ring). At desktop 1366×768 and mobile 390×844, the shell retained a 64px topbar and document/body widths matched the viewport. The target dashboard, academic, generation, conflict and audit pages each exposed only one main control, so their data is insufficient to claim the actual workspace rendered; calendar was the exception. Native 200% zoom did not run because Chrome blocked the temporary zoom extension. See `var/p4d-evidence/admin-preview-qa-20261118.json`; route screenshots are in `var/p4d-evidence/admin-preview-screenshots-20261118/`. Connected browser and actual screen-level responsive/accessibility acceptance remain UNVERIFIED.
