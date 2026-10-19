# UX-06 dashboard and deployment audit

Verified 19 October 2026. Local interface implementation and cloud readiness are
reported separately. No commit, push, deployment, cloud provisioning, migration,
security-rule change or production data write was performed.

## Executive status

| Area | Result |
| --- | --- |
| LOCAL FRONTEND | PASS — canonical connected workspace and explicit production presentation artifact |
| LOCAL BACKEND | PASS — real generation/independent validation/save/reopen and recovery |
| FIREBASE INITIALIZATION | PASS locally; intended project initialization on Vercel BLOCKED/unverified |
| FIRESTORE | BLOCKED — administrative metadata needs OAuth; no provisioning/rules claim |
| VERCEL FRONTEND | FAIL for direct-route refresh; root and client navigation work |
| PUBLIC TIMETABLE API | NOT DEPLOYED at configured public URL: actual timetable requests return 404 plain text |
| PRODUCTION AUTHORIZATION | NOT CONFIGURED — preview role remains separate from verified server identity |
| UX-06 INTERFACE | PASS locally, including separate read-only production build; not deployed |
| DATABASE INTEGRITY | PASS — both SQLite checks, foreign keys, original checksums and publication counts |
| DEPLOYMENT READY | PARTIALLY — reviewed read-only artifact staged; owner approval and Vercel settings verification required |

## Baseline and actual diagnosis

Baseline working tree was clean at `409279e6a44df34097c3c854b1c46ac1bc5cb201`.
Read-only `git ls-remote` confirmed pushed main at the same SHA. Applicable project
instructions, current code, prior C1/C2/UX-04/UX-05 reports and tests were inspected.
GitHub's latest successful Production deployment records this SHA. Its unique
Vercel URL redirects to Vercel login; the precise public alias SHA cannot be
certified without authenticated deployment metadata. Do not equate that record
with proof that the alias serves a particular artifact.

### Local instances

Canonical **http://127.0.0.1:5173/** uses Gateway 8000, Academic 8001, Scheduling
8002 and existing `var/*.sqlite3`. `npm run dev` verifies health, sandbox contracts,
explicit database paths and strict frontend port before readiness. No fixture import
occurs on startup. IPv4 loopback avoids the prior localhost/IPv6 mismatch.

The earlier 5190 workspace uses Gateway 8830/8831/8832 and isolated QA databases.
It has synthetic published data absent from canonical publication history. The
origins have separate expiring P0 sessions. Neither selecting a role nor changing a
port transfers source/context storage. The prior rejection of an entered draft by
anonymous calendar review was a correct 403 authorization/source boundary, repaired
in UX-05 by synthetic-only GET discovery rather than weakening that guard. See
[the exact prior request and response](ux-05-reliability-and-interface-audit.md).

UX-06 re-exercised this repaired architecture: an explicitly configured second
frontend on 5174 used the same Gateway, selected the same permitted saved sample,
refreshed and navigated to Schedule. An actual Gateway outage stopped the owned
launcher, the frontend showed Retry without stale classes, and `npm run dev`
restarted the services. Retry restored the same draft without requiring a recovery
refresh. A separate launcher test on explicit QA ports verified health and owned
process cleanup. The temporary 5174 diagnostic frontend is not a new canonical URL.

### Public Vercel failure

Actual Chrome welcome → role journeys requested:

`GET https://class-sync-bhiv.vercel.app/api/v1/timetables/periods`

Student and Teacher both received **404**, content type `text/plain; charset=utf-8`,
body beginning `The page could not be found`, then `NOT_FOUND`. The sandbox periods
path also returns 404. Direct `/dev/role-preview` returns 404. Root, client-side
navigation and brand images work; these do not establish API or refresh readiness.

The Vite development proxy is not part of the deployed static output. The repository
has no deployed public Gateway host, Python Vercel function or remotely shared SQLite
store. This is a missing routing/backend deployment, not a Firebase permission error
or a calendar rendering failure. No API response is rewritten into HTML by the staged
configuration. Actual Vercel Root Directory/output/env settings remain inaccessible.

