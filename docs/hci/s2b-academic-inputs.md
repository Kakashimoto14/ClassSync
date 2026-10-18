# S2B — Academic input workflow evidence

## Goal and before-state

Administrators need to enter their own academic period, subjects, sections, faculty,
resource facts and constraints, inspect missing inputs, and generate/save a real
timetable. S1/S2A could generate and persist validated solver results, but the normal
entrance offered only a fixed synthetic test input. Existing academic-management
screens showed representative records instead of persisted scheduling inputs.

S2B replaces the relevant Administrator entry screens with period-scoped CRUD while
preserving Student/Teacher data, source classification, P0 sessions, S2A immutability
and the Soft Rouge visual system. The original synthetic generator remains separately
selectable. This is scripted functional/visual QA, not a human-participant study.

## Notice → Explain → Improve → Validate

| Observed need | HCI principle | Improvement | Evidence |
| --- | --- | --- | --- |
| Users could not supply their own timetable inputs | Task analysis and user control | Persisted records and a period → readiness → generate → save flow | Entire example entered through real forms and real APIs |
| Many related data types risk a giant form | Meaningful grouping and progressive disclosure | Focused Programs/Subjects/Sections/Faculty/Offerings/Resources/Constraints views; advanced fields disclosed separately | Mobile entry completed at 390px; desktop record edit completed at 1440px |
| Remembering IDs invites mismatched references | Recognition over recall and error prevention | Labelled selectors, searchable checkbox groups, structured section fields; server-side foreign keys | Correct BSIT-3A/3B ownership, eligibility and period references verified |
| Missing data could be mistaken for a feasible schedule | Visibility of system status | Required errors versus warnings; Generate disabled when blocked; solver still establishes feasibility | Empty period blocked; complete entered batch passed independent validation |
| Resources might look usable simply because listed | Accurate mental model | Provisional flags, explicit operational eligibility, verified metadata and source notes | All 59 supplied CdM records remained unverified; QA resources entered separately |
| A save or source edit might silently replace a draft | Consistency and recovery | Server-confirmed save states, revisions, immutable input snapshots, source-aware draft routes | Earlier draft unchanged after subject edit, refresh and all-service restart |
| Navigating categories could lose period context | Orientation and consistency | Period carried in every category URL; familiar labels and active state | Tab route/period identity checks and reload verification |

## Actual entered test scenario

The final scenario was entered by browser automation through the same visible forms
an Administrator uses. No backend test fixture or synthetic scenario was submitted
in place of those entries.

- Period: `S2B entered period — verified workflow`.
- ID: `a769a019-82ae-456b-a29b-937700631ee3`.
- The owner-supplied catalog supplied nine programs and 59 provisional spaces;
  one additional explicitly labelled QA program was created to verify configurability.
  Catalog availability did not imply that all programs had sections or curricula.
- Two user-entered QA subjects, associated explicitly with BSIT, each requiring
  180 weekly contact minutes: one single-180 pattern and one distinct-day 90+90 pattern.
- Two sections: BSIT-3A and BSIT-3B, structured year/letter fields and explicitly
  entered verified test population of 20 each.
- Two explicitly entered faculty records, eligible for both subjects, with Monday,
  Wednesday and Friday 08:00–14:00 availability, 540-minute weekly and 180-minute
  daily workload limits.
- Two separate QA resources with explicitly entered 25-person capacity, operational
  assertions and provenance notes stating these were development QA assertions,
  **not official CdM metadata**. No capacity/facility facts were added to the 59 spaces.
- Four offerings: both subjects for each section; eligible faculty/resources chosen
  explicitly. Operating hours were entered as Monday/Wednesday/Friday 08:00–14:00.

This proves the user-entry pipeline, not the authenticity of university curricula,
faculty or room data. Actual institutional records still need approved sources.

## Observed outcome

The real Gateway → Academic service → Scheduling service → OR-Tools path returned
**optimal**, six sessions, 4/4 offerings, 720/720 instructional minutes, and zero hard
conflicts. Runtime was 0.791 seconds; objective and best bound both 216 for this small
instance. No general large-campus optimality or runtime guarantee is inferred.

The result was saved through S2A as draft
`99b13949-daa6-4bde-869b-9a06b4e80067`, classified `development-entered`, unpublished.
Refreshing and restarting Academic, Scheduling and Gateway preserved the period's
records and exact saved assignments without calling the solver again. A later
subject-name edit updated current records but left the saved input snapshot and
assignments unchanged. An empty second period contained none of the first period's
subjects/sections/faculty/offerings and could not generate.

Both Student and Teacher direct links to Academic Data were forbidden while their
preview roles remained selected. Protected mutation without a verified token returned
401. Original synthetic draft endpoints could not load the entered draft (404).
The original 12-offering synthetic test scenario remained separately selectable.

The full browser pass reported ten route/heading/role/viewport identity checks,
15 confirmed record writes, real generation and save, and no unexplained console
errors. The writes include a later source edit; source records remained durable.
All six pre-S2B draft payload checksums were unchanged by migration and passed the
independent validator.

