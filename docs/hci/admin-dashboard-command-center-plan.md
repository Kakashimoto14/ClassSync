# Administrator Dashboard Command Center — Audit and Implementation Plan

**Status:** Approved by the owner on 16 November 2026; local implementation complete, visual/browser acceptance pending
**Target worktree:** `C:\Projects\ClassSync\var\feature-auth-onboarding-saas`
**Target branch:** `feature/auth-onboarding-saas`
**Audited HEAD:** `7165fa130e413f8dc8893b85d30ecbe530ef8173`
**Scope:** `/admin/dashboard`, its shell navigation, and related styles/tests.
**Change boundary:** Local implementation stayed within the approved dashboard slice. No package manifests, lockfiles, application service/database code, branch state, or unrelated worktrees were changed.

## 1. Audit snapshot

The feature worktree was checked before source inspection:

- `git status --short --branch` identified `feature/auth-onboarding-saas` and a pre-existing dirty working tree.
- `git branch --show-current` returned `feature/auth-onboarding-saas`.
- Existing uncommitted work is preserved. The `main` worktree, branch refs, and worktree registrations are out of scope.

### Current route and implementation

`/admin/dashboard` is served by `AdminSchedulingHome` from `apps/web/src/pages/OperationsPreviewPage.tsx`. `AdminSchedulingHome` has two explicit modes:

- `PresentationOverview` displays frozen sample presentation data and expressly says it has no live synchronization, database writes, or publication authority.
- `ConnectedOverview` loads periods, drafts, academic readiness, and publication state from existing APIs. In the sandbox mode its API results are sandbox data, not institutional production evidence.

`apps/web/src/pages/dashboards/AdministratorDashboard.tsx` is a separate demo-record dashboard. It summarizes `SchedulePreviewData`, conflicts, pending preview requests, and a sample day. It is covered by dashboard preview tests and is not the connected `/admin/dashboard` implementation. The redesign must not merge demo fixtures into the connected dashboard or silently change the meaning of the preview component.

The connected dashboard currently:

- Loads academic periods and a page of scheduling drafts together, then loads readiness and publication state for the selected period.
- Uses an inline period `<select>` but gives it a separate page row and limits it to 680px.
- Renders a primary action card and a second “Needs attention” card. Each blocking issue repeats the same “Review requirement” destination, regardless of issue code.
- Displays four useful counts as a vertical definition list, then publication state as plain text.
- Displays a draft snapshot or a minimal empty message.
- Adds four bottom action links that overlap routes already present in role navigation.
- Shows a hardcoded “Local academic sandbox” label in the connected component. This needs mode-derived, truthful labeling before being made more prominent.
- Has layout-shifting “Loading…” paragraphs and can temporarily clear previously displayed readiness when the period changes.

The existing `AdminSchedulingHome.test.tsx` has three connected-mode cases: ready state, a blocking issue, and a backend list failure. `AppShell.test.tsx` covers the current typed, client-side destination search and route filtering. The `AdministratorDashboard` demo behavior is separately covered by `Dashboards.test.tsx`, `OperationsDashboards.test.tsx`, and `PreviewOperationsViews.test.tsx`.

### Related implementation facts and constraints

