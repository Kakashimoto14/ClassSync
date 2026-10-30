# P4a/P4b stability recovery — final local acceptance

**PASS — approved bounded local scope, 30 October 2026. Stop here; P4c/P4d not started.**

Base/current HEAD: `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`. Existing dirty work retained. Authoritative final connected evidence: `../production/local-20261029/p4-stability-browser-09-patched.json`, its log, and `p4-stability-final-service-timeline.json`. All records/identities are authorized generated fixtures, not institutional records. Production and manual screen-reader acceptance are not claimed.

## Confirmed failure and correction

The retained attempt06 PostgreSQL log records `remaining connection slots are reserved for roles with the SUPERUSER attribute` at **02:24:55.846 and02:24:57.606 +08**, before fast shutdown **02:25:29.659**. The browser's GET calendar503 and later GET periods503 occurred during navigation/refresh before cleanup. Auth checks and other reads succeeded around those failures. The disposable cluster's unchanged ten-connection configuration was competing with two setup-only pools and two service pools. This was an unintended qualification resource outage;503 was the correct fail-closed response, never an empty timetable.

Smallest correction: after seeding/publishing finishes in `scripts/postgres_student_experience_qualification.py`, dispose the **setup runtime and owner engines before the TCP service handoff**, and release the owner pool after fixture-control transactions. Observed setup idle connections **owner1/runtime1 →0/0**. Production service pools remain five connections/no overflow; cluster limits, timeouts, privileges, membership verification and RLS are unchanged. No scheduling/publication persistence implementation or schema changed.

Added test-only ASGI observations: timestamp, method, path/query, request ID, originating service, authorization-provider presence, Scheduling pool state and cleanup phase. Services stay alive until browser completion, except the explicitly tagged outage control. Vite targets the owned Gateway; Student reads use Gateway→Scheduling, with no Academic HTTP request in this journey. Final healthy reads have configured providers and successful current membership; no premature disposal/startup/proxy/token fault is observed.

**Forensic limit:** attempt06 did not retain per-request payloads/IDs/service HTTP events or query strings. Its individual503s cannot be retrospectively assigned uniquely to Gateway identity lookup versus Scheduling persistence. PostgreSQL admission exhaustion before shutdown is confirmed; exact origin and query data are recorded for the new instrumented runs. This distinction is retained rather than guessed.

Attempt07, with cleanup, recorded Gateway22×200 + intended wrong-role403, Scheduling15×200 and no healthy503/slot rejection, then failed in an old test-only held-route teardown (`Route is already handled`). Release + `page.unrouteAll({behavior:'wait'})` fixes that explained race without suppressing exceptions. Attempt08 passed the complete journey. A subsequent required security audit found the Vite advisory below; final attempt09 passed the complete journey on patched Vite6.4.5. Old failures remain in their logs; limits/assertions were not weakened and counters were not reset.

## Connected workflow acceptance

| Requested workflow | Final actual evidence |
|---|---|
| Login and correct Student role | Firebase SDK email/password sign-in; current PG membership; Teacher access denied, Student access verified |
| Session/navigation/refresh | Home→class details→actual room-detail link→room-detail refresh→back→rooms→back/forward→full timetable→refresh→Home; published rows/version loaded |
| Published timetable and information | Actual PostgreSQL publication served through real TCP services; course, times, room/building, instructor and version from that response |
| Logout and stale-session cleanup | Sign out, direct protected-route revisit remains signed out; no class DOM revived |
| Unauthorized/revoked/unassigned | Unbound signed-in account denied; audited PG revocation denies; restoration recovers; real unassignment gives honest empty/denied state with no classes |
| Genuine outage/recovery | Stop owned Scheduling endpoint, keep Gateway/identity alive: helpful unavailable state/no classes, restart owned Scheduling endpoint and retry successfully. Fixture updates Gateway's owned upstream port on restart; no production config changed |
| Presentation separation | Final presentation artifact Home and timetable at all five widths; zero API requests/runtime/console errors; keyboard/dialog/room/deep refresh pass |
| Healthy reliability | Final instrumented run: Gateway62×200, Scheduling49×200, expected authorization denials; **zero healthy-flow503s** |
| Intentional failures | Exactly three Gateway503s in `outage` phase: two GET periods and one GET calendar. Provider remains present and cleanup false; Scheduling was intentionally stopped. Browser-injected403 is separately labeled and does not substitute for real denials |
| Responsive/accessibility | Connected Home360/390/768/1024/1440, no overflow; final action sits above fixed mobile nav; Enter/dialog/Escape/focus restoration; native Chrome `tabs.setZoom(2)`/DPR2, no overflow. Desktop/mobile/native screenshots inspected. Presentation timetable also checked at all five widths |

