# S1 real weekly generation and validation

This records the S1 baseline. [S2A](s2a-drafts.md) subsequently adds explicit persistent
draft saves; the original generation response still describes an unsaved candidate.

Implemented and verified locally on 2026-10-18. S1 produces a complete validated
**generated preview** for the supplied academic-period batch. It does not save,
publish, notify, or replace existing dashboard demonstration records.

## Run locally

Use Python 3.12+ and Node 20+. From the repository root, create a virtual
environment if needed:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e packages/api-contracts
Push-Location services/scheduling
..\..\.venv\Scripts\python.exe -m pip install -r requirements.txt
Pop-Location
Push-Location services/gateway
..\..\.venv\Scripts\python.exe -m pip install -r requirements.txt
Pop-Location
npm install
```

Start each Python process in a separate PowerShell terminal from the repository
root. These flags are intentionally opt-in and must be present on **both**:

```powershell
$env:CLASSSYNC_ENV='development'
$env:ENABLE_SCHEDULING_SANDBOX='true'
.\.venv\Scripts\python.exe -m uvicorn services.scheduling.app.main:app --host 127.0.0.1 --port 8002
```

```powershell
$env:CLASSSYNC_ENV='development'
$env:ENABLE_SCHEDULING_SANDBOX='true'
.\.venv\Scripts\python.exe -m uvicorn services.gateway.app.main:app --host 127.0.0.1 --port 8000
```

```powershell
npm run dev --workspace=@classync/web -- --host 127.0.0.1 --port 5182 --strictPort
```

Open `http://127.0.0.1:5182/dev/role-preview`, explicitly choose Administrator,
then Schedule Manager → Generate Weekly Schedule. Load the complete example,
review its counts, and generate. The alternate scenario is deliberately impossible.
The JSON input editor accepts the full batch and calls backend readiness validation
before generation. Change availability, eligibility, operating windows, session
patterns, or objective weights there to generate new allocations. Dirty edits
clear stale output and disable generation until applied. No official accounts or
faculty records are implied by the example.

Vite forwards `/api` to Gateway port 8000. The client defaults to `/api/v1`, avoiding
cross-port session contexts and permissive CORS changes. A custom API base can be
configured with `VITE_API_BASE_URL`. In a normal production build, the sandbox UI
is unavailable. Production administrative sign-in integration remains outside S1.

## Implementation map

| Layer | Files and responsibility |
| --- | --- |
| Domain/contracts | `packages/api-contracts/classync_contracts/scheduling.py`: strict v1 DTOs, time and pattern invariants, provenance, run/validation results |
| Catalogs | `classync_contracts/catalogs/*.json`, `services/scheduling/app/catalog.py`: owner-supplied catalog/inventory and separate synthetic input |
| Readiness | `services/scheduling/app/readiness.py`: unique IDs, complete references, naming policies, explicit eligibility and required verified metadata |
| Hard constraints | `constraint_model.py`: pattern choices, shared instructor choice, unary-legal placement tables, optional intervals and NoOverlap, locks |
| Preferences | `objectives.py`: weighted gaps, daily loads, preferred days, building mixing and prior placement preservation |
| Execution | `engine.py`: hash/run identity, bounded CP-SAT execution, accurate status mapping, validated result mapping |
| Independent validation | `validation.py`: ordinary Python candidate checks, no CP-SAT state or solver dependency |
| Security/API | Scheduling `main.py`, Gateway `main.py`, shared `scheduling_security.py`: independent authorization, opt-in sandbox, safe proxy errors |
| Browser contracts | `scripts/export_scheduling_contracts.py` derives `packages/shared-types/src/scheduling.ts` and `packages/api-contracts/schemas/scheduling-v1.json` from Python models |
| Frontend | `WeeklySchedulingPage.tsx`, `scheduling-api.ts`, `scheduling-labels.ts`, `weekly-scheduling.css`; integrated at existing Create Schedule route in `ProductScreenPage.tsx` |

The canonical CdM JSON also feeds the existing room directory adapter. It retains
all stable resource IDs and excludes unverified resources from solver eligibility.
P0 storage/route guards and P1 dashboards/navigation were not rewritten.

## Working API