- Academic readiness is returned by `checkAcademicReadiness()` in `apps/web/src/lib/academic-api.ts`; its shared result type comes from `packages/shared-types/src/scheduling.ts`. Useful fields include `sections`, `offerings`, `eligible_resources`, `ready`, `issues`, and period revision.
- The backend `services/scheduling/app/academic_input.py::academic_readiness` emits stable codes including `missing_sections`, `missing_offerings`, `missing_academic_calendar`, `missing_operating_hours`, `section_without_offerings`, `missing_room_eligibility`, `missing_faculty`, `teacher_availability_missing`, `faculty_workload_unverified`, `room_availability_unverified`, `missing_weekly_minutes`, `missing_patterns`, `scope_not_complete`, and verification-related codes. The dashboard should route by typed issue codes, not inspect free-form messages.
- `apps/web/src/pages/AcademicGenerationPage.tsx` already has a `fixPath()` helper and an issue grouping in `ReadinessSummary`. Before creating a second mapping, implementation should extract or share a typed destination resolver from this existing code, avoiding drift between the dashboard and generation page.
- `eligible_resources` counts active, schedulable resources with operational condition. It does not establish room availability, per-offering compatibility, verified capacity, or general suitability. Avoid naming the KPI “Eligible Classrooms” unless backend semantics are expanded and proven. Prefer “Schedulable spaces” with explanatory text or keep the established “Classroom candidates” label.
- The feature branch’s current CdM inventory is **53 spaces**, with the row-derived split of 41 schedulable and 12 excluded. Do not use the stale “59 CdM spaces” number from the supplied mock specification. A schedulable designation still does not imply available. Do not infer seat counts or unlisted equipment.
- `AppShell.tsx` currently filters the already-authorized `roleRoutes` in browser memory; it does not submit search text to a service. An Administrator command menu is an interaction simplification, not a replacement for backend authorization or input validation.
- Motion is already listed in `apps/web/package.json`. Active reduced-motion rules are in `apps/web/src/entrance.css`, `apps/web/src/pages/institutional-entrance.css`, and `apps/web/src/operational-ui.css`; `apps/web/src/styles/motion.css` is an unused stylesheet and is removed by the CSS cleanup. Any Motion use still needs route-chunk/bundle measurements and accessibility checks.
- Existing Soft Rouge design tokens live in `apps/web/src/theme.css` / token styles. Reuse those tokens, with restrained color and purposeful iconography. Avoid glass effects, decorative illustration, gratuitous gradients, and a conspicuously generated visual style.

## 2. Target information architecture

The connected Administrator dashboard will use four visual tiers with one primary task path:

1. **Command header:** “Scheduling overview” (or “Scheduling command center” after copy review), a truthful environment/status badge, an inline selected-period menu, and a refresh-readiness button. The period selector uses existing period records only; it is not a free-text field.
2. **Metric ribbon:** Four equal desktop cards for active sections, subject offerings, schedulable room candidates, and saved drafts for the selected period. Each card is a single accessible link to its existing management destination. Counts must be tied to the selected period and must not show zero while data is still loading.
3. **Readiness workflow:** One unified card replaces the separate primary-action and attention cards. It contains a progress/status summary only where progress can be derived from actual readiness data, one primary CTA, and concise blocker rows. Each row has one issue-specific route. If there are more blockers than fit, show a bounded initial set and a native disclosure/action to reveal the remainder; never clip blockers or hide them behind a fixed-height scroll container.
4. **Publication and activity:** A publication card clearly distinguishes published revision from draft state, with the selected period label and a link to the timetable. A neighboring draft/activity snapshot shows the latest known draft for that period, timestamp in Asia/Manila, session count, and validation/conflict state. Empty, loading, stale, and error states remain explicit and compact.

The intended desktop composition is a compact header, a four-column metric row, then a roughly 60/40 two-column body. At narrower breakpoints it becomes two-column metrics and then a single-column flow. “Single screen” is an optimization target for ordinary 900px/1080px desktop viewports; the page must retain normal document scrolling at smaller heights, 200% zoom, narrow widths, large text, loading/errors, and expanded issue details. Do not force `overflow: hidden` or sacrifice keyboard access to claim zero scroll.

### Readiness interaction rules