Final09 records Vite6.4.5, empty runtime/console error lists, zero outbound emulator attempts, Auth stopped and PostgreSQL stopped. Browser plugin absent; installed Playwright/Chrome used. Headless safe-area insets are zero; existing CSS retains `env(safe-area-inset-bottom)`. No physical-notch or manual assistive-technology certification is implied.

## Student UX refinements

- Publication UUID moved from primary dashboard text into a collapsed disclosure.
- Period selector uses concise academic-year/semester labels; complete selected title wraps below it and is programmatically associated.
- Compact Next Class spacing; readable course/time/location/instructor hierarchy; weekly event names and instructors replace code-only emphasis. Empty days remain visible and quieter.
- Concise truthful updates/unavailable copy; Soft Rouge tokens, logo and existing components retained.
- Independent review found actual PG room IDs lacked a class-room action. Institutional Student details now link the authorized occurrence's room ID/date; room-detail route filters current authorized calendar records and provides an honest unknown-ID state. Requested date is validated and route-keyed scope resets prevent stale selection. Unit and actual browser action/deep-refresh checks pass.

## Final gates

| Gate | Result / retained evidence under `../production/local-20261029/` |
|---|---|
| Complete frontend after security patch | **731/43 files PASS**,132.36s, unchanged300s/two workers — `p4-stability-final-web.log` |
| Affected backend | **125 PASS**,2.87s; one existing Starlette/httpx warning — `p4-stability-backend.log` |
| Security regressions | **17 PASS**, includes actual denied synthetic .env query vectors — `p4-stability-final-security.log` |
| Lint/typecheck/Ruff/pip check | PASS — stability final/static logs |
| Institutional + presentation builds | PASS — `p4-stability-final-build.log`, `p4-stability-final-presentation-build.log` |
| Actual artifact/mode/SPA/API checks | **4 PASS** — `p4-stability-final-artifacts.log` |
| npm audit | **0 findings** — `p4-stability-npm-audit-final.json` |
| Python exact audit | **68 versions/0 findings**, pinned pip-audit2.10.1; internal source provenance verified — `p4-stability-python-audit/` and log |
| Connected + presentation browsers | PASS — attempt09 JSON/log/timeline; `p4-stability-presentation-browser.json`/log |

Required security repair: fresh audit found [GHSA-8g5g-mxqh-grgj](https://github.com/advisories/GHSA-8g5g-mxqh-grgj), Vite6.4.4 denied-file query bypass, patched6.4.5. Workspace-only install initially left the vulnerable root copy; root scripts invoke that CLI. Explicit root/workspace6.4.5 pin + override now deduplicates every Vite consumer. Lockfile comparison against the preserved pre-install dirty lock shows **only Vite6.4.4→6.4.5**, no added/removed package paths. No blind audit fix, exclusions, framework change or unrelated version update. Current installed-version and actual synthetic-file denial tests enforce the patch.

One focused independent milestone review was performed; its room-action finding was resolved and tested. No repeated reviewer loop. The earlier full-suite timeout remains historical; final serial runs pass without changed workers/timeouts/skips. Existing >500kB chunk/mixed Firebase-import warnings and dependency-hashing recommendation remain nonblocking observations, not hidden results.

## Preservation, evidence and stop

`p4-stability-preservation.json`: all three original SQLite SHA256s match; all61 P3b backend/package source hashes match. `p4-stability-owned-status.json`: all three recovery clusters pg_ctl3/no server running. Auth markers/final qualification confirm stopped/outbound0. No original DB migration/import, real identity/Firebase change, cloud resource, message, commit/push/deploy or destructive action.

Final connected screenshots have unique `p4-stability-classsync-auth-run-e387f44c1f6944989a9371f0dd7977b6-*.png` names in the authorized visualization directory. Earlier recovery scripts reused `p4-student-after-*` names; those paths now contain newer snapshots and must not be treated as immutable copies of the initial checkpoint. Original hash manifest remains historical. Attempt08 recovery copies and final09 unique files are separately identifiable; final source/evidence hashes are recorded in `p4-stability-exit-evidence.json`.

**P4a/P4b PASS for bounded local acceptance. Stop; no P4c/P4d implementation.** Remaining limits: generated local records, Chrome coverage, manual screen reader/physical notch/cross-browser/production acceptance unverified, historical individual503 attribution unavailable. Teacher compact teaching/request UX and Administrator readiness/review/publication UX remain the explicitly deferred backlog; institutional data/authority and production deployment remain separately gated.