All paths below begin `/api/v1/scheduling`. Gateway wraps successful service
responses in `{ "data": ... }`; the Scheduling service returns the typed object.

| Method/path | Behavior |
| --- | --- |
| `GET /sandbox/scenario?infeasible=false` | Complete synthetic input; use `true` for the impossible variant |
| `GET /sandbox/catalogs` | Nine-program catalog and 59 provisional CdM spaces |
| `POST /sandbox/readiness` | Validate and normalize a `GenerationInput`; return diagnostics |
| `POST /sandbox/generate` | Run the actual CP-SAT solver on the supplied full batch |
| `POST /sandbox/validate` | Independently validate `{inputs, assignments}` |
| `POST /readiness`, `/generate`, `/validate` | Equivalent protected operations, requiring a verified Firebase Administrator token at both services |

Sandbox requests require development environment **and** the enabled sandbox flag;
input must be explicitly synthetic with synthetic resources. A frontend role or
`ALLOW_UNAUTHENTICATED_DEVELOPMENT` does not authorize protected scheduling. Token
verification checks revocation and an administrator custom claim. Publication is
not an operation: `/sandbox/publish` returns 404. See [security](../security.md).

## Solver behavior and constraints

OR-Tools **9.15.6755 CP-SAT** generates all supplied offerings together. Each offering
selects exactly one permitted pattern, one explicitly eligible instructor, and a
legal day/start/room for every session. Weekly minutes are exact by construction
and rechecked independently. Two 90-minute sessions require distinct days.

Hard constraints enforce room, teacher, section and explicitly enrolled student
exclusivity; half-open intervals and configured buffers; valid complete references;
allowed days/hours; teacher availability/exclusions; room availability/blocks and
known operational status; verified type/equipment/capacity where required;
program/building restrictions; and exact locked placements. Buffer checking also
handles the recurring week boundary. Candidate validation identifies affected
assignment IDs and checks patterns, minutes, instructor consistency, locks and all
resource conflicts without reading solver variables.

Search first obtains a complete hard-feasible incumbent, then adds weighted soft
objectives and hints for the remaining budget. Default weights and assumptions are
[documented separately](rules-and-assumptions.md). Building optimization is a
same-day mixed-building pair proxy, not walking-distance routing. Gap penalties
measure daily span minus instruction; section and room balancing penalize squared
daily loads. These proxies can compete and are configurable.

Statuses are `optimal`, `feasible`, `infeasible`, `invalid_input`, `invalid_model`,
`unknown`, or `validation_failed`. Only CP-SAT's proved objective optimum is labelled
optimal. A satisfaction incumbent retained after optimization timeout is feasible,
with an explicit diagnostic and null objective/bound if no scored incumbent was
obtained. Unknown is never presented as proven infeasibility. No partial successful
batch is returned. Independent validation failure hides assignments and prevents
success. Unsolved inputs have null conflict count, rather than an asserted zero.

Run metadata includes UUID, normalized input SHA-256, period/data version, seed,
solver version, budget/runtime, objective/bound when available, complete per-offering
minute coverage, and `persisted=false`. A fixed seed and one search worker support
repeatable runs; the same complete input produced identical allocations in the two
recorded browser runs, and a proven small case has an explicit reproducibility test.
Wall-time-limited optimization can still stop at different incumbents on different
hardware/load; no cross-platform bit-for-bit optimum guarantee is claimed.

S1 permits at most 1,000 offerings, 500 teachers/sections, 200 rooms and 500,000 legal
placement tuples, with a search budget up to 30 seconds and one generation at a time
per process. Limits reject the whole input with diagnostics, never silently drop
offerings. Model construction, transport and validation add time beyond the solver
budget. This discrete model has not been benchmarked against a complete official
university dataset. Large instances need profiling and potentially a queued worker
deployment. Student-overlap validation currently uses pairwise candidate checks.

## Actual verification

Executed locally, rather than inferred from mocked frontend responses:

- `npm run lint`, `npm run typecheck`, `npm run build`: passed.
- `npm run test:web`: 158 tests passed across 20 files, including P0/P1 and four
  new scheduling UI tests for actual submission state, failures and input editing.