- Do not hardcode example counts, a sample section such as `BTLEd-ICT-1A`, a fixed “1 of 4” progress value, or a fixed set of blocker categories.
- Derive blocker rows from `checked.issues`. Map stable issue codes through a shared, exhaustive resolver. Unknown codes route to the general scheduling-readiness screen and remain visible with their actual message.
- Relevant existing destinations include academic periods/setup, subjects/curriculum, faculty, sections, subject offerings, resources, and scheduling constraints. Preserve the selected period in destination query parameters. Where a safe record ID can be used as a supported selection parameter, use it; do not invent route parameters that destination pages do not read.
- Group related codes only if the mapping and tests prove every blocking issue remains discoverable. Warnings stay distinguishable from blockers and must not make readiness look failed or complete incorrectly.
- The unified card has one high-emphasis CTA: setup/resolve when blocked, generation when ready and no current validated draft, or review when a current draft exists. Keep a secondary “generate another candidate” action only when the current draft state makes it valid.
- Refresh re-runs the existing APIs and announces completion/failure. Period changes must ignore stale responses and keep the shell stable with fixed-size skeletons. Do not show stale metrics under a new period label.

## 3. File-by-file implementation plan

| File | Planned change | Dependencies / guardrails |
|---|---|---|
| `apps/web/src/pages/AdminSchedulingHome.tsx` | Refactor `ConnectedOverview` into the four-tier semantic structure. Move period selection into the header. Derive KPI values, single primary CTA, readiness rows, publication state, and draft snapshot from existing API records. Add refresh action, stable loading skeletons, truthful environment label, and accessible progressive disclosure for excess blockers. Keep `PresentationOverview` visibly read-only and do not mix presentation records with connected state. | First confirm actual `appMode` labels and existing route destinations. Preserve stale-response cancellation. No fabricated metrics or institutional claims. |
| `apps/web/src/pages/dashboards/AdministratorDashboard.tsx` | No connected workflow rewrite. Verify demo dashboard remains explicitly demo-only and retains its current preview record semantics. Only adjust shared visual classes if necessary and separately regression-tested. | Must not be used as a data source for `/admin/dashboard`; keep sample data obvious. |
| `apps/web/src/pages/AcademicGenerationPage.tsx` | Extract existing issue-code route/group resolution into a reusable typed helper if its behavior can be preserved, or adapt it to consume the shared resolver. Remove duplicate regex routing only after parity tests. | Dashboard destinations and existing deep links must agree. Unknown issue codes have a safe fallback. |
| `apps/web/src/lib/readiness-navigation.ts` (new, if extraction is needed) | Add typed mapping from known readiness issue codes to existing route targets/action labels. Provide period query preservation and optional record selection only for confirmed supported route parameters. | Mapping derived from actual backend `academic_readiness` and solver diagnostics; tests cover known and unknown codes. |
| `apps/web/src/components/layout/AppShell.tsx` | Replace Administrator’s editable “Find a page” textbox with a button that opens a grouped selection-only command menu containing only the current `roleRoutes` after `availableRoute` filtering. Preserve current typed search for Student/Teacher unless product approval explicitly scopes them too. Use canonical routes, close on Escape/selection/navigation, restore focus, and support keyboard traversal. No search text is sent to a backend. | Do not weaken route guards or claim this is a security control. Keep route list deduplicated and role-scoped. |
| `apps/web/src/components/layout/AppShell.test.tsx` | Replace Administrator text-search assertions with command-menu open, role-scoped destinations, no planned/unavailable routes, Escape/focus-return, keyboard movement/selection, and navigation-close cases. Retain Student/Teacher search behavior and existing role navigation checks. | Accessibility semantics and route availability should be tested against `routeDefinitions`, not duplicated hardcoded lists where avoidable. |
| `apps/web/src/operational-ui.css` | Replace the asymmetric dashboard grid and bottom tool-link layout with scoped Command Center grid, compact header/period control, KPI ribbon, readiness list rows, publication/activity cards, skeletons, responsive stacking, focus/hover states, and progressive disclosure. Keep other operational page rules intact. | Use existing tokens. Avoid broad selector changes to unrelated workflows. Respect 44px target sizes and visible focus. |
| `apps/web/src/operational-ui.css` and `apps/web/src/styles.css` | Review the active rules for `.admin-dashboard`, the command center, and shell layout. Scope changes to connected Administrator classes; preserve Student/Teacher dashboards and demo geometry unless screenshot review identifies a shared issue. | Regression review at all listed viewport sizes. |
| `apps/web/src/styles.css` and `apps/web/src/operational-ui.css` | Style sidebar navigation scrollbars and command-menu overlays in the imported stylesheets, preserving visible scroll affordance on hover/focus and high-contrast behavior. | Do not hide scrollbars entirely or reduce navigation usability. |
| `apps/web/src/main.tsx` | If Motion is approved after bundle review, wrap the application root with `LazyMotion` and `MotionConfig reducedMotion="user"`, using `m` components rather than full `motion` within strict LazyMotion. | Add package and lockfile change only in implementation phase; compare production chunk report before/after. Prefer CSS transitions if Motion cannot meet bundle gate. |
| `apps/web/package.json` and workspace lockfile (`package-lock.json` or actual configured lockfile) | Add a pinned-compatible `motion` dependency only if the measured interaction benefit justifies its incremental bundle cost. | Confirm lockfile manager from root package metadata. No broad dependency upgrades. |
| `apps/web/src/pages/AdminSchedulingHome.test.tsx` | Expand tests for no-period, selected period, refresh, loading layout, stale response, publication available/error, draft available/empty/invalidated by revision, one CTA, mapped blocker destinations, unknown issue fallback, and truthful counts/labels. | Use isolated mocked API responses, never treat them as proof of backend integration. |
| `apps/web/src/pages/dashboards/Dashboards.test.tsx`, `OperationsDashboards.test.tsx`, `PreviewOperationsViews.test.tsx` | Preserve and run as regression coverage for the separate demo dashboard and role dashboards. Change only if shared CSS or shell semantics require an explicit expectation update. | No preview-data authority change. |
| `apps/web/src/pages/institutional-entrance.css` and `apps/web/src/operational-ui.css` | Reuse active reduced-motion conventions; check CSS animations and Motion behavior under `prefers-reduced-motion`. | No parallel or conflicting motion policy. |
| `README.md` | After implementation is approved and accepted, update the UI feature note or local development guidance only if the new dashboard behavior changes documented product usage. | No source implementation in this plan phase; keep this plan link separate from product claims. |

