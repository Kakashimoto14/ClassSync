# P4a/P4b evidence — current acceptance and historical checkpoint

**Current: PASS for approved bounded local scope, 30 October 2026.** See [final stability evidence](P4_STABILITY_EVIDENCE.md), latest STATUS and `../production/local-20261029/p4-stability-exit-evidence.json`. Stop; P4c/P4d not started. Production/manual screen-reader acceptance is not claimed.

## Initial P4 checkpoint — PARTIAL (historical)

The initial implementation and one approved retry ended PARTIAL. Base/current HEAD was `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`. Prior dirty work was retained; no commits/deployments/cloud/real records/original database writes. This historical result is superseded by the later stability exit, not erased.

Implemented then: configured Firebase sign-in and verified Student continuation; guarded Student route; bounded same-origin authenticated read-only periods/calendar client; Soft Rouge Next Class/today/week/version/updates/room discovery; truthful unavailable/denied/empty/sample/unknown states; hidden planned navigation. Other institutional clients remained closed; server role/tenant/record authorization was unchanged. A month-boundary query issue was corrected to current Monday through +62 days, respecting the63-inclusive-day backend limit.

Initial actual positives: owned demo Auth/current disposable PostgreSQL/TCP Gateway+Scheduling login, periods200/calendar200, published Home/version/class information, all360/390/768/1024/1440 screenshots/no overflow, keyboard class dialog/focus restore and rooms with unknown occupancy. These were generated local fixtures, not institutional records. Presentation production-artifact browser separately passed all five Home widths, zero API requests/runtime/console errors, keyboard/details/rooms/deep refresh. No same-data controlled visual comparison was claimed: before images used empty sandbox data; connected after images used a generated published fixture.

Initial gates and retained files (`../production/local-20261029/`):

- Relevant frontend50/9 PASS in72.23s: `p4-relevant-final.log`; subsequent empty-copy7 PASS: `p4-empty-copy-regression.log`; isolated Admin/verified-role7/2 PASS: `p4-route-admin-regression.log`.
- Initial full web run FAILED unchanged300s timeout with Admin readiness timing failure, subsequently passing isolated: `p4-web-tests.log`. Restricted focused attempts had also timed out without results. No timeout, worker, skip, xfail or assertion weakening.
- Affected backend125 PASS/one existing warning: `p4-backend-regressions-fresh.log`. First attempt77 passed/48 setup errors used inaccessible existing pytest temp root: `p4-backend-regressions.log`; fresh owned basetemp/cache resolved setup.
- Lint/types/builds PASS, artifact4 PASS (`p4-artifacts.log`), runner allowlist2 PASS, targeted Ruff/whitespace PASS. Dependencies were unchanged at that checkpoint; no fresh dependency audit was claimed then.
- One initial focused review found stale class fallback, incomplete token timeout, wrong sample dialog label, lost sample controls and incomplete week coverage. Those five issues were corrected/tested without repeated review loops.

Failed connected history retained: one tools root lacked firebase-tools; fresh initdb exceeded unchanged45s; another attempt reached PG/TCP but frontend loading timed out; another signed in but dashboard date-range failed; another initdb exceeded45s. Owner then approved exactly one serial retry. `p4-student-browser-06-approved-serial.log` recorded actual successful Home, five screenshots, details/rooms/navigation followed by real calendar503/periods503 and failed return Home. Its success JSON was absent: not PASS. It stopped before live offline/loading/injected denial/revoked/unassigned/logout/native200 assertions. Those cases remained IMPLEMENTED-UNVERIFIED at that checkpoint; screen reader unverified. Root cause was unconfirmed then, not assumed to be frontend/configuration/capacity.

Initial preservation: `p4-original-preservation.json` matched all3 original SQLite hashes; `p4-p3b-source-preservation.json` matched61 P3b backend/package hashes; `p4-owned-cluster-status.json` showed all5 marked P4 clusters pg_ctl3/no running server; `p4-owned-auth-status.json` showed5 stopped Auth servers/outbound0. Baseline launcher was stopped by verified owned PID tree because tool stdin closed. No user process, original file or evidence was deleted.

Authoritative initial machine checkpoint remains `p4-exit-evidence.json`, with source/screenshot hashes and observed API statuses; original logs, STATUS entry, APPROVALS and P4_ACCEPTANCE retain command/provenance/stop history. Existing `p4-student-after-*` screenshot paths were reused by early recovery runs; historical hashes must not be represented as matching those newer files. Final recovery uses unique run-tagged screenshot filenames and a separate final hash manifest. This index was restored from retained checkpoint records after a Windows text-encoding write failure; those original machine/log records and application sources were unaffected.

## Final recovery and deferred work

The owner reopened bounded stability recovery. PostgreSQL admission exhaustion was confirmed in retained server logs before cleanup. Releasing setup-only pools before HTTP handoff resolved the qualified healthy flow; final correlated evidence distinguishes deliberate outage503s. Reviewed actual-room navigation, UI refinements and a required Vite6.4.5 security patch are covered in [P4_STABILITY_EVIDENCE.md](P4_STABILITY_EVIDENCE.md).

Teacher teaching/request UX and Administrator readiness/review/publication UX remain PLANNED only. Keep P3b identity/RLS/publication/restore intact. Real institutional data/policy/hosting/cutover require separate authority. **Stop at P4a/P4b.**

## Student refinement follow-up

The owner's later preferred-mockup Student task is **PASS for bounded local acceptance**. Current detailed report, fresh commands, screenshots, one independent review and limitations: [STUDENT_REFINEMENT_EVIDENCE.md](STUDENT_REFINEMENT_EVIDENCE.md). Machine exit evidence: `../production/local-20261029/student-refinement-exit-evidence.json`. Prior stability and initial PARTIAL history above remain preserved. Stop; P4c/P4d not started.
