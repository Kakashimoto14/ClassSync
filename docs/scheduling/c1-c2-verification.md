# C1/C2 local verification record

Evidence directory:
`C:/Users/lenovo/.codex/visualizations/2026/10/18/01a14e48-eb6b-7620-a8fa-0d5b6a108c65`.

## Gates and data

C1 was verified before C2 work: real fixture import, readiness, OR-Tools generation,
validation, immutable draft save and Student/Teacher generated-occurrence browsing.
The initial backend regression gate passed 68 tests; affected frontend suites passed.
The sample offers two explicitly synthetic subjects to BSIT 3A, producing four weekly
sessions. All nine CdM program identities, 132 synthetic subject/faculty records and
59 provisional inventory entries are covered by provenance tests. Synthetic solver
rooms are separate from that inventory. See the curriculum register for source gaps.

C2 exercised three independent Chrome contexts against real local HTTP services and
separate SQLite files. The test-only verifier ran outside the repository on loopback;
it represents controlled claims for integration testing, not live Firebase identity.
Normal application authorization still requires verified Firebase credentials. No
test token, auth bypass or QA database is included in shipped application code.

`c2-cross-client.json` records Administrator UI publication, initial delivery to the
mock BSIT 3A Student and eligible Teacher, a reviewed room revision, both updated
calendars, unchanged page time origins, retained superseded history and HTTP 401 for
unauthorized publication. `c2-recovery.json` records another committed revision while
the Student was offline: Teacher Next Class updated after 463 ms including publish,
refetch and render; Student Next Class recovered after 133 ms online. These are local
observations, not network latency guarantees. No manual page reload occurred.

Backend tests cover immutable snapshots/history, checksums, source revisions,
semester/date validation, exception conflicts, irregular enrollment, tenant and role
projection isolation, duplicate/idempotent requests, competing publication writers,
rollback, operational restrictions/reservations, revision conflicts, unknown occupancy
coverage and production sandbox gating. Frontend stream tests cover ordered cursors,
duplicate/stale event suppression and online-resume refetch.

## Browser and accessibility

Screenshots include:

- `c1-admin-calendar.png`, `c1-student-calendar-{390,1440}.png`,
  `c1-teacher-calendar-{390,1440}.png` (C1 gate).
- `c2-admin-published-1440.png` (publication confirmation/audit).
- `c2-student-initial-390.png`, `c2-student-revised-390.png`,
  `c2-teacher-initial-1440.png`, `c2-teacher-revised-1440.png` (live revisions).
- `c2-final-{student,teacher}-dashboard-{390,1440}.png`,
  `c2-final-{student,teacher}-calendar-390.png`,
  `c2-final-{student,teacher}-week-1440.png` (final composition).

390px/1440px screens were rendered in Chrome. Additional 360, 768 and 1024px checks
reported no horizontal overflow. Calendar controls use native buttons/selects,
visible focus treatment, explicit labels and pressed states. Dates and agenda changes
are usable without animation; final visual checks use reduced motion and keyboard
Tab navigation. This is targeted accessibility QA, not a complete WCAG conformance audit.
Existing brand, entrance motion and preview-session persistence tests remain intact.

## Commands and deployment

The final complete backend regression suite passed 77 tests. Ruff, lint, typecheck,
the final 185-test frontend suite and production build passed. Earlier concurrent runs hit native solver time limits
and one component timeout; quiet reruns passed without altering engine constraints or
validation assertions. The remaining backend warning is upstream Starlette/httpx
TestClient deprecation.

Final production output: 497.06 kB JavaScript (148.14 kB gzip), 72.67 kB CSS
(13.76 kB gzip), measured by Vite. No dependency was added; no baseline bundle delta
or institution-wide performance claim is inferred from these output sizes.

Final browser checks also saved semester phases through the running Academic editor/API,
confirmed the source revision increment and unchanged records, rendered production logos,
and verified production role-preview redirects to sign-in without sandbox API requests.
The temporary deterministic verifier processes were then stopped and replaced by normal
services on ports 8801 (Academic), 8812 (Scheduling) and 8810 (Gateway), using only the
isolated QA databases. The local preview at `http://127.0.0.1:5186/` can inspect the retained
synthetic publications; it cannot publish without a real verified Administrator token.

Read-only verification of `https://class-sync-bhiv.vercel.app/` returned HTTP 200;
`/api/v1/timetables/periods` returned HTTP 404. Public C2 publishing/streaming is therefore
not available. No commit, push or deployment was performed. Required infrastructure
and the separate-service academic revision coordination limit are documented in
`publication-and-realtime.md`. The local implementation is not a claim of institutional
authentication readiness, school-wide solver readiness or public real-time capability.