### Route mapping to verify during implementation

Use existing route definitions rather than constructing unverified URLs. Candidate destinations based on current route/config sources include:

- Sections → `/admin/sections`
- Offerings → `/admin/offerings`
- Rooms/resources → `/admin/academic/resources`
- Constraints / operating windows → `/admin/scheduling-constraints`
- Academic period/calendar → `/admin/academic`
- Faculty → `/admin/teachers`
- Curriculum/subjects → `/admin/subjects`
- Draft list → `/admin/schedule-manager/drafts?source=academic`
- Published timetable → `/admin/calendar`
- Generation/readiness → `/admin/ai-scheduling?period=<validated-period-id>`

Before linking a KPI or issue row, verify the route exists, is available in the current role/mode, and its destination consumes any supplied query parameters. Do not expose planned/unavailable routes as actions.

## 4. Selection-only Administrator command menu

The topbar menu is an accessible navigation picker, not a text search box:

- Trigger is a labeled button (“Open page menu”), with a visible shortcut hint if implemented. It opens a grouped menu using administrator route definitions already filtered through `availableRoute`.
- Selection is from a short curated set of entry pages and existing routes. Avoid “record detail” routes requiring an ID selection.
- Keyboard: Enter/Space opens; Arrow Down/Up moves through options; Home/End moves to group endpoints; Enter activates; Escape closes and returns focus to trigger; Tab follows a documented predictable popover behavior. Support touch and pointer selection without requiring shortcut knowledge.
- Screen readers receive an announced menu name and option labels. Current route is identified without implying current page access is authorization. Focus remains visible.
- Menu closes after navigation. Mobile menu interaction remains separate from command menu and sidebar navigation.
- No `query` state or query input is required for the Administrator path. Student/Teacher existing route search remains unchanged in this scope.