[Current Vercel failure screenshot](screenshots/ux06/before-vercel-student-390.png).

## Firebase and infrastructure decision

The existing SDK was reused. The local six-key registration identifies
`classsync-f444c`; Firebase web-config API returned 200 matching project/app IDs.
Actual browser initialization reports the existing default app `[DEFAULT]`.
Initialization now distinguishes absent, incomplete, mismatched and failed config,
without logging secrets or creating duplicate apps.

Firestore database metadata returned **401 UNAUTHENTICATED**; a valid anonymous
collection-list probe returned **403 PERMISSION_DENIED**. Database provisioning,
region, collections, indexes, full rules and anonymous administrative-write denial
cannot be certified from those probes. No document was written or rule changed.
The public bundle does not embed the expected local project/app identifiers;
authenticated Vercel env settings and production initialization remain unverified.

**Recommend Option A now:** explicitly selected, versioned, bundled read-only
presentation. **Option B later:** approved Cloud Run FastAPI/OR-Tools services,
durable PostgreSQL, verified Firebase identities and deployed version-aware events.
Costs, CORS/IAM, region, database migration/rollback and deployment require approval.

Details: [Firebase readiness](../infrastructure/firebase-readiness.md) and
[deployment decision, costs and approval steps](../infrastructure/vercel-backend-deployment-plan.md).

## Implemented screen and workflow changes

| Surface | Change and truthful boundary |
| --- | --- |
| Student Home | Retained next-class hierarchy, real next occurrence/no-class state, compact source/context, valid time/room and direct Schedule/Room actions; shortened synthetic faculty display names without changing IDs |
| Teacher Home | Shared authoritative timetable context; readable instructor alias; pending request first, recent decisions disclosed, fixed demo source explicitly separate from selected faculty; no submission or approval simulation |
| Administrator Home | Actual period/readiness/drafts/publication reads; requirements → generation → current validated draft review; at most three blockers; real scope counts and recent snapshot metadata; no fabricated unsaved result/published state |
| Calendar/details/rooms | Shared context retained; explicit presentation badge; registered synthetic room destinations remain usable; availability receives the correct role and explicitly states that live occupancy is unavailable in presentation mode |
| Scheduling | Existing OR-Tools path unchanged; default generation setup stays focused; sample import moved to dedicated Academic Setup → Sample Academic Scenario |
| Conflict Center | Independent validator leads; loading differs from empty; timetable is secondary disclosure; conflict review opens the enclosing disclosure and focuses the assignment |
| Saved Drafts | Neutral outlined reopen action, solver/source and actual stored-validation status; immutable content unchanged |
| Academic Management | Dedicated deliberate sample setup only on setup root; ordinary management pages no longer repeat the import module |
| Reports/utilization | Removed invented report bars and disabled fake filters; concise Coming soon with real timetable navigation |
| Institutional rules | Existing planned governance screen retained; no fake policy editor. Enforced constraints remain in real readiness/generation/validator contracts |
| Shared interactions | Neutral 44px disclosure rows/chevrons, recognizable underlined normal navigation, outlined ordinary actions, original primary/status/destructive semantics preserved |

The Admin homepage does not invent a cross-route unsaved candidate store or offer
publication as a consequence of saving. Real generation results retain their existing
Save Draft action. A current draft is offered only when its stored academic revision
matches the checked period. Historical snapshot validation is labelled as such.
Classroom counts are candidates, not assurances of capacity/equipment suitability.

## Read-only presentation contract

Two independent opt-in build flags are required: `VITE_ENABLE_ROLE_PREVIEW=true`
and `VITE_ENABLE_PRESENTATION_SAMPLE=true`. Defaults remain false. The role chooser
states read-only/version/no live synchronization before entry; local users can also
choose the source deliberately. Backend failure never silently selects this source.

