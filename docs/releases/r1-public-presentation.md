# R1 — public read-only presentation release

Status: locally prepared; **not committed, pushed or deployed**. This is the release
procedure for the existing `class-sync-bhiv` project, not a backend deployment.
It supersedes UX-06's generic-build instructions for this presentation project.

## Actual public baseline and project access

Rechecked 19 October 2026 with read-only HTTP and actual Chrome role journeys:

| Request | Actual response |
| --- | --- |
| `/` | 200 HTML; public script `/assets/index-CbQh0kvf.js` |
| `/student/dashboard` | 404 plain text |
| `/teacher/schedule` | 404 plain text |
| `/admin/dashboard` | 404 plain text |
| `/api/v1/timetables/periods` after Student/Teacher entry | 404 `text/plain; charset=utf-8`, `NOT_FOUND` |
| Vercel project-settings API without authenticated access | 403 JSON |

No `.vercel/project.json`, Vercel CLI auth file or Vercel connector is available.
The **actual private Root Directory, output override and environment settings are
unverified**, not assumed to match the repository. Latest successful GitHub
Production deployment records SHA `409279e6a44df34097c3c854b1c46ac1bc5cb201`.
Its unique URL is protected by Vercel login; public alias SHA is not certified.
After approval, verify the actual project settings and deployed release SHA rather
than treating a GitHub deployment record as alias proof.

## Routing correction

`vercel.json` explicitly sets Vite, repository-root `npm ci`,
`npm run build:presentation` and `apps/web/dist`. Existing frontend route-prefix
rewrites are retained; `/forbidden` is added for role-boundary refresh. Direct role
routes serve `index.html`, then the normal React router/P0 guard selects the screen.
An unauthenticated deep link may correctly show welcome/role selection first.
No auto-login or automatic role assignment was introduced.

There is **no broad catch-all or `/api` rewrite**. Existing static files take
precedence; missing JavaScript/images and missing API routes remain actual 404s.
The local production server loads the actual `vercel.json` rewrites, uses the built
files, preserves static precedence, has no API proxy and fails on an occupied port.
This is Vercel-equivalent route emulation, not an actual Vercel edge deployment.

