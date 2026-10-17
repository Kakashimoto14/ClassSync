# P0 — Preview session and navigation reliability

Verified 18 October 2026 (Asia/Singapore). Scope: existing React/TypeScript/Vite
frontend, for the ITHUMCI presentation. Existing uncommitted presentation work was
preserved. No backend authentication, permissions, dependencies, palette, or unrelated
screen redesign was changed. No commit or push was made.

## User goal and context

A presenter chooses Student, Teacher, or Administrator and explores that workspace.
Navigation, history, refresh, and valid deep links should preserve that explicit
selection. A restricted link should explain the restriction and offer recovery
without silently selecting another role or discarding the current preview.

## Reproduced issue and confirmed causes

1. `apps/web/src/auth/DevelopmentRoleProvider.tsx` initialized
   `useState<UserRole | null>(null)` and retained selection only in memory.
   Reloading/remounting therefore removed the role. `RoleRoute` in
   `apps/web/src/routes/RouteGuard.tsx` then redirected to login with a return URL;
   the shell also had a role-picker fallback. The previous access test explicitly
   required an in-memory session without persistence. The provider was already
   above all routes; normal React Router navigation alone did not remount it.
2. Browser QA reproduced an Exit redirect race: clearing the role while still on
   a protected screen allowed the missing-role guard to override the explicit login
   destination. `AppShell.tsx` now completes that navigation synchronously before
   clearing the preview.
3. `auth/access.ts` matched return paths exactly while React Router accepts trailing
   slashes. Valid trailing-slash detail links could fall back to the dashboard.
   The guard also omitted URL fragments from its return URL. Both are corrected.
4. Preview selection/restoration had no production gating. This was a separate
   access-boundary defect, corrected without adding or changing backend permissions.

Inspection covered the context/hook/provider, guard, router, shell, authentication
entry, role picker, route registry, dashboard links, mobile/sidebar navigation,
search, rooms/buildings and return links, schedules, teacher requests, and conflicts.
Application destinations already use React Router `Link`/navigation. The remaining
shell anchor is the intentional skip-to-content link. No application
`window.location` navigation, hard-coded cross-port internal links, or URL-based
role inference was found.

## Implemented improvement and changed files

- `auth/preview-session.ts`: sessionStorage key `classsync.preview.v1`, schema version,
  validated role, and selection timestamp only. Eight-hour absolute expiry, including
  an open-page timer; navigation and restoration do not renew it. Malformed, expired,
  future-dated, unsupported-version, and invalid-role records are removed. Storage
  errors fall back to usable in-memory preview without throwing.
- `auth/DevelopmentRoleProvider.tsx`: synchronous lazy restoration before route guards,
  explicit selection/exit writes, expiry, and back-forward-cache restoration handling.
  `development-role-context.ts` and `useDevelopmentRole.ts` keep their existing API.
- `pages/DevelopmentRolePreviewPage.tsx`: accurate continuity/scope explanation,
  current-workspace continuation, explicit role selection, and disabled-build redirect.
- `pages/AuthPage.tsx`: hides preview entry outside permitted builds and gives
  environment-appropriate sign-in-unavailable guidance.
- `components/layout/AppShell.tsx`: visible Switch preview role control, safe Exit,
  and menu/search cleanup on query changes without stealing room-pagination focus.
- `auth/access.ts`, `routes/route-config.ts`, `routes/RouteGuard.tsx`: consistent
  trailing-slash ownership/active destination handling and complete query/hash return
  URLs. Exact registered route ownership remains required.
- `routes/app-routes.tsx` and `routes/router.tsx`: extracted the unchanged route tree
  so regression tests use exactly the application's routes with a memory router.
- `apps/web/.env.example`: documents `VITE_ENABLE_ROLE_PREVIEW=false` while retaining
  the existing API/Firebase configuration examples.
- Tests: `auth/preview-session.test.tsx`, `routes/NavigationReliability.test.tsx`,
  `auth/access.test.tsx`, and `components/layout/AppShell.test.tsx`. `vitest.config.ts`
  limits concurrent workers to two to avoid resource-contention timeouts; assertions
  and existing test timeout limits were retained.

Preview is available in Vite development, or when a build explicitly sets
`VITE_ENABLE_ROLE_PREVIEW=true`. Set that only in `apps/web/.env.local` or the build
environment for an explicitly non-authenticated demonstration. Ordinary production
builds default to unavailable, discard persisted preview selection, and hide the
role picker. No passwords, tokens, or private student data are stored. These UI
roles never become authenticated users or backend permissions.

## HCI rationale

These are the concepts supplied in the task; no separate ITHUMCI handbook text or
participant study was provided.

| Concept | Application |
| --- | --- |
| Mental models and consistency | An explicit workspace selection survives navigation and refresh; ownership uses the registered role routes. |
| Visibility of system status | Existing role/demo indicator and active sidebar/mobile destinations remain; detail routes keep their parent section active. |
| User control and recovery | Explicit switch, continue, and Exit controls; forbidden and unknown-page recovery returns to the selected workspace. |
| Error prevention | Valid query/trailing-slash links retain destinations; roles never change based on a URL; search offers role-owned entry routes. |
| Recognition over recall | Existing Dashboard, Schedule, Rooms, Requests, and Conflicts labels are retained. |