`classsync-presentation-v1` was exported read-only from an existing server-approved,
validated synthetic-only draft. It contains one BSIT 3A section, two synthetic
offerings, four weekly sessions and 53 dated occurrences, October–December 2026.
It records input hash/source draft/validation at export; this is not current campus
validation or an official published timetable. Teacher aliases keep stable IDs.
All change flags are false. Other identities are rejected rather than substituted.
Outside the exported date range an empty agenda is correct.

The artifact uses lazy bundled data, no backend reads/writes or event stream.
Admin connected tools show a truthful unavailable boundary instead of enabled
mutations. Live room occupancy is explicitly unavailable. The normal production
build still disables three-role preview. Server sandbox/auth policies were unchanged.

Root `vercel.json` stages frontend-only route rewrites. A local static emulator
verified the artifact, deep links and `/api` 404 plain-text behavior. This is not a
Vercel deployment or certification of unapplied project configuration.

## ITHUMCI and accessibility evidence

The actual 70-page handbook was available at
`C:/Users/lenovo/Downloads/ITAPPSD/WEEK 6/ITHUMCI_Detailed_Student_Book_Complete.pdf`.
Relevant module overview pages were re-read: M2 p6, M3 p9, M6 p18, M7 p21,
M11 p31, M12 p34. Existing project HCI reports supplied implementation context.
No human-participant study or participant-derived performance claim was made.

| Observed problem → HCI principle | Implemented correction | Verification |
| --- | --- | --- |
| Public API failure appeared to be a timetable fault → M3 mental models, Nielsen visibility/recovery | Distinct infrastructure diagnosis; explicit optional sample, no automatic fallback | Real public 404/plain-text evidence; local source/error tests |
| Long synthetic IDs competed with next-class facts → M2 attention/recognition, M11 hierarchy | Readable display aliases with stable IDs and source details secondary | Both role Homes/details, 360–1440px |
| Teacher request demo could look related to selected faculty → M3 source/status visibility | Separate demonstration source beside pending-first request list; explanation disclosure | Correct pending request detail route, no fake submission |
| Admin promotional page did not answer what to do next → M6 task analysis, M7 information architecture | Readiness/revision-based primary action and real period context | Ready/current-draft and blocked period UI plus component tests |
| Full timetable obscured conflict work → M2 attention, Nielsen minimalism | Validator first; timetable secondary; affected-assignment focus retained | Real independent validation and exact assignment navigation test |
| Rouge summaries looked like errors → M3 signifiers, M11 color/affordance | Neutral disclosure rows, chevrons, outlines and underlined navigation | Rendered shared controls; 44px targets; contrast checks |
| Repeated import configuration competed with management → M6 task simplification, M7 grouping | Dedicated reviewed setup route | No import on review; explicit backend import succeeds; generation link retains period |
| Fake report charts implied operational statistics → Nielsen real-world match, feedback | Honest unavailable/Coming soon state and useful real link | No report bars, route screenshot |
| Mobile class facts/actions could be hard to reach → M12 operability, user control | Existing shared padded sheet, keyboard trap, inert background and safe scroll retained | Tab/Shift+Tab, Escape, Close, restoration, short screen and reflow equivalent |
| Wrong default role leaked into room availability → M3 consistency, error prevention | Pass role through shared availability page | Teacher/Admin regression tests and production presentation browser checks |

Focus and dialog checks passed at 360×800, 390×400, 720×450 and 1440×900.
720×450 is a 200% reflow equivalent of 1440×900, not native browser toolbar zoom.
Visible actions, no horizontal overflow, inert background, initial focus, Tab wrap,
Escape and restoration were exercised. Reduced-motion browser rendering was used.
Measured color ratios on surface: ink 15.55:1, secondary 4.97:1, rouge/white 8.34:1,
warning 4.65:1. These are scoped engineering checks, not a full WCAG compliance audit
or a screen-reader participant evaluation.

