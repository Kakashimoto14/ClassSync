# B1 logo integration follow-up

The owner-supplied provisional raster logo files are now integrated through
`ClassSyncLogo`. This supersedes the missing-asset status in the original B1 report;
an official vector master and dark raster export still have not been supplied.

## Scope

Changed `ClassSyncLogo.tsx`, its tests, shared logo styles in `styles.css`, icon links
in `index.html`, and the new public app manifest. Updated `branding.md` with provenance
and placement rules. Existing B1 entrance layout, animations, access flow, routes,
backend, scheduling, academic management and draft persistence were not redesigned
or modified in this follow-up. Pre-existing workspace changes were preserved.

The horizontal image is used in navigation and compact welcome views. The full image
with embedded tagline is used at welcome widths of 1280px and above, at 480px wide.
The mobile header uses a 144px horizontal lockup. The supplied ribbon-only mark is
registered for symbol contexts, and the supplied ribbon icons power favicon/touch/app
icon references. The manifest adds icon metadata only; no service worker or offline
cache behavior was introduced.

Images preserve native colors and alpha. No crop, CSS filter, recoloring or distortion
is applied. Intrinsic dimensions reserve space. Successful images add no duplicate
text. A real image failure replaces the picture with readable text. Named home links
retain accessible names when their decorative image fails. Dark surface requests
use a neutral light backing since no dark artwork was supplied.

## Rendered checks

Browser plugin not available; used existing bundled Playwright and installed Chrome.
The flow under test was welcome → role selection → selected workspace → refresh.

- At 360, 390, 1024 and 1440px, normal images decoded successfully, retained their
  natural aspect ratio, had no filter, and produced no horizontal overflow.
- Visually inspected mobile and desktop entrance, desktop sidebar, and mobile header.
- Verified the responsive source is horizontal below 1280px and full at 1440px.
- Verified Student, Teacher and Administrator workspace navigation, returning preview
  access, and refresh continuity. No normal-load console/runtime errors were reported.
- Aborted actual artwork network requests: the component showed ClassSync text and
  removed broken images. The resulting ERR_FAILED logs are expected test-injected
  failures, recorded separately from normal-load console health.
- Production Vite preview at `http://127.0.0.1:5184` decoded mobile and desktop entrance
  logos successfully. All favicon, touch-icon, manifest, app icon and logo URLs returned
  HTTP 200 with appropriate content types. Normal production role-preview gating passed.

Development preview: `http://127.0.0.1:5183`.

Evidence directory:
`C:/Users/lenovo/.codex/visualizations/2026/10/18/01a14e48-eb6b-7620-a8fa-0d5b6a108c65/`

Captures: `logo-welcome-{360,390,1024,1440}.png`,
`logo-workspace-{360,390,1024,1440}.png`, `logo-network-fallback.png`,
`logo-production-{390,1440}.png`.

Scripts/results: `logo-qa.cjs`, `logo-browser-results.json`, `logo-production.cjs`,
`logo-production-results.json`.

## Verification commands

- `npm run lint`: passed.
- `npm run typecheck`: passed.
- `npm run test:web`: final rerun passed, 182 tests in 22 files. The initial concurrent
  run had one existing PresentationRoutes test exceed its 5-second timeout; an
  unmodified standalone rerun passed, including that test.
- `npm run build`: passed. No new runtime dependencies were added.
- `git diff --check`: passed apart from informational Windows line-ending notices.

## Existing Vercel deployment

The user supplied `https://class-sync-bhiv.vercel.app`, project `class-sync-bhiv`, and
explicitly prohibited commits, pushes or deployments without approval. Read-only
remote browser checks were performed after local production verification.

The deployment is older than the local B1 entrance and logo integration:

- Root at 390px and 1440px shows the older entrance copy and plain ClassSync text.
  Its logo element is marked `data-logo-asset="pending"` and contains no image.
- It has no favicon/icon link, and `/favicon.ico` returns 404.
- The horizontal, full, ribbon-only and 32px icon PNG URLs return HTTP 404, as does
  `/manifest.webmanifest`.
- Direct `/auth/login`, `/dev/role-preview`, `/student/dashboard`, `/teacher/dashboard`
  and `/admin/dashboard` requests return Vercel 404 pages. This is a deployed SPA
  history-fallback issue, separate from the local logo change.

Remote evidence: `logo-vercel-welcome-{390,1440}.png`,
`logo-vercel-login-{390,1440}.png`, `logo-vercel-results.json`, and the executed
`logo-vercel.cjs` / `logo-vercel-client.cjs` scripts in the evidence directory above.

The new integration is verified locally, including the production output. It is not
verified as deployed because these local changes are not on the existing Vercel site.
No commit, push, deployment, or hosting configuration change was performed.

Client-side navigation from the deployed homepage's Explore ClassSync action was
also tested. All three dashboards open at both 390px and 1440px through that flow,
but each visible sidebar/mobile-header logo is still the older text fallback, with
`data-logo-asset="pending"` and no image. Their direct-URL 404 behavior is distinct
from this working client-side navigation. Captures:
`logo-vercel-{student,teacher,administrator}-{390,1440}.png`.
