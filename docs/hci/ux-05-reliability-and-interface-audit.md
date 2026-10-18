# UX-05 — reliability and interface audit

## Scope and baseline

19 October 2026. All pre-existing uncommitted C1/C2 and UX-04 work was preserved.
This repair does not change OR-Tools constraints, historical drafts, publication
authorization, institutional identities or the branding assets. No deployment or
commit is part of this phase. Browser plugin was not available; actual browser
verification uses installed Chrome through Playwright.

## Confirmed reliability defect

The environments were different, not interchangeable frontends:

| Frontend | Gateway / storage | Observed baseline |
| --- | --- | --- |
| `127.0.0.1:5173` | Gateway 8000, Academic 8001, Scheduling 8002; `var/*.sqlite3` | Zero publication heads, eight saved drafts across scopes; entered academic drafts were not permitted synthetic reviews |
| `127.0.0.1:5190` | Gateway 8830 / Academic 8831 / Scheduling 8832; isolated prior QA databases | Published synthetic BSIT 3A version 3 and generated synthetic drafts |
| `localhost:5174` | No active server at baseline | Connection refused |
| `localhost:5173` | Resolved to IPv6 `::1` in this environment | HTTP 404; IPv4 `127.0.0.1:5173` returned 200. The supported Vite binding is IPv4 loopback |

The exact reproduced failure was:

`GET http://127.0.0.1:5173/api/v1/scheduling/sandbox/calendar/7ba93163-b228-4548-b288-c19a012bb724?start=2026-10-01&end=2026-11-30&role=student&section=&teacher=`

HTTP **403**:

```json
{"error":{"code":"scheduling_rejected","message":"Only explicitly synthetic saved schedules have anonymous calendar review","requestId":"6c34a05b-811d-4a95-bde9-64a962983108"}}
```

The old review chooser used the general entered-academic draft list, then selected
the first/current saved draft. The calendar endpoint correctly rejected its source.
Separate origins also had separate role/context session storage. No frontend
`VITE_API_BASE_URL` override file was present; the Vite proxy defaults to Gateway
8000, whereas the earlier 5190 launcher explicitly targeted 8830. Process command
lines and active port bindings were inspected; normal service restarts retained data.

### Exact repair

- Canonical origin: **http://127.0.0.1:5173/**, started with `npm run dev`.
  Vite itself now sets host, port and `strictPort`, including standalone invocations.
  Port conflict fails rather than silently selecting 5174. The launcher checks the
  new discovery API at Gateway and Scheduling and prints API/database configuration.
- New **GET-only**, development-gated `scheduling/sandbox/calendar-samples` discovery
  lists only owned academic-sandbox snapshots meeting the same synthetic/room-source
  predicate as calendar review. It returns summaries, not private input snapshots.
  Pagination is applied after eligibility; the client reads all permitted pages.
- The original 403 guard is retained. There is no new institutional read or mutation
  permission. A stale/entered draft is not requested and is not silently replaced;
  the user can choose another permitted sample.
- Review selection and selected view/date remain within the normal origin-specific,
  expiring P0 role session. Generated review remains visibly unpublished. A published
  scope is never silently replaced with generated sample classes.
- Errors show “Couldn't load your timetable.” with Retry and Change sample. Permission,
  missing-sample and service failures retain their distinct causes; technical detail
  is secondary. Unpublished, unselected and no-class states remain separate.

An explicit Administrator UI import created the default synthetic BSIT 3A scenario
in the canonical database, then the real engine generated and saved its timetable.
No fixture import occurs during startup. Existing eight draft checksums were recorded
before this deliberate setup for final integrity comparison.

## Screen and component inventory