## Browser and regression results

- Student/Teacher connected journeys: selected permitted sample, next class/no-class,
  Dashboard → Schedule → another date → details → matching room, refresh/context
  continuity. Five widths: 360, 390, 768, 1024, 1440. No horizontal overflow/runtime
  errors in checked flows. Date/view persistence and real 90-minute block geometry pass.
- Administrator: blocked readiness/category action; deliberate idempotent import;
  real solver **feasible, 2/2 offerings, 4 sessions, 0 hard conflicts**; independent
  validation; section/teacher/room/day filtering; save and reopen every exact
  assignment ID. New QA draft `082355c1-29d6-43e0-92ef-80a716b9112b` was deliberately
  appended. Separate real scenario returned **infeasible**, with no Save Draft action.
- Admin Home: valid current-draft review, blocked requirements, period refresh,
  maximum three issues, all five widths; Reports accurately unavailable.
- Production presentation: three independent role sessions, refresh and direct routes,
  nested backend-tool boundaries, details/rooms, five widths, loaded logo/favicon,
  no mutation controls and zero timetable/API requests. Live room availability
  explicitly unavailable. Local route emulation returns API 404 plain text, not HTML.
- Default production build: protected role routes and role chooser gated; logos/favicon
  loaded; no sandbox calls/runtime errors.
- Real Vercel: root/client routing/brand images pass; Student/Teacher API requests and
  direct-route entry fail as documented. No UX-06 public deployment was attempted.

Automated checks: `npm run lint` and `npm run typecheck` pass;
`npm run test:web`: **210 tests across 32 files pass**, including all existing route
coverage and 16 additional Firebase/sample/Admin/read-only route tests. No failing
test was removed. Production builds and final artifact browser results are checked
separately below.
Backend suite: **78 passed**, one upstream Starlette/httpx deprecation warning.
Ruff: pass. SQLite integrity: both `ok`; foreign-key checks empty. Academic records
remain **567**. All **11 original draft checksums** are unchanged and all **12**
current payload hashes verify. Publication heads/versions both remain **0**.
This phase does not claim a new public or local publication event.

## Before/after screenshots

These are actual browser captures, not mockups. Dates/rooms are synthetic source data.
Fixed navigation in full-page captures reflects the viewport at capture time.

| Surface | Before | After |
| --- | --- | --- |
| Student mobile | [Before](screenshots/ux06/before-student-390.png) | [After](screenshots/ux06/after-student-home-390.png) |
| Teacher mobile | [Before](screenshots/ux06/before-teacher-390.png) | [After](screenshots/ux06/after-teacher-home-390.png) |
| Admin mobile | [Before](screenshots/ux06/before-administrator-390.png) | [After](screenshots/ux06/after-administrator-390.png) |
| Admin desktop | [Before](screenshots/ux06/before-administrator-1440.png) | [After](screenshots/ux06/after-administrator-1440.png) |
| Reports | [Before](screenshots/ux06/before-reports.png) | [After](screenshots/ux06/after-reports.png) |

[Shared mobile class details](screenshots/ux06/after-student-details-390.png),
[desktop calendar](screenshots/ux06/after-calendar-1440.png),
[production presentation Student](screenshots/ux06/presentation-student-390.png),
[production presentation Admin](screenshots/ux06/presentation-administrator-1440.png).

Additional raw screenshots, executable QA scripts and JSON evidence are in
`C:/Users/lenovo/.codex/visualizations/2026/10/18/01a14e48-eb6b-7620-a8fa-0d5b6a108c65`,
using the `ux06-` prefix. Browser plugin was unavailable; installed Chrome/Playwright
was used. External diagnostics were read-only. No cloud secrets were logged.

## Remaining blockers and exact next phase