## Regression and browser verification

The regression suite uses the real route tree/provider, not mocked authorization,
for selection, dashboard and nested-route remounts, direct query/hash links, history,
explicit role changes, Exit, and cross-role recovery. Storage tests include all three
roles, malformed/stale records, blocked storage, mounted expiry, ordinary production
gating, and explicit demonstration-build opt-in. Existing directory focus/pagination,
dashboard, route ownership, search, drawer, and calendar tests remain in scope.

Browser plugin was not available. Used the bundled Playwright package and installed
Chrome; no driver was downloaded. Development URL: `http://127.0.0.1:5182`.
The existing server was confirmed to serve current edits. A separate Vite server at
port 5186 supports origin isolation checks. Production preview uses port 5187.

| Scenario | Actual outcome |
| --- | --- |
| Student → Dashboard → Schedule → Rooms → detail → back/forward | Same role and correct URLs; room return opens the directory. |
| Teacher → Schedule; dashboard request → Request Detail → back | Same Teacher role, selected request retained, dashboard recovered. |
| Administrator → Conflict Detail → Room Directory → Dashboard | Same Administrator role; conflict record and active parent destination retained. |
| Refresh each dashboard and each role's selected detail | Page and role restored without login/selection redirect. |
| Explicit role switch | Visible switch opens picker; only selecting a role changes it. |
| Exit and browser history | Stored preview removed; history does not revive the workspace. |
| Cross-role destination | Forbidden page retains current role; dashboard recovery works. |
| Invalid persisted record | Cleared and returned to sign-in with requested destination. |
| Fresh tab/context, different hostname, different port | Did not inherit the selected role; original origin retained it. |
| Ordinary production build | Picker redirected to login, Explore entry hidden, seeded preview discarded, protected deep link rejected. |
| Responsive layouts | All three role flows exercised at 390 and 1440px; additional Student dashboard/directory/calendar checks at 360, 768, and 1024px. |

Browser checkpoints record actual URL, first heading, stored role, active navigation,
meaningful page content, overlays, console output, and horizontal overflow.
The final Chrome run passed 65 recorded checkpoints, waiting for the destination's
expected heading before taking evidence (rather than treating a URL update alone
as a completed render). Search-result navigation also opened the Student directory
and cleared its search menu. Inspected screenshots showed readable desktop/mobile
layouts, correct active destinations, and an understandable forbidden recovery page.
Screenshots and the browser script/results are outside the repository at:
`C:/Users/lenovo/.codex/visualizations/2026/10/17/01a14b83-8f79-7a40-82da-d3d7b664de7f/`.

Selected screenshots: `p0-admin-dashboard-1440.png`, `p0-admin-dashboard-390.png`,
`p0-student-detail-1440.png`, `p0-student-detail-390.png`, and
`p0-forbidden-1440.png` / `p0-forbidden-390.png`. Machine-readable checkpoints:
`p0-browser-results.json`; repeatable local browser script: `p0-qa.cjs`.

## Scope and remaining limitations

- Session storage is scoped to the tab and exact origin (scheme, host, port).
  Keep the presentation at one URL. Independent tabs and contexts choose their own
  role. Browser-duplicated/opener-created tabs can initially copy sessionStorage;
  their later selections and Exit are independent. There is no cross-tab role sync.
- Same-origin frames in the same top-level tab share sessionStorage; separate
  origins/contexts do not. No embedded presentation host was provided, so physical
  embedding, third-party storage policies, and that host's navigation remain unverified.
- If storage is blocked, navigation still works but refresh continuity cannot be
  guaranteed. Browser session restoration may retain sessionStorage; the absolute
  expiry still bounds it. Client time is sufficient for sample UI, not security.
- Vite's development/preview servers support history fallback. A deployed static
  host must serve index.html for valid nested SPA paths; production hosting rewrite
  rules were not exercised or modified here.
- A full reload still resets unrelated unsaved component state unless encoded in
  existing URLs/history. This change persists preview selection only. No live
  authentication, scheduling mutation, or multi-device continuity was added.
- Desktop Chrome automation is not physical-device, screen-reader, zoom, or WCAG
  certification. No participant data or usability metrics are claimed.

## Required checks

| Command | Final outcome |
| --- | --- |
| `npm run lint` | Passed; no warnings. |
| `npm run typecheck` | Passed. |
| `npm run test:web` | Passed: 152 tests, 19 files. |
| `npm run build` | Passed: 1,692 modules; JS 462.58 kB / 138.44 kB gzip. |
| `git diff --check` | Passed. |

The first test runs caught and resolved the query-change pagination focus regression
and the utility-link ownership assertion. A test fixture was corrected to expect the
actual room name rather than a generic Details heading. Resource-contention timeouts
in parallel runs were resolved by bounding worker concurrency. The final full run
passed without increasing existing test timeout limits (the new multi-step journey
test explicitly allows 15 seconds).

Browser QA found no runtime exceptions or framework overlays. The existing missing
`/favicon.ico` produces a single verified 404 console message; it does not affect
navigation and was left outside P0. No participant measurements were collected.