| Surface | Implemented change |
| --- | --- |
| Student / Teacher Home | Date and compact context; subject → prominent time → room/building → supporting facts; no-class message above the real upcoming class; no duplicate remaining entry |
| My Schedule / Teaching schedule / Calendar | Same workspace hook/source; remembered Day/Week/Month choice; seven-day strip, immediate agenda, Today and month expansion retained; readable clipped block summaries preserve real geometry |
| Class details | Shared `ClassSessionDetails`; grouped schedule/classroom/academic facts, compact source badge, lower-priority resource note, valid-room link only |
| Modal primitive | Reused focus trap, inert background, Escape, restoration; scoped class permits a padded mobile sheet with capped scroll area and persistent actions |
| Room details | Home goes directly to a valid registered detail route; class sheet uses the same destination resolver |
| Administrator readiness | Accurate sections/offerings/assigned-teacher counts; classroom **candidates**, not an assurance of suitability; grouped blockers and category actions, original diagnostics behind disclosure |
| Blocked generation | Explicit blocker count plus Resolve Requirements; validation still disables generation |
| Academic Setup / sample import | Review before deliberate import; customization secondary; confirmation routes directly to real period readiness/generation |
| Alerts / Requests | Separate legacy demonstrations labelled explicitly so they cannot be mistaken for selected-timetable events or current faculty requests |
| Drafts / Conflict Center | Existing immutable save/reopen and independent validation retained and exercised |

Readiness adds a backwards-compatible `assigned_faculty` projection to its response;
it counts distinct active faculty referenced by active offerings. Older responses
without it use solver teachers when available, or explicitly label the catalog count.
The solver itself and resource suitability rules are unchanged.

## ITHUMCI evidence and heuristic matrix

The actual local 70-page handbook was found at
`C:/Users/lenovo/Downloads/ITAPPSD/WEEK 6/ITHUMCI_Detailed_Student_Book_Complete.pdf`.
Relevant module overview/discussion pages were read: Module 2 p.6, Module 3 p.9,
Module 6 p.18, Module 7 p.21, Module 11 p.31, Module 12 p.34. Existing HCI reports
provided project context. The following are implementation/engineering observations,
not human-participant study results.

| Observed problem → HCI explanation | Implemented change | Verification |
| --- | --- | --- |
| Port/data differences appeared random → Module 3 mental models, feedback; Nielsen visibility/recovery | Canonical URL, strict port, printed API/DB paths; filtered source discovery | Same draft/section loaded at 5173 and explicitly configured 5174 after refresh and navigation |
| Correct permission rejection became a dead-end → Module 3 constraints and recovery | Keep guard; exclude entered drafts from chooser; explicit Change sample and technical disclosure | Backend source/owner filtering and production-gate regression; stale-draft frontend test |
| Next-class facts competed with technical selectors → Module 2 attention/recognition, Module 11 hierarchy; Nielsen minimalism | Compact outlined context control, prominent subject/time/location and concise remaining agenda | Rendered mobile/desktop Home; next class appears once |
| Dialog paragraphs touched edges → Module 7 grouping, Module 11 spacing/type | Distinct time/classroom/facts groups, padded body, source badge and quiet resource note | Mobile sheet screenshots; same component in both roles |
| Small/stranded modal actions → Module 2 motor interaction, Module 12 operability; Nielsen user control | Reachable outlined footer actions, explicit Close, focus containment/restoration, inert background | Escape/Close/Tab/Shift+Tab and short-viewport checks |
| Room count implied verified suitability → Module 3 signifiers/constraints; Nielsen real-world match | Classroom candidates label and actual per-offering blockers; no resource metadata invented | Real readiness data; resource assumptions remain explicit |
| Repeated blocker prose required recall → Module 6 task analysis, Module 7 navigation | Grouped category actions with period retained; original affected records discoverable | Blocked-period Resolve Requirements and category navigation checks |
| Import required technical configuration up front → Module 6 task reduction; Nielsen error prevention | Simple default sample, optional customization, review then explicit import | Test confirms no request on review and no false success on rejection; real import/generate path |
| Rouge text looked like errors everywhere → Module 11 color and affordances | Neutral outlined ordinary actions; brand primary and warning status with text/count | Rendered control hierarchy and contrast checks |
| Source-conflicting old requests/alerts → Module 3 consistency; Nielsen visibility | Label separate demonstration record source | Related role-route inspection; no fabricated live delivery |

