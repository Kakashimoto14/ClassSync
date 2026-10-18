# UX-04A/B: role workflows

## Scope and record integrity

This phase changes access, context and presentation. It reuses academic readiness,
OR-Tools generation, independent validation, immutable draft persistence and C2
published projections/SSE. It introduces no assignment-editing endpoint, automatic
fixture import, publication bypass, fake login or LLM operation. All pre-existing
uncommitted C1/C2 work was retained. Browser QA uses the existing isolated C1/C2
sample databases; working `var/` records were not replaced.

## Action trace

| User action | Route / actual API |
| --- | --- |
| Student/Teacher Home → Schedule | Shared role workspace → `/student/schedule` or `/teacher/schedule` |
| Choose period/identity | Existing `/timetables/sandbox/periods` and `/calendar/{period}`; production projection uses verified identity instead |
| Receive schedule change | Existing server-originated `/timetables/{sandbox/}events/{period}` → authoritative refetch |
| Tap class / Room Details | Accessible class dialog → registered room detail route; synthetic rooms resolved from the selected timetable |
| Room occupancy | Existing published `/timetables/{sandbox/}availability`, with remembered selected date; occupancy spans active scopes, not only the personal timetable |
| AI-Powered Scheduling | `/admin/ai-scheduling` → academic periods/readiness → `/scheduling/sandbox/academic/{period}/generate` |
| Save Draft / reopen | Existing server-held run → `/scheduling/sandbox/academic/drafts` → exact immutable detail |
| Conflict Center | Load exact draft → independent `/scheduling/sandbox/validate`; no outcome invented |
| Academic fixes | Issue-specific Faculty, Offerings, Sections, Resources or Constraints route with period retained |
| Teacher requests | Existing separately labelled request demonstration and exact detail links; not published faculty requests |

Old Generate Schedule and AI Conflict Detection URLs remain supported aliases. Main
navigation exposes one automated scheduling destination and one Conflict Center.
Academic Setup and Campus group labels replace development-phase labels. Student
bottom navigation remains Home, Schedule, Rooms, Alerts; Teacher prioritizes Requests.
Persistent period IDs/titles are unchanged. Semester-backed display labels use academic
year/semester; known legacy/sample titles receive a display-only Sample label.

## HCI evidence

| User problem | Principle | Change | Observed result |
| --- | --- | --- | --- |
| Empty Home until several selectors are configured | Recognition over recall | Prefer an existing published sample period and BSIT 3A/eligible faculty; remember choice per role and preview session | Fresh Student and Teacher contexts showed the correct next assignment without setup |
| Source settings compete with the actual day | Progressive disclosure | Compact truthful sample label and secondary Change context control | Next Class, location and action fit in the first phone viewport |
| Context disappears between pages | Consistency and user control | Versioned session context shared by Home, Schedule, Calendar and scheduled Rooms; explicit URLs override initial context | Identity, period and selected date survived navigation and refresh |
| Class inspection requires another page | Recognition and minimal navigation | Date selection updates agenda; Day/Week/Month, mobile week strip and class dialog | Correct class/room inspected; Escape closed dialog and restored trigger focus |
| Solver hidden behind Coming Soon | Match with real-world tasks | AI-Powered Scheduling leads to the real constraint solver; LLM recommendations remain planned | Administrator generated a complete validated batch from the main destination |
| Readiness problems require searching | Recovery and error prevention | Short blocking list with period-specific fix links; all warnings behind disclosure | Missing-input tests kept Generate disabled and exposed the correct Faculty fix |
| Unclear solver success or save status | Visibility of system status | Server-confirmed solver status, coverage, minutes, sessions and conflicts; duplicate-run guard and real Save Draft | Browser generation/save/reopen preserved all assignment IDs exactly |
| Disconnected conflict destination | Visibility and actionable feedback | Independent snapshot validation, blocking violation details and affected-assignment links | Real validator confirmed zero conflicts; focused test checked a violation without inventing resolution |
| Missing services look like an empty timetable | Visibility and recovery | Specific service errors, retry and last-confirmed data; no fallback classes | Failure/recovery browser check distinguishes service error from no-class/unpublished states |
| Starting three services is error prone | Error prevention | `npm run dev` checks service health and sandbox routes before reporting Ready | Real launcher started Gateway, Academic, Scheduling and Vite successfully |