Selection-only controls reduce accidental raw input, but are not an injection defense. Server-side Pydantic validation, authorization, parameterized queries, output encoding, and audit rules remain authoritative.

## 5. Motion and visual behavior

If implementation proceeds with Motion for React:

- Add `motion` only after confirming the workspace lockfile and measuring the existing bundle baseline.
- Use `LazyMotion` with `domAnimation` and `strict`, and import the lightweight `m` components where strict mode is enabled. Use a root `MotionConfig reducedMotion="user"`. Official Motion guidance states that `m` plus `LazyMotion` can reduce initial animation payload, while strict mode requires avoiding full `motion` components within the boundary; reduced-motion mode disables transform/layout animation while allowing opacity/color animation. Sources: [Motion bundle-size guide](https://motion.dev/docs/react-reduce-bundle-size), [LazyMotion](https://motion.dev/docs/react-lazy-motion), [MotionConfig](https://motion.dev/docs/react-motion-config).
- Limit animation to one-time content entrance (small opacity/vertical offset), subtle KPI hover feedback, and readiness progress changes. Avoid animating metric values, large layout reflows, flashing empty states, or blocking route interaction.
- Period switching uses stable-height skeletons and stale-request protection. Animate a light opacity transition only if it does not delay state or increase layout shift. Avoid `AnimatePresence mode="wait"` if it creates a blank dashboard between API results.
- Every transition has an equivalent non-motion state. Test with operating-system reduced motion enabled. Bundle size is a measured acceptance criterion, not an assumed benefit.

The dashboard should keep the existing Soft Rouge visual identity, restrained semantic colors, strong labels, readable contrast, and purposeful icons. Cards should be clear surfaces with visible borders and actions, not decorative tiles that make status harder to scan.

## 6. Test and review gates

### Automated checks

Run from the feature worktree after implementation:

```powershell
npm run test --workspace=@classync/web -- src/pages/AdminSchedulingHome.test.tsx src/components/layout/AppShell.test.tsx src/pages/dashboards/Dashboards.test.tsx src/pages/dashboards/OperationsDashboards.test.tsx src/pages/PreviewOperationsViews.test.tsx
npm run typecheck --workspace=@classync/web
npm run lint --workspace=@classync/web
npm run build --workspace=@classync/web
```

Confirm the repository workspace syntax and test file paths against the root package manager before running; adjust the command rather than asserting an unverified command works. Run the existing full web test suite after targeted tests. Existing browser verification scripts and Playwright configuration should be inspected and used if available; do not add a new browser dependency without need.

### Functional acceptance

1. Current period is preserved from workspace preference when valid; otherwise the existing `defaultPeriod()` behavior is retained.
2. Every KPI is period-scoped, never displays a fabricated zero during loading, and navigates to the correct available route.
3. The active-sections, offering, candidate-resource, and draft counts match API fixtures; room language does not imply verified capacity, availability, or per-course suitability.
4. Readiness status and primary action match `ready`, blockers, validated draft, and current academic revision. A stale draft is not presented as current.
5. Every returned blocking issue is visible or discoverable, specific known codes use the correct destination, unknown codes retain their message and have a safe fallback, and no three identical generic action buttons appear.
6. Publication errors remain distinct from “unpublished”; a draft is never labeled as published and publication state is never read from sample data in connected mode.
7. Refresh and period switching recover from failure without stale-period data appearing beneath the new period label.
8. Presentation-only mode retains its explicit sample/read-only disclosure; the separate demo `AdministratorDashboard` still displays preview records only.
9. Administrator command menu contains only current, role-authorized, non-planned routes. Student/Teacher search behavior and all existing role navigation remain intact.

### Visual and accessibility acceptance

- Inspect rendered dashboard at 360, 390, 768, 1024, and 1440 CSS pixels; inspect desktop at both 900px and 1080px viewport heights.
- At ordinary 900/1080 desktop heights with normal content, the header, KPI row, readiness card, publication, and draft snapshot should fit with no avoidable page scroll. Long errors, large text, zoom, or expanded blockers may scroll naturally.
- Verify native 200% zoom, no clipped card/action, no horizontal overflow, and clear focus/hover/selected states.
- Keyboard-only test: period selector, refresh, KPI links, readiness disclosures and actions, command menu, sidebar, and route changes. Confirm focus is restored/placed predictably.
- Test `prefers-reduced-motion: reduce`. Manually verify screen-reader announcements for loading, readiness refresh, alert, and command menu. Mark any manual checks not performed as unverified.
- Measure production bundle delta after Motion installation; no arbitrary “under 500 kB” claim unless verified against current splitting and actual emitted chunks.

### Independent review

Review the diff against the original dirty working tree. Verify no existing user changes were overwritten; no unrelated route/dashboard styles changed; no mocked data became connected metrics; no action points at an unavailable route; no accessibility assertions were deleted or weakened; and the current room inventory count is not reverted to 59.

## 7. Implementation sequence and gates

1. **Baseline route/state verification** — verify route entry, mode selection, actual data contract, route query handling, lockfile, and existing dashboard screenshots/tests. Gate: no architecture or design proposal depends on an assumed API field or mode.
2. **Shared readiness destinations** — extract/normalize the existing issue-code mapping with parity tests against `AcademicGenerationPage.tsx`. Gate: every current blocker code has a destination; unknown code behavior is explicit.
3. **Connected dashboard structure** — build four-tier JSX and period-scoped state without Motion. Gate: targeted tests verify all data states and actions.
4. **Responsive style and AppShell menu** — implement scoped CSS, selection-only admin menu, scrollbar styling, and shell tests. Gate: route authorization semantics and other role search are unchanged.
5. **Motion evaluation/integration** — measure whether Motion provides enough interaction value over existing CSS; if approved, install and add `LazyMotion`/`MotionConfig` with reduced-motion and bundle assertions. Gate: no regression in build, bundle budget, keyboard behavior, or reduced-motion experience.
6. **Full QA and documentation** — run full web checks and browser-size/keyboard review; update `README.md` and `docs/autonomy/STATUS.md` with actual commands, outcomes, and remaining limitations. Gate: evidence is recorded without claiming live backend/institutional validation from mocked UI tests.

## 8. Implementation acceptance record

The owner approved implementation on 16 November 2026. The local code slice is implemented in the feature worktree. It retains the plan's scope: connected dashboard state, issue-specific readiness links, an Administrator-only route picker, scoped responsive styles, reduced-motion-aware CSS transitions, tests, and a README update. No Motion package or lockfile change was made because the existing CSS motion primitives met this slice's needs without adding bundle cost.

Fresh local evidence:

- Focused Admin dashboard, shell, readiness routing, academic management, and preview regression tests: **49 passed across 5 files**.
- Frontend typecheck and lint: passed.
- Production build: passed; existing Firebase mixed static/dynamic import warning and >500 kB JavaScript chunk warning remain.
- Full `npm run test:web`: **three failures** in `PresentationRoutes.test.tsx` for stale room/building expectations against the already-updated inventory: two cards expect 3 and receive 4; the Court room link label is not found. These are outside the files changed by this implementation and remain unresolved.
- A live browser screenshot, responsive manual review, real API journey, screen-reader review, and institutional provider check were not performed. The expected local web/API ports were not listening and no local Playwright package was installed.

No merge, switch, commit, push, deployment, hosted-setting change, or database write occurred. Existing dirty work and the `main` worktree remain preserved.