1. Owner approval to deploy the reviewed read-only artifact; inspect actual Vercel
   Root Directory/env/output settings, apply staged route config, verify deployed
   SHA and re-run public three-role/refresh/API-no-call checks. Current site remains
   broken for timetable reads until an approved change is deployed.
2. Authenticated Firebase/Vercel console verification: app display label, Firestore
   provisioning/location/rules/indexes and intended production web config. The denied
   probe is not a complete security audit.
3. Full backend deployment requires approved budget/region/IAM/CORS, durable data
   migration/rehearsal/rollback and verified institutional authorization. Until then
   no public generation/save/publish or live room availability is claimed.
4. Teacher requests remain fixed separate demonstrations; reports and unsupported
   governance/recommendation tools remain planned. No UX-04C editing, AI, OCR or
   unrelated feature development was started.

The immediate recommendation is **Option A deployment review**, not an automatic
cloud migration. Option B must be an independently approved infrastructure phase.

## Files modified

- `apps/web/.env.example`
- `apps/web/src/components/scheduling/ClassSessionDetails.tsx`
- `apps/web/src/components/scheduling/TeacherRequestOverview.tsx`
- `apps/web/src/data/presentation-timetable.v1.json`
- `apps/web/src/lib/firebase-config.test.ts`
- `apps/web/src/lib/firebase-config.ts`
- `apps/web/src/lib/firebase.ts`
- `apps/web/src/lib/presentation-sample.test.ts`
- `apps/web/src/lib/presentation-sample.ts`
- `apps/web/src/lib/session-room.ts`
- `apps/web/src/lib/use-schedule-workspace.ts`
- `apps/web/src/lib/workspace-context.ts`
- `apps/web/src/main.tsx`
- `apps/web/src/operational-ui.css`
- `apps/web/src/pages/AcademicGenerationPage.tsx`
- `apps/web/src/pages/AcademicManagementPage.tsx`
- `apps/web/src/pages/AdminSchedulingHome.test.tsx`
- `apps/web/src/pages/AdminSchedulingHome.tsx`
- `apps/web/src/pages/ConflictCenterPage.tsx`
- `apps/web/src/pages/DevelopmentRolePreviewPage.tsx`
- `apps/web/src/pages/PresentationReadOnlyRoutes.test.tsx`
- `apps/web/src/pages/PreviewOperationsViews.tsx`
- `apps/web/src/pages/ProductScreenPage.tsx`
- `apps/web/src/pages/PublishedRoomAvailability.tsx`
- `apps/web/src/pages/RoleScheduleWorkspace.tsx`
- `apps/web/src/pages/RoomDiscoveryPages.tsx`
- `apps/web/src/pages/SchedulingDraftPages.tsx`
- `apps/web/src/pages/TimetableValidation.tsx`
- `docs/development.md`
- `docs/infrastructure/firebase-readiness.md`
- `docs/infrastructure/vercel-backend-deployment-plan.md`
- `vercel.json`
- `docs/hci/screenshots/ux06/` — selected actual browser evidence

- `docs/hci/ux-06-dashboard-and-deployment-audit.md` — this report

## Final production bundle measurements

Both final `npm run build` and the explicitly flagged presentation build pass.
The connected build emits main JavaScript **518.64 kB / 154.09 kB gzip**, lazy role
workspace **14.62 / 4.73 kB**, shared SDK chunk **113.12 / 23.32 kB**, and CSS
**84.62 / 15.87 kB**. The recorded UX-05 main was 495.92 / 148.67 kB: main grows
22.72 kB raw / 5.42 kB gzip. This is bundle measurement, not a device frame-rate
or Lighthouse claim.

The presentation main is **523.91 / 155.58 kB**, role workspace **15.68 / 4.92 kB**,
and lazy versioned dataset **31.91 / 2.00 kB**. Its total emitted JavaScript is
approximately **3.68 kB gzip** above the connected variant. No animation/UI library
was added. Vite reports the main chunk above 500 kB; this non-failing warning is
retained as a future performance task rather than suppressed.
