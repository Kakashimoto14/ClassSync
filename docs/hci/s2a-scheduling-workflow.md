# S2A — Persistent scheduling draft workflow

Implemented and locally verified on 2026-10-18. This is scripted functional and
visual verification, not a participant usability study. No physical-device or
screen-reader testing or full WCAG compliance is claimed.

## Administrator goal and before-state

An Administrator needs to generate a complete weekly timetable, verify its coverage
and conflicts, retain that exact candidate, and return later to review it. S1
generated and independently validated real schedules, but its result existed only
in page memory. Refreshing or leaving the page lost the candidate and required a
new solver run, which could produce a different feasible allocation. Preview role
continuity worked; timetable persistence did not exist.

The presentation context includes a narrow mobile viewport, desktop weekly review,
and restarting local Python services. Official curricula and operational resource
metadata are still absent, so this evidence uses the explicitly synthetic scenario.

## Notice → Explain → Improve → Validate

| Notice / problem | HCI explanation | Implemented improvement | Verification |
| --- | --- | --- | --- |
| Generated work disappeared on refresh | User control and recovery: users need durable work and a reliable return path | Explicit backend Save as Draft, saved-list route, stable detail URL, immutable SQLite snapshot | Same complete record returned after page refresh and both Python services restarted |
| A Save click could be mistaken for completed persistence | Visibility of system status | Saving state, disabled Save, server-confirmed “Draft saved”, identity and Open saved draft | Delayed real request showed loading; aborted request showed error without success; retry saved once |
| Arbitrary client validation flags could imply a valid schedule | Error prevention and trustworthy feedback | Save only references an owned server run; independent validation and complete coverage checks run again before the transaction | Forged fields rejected with 422; incomplete/infeasible/unknown/incorrect-minute runs rejected by backend tests |
| Repeated Save or regeneration might duplicate/overwrite work | Predictability and user control | Idempotent Save plus immutable run/draft IDs; new generation is a separate candidate | Concurrent retries produce one ID; changed availability produced a second ID with the first snapshot unchanged |
| Users would need to remember solver metadata to recover a result | Recognition over recall and information hierarchy | Human-readable title, period/date, compact coverage/session summary, Open Draft action | Browser selected the actual returned draft ID from the persistent list and reopened it |
| Saved drafts could look like official published schedules | Consistency and accurate mental model | Draft · Unpublished, Synthetic preview and explicit schedule-distribution boundary | No publication operation; Student/Teacher data stays unchanged; protected API rejects preview-role claims |
| Detail route initially had no active mobile navigation item | Information architecture and orientation | Explicit navigation ownership: Saved Drafts on desktop, Schedule on mobile, Back to Saved Drafts | Route regression test and actual mobile active-state assertion passed |

## New flow and interface decisions

From Schedule Manager: Generate Weekly Schedule → Load scheduling inputs → Generate
Weekly Schedule → automatic independent validation → Save as Draft → View Saved
Drafts → Open Draft. This requires six link/button activations from Schedule Manager
with the prefilled title; editing the title is optional. From an already validated
result, Save then Open saved draft takes two activations; using the list takes three.
These are scripted interface step counts, not measured human task-completion times.

Save is available only for a successful validated result. It sends run identity,
expected input hash, title and an idempotency key; no client assignment or validation
claim is accepted. Success is shown only after the database transaction commits.
A failed connection retains the retry action and points to Saved Drafts in case the
server committed before confirmation was lost.

Saved Drafts uses compact rows with title, period, created date, offerings, session
count, minutes, validation and Draft status. The detail view reuses S1's day/section
grouping and five filters (program, section, teacher, room, day) so generated and
saved timetables behave consistently. Dates/IDs/provenance stay secondary to title,
coverage and timetable. New routes retain typed role ownership. The approved Soft
Rouge palette, Inter typography, Student bottom navigation and P0 storage are retained.

Saved input snapshots retain structured stable program/section/resource references.
The nine-program catalog and 59-space provisional CdM inventory are unchanged by
draft saving. Synthetic room facilities, faculty and offerings do not become official
academic records merely because a draft was saved.

## Actual functional verification

The final browser run used installed Chrome through the already available bundled
Playwright. The Browser plugin was unavailable; no additional browser driver was
downloaded. Vite at `http://127.0.0.1:5182` forwarded real requests through Gateway
8000 to Scheduling 8002, CP-SAT and the actual local SQLite database.

| Scenario | Observed outcome |
| --- | --- |
| Generate complete synthetic example at 390px | Feasible, 17 sessions, 12/12 offerings, 2,160/2,160 minutes, zero hard conflicts; solver/runtime metadata retained |
| Save with a deliberately interrupted network request, then retry | Error shown without false success; real retry returned 201 and a draft ID |
| List, open and refresh | Stored assignments and complete draft metadata exactly matched the saved response; no regeneration request |
| Restart Scheduling and Gateway, then reopen | Same draft, input, result and every assignment returned unchanged; no solver call |
| Filter saved sessions | Program, section, teacher, room and day filters matched expected persisted assignment IDs/counts |
| Change instructor availability and regenerate at 1440px | Different valid allocation and input hash; saved as a separate draft; original snapshot unchanged |
| Impossible scenario | Proven infeasible, no sessions and no Save action; direct Save of that unsuccessful run returned 404 |
| Forged validation/assignment fields | Save request rejected with 422 |
| Protected drafts / sandbox publication | Unauthenticated protected list returned 401; sandbox publication returned 404 |
| List connection failure and missing draft | Understandable error, retry/back controls; no substitute timetable shown |
| Student/Teacher direct access to Administrator draft | Forbidden page retained the chosen role and did not fetch saved draft data |
| P0/P1 smoke | Student refresh retained role and Home · Schedule · Rooms · Alerts navigation |