These are engineering observations and automated/browser checks. No participant or
usability-study results are claimed. Reduced motion, keyboard focus, narrow layouts,
overflow, loading, empty and service-error states are part of targeted QA, not a full
WCAG conformance certification.

## Evidence and limits

Before/after screenshots and executable QA scripts are outside source in the task
visualization directory under the `ux04-` prefix. `ux04-browser-results.json` records
three independent role journeys and 360/390/768/1024/1440px checks. The sample Student
uses BSIT 3A; Teacher uses an eligible synthetic instructor. Administrator readiness,
generation, filters, validation, save and immutable reopen use real local services.
There is no mocked success response in those journeys and no publication action.

### Final verification — 19 October 2026

- `npm run lint`, `npm run typecheck`, `npm run test:web` and `npm run build` pass.
  Frontend: 26 files, 190 tests. Python regression suite: 77 tests pass, with one
  upstream Starlette/httpx deprecation warning. Ruff and `git diff --check` pass.
- Three independent Chromium role sessions exercise real local APIs. The final
  Administrator run was feasible: two required offerings, four sessions, zero hard
  conflicts. Saving and reopening preserved every assignment ID. This is a controlled
  sample, not a school-wide solver benchmark.
- Student BSIT 3A and an eligible sample Teacher share published scope data across
  Home, Schedule and Rooms. Date selection survives navigation and refresh. Class
  dialogs support Escape and restore focus. Existing request detail links work but
  remain separate demonstrations, as described below.
- No horizontal overflow at 360, 390, 768, 1024 and 1440px. Reduced-motion journeys,
  a 390×700 viewport, unpublished state, injected network failure and successful
  retry were checked. Mobile generation setup has the primary action above bottom
  navigation at 360/390×844. Scope counts reflect the two solver teachers, not all
  132 faculty records in the sample catalog.
- Final production preview gates preview-role and protected workspace routes at
  sign-in, loads logo assets and both favicon sizes, makes no sandbox API calls and
  reports no browser runtime/console errors. No Vercel deployment was triggered.
- One-command startup was tested on fresh ports with three healthy services and
  reachable frontend; `stop` exited cleanly without leaving owned ports running.
  Existing user services and working SQLite data were retained.
- Vite output: main JavaScript 495.62 kB / 148.51 kB gzip; lazy role workspace
  10.52 / 3.60 kB; CSS 77.57 / 14.61 kB. Against the recorded C1/C2 output, total
  emitted JavaScript increases by 9.08 kB (3.97 kB gzip), while the main chunk is
  1.44 kB smaller. CSS increases by 4.90 kB (0.85 kB gzip). No dependency added.
  These are build-size measurements, not a device performance or Lighthouse score.

Evidence files: `ux04-before-{student,teacher,administrator}-{390,1440}.png`,
`ux04-after-{student,teacher}-home-{390,1440}.png`, mobile class/schedule captures,
`ux04-after-admin-setup-{360,390}.png`, `ux04-after-admin-review-{390,1440}.png`,
`ux04-service-error-390.png`, `ux04-unpublished-390.png`, and the browser, generated,
states, startup and production JSON reports. They are stored in
`C:/Users/lenovo/.codex/visualizations/2026/10/18/01a14e48-eb6b-7620-a8fa-0d5b6a108c65`.
Browser verification used desktop Chrome emulation, not physical phones or a full
assistive-technology audit. C2 publication/reconnect regressions are covered by the
existing backend/frontend tests; this phase did not republish the sample timetable.

## Exact follow-on work

**UX-04C editing:** persisted assignment revision/working-copy APIs and their validation,
concurrency, revision comparison and recovery UX are missing. Saved drafts stay immutable.
No fake Edit Timetable or Review Changes button is introduced. C2 occurrence exceptions
are not a general timetable editor.

**UX-04D publication:** existing local version/audit/SSE infrastructure and its protected
panel are retained. Production identity/enrollment provisioning, shared persistence,
reachable authenticated API/stream hosting and cross-service academic revision
coordination remain prerequisites. Public Vercel publishing is not enabled here.

**Requests:** the current request list/detail is an explicitly separate demonstration.
There is no persistent faculty-request submission/decision workflow tied to the selected
synthetic faculty identity. It must be integrated before showing these as that faculty
member's live pending requests. It is not silently inferred from legacy fixtures.