Reference interaction guidance: [Google Calendar date/view navigation](https://support.google.com/calendar/answer/6110849),
[WAI-ARIA modal dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/),
[Nielsen's usability heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/).

## Evidence, release checks and limits

QA artifacts use the `ux05-` prefix in
`C:/Users/lenovo/.codex/visualizations/2026/10/18/01a14e48-eb6b-7620-a8fa-0d5b6a108c65`.
Before images capture the real failing entered draft, original class dialog,
Student 5190 Home and blocked Administrator period. The 5190 Home and canonical
Home use different data sources; that comparison demonstrates hierarchy, not equal
room assignments. Dialog/readiness before/after comparisons concern the shared UI.

The reliability report records matching permitted draft IDs across 5173/5174;
restart report records an actual Gateway/service outage, visible error and Retry
recovery with the same selected draft, without a manual refresh for recovery.
No fake API success was injected.

### Navigation, API and accessibility results

- Student and Teacher: selected permitted BSIT 3A/faculty, Home, refresh, Schedule,
  another date, details, Escape/Close, focus restoration and matching room route pass.
  View selection persists across Home/Schedule. Checked at 360×800, 390×844, 768,
  1024 and 1440px with no horizontal overflow or runtime errors.
- Administrator: real blocked period reports three blockers; Resolve Requirements
  focuses the issue list; teaching-window review retains the selected period.
  Explicit review/import reuses the sample without overwriting edits. Real run:
  feasible, 2/2 offerings, 4 sessions, 0 hard conflicts. Four filters work, independent
  validator confirms the snapshot, and reopening preserves every assignment ID.
  A separate insufficient-time scenario returns authoritative **infeasible**, with
  no Save Draft action. No solver constraint was relaxed.
- Teacher pending demonstration request opens its exact detail. Student Alerts and
  Requests explicitly disclose their separate fixed record source.
- Modal: named dialog, initial Close focus, Tab/Shift+Tab containment, Escape,
  visible footer Close, restored trigger focus and inert background pass. Content
  scrolls while footer remains reachable at 390×400. A 720×450 CSS viewport tests
  the reflow equivalent of 1440×900 at 200%; native browser toolbar zoom was not
  automated and is not claimed. Desktop and mobile screenshots were inspected.
- Reduced motion enabled in browser checks. Core controls use at least 44px touch
  height. Week-strip date cells are compact, separated targets; not all are 44px wide.
  Checked contrast: ink/surface 15.55:1, secondary/surface 4.97:1, rouge/white 8.34:1,
  warning/soft-warning 4.65:1. These spot checks do not certify every state or WCAG.
- Both working SQLite databases pass integrity/foreign-key checks. All eight
  pre-existing draft checksums match their recorded baseline; new QA drafts are
  separate immutable rows. No database was deleted, replaced or reset.
- Occupied default-port startup exits with “Port 5173 is already in use”; it does
  not silently create 5174. The temporary explicit 5174 diagnostic frontend was
  stopped after verification; canonical 5173 remains available.

Regression history is retained: the first concurrent backend run had two solver
time-budget failures (`unknown`) and the first concurrent frontend run had one
async DOM timeout. The two backend cases passed quietly, then the full backend
suite passed **78 tests** without changing solver constraints/time limits. A later
focused frontend check caught a test that read rows synchronously after selecting
a date; it now awaits the announced loading state instead of depending on stale
agenda content. Final frontend release results are appended below.

### Before/after screenshot comparisons

| State | Before | After |
| --- | --- | --- |
| Class details, 390px | [Original cramped dialog](C:/Users/lenovo/.codex/visualizations/2026/10/18/01a14e48-eb6b-7620-a8fa-0d5b6a108c65/ux05-before-details-390.png) | [Shared grouped sheet](C:/Users/lenovo/.codex/visualizations/2026/10/18/01a14e48-eb6b-7620-a8fa-0d5b6a108c65/ux05-after-student-details-390.png) |
| Administrator blockers, 390px | [Original issue list](C:/Users/lenovo/.codex/visualizations/2026/10/18/01a14e48-eb6b-7620-a8fa-0d5b6a108c65/ux05-before-admin-390.png) | [Grouped issues and actions](C:/Users/lenovo/.codex/visualizations/2026/10/18/01a14e48-eb6b-7620-a8fa-0d5b6a108c65/ux05-after-admin-blocked-390.png) |
| Error recovery, 390px | [Permission dead-end](C:/Users/lenovo/.codex/visualizations/2026/10/18/01a14e48-eb6b-7620-a8fa-0d5b6a108c65/ux05-before-error-390.png) | [Concise service error and Retry](C:/Users/lenovo/.codex/visualizations/2026/10/18/01a14e48-eb6b-7620-a8fa-0d5b6a108c65/ux05-after-error-390.png) |
| Student hierarchy, different disclosed sources | [Prior QA Home](C:/Users/lenovo/.codex/visualizations/2026/10/18/01a14e48-eb6b-7620-a8fa-0d5b6a108c65/ux05-before-student-5190.png) | [Canonical sample Home](C:/Users/lenovo/.codex/visualizations/2026/10/18/01a14e48-eb6b-7620-a8fa-0d5b6a108c65/ux05-after-student-home-390.png) |

Other evidence: `ux05-after-admin-ready-390.png`, Administrator review at 390/1440,
Teacher Home at 390/1440 and details at 390, `ux05-after-calendar-1440.png`,
`ux05-details-390x400.png`, `ux05-details-720x450.png`, `ux05-infeasible-390.png`,
and JSON reports `ux05-baseline`, `ux05-reliability-gate`, `ux05-restart`,
`ux05-admin`, `ux05-accessibility`. Error-comparison screenshots deliberately show
different failure causes; the original 403 guard still returns 403.

### Files touched in this phase

- Startup/configuration: `apps/web/vite.config.ts`, `scripts/dev.py`, `docs/development.md`.
- Read-only discovery and counts: Scheduling `main.py`, `draft_repository.py`,
  `academic_input.py`; Gateway `main.py`; academic DTO and generated schema/types.
- Context/API: `use-schedule-workspace.ts`, `workspace-context.ts`,
  `sample-calendar-api.ts`, `session-room.ts`.
- Shared UI: `DialogSurface.tsx`, `ClassSessionDetails.tsx`, `RequestSummary.tsx`,
  `class-session.css`, `ux-workflows.css`, `main.tsx`.
- Screens: `RoleScheduleWorkspace.tsx`, `AcademicGenerationPage.tsx`,
  `AcademicFixtureImport.tsx`, `AcademicManagementPage.tsx`,
  `PreviewOperationsViews.tsx`, `ConflictCenterPage.tsx`.
- Focused tests: structured role workspace, sample calendar client, fixture import,
  academic management, Scheduling draft discovery/authorization and calendar counts.

Repository HEAD advanced during this work to `baf4025`, containing existing workspace
changes and some earlier repair edits. This agent issued no commit, reset, amend,
push or deployment command and preserved that external change.

Limits: university sign-in/shared hosting remains unconfigured; legacy request and
alert demonstrations are not new realtime features. A synthetic resource does not
verify a CdM room. No general timetable editor, publication feature or AI capability
was added. Browser emulation is not physical-phone testing or WCAG certification.

## Final release gate

| Check | Result |
| --- | --- |
| `npm run lint` | Pass, zero warnings |
| `npm run typecheck` | Pass |
| `npm run test:web` | Pass: 28 files, 194 tests, final run 155.46s |
| Python tests | Pass: 78 tests, 64.00s; one upstream Starlette/httpx deprecation warning |
| Ruff / `git diff --check` | Pass |
| `npm run build` | Pass; no dependency added |
| Production preview | Page title/identity, nonblank sign-in/entrance, no framework overlay; protected routes gated; logo/favicon assets loaded; zero sandbox calls or runtime/console errors |
| Canonical services | Gateway 8000, Academic 8001, Scheduling 8002 all healthy; Vite 5173 reachable |
| Data integrity | Both SQLite integrity/foreign-key checks pass; all 8 original draft checksums unchanged; 3 separate QA draft rows added deliberately |

Final Vite output: main JS **495.92 kB / 148.67 kB gzip**, lazy role workspace
**13.11 / 4.27 kB**, CSS **81.92 / 15.39 kB**. Compared with the recorded UX-04
build, total emitted JavaScript grows approximately 2.89 kB (0.83 kB gzip) and CSS
4.35 kB (0.78 kB gzip). These are bundle-size measurements, not device frame-rate
or Lighthouse measurements. No animation package or modal library was introduced.

Evidence JSON files include `ux05-production.json` and `ux05-integrity.json`; final
frontend/backend logs retain both initial failures and subsequent passing release
runs. No test failure was suppressed or solver assertion weakened. The supported
presentation uses the explicit synthetic review until an authorized publication
exists. No public Vercel deployment or new publishing operation was performed.
