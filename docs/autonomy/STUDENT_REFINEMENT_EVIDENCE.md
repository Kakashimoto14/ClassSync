# Student experience refinement — local acceptance evidence

**PASS — approved Student refinement, 30 October 2026.** Base/current HEAD: `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`; existing dirty work retained, no commit. P4c/P4d not started. Machine evidence: `../production/local-20261029/student-refinement-exit-evidence.json`.

## Baseline and decisions

Actual current artifact was opened before changes. Main defects: technical metadata and term controls displaced Next Class; sparse samples hid multiple-class behavior; weekly Home cards repeated full events; mobile calendar content was cramped; preview and connected Alerts did not share a trustworthy source. Prior P4 stability PASS superseded the historical persistent-failure checkpoint. The owner's new task explicitly authorized this bounded refinement; no retry allowance was silently reused.

One concise source review informed implementation:
- [Digital.gov](https://digital.gov/guides/plain-language/design): put useful information first; use descriptive headings and selective emphasis. Applied to Next Class/today/week hierarchy and reduced filler.
- [Apple tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars): stable destinations and descriptive labels. Applied to Home, Schedule, Rooms, Alerts, including an honest unavailable Alerts state.
- [Material navigation](https://m2.material.io/design/navigation/): top-level destinations share a consistent navigation hierarchy. Secondary supported features remain separately accessible.
- [WCAG reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) and [focus visibility](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/): readable responsive content and unobscured focus. Mobile uses an agenda; real native200 and keyboard clearance were tested. This is not WCAG certification.

## Implemented

Student Home now has a read-only source-backed term, compact Next Class/ongoing card with room action, complete chronological today agenda, selected-class emphasis, and a compact linked week/day/count strip. Primary publication UUIDs, timezone identifier, repeated sample badges and the Home term selector are removed. Stable IDs remain internal; readable fields use a small presentation mapper with truthful missing-name fallbacks. Manila time ranges are consistent, including details.

Student Schedule reuses the existing workspace hook, buttons, details dialog and tokens. It provides previous/next week, Today, selected dates/deep links, full day agenda, duration-positioned desktop grid and retained Day/Week/Month selection. Historical term selection and saved synthetic samples live in Schedule options. No decorative export action was introduced. Date URLs restore correctly after refresh/back/forward; pending month data cannot appear as an empty success; midnight endings use elapsed duration.

Navigation has four consistent primary Student destinations. Search is explicitly page navigation; schedule rooms have their own useful name/building search. Existing provisional/demo room-directory filters and details are preserved, with a separate link to schedule rooms. Schedule-room links carry explicit context instead of guessing from an ID prefix. Alerts uses current timetable change flags; old illustrative announcements remain separate. Availability, equipment and physical occupancy are never inferred from schedule gaps.

## Isolated data

`python -m scripts.student_presentation_fixture` exports the bundled synthetic JSON using existing domain input models, independent timetable validation, occurrence expansion and dated constraint validation. Three subjects / nine weekly sessions: Mon2, Tue1, Wed2, Thu1, Fri3; empty weekends; 60/90/120-minute sessions; adjacent Friday classes and an afternoon class. Names/room labels are illustrative references from the owner's mockups, not official curriculum, people or facilities. Internal synthetic resource assumptions are not exported as institutional certifications. No database is opened by this exporter.

A separate `fixture(room_change=True)` validates a Friday LAB-201 → LAB-202 scenario without changing the default bundle. Controlled-clock assertions cover ongoing, exactly-ended/adjacent, later today, tomorrow, empty weekend and no upcoming classes. Home/calendar share the same source. Connected qualification names are saved in its disposable academic fixture before publication, rather than hardcoded into UI ID mappings. No original SQLite or production/shared PostgreSQL/Firebase data was seeded.

## Final verification

All logs below are in `../production/local-20261029/`.

| Verification | Actual result / evidence |
|---|---|
| Complete frontend | **739/45 files PASS**, 167.06s: `student-refinement-web-final.log` |
| Additional change UI assertion | **10 Home tests PASS**, including one case added after full regression; no product code changed: `student-refinement-change-ui.log` |
| Backend authorization/publication + initial fixture | **126 PASS**, one existing Starlette/httpx warning: `student-refinement-backend.log` |
| Calendar / richer fixture / separate room change | **6 PASS** (one initial fixture case repeated): `student-refinement-calendar.log` |
| Lint / types / security / ordinary + presentation builds / artifacts | All exit0; **17 security, 4 artifact checks**: `student-refinement-final-gates.json` and associated logs |
| Dependency audits | npm0 findings; pinned pip-audit2.10.1, 68 exact versions,0 findings; dependencies unchanged in this task |
| Ruff / whitespace | PASS: `student-refinement-ruff-final.log`, `student-refinement-whitespace-final.log` |
| Final production presentation browser | Home AND Schedule at360/390/768/1024/1440; details/focus restore, dates/week/Today/views, refresh/back, room search/details, Alerts, Teacher/Admin route smoke; no overflow, API requests or console/runtime errors: `student-refinement-after-browser.json`, `student-refinement-presentation-exit.log` |
| Final connected browser | Real owned Auth/current PG/TCP Gateway+Scheduling; all five widths, published version/data, login/role/session/navigation/refresh/logout, class/room actions, denied/revoked/unassigned, held loading, offline/reconnect and actual stopped Scheduling/recovery: `student-refinement-connected-exit.json`, `student-refinement-exit-student-browser-result.json` |
| Native200 | Actual `chrome.tabs.setZoom(2)`, DPR2, Home and Schedule screenshots; additional keyboard test confirms room action and last daily class fully above fixed bottom nav: `student-refinement-native-focus.json` |
| Data preservation | All3 original SQLite +61 P3b backend/package SHA-256 values match: `student-refinement-preservation-final.json` |

Final connected client responses: **73×200, 7×403 expected access negatives, 3×503 intentional outage; zero healthy503**. Server timeline attributes those outage GET `/api/v1/timetables/periods`503s to Gateway while Scheduling was deliberately stopped; configured providers remained present, before cleanup. Recovery passed. Earlier genuine503 root cause remains the documented setup-only idle pool handoff exhausting the guarded ten-connection cluster; releasing setup owner/runtime engines before service handoff remains intact. No service pool/privilege/RLS/timeout relaxation. Both final owned Auth and PG report stopped; denied outbound requests0. Pure static presentation preview remains available locally.

## Independent review and resolved failures

One independent focused review found four P2 cases: ID-prefix room routing, inaccessible fresh saved-sample mode, false empty state during new-month loading, and midnight geometry. All corrected; targeted edge/navigation11 tests and the final full suite passed. No second general reviewer loop.

Retained intermediate failures are not represented as passes: the initial full run14 failures exposed loss of legacy room workflows and stale content assertions; a JSX insertion error was corrected; subsequent date-URL assertions and same-selected-sample reset behavior were corrected/tested. Presentation browser caught date history after reload and passed after canonicalization. A supplemental native-focus harness initially left Chrome's extension-disable default enabled; matching the existing qualification's owned-profile extension setup resolved it, without product changes. No test limits/assertions/skips were weakened.

## Visual evidence and limits

Fresh Home before captures and final Home/Schedule after captures cover all five widths. Indexes: `student-refinement-before-browser.json` / `student-refinement-after-browser.json`. Controlled presentation clock: `2026-10-30T08:15:00+08:00`. Before/after data intentionally differs because fixture enrichment is part of this task; no pure same-data style comparison is claimed. The supplied images are illustrative composites, not exact browser viewports.

Reference/implementation comparison sheets (opened and inspected):
- [Home](C:/Users/lenovo/.codex/visualizations/2026/10/29/01a188af-fa90-7501-9d68-4318e4ff47fb/student-refinement-home-comparison-1793310552200.png)
- [Schedule](C:/Users/lenovo/.codex/visualizations/2026/10/29/01a188af-fa90-7501-9d68-4318e4ff47fb/student-refinement-schedule-comparison-1793310552200.png)

IAB captured the baseline, then reported `browser.user is unavailable`; owned Chrome/Playwright performed rendered acceptance and native zoom. Native screenshots, mobile/desktop screenshots and comparisons were inspected. Manual screen-reader, physical-device usability and production/institutional acceptance remain unverified. Push delivery and verified physical room availability remain unavailable and are not simulated. Teacher/Admin received regression smoke coverage, not a new authenticated redesign acceptance.

Stop here. Remaining P4c Teacher backlog: compact teaching agenda, real request/status workflow and role-specific rendered acceptance. P4d Admin backlog: period/readiness/blocker hierarchy and generate → validate → review/approve → publish task usability. Both require their separate approved milestones; no cloud/prod/original-data authority is implied.