Official references: [Vite SPA deep-link configuration](https://vercel.com/docs/frameworks/frontend/vite#using-vite-to-make-spas),
[Vercel rewrites and filesystem precedence](https://vercel.com/docs/routing/rewrites),
[monorepo settings](https://vercel.com/docs/monorepos),
[supported Node versions](https://vercel.com/docs/functions/runtimes/node-js/node-js-versions).

## Explicit public sample strategy

`npm run build:presentation` deliberately enables both presentation and role-preview
flags. Generic `npm run build` retains its ordinary production behavior. Vercel's
reviewed build command explicitly chooses the read-only artifact; no failed API
request activates it. A stale connected preview session or hostile source query
cannot select live/private data in that artifact.

The existing deterministic `classsync-presentation-v1` data is unchanged: one BSIT
3A section, two synthetic offerings, four weekly sessions, 53 dated occurrences
in October–December 2026, source input hash and validation-at-export metadata.
Student Home/Schedule/Calendar and Teacher assignments use the same data and stable
identities. Invalid sample identities have an explicit reset action. Dates outside
the frozen range correctly have no occurrences; the sample does not invent future
classes or roll the fixture dates forward.

Admin Home and calendar remain as implemented in UX-06. Conflict Center adds only
a frozen sample summary: **0 hard conflicts at export**, two offerings/four weekly
sessions, explicitly no new validation or live analysis. Unsupported generation,
save, academic mutations and publication remain unavailable. Demo requests remain
separate fixed records. There is no fake backend success, live occupancy or live
synchronization. Existing server authorization and Firestore/IAM rules are unchanged.

The production build writes static `/release.json`: mode, sample version, source
commit and whether local uncommitted changes were detected. Local dirty builds do
not claim a new deployed SHA. Git deployments use `VERCEL_GIT_COMMIT_SHA`; if absent,
the build reads its checkout HEAD. This file contains no credentials or records.
The production preview command rejects an ordinary/non-presentation artifact.

## Firebase status and required environment

Local initialization previously passed because ignored `apps/web/.env.local`
contains the six web values for the existing `classsync-f444c` registration. That
ignored file is not shipped by Git. The current public bundle lacks the expected
project/app IDs. Private Vercel variables cannot be inspected without authenticated
project access (403); their exact missing/mismatched values remain unverified.

**R1 does not require Firebase, Firestore, backend credentials or a public API.**
Missing/incomplete/failed SDK initialization returns a non-ready state rather than
throwing through the presentation. The release is tested with all six Firebase
values deliberately empty; no Firestore call is required. No security rules, IAM,
provider, identity claim or paid service is changed. Existing Firestore rules were
not fully audited; the earlier denied probe is not a complete rules certification.

| Production/Preview setting | Required value/action |
| --- | --- |
| Project | Existing `class-sync-bhiv`; confirm correct owner/team |
| Root Directory | Repository root `.` (must inspect/confirm actual setting) |
| Framework | Vite |
| Install | `npm ci` |
| Build | `npm run build:presentation` |
| Output | `apps/web/dist` relative to repository root |
| Node | 22.x; locally tested 22.23.1, pinned in root package and lockfile |
| `VITE_ENABLE_ROLE_PREVIEW` | `true`; release command also explicitly sets it |
| `VITE_ENABLE_PRESENTATION_SAMPLE` | `true`; release command also explicitly sets it |
| `VITE_API_BASE_URL` | Unset; no localhost/private host or public sandbox target |
| `ENABLE_SCHEDULING_SANDBOX` / backend credentials | Unset; not part of static release |
| `VERCEL_GIT_COMMIT_SHA` | Vercel-provided Git commit metadata; ensure available |

Firebase web values are optional for this R1 artifact. For later intended-project
initialization, configure **all six** in the appropriate Vercel environment and
rebuild: `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`,
`VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_STORAGE_BUCKET`,
`VITE_FIREBASE_MESSAGING_SENDER_ID`, `VITE_FIREBASE_APP_ID`. Copy values securely
from the existing registration; do not create another app. Never put Admin/private
service credentials in `VITE_*`. Firebase setup alone cannot supply the timetable API.

## Local release procedure

```powershell
npm ci
npm run lint
npm run typecheck
npm run test:web
npm run build
npm run build:presentation
npm run preview:presentation
```

Open **http://127.0.0.1:5188/**. This is the actual production output with no Python
proxy. `CLASSSYNC_PRESENTATION_PORT` can explicitly select another port; there is no
silent fallback. `CLASSSYNC_PRESENTATION_DIST` is an optional explicit artifact path.
The connected development URL remains `http://127.0.0.1:5173/`; the older 5190 QA
workspace is unrelated to this release check.

## Deployment steps — only after owner approval

1. Review the R1 delta and the full UX-06+R1 working-tree release patch/inventory.
   UX-06 is still uncommitted; deploying only a subset of R1 would omit dependencies.
   Preserve databases, ignored environment files and prior work. Do not stage secrets.
2. With explicit commit/push/deployment approval, commit the reviewed sources and
   record the new full SHA. Do not label baseline `409279e...` as the new release.
3. Authenticate to the existing Vercel project. Inspect and confirm the table above,
   including repository root and Production/Preview scope of flags. Do not create a
   second project, backend, database or paid service.
4. Push only the approved release branch/commit. A push to an auto-deployed branch
   may trigger deployment immediately; it therefore needs deployment approval too.
   Prefer a reviewed Preview deployment, then authorized Production promotion.
5. Inspect build logs: correct SHA, explicit presentation target and expected output.
   Keep the previous deployment available for rollback.
6. Verify the immutable deployment and public alias `/release.json`: correct new
   committed SHA, read-only mode, `classsync-presentation-v1`. Reconcile any dirty/
   unavailable metadata with build logs; do not invent a SHA certification.
7. On the public alias, use independent Student/Teacher/Admin browser contexts at
   390px and 1440px. Test root/direct role routes/refresh/role switching, next class,
   calendar date/details/room, Teacher assignments/requests, Admin frozen conflict
   summary, unavailable mutation tools, logos/favicon and browser console/network.
8. Confirm zero application API/backend requests in presentation journeys; API and
   missing static paths stay real 404s. Confirm no private drafts or write controls.
   Only then report **VERCEL PASS**. On regression, roll back the deployment rather
   than weakening authorization or silently enabling a development backend.

## R1 affected files

- `.github/workflows/quality.yml`: Node 22, both production variants and release
  mode/sample/SHA assertions on future approved pushes and pull requests; no deployment step.

- `package.json`, `package-lock.json`, `vercel.json`: explicit release/preview commands,
  matching Node 22 engine metadata (no dependency changes), and static routing.
- `scripts/build-presentation.cjs`, `scripts/preview-presentation.cjs`: portable build,
  public provenance metadata and strict config-driven local production server.
- `apps/web/src/lib/use-schedule-workspace.ts`: presentation source for returning sessions.
- `apps/web/src/pages/RoleScheduleWorkspace.tsx`: valid identity recovery and Admin scope label.
- `apps/web/src/pages/PublishedRoomAvailability.tsx`: build-level read-only boundary.
- `apps/web/src/operational-ui.css`: scope connected-dashboard grid placement so the
  presentation heading retains its intended position above the main action.
- `apps/web/src/pages/ProductScreenPage.tsx` and
  `apps/web/src/components/scheduling/PresentationConflictSummary.tsx`: frozen conflict information.
- `apps/web/src/pages/R1Presentation.test.tsx`, `apps/web/src/lib/firebase-config.test.ts`: regressions.
- This release guide. The versioned dataset and original UX-06 dashboard layouts are unchanged.

Final executed QA, database manifests, exact patches and screenshots are recorded
with the release evidence after verification below.


## Verification scope and findings

The Browser plugin is not available; installed Chrome with Playwright is used.
The tested release flow is direct entry → explicit role preview → sample dashboard
→ another calendar date → class details/room → refresh. A separate test exercises
unauthenticated entry, wrong-role refresh and expired P0 sessions.

Browser QA found and repaired a same-month date-selection defect introduced by
presentation source locking: reapplying an unchanged scope cleared loaded data
without requiring a new fetch. The hook now clears data only when the effective
source/identity changes. A focused regression selects another date and confirms its
agenda stays loaded. An initial new persistence assertion was also corrected to
await the asynchronous session write; no existing test was removed.

Backend business logic, OR-Tools, authorization and databases were not modified.
The UX-06 78-backend-test result is baseline evidence, not a new R1 backend run.
Read-only before/after manifests cover every SQLite table (including all draft and
publication rows), with integrity and foreign-key checks. R1 makes no fixture import,
generation, draft save or publication request.

Security boundaries: preview roles are presentation state, not server identity;
the bundled JSON is intentionally public and synthetic; no private drafts or
credentials are included. Firestore provisioning/full rules remain administratively
unverified and unchanged. The existing public site is not reported as VERCEL PASS.

GitHub Actions now builds the exact read-only release target after its existing
checks, on Node 22 matching local verification and the recommended Vercel setting.
A CI assertion checks mode, sample version and checkout SHA. This workflow has not
been triggered remotely during R1; its build/assertion commands are verified locally.

The root package and lockfile now pin Node `22.x`, avoiding an open-ended `>=20`
range selecting a newer untested Vercel major. CI uses the same major. No package
version or dependency graph was changed.


## Final local release acceptance

**LOCAL R1 PASS. PUBLIC VERCEL NOT RELEASED/NOT VERIFIED.**

| Check | Result |
| --- | --- |
| Lint / TypeScript | PASS |
| Frontend tests | **216 passed, 33 files**, all existing tests retained |
| Generic production build | PASS |
| Explicit presentation build | PASS, all six Firebase web values deliberately empty |
| GitHub release metadata assertion | PASS locally; remote Actions not triggered |
| Direct production routes | 14 HTTP entry paths return HTML, including nested draft/setup and forbidden paths |
| Role access | Unauthenticated entry, wrong-role refresh and expired P0 sessions remain gated |
| Three-role browser journeys | PASS on built output at 360, 390, 768, 1024 and 1440px |
| Student/Teacher schedule | Same versioned sample, date selection/details/room navigation and refresh pass |
| Administrator | Sample timetable, frozen export conflict summary and unavailable connected tools pass |
| Console / runtime / overflow | No errors or horizontal overflow in checked journeys |
| Network | **Zero application API requests** during checked presentation journeys |
| Missing API / write paths | Real 404 plain text, never HTML or simulated success |
| Static branding / favicon | Loaded; missing asset paths remain 404 |
| Preview startup | Strict port; ordinary/non-presentation artifact rejected |
| Database integrity | Every table hash and row count unchanged; integrity/foreign-key checks pass |

Browser plugin unavailable; actual installed Chrome/Playwright was used. The local
server reads actual Vercel rewrite configuration and serves production output only;
Python services are not used or proxied. These checks do not certify an unapplied
Vercel project setting, remote GitHub run or an undeployed commit.

Vite retains a non-failing main-chunk-over-500-kB warning. No dependency, animation
library, Firestore rule, IAM permission, backend authorization or paid service changed.
The only dependency-lock edit is the matching root Node engine metadata.

### Review artifacts

All raw evidence and screenshots are in:

`C:/Users/lenovo/.codex/visualizations/2026/10/18/01a14e48-eb6b-7620-a8fa-0d5b6a108c65/r1`

- `r1-only.patch`: exact R1 text delta against the preserved pre-R1 working files.
- `full-ux06-r1-release.patch`: Git-generated tracked and untracked release diff
  against HEAD; includes required, still-uncommitted UX-06 sources and assets.
- `r1-files.json`: complete R1 path/status/SHA-256 inventory.
- `web-tests.log`, `build-default.log`, `build-no-firebase.log`.
- `r1-presentation.json`, `routing-boundaries.json`, `startup-safety.json`.
- `database-before.json`, `database-after.json`: identical full-table manifests.
- `public-baseline.json`: actual current Vercel root/deep-route/project-access statuses.

Both review patches pass `git apply --reverse --check --ignore-whitespace` against the current working
tree (Windows CRLF/LF normalization). Actual ignored Firebase key/app values are excluded. No index staging or
commit was used to produce them.

Screenshots (actual local production artifact):

- Student mobile: `r1-presentation-student-390.png`.
- Teacher mobile: `r1-presentation-teacher-390.png`.
- Administrator desktop: `r1-presentation-administrator-1440.png`.
- Class details: `r1-presentation-student-details.png` and Teacher/Admin equivalents.
- Conflict summary: `r1-conflicts-390.png`, `r1-conflicts-1440.png`.
- Both 390px and 1440px Home captures exist for all three roles.

Approval remains necessary for committing/pushing the reviewed combined sources,
changing actual Vercel project settings and deploying. The original 5190 workspace
is not the R1 production preview; review R1 at **http://127.0.0.1:5188/**.