The final evidence contains 18 page/role/URL identity checks, three real solver runs,
and complete saved/restored snapshots. The first generation took 15.350s, the changed
availability run 15.324s, and the impossible input 0.023s. Both successful results
were **feasible**, with no claim that the objective optimum was proven.

Actual final draft IDs in the local evidence:

- Original: `678609c6-7cec-4b90-ae86-e56d3405a03d`.
- Changed availability: `ee1adc45-bfae-49a3-b437-2f72c7dfff4a`.

Repeated QA runs deliberately leave distinct local synthetic drafts; titles can
repeat, while UUIDs identify records and prevent overwriting. No database file is
committed. Tests use separate temporary databases.

## Accessibility and visual checks

Screens were inspected at 390×1000 and 1440×1000 with reduced-motion preference.
The browser checked actual URLs, meaningful headings, role state, no Vite overlay,
no horizontal overflow, and relevant console health. Keyboard Enter opened Saved
Drafts, result/saved headings received programmatic focus, and Save/loading/error
feedback uses status/alert semantics. Saved details keep the correct navigation
active. Labels and text accompany status colors. Missing-draft 404 resource logs
are expected for that explicit negative test; no unexplained console errors remained.

The rendered mobile saved confirmation, list, saved detail, desktop detail and
weekly timetable were visually inspected. This verifies the requested viewports in
desktop Chrome emulation, not physical-device touch behavior or assistive technology.

## Screenshot and raw-evidence locations

Directory:
`C:/Users/lenovo/.codex/visualizations/2026/10/17/01a14b83-8f79-7a40-82da-d3d7b664de7f/`

- `s2a-saving-390.png`, `s2a-saving-1440.png`: pending real Save.
- `s2a-saved-confirmation-390.png`, `s2a-saved-confirmation-1440.png`: confirmed persistence.
- `s2a-draft-list-390.png`, `s2a-draft-list-1440.png`: actual stored drafts.
- `s2a-draft-detail-390.png`, `s2a-draft-detail-1440.png`: saved/unpublished review.
- `s2a-after-backend-restart-390.png`: unchanged saved record after service restart.
- `s2a-saved-filters-390.png`, `s2a-saved-timetable-1440.png`: filtering and weekly layout.
- `s2a-save-error-390.png`, `s2a-list-error-1440.png`, `s2a-missing-draft-1440.png`: recovery states.
- `s2a-infeasible-no-save-1440.png`: infeasible output cannot be saved as valid.

`s2a-qa.cjs` is the executed final script; `s2a-browser-results.json` contains its
actual inputs, results, checks and exact saved/restored records. The restart-ready
and restart-done files record the orchestration handshake with real process restarts.
Expected network failures were injected; successful solver/save responses were not mocked.

## Automated checks

The Python suite covers repository save/retrieve/list, a separate Python-process
reopen, concurrent saves, idempotency conflicts, complete assignment snapshots,
new drafts without overwrites, invalid/forged server metadata, exact minutes,
expiry, schema/corruption errors, transactional rollback and safe retry, migrations,
real Gateway/service roundtrips, authorization and scope isolation. S1 constraint
and independent-validator tests remain part of the same suite.

Frontend tests cover generation → save, pending/failed save and same-key retry,
list → detail navigation, direct detail remount/reload, filtering, empty/error
recovery, unpublished state, infeasible output and Student/Teacher role boundaries.
Navigation ownership has a focused regression test, and the P0/P1 suite remains.
Final command outcomes:

| Check | Actual result |
| --- | --- |
| `npm run lint` | Passed |
| `npm run typecheck` | Passed |
| `npm run test:web` | 168 passed across 21 files (122.15s final run) |
| `npm run build` | Passed; 1,699 modules transformed |
| `.venv/Scripts/python -m pytest -q` | 51 passed (24.28s final run) |
| `ruff check services packages scripts` | Passed |
| Explicit migration/integrity checks | Schema 1; no foreign-key issues; database ignored by Git |
| Real Chrome workflow | Passed at 390px and 1440px, including both-service restart |

The root Python suite passed **51 tests** after running without concurrent frontend
build/test load. A deliberately oversubscribed verification attempt exhausted two
short eight-second solver fixtures and honestly returned unknown; no draft was
accepted from those results. Run wall-time-sensitive solver tests without competing
builds on the presentation laptop. Ruff and explicit schema-v1 migration/integrity
checks passed, with zero foreign-key issues; the database path is confirmed ignored
by Git. One upstream TestClient/httpx deprecation warning remains.

## Remaining limitations and S2B recommendation

SQLite is appropriate to this single-host local workflow, not distributed production
storage. No large institutional workload benchmark, live university identity test,
physical-device test or screen-reader audit was performed. Official curricula,
faculty/resource availability, verified facilities/capacities and complete enrollment
inputs are still required for institutional coverage.

There is no editing, revision history, publication/activation, distribution,
notification, audit UI or retention-management workflow. Unsaved server runs expire
for saving after 24 hours; storage cleanup is an operational follow-up. A generated
candidate still disappears from the page on refresh unless explicitly saved. Saved
drafts remain accessible through their list and stable URL.

S2B should define authorized immutable revisions and audit/optimistic-concurrency
rules before adding draft editing, and profile a PostgreSQL-backed deployment path.
Publication remains a separate later scope. See [technical persistence details](../scheduling/s2a-drafts.md).