## Browser and accessibility scope

Used the existing installed Chrome and bundled Playwright at 390×1000 and 1440×1000,
with reduced motion. The Browser plugin was unavailable; no driver download occurred.
The running frontend was `http://127.0.0.1:5182`, Gateway 8000, Academic 8001 and
Scheduling 8002. Page identity, role retention, rendered headings, no framework
overlay, no horizontal overflow, real network payloads/responses, persisted-record
equality, filters, source isolation, empty states and restart behavior were checked.

Screens inspected include missing/ready input summaries, entered subject lists,
generated/save feedback, and mobile/desktop saved timetable views. Controls have
labels, native keyboard operation, focus feedback, status/alert text and explicit
Save/Cancel actions. Errors never produce a success message. Advanced constraints
remain visible on demand. No physical-device, screen-reader, participant usability
or full WCAG compliance claim is made.

## Evidence files

Directory:
`C:/Users/lenovo/.codex/visualizations/2026/10/17/01a14b83-8f79-7a40-82da-d3d7b664de7f/`

- `s2b-missing-readiness-390.png`, `s2b-ready-390.png`.
- `s2b-subjects-390.png`, `s2b-generated-390.png`, `s2b-saved-390.png`.
- `s2b-reopened-390.png`, `s2b-reopened-1440.png`, `s2b-weekly-timetable-1440.png`.
- `s2b-saved-filters-1440.png`, `s2b-after-restart-1440.png`, `s2b-empty-period-1440.png`.
- `s2b-qa.cjs`: executed browser workflow.
- `s2b-browser-results.json`: actual submitted records, source snapshot, generated
  result, saved draft and browser checks.
- `s2b-baseline-drafts.json`: pre-migration draft IDs/checksums for preservation checks.
- `s2b-faculty-form-390.png`, `s2b-faculty-form-1440.png`, `s2b-resource-form-390.png`.
- `s2b-invalid-resource-390.png`: real 422 rejection and visible recovery action.
- `s2b-final-reopened-390.png`, `s2b-final-reopened-1440.png`: unchanged draft after
  another service restart and final migrations.
- `s2b-followup.cjs`, `s2b-followup-results.json`: final error recovery, Cancel,
  keyboard Tab, role continuity and saved-assignment checks.
- `s2b-migration-check.py`, `s2b-migration-results.json`: both actual database schemas,
  integrity/foreign-key results and six preserved pre-S2B draft checksums.

Automated tests cover CRUD, naming/ownership, patterns, faculty eligibility/workload,
resource provenance/equipment, readiness errors, period isolation, persistence in a
new process, stale/concurrent writes, corrupt records, database references, protected
ownership and real Gateway/solver/draft integration. Existing S1/S2A/P0/P1 tests remain.

## Final verification — 18 October 2026

| Check | Actual result |
| --- | --- |
| `npm run lint` | Passed, no warnings |
| `npm run typecheck` | Passed |
| `npm run test:web` | 176 tests passed across 22 files |
| `npm run build` | Passed, 1,704 transformed modules |
| `.venv/Scripts/python.exe -m pytest -q` | 65 tests passed; one upstream Starlette/httpx TestClient deprecation warning |
| `.venv/Scripts/python.exe -m ruff check services packages scripts` | Passed |
| Migration tests | Fresh schema, version-1 upgrade, repeated migration, future-schema refusal, immutable snapshot preservation and database references passed |
| Actual local databases | Academic and Scheduling both version 2; quick checks OK, zero foreign-key errors; six earlier draft checksums unchanged and independently valid |
| Chrome 390px / 1440px | Complete entry → readiness → generation → save → reopen → refresh → service restart; filters, period/source/role isolation and no horizontal overflow passed |
| Final real error recovery | Verified-capacity flag without supporting data rejected with 422; no success displayed; Reload retrieved identical saved records |
| Cancel / keyboard | Cancel made no record change; Tab moved between labelled faculty inputs; browser produced no uncaught page errors |

The final browser pass ran against the restarted current services after both schema
upgrades. It confirmed current period revision 85 was ready and the earlier draft
still retained its original validated assignments. Browser scripts use real service
requests and the installed Chrome; no successful responses or solver results were
mocked. Automated unit/API tests use isolated temporary databases and authenticated
test claims; live university identity-provider configuration remains unverified.

## Remaining work

Approved calendar/contact-hour rules, official curricula/offerings, verified faculty
assignments/availability, resource capacities/facilities/operational restrictions and
complete enrollments are still needed for institutional coverage. Readiness cannot
verify the truth of an Administrator's assertions or prove that all university
offerings have been supplied.

SQLite, period-local source records, owner-scoped access and current-record provenance
are local foundations. S2C revision/audit history, organization-wide sharing,
production identity/deployment validation and scale profiling remain deferred.
Publication, activation, notifications, AI/OCR and timetable editing were not added.