- Root Python suite: 35 tests passed. Covers both 180-minute patterns, duration
  rejection, each resource exclusivity independently, student enrollment,
  availability, maintenance, verified capacity/equipment/type, restrictions, locks,
  half-open/buffer/week-wrap behavior, timeout/unknown, invalid model, repeatability,
  multi-program generation, validation failure, readiness, Gateway/service roundtrip,
  production rejection, verified claim handling and publication absence.
- `ruff check services packages`: passed. Existing import/line formatting issues
  were corrected; service health-test imports and CI service working directories
  were fixed so root checks collect the separate applications correctly.
- The Python suite emits one upstream TestClient/httpx deprecation warning.
  Authorized token handling is tested with mocked verified Firebase claims; a live
  university Firebase identity/deployment has not been configured or exercised.

Browser automation used installed Chrome with the existing bundled Playwright;
no new browser driver was downloaded. It exercised the running Vite → Gateway →
Scheduling → CP-SAT services at 390×1000 and 1440×1000.

| Actual run | Result | Coverage | Runtime |
| --- | --- | --- | --- |
| Complete synthetic input, 390px | Feasible, 16 sessions, 0 hard conflicts | 12/12 offerings, 2,160/2,160 minutes | 15.811s |
| Teacher availability changed and reapplied, 390px | Feasible; old blocked interval avoided, new input hash | 12/12 offerings, 0 hard conflicts | 10.434s |
| Complete synthetic input, 1440px | Feasible, 16 sessions, 0 hard conflicts | 12/12 offerings, 2,160/2,160 minutes | 15.431s |
| Impossible input, 390px / 1440px | Proven infeasible, no assignments | Section needs 540 minutes; week supplies only 180 | 0.038s / 0.043s |

The browser verified real request payloads and responses, disabled progress state,
all five filters, section grouping, a second independent validation request,
incomplete-input diagnostics, and a deliberately injected network failure's recovery
message. A duplicate-overlap candidate produced validator diagnostics with affected
IDs. Protected generation returned 401 and sandbox publication 404. URLs, rendered
pages, active role, no horizontal overflow, keyboard navigation and relevant console
errors were checked. Student Home → Schedule → Rooms, refresh continuity, forbidden
Administrator access and return to Student Home retained the selected Student role.
No participant study or full accessibility conformance claim is made.

## Screenshots and raw evidence

Evidence directory:
`C:/Users/lenovo/.codex/visualizations/2026/10/17/01a14b83-8f79-7a40-82da-d3d7b664de7f/`

For each width 390 and 1440: `s1-input-readiness-{width}.png`,
`s1-generation-{width}.png`, `s1-success-summary-{width}.png`,
`s1-weekly-timetable-{width}.png`, `s1-section-filter-{width}.png`, and
`s1-infeasible-{width}.png`. Also `s1-incomplete-inputs-1440.png` and
`s1-network-error-1440.png`. Readiness, mobile results, desktop timetable and
infeasible screenshots were visually inspected. Full-page captures can include
fixed shell/navigation at their capture scroll position.

A final real-solver browser pass verified result focus clearance beneath the sticky
header at both widths. Prefer `s1-result-focus-{width}.png` and
`s1-infeasible-result-{width}.png` for the result status screenshots;
`s1-focus-qa.cjs` records that follow-up check.

`s1-browser-results.json` contains actual inputs/results, runtime metadata,
interaction/security checks and validator conflict evidence. `s1-qa.cjs` is the
executed browser script. These are local QA artifacts, not production datasets.

## Remaining work beyond S1

Official input collection/verification remains a prerequisite for institutional
coverage. Generated previews live in page memory; refreshing retains the preview
role but discards an unsaved generated timetable. No draft database, editing,
publication, audit history, notifications, live Firebase sign-in UI, registrar data
import, or distributed job queue is included. The existing Conflict Center retains
its labelled demonstration records; real validator findings appear in the generation
workflow and are not attributed to the old seeded conflicts.

S2 should address durable authorized drafts and versioning, approved editing and
audit rules, scale benchmarks, and production identity integration before any
publication workflow. S1 does not automatically start those features.

Solver references: [official CP-SAT status semantics](https://developers.google.com/optimization/cp/cp_solver)
and [official search limits](https://developers.google.com/optimization/cp/cp_tasks).
