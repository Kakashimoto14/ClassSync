# Selected Claude Student redesign — implementation checkpoint

**PARTIAL — 30 October 2026.** Actual React/CSS changes implemented after owner-approved recovery. Prior dirty work retained; no commit/push/deployment/production changes. Current gate requires owner decision before more edits/retries.

## Approved recovery

AppShell now renders both `Student · University` and `Student · Demo`. Exact previously failing institutional test ran once and PASSED (`approved-recovery.log`,1 selected pass;3 other tests not selected by the explicit filter). The former gate is resolved; its history remains preserved.

## Actual code changes

- `AppShell.tsx`: account labels restored; selected Student shell retained with four working primary destinations.
- `main.tsx` and new `claude-student.css`: Student-scoped warm neutral/white surfaces, selected burgundy/rose palette,248px sidebar, compact header, navigation selection, typography, cards, responsive styling. Teacher/Admin styles remain outside the Student selector.
- New `components/ui/StudentPageHeader.tsx`: reusable title/context/term/action composition.
- `StudentHome.tsx`: combined context header, rose Next Class/status pill, separate agenda cards, compact week, styled schedule rooms, room-date class relationships and alert empty state. Existing API/provider/error/identity logic retained.
- `StudentSchedule.tsx`: Day/Week/Month buttons, selected grid/card treatments, aligned seven-column month calendar with leading blanks, date-specific day movement and month/year navigation. Existing workspace/API/context retained; new month test has not passed.
- `StudentSchedule.test.tsx`: added month alignment/year-boundary coverage; this new case currently fails at reads around pending render transitions.
- `scripts/claude_student_browser.cjs`: phase capture workflow on owned local presentation frontend5190. No embedded prototype runtime or fonts imported.

## Visible evidence

All image paths are indexed by `shell-browser.json`, `home-browser.json`, `schedule-browser.json`, `rooms-alerts-browser.json` under `docs/production/claude-student-20261030/`. Each phase captured actual390/1440 layouts (2 shell,2 Home,4 Schedule/options,8 rooms/alerts). No console/runtime errors or API requests were recorded. This is presentation evidence, not connected acceptance.

Inert reference renders were produced from the previously decoded template text with scripts/font faces removed and network blocked. Original temporary decoded text was readable in the default tool surface but denied in the escalated browser surface; copied inert text into the evidence workspace without executing the bundle. Reference screenshots: `claude-selected-reference-1.png` through6 in the task visualization folder. Selected source SHA remains in CLAUDE_STUDENT_REDESIGN_REFERENCE.md.

Inspected differences: official logo replaces prototype text wordmark; actual class state/data replaces hardcoded greeting/counts; reminders/export/toggles unavailable are omitted. Rose featured card, white pill, separate agenda cards, warm canvas, rounded room cards and four-destination navigation implemented. Desktop reference's right agenda column/summary composition and final fidelity refinement remain open. Mobile Today wrapping was corrected in source; needs final capture. New month behavior requires acceptance.

## Tests and stop

- Approved recovery exact test1 PASS.
- Focused Home/Schedule/AppShell/institutional route tests30 PASS (`phase-tests.log`).
- New month suite: first attempt5 PASS/1 FAIL (`month-tests.log`), corrected attempt5 PASS/1 FAIL (`month-corrected.log`). Both fail in the new case when querying the month navigation around asynchronous loading. The correction added waits after navigation but did not add a wait after initial Month selection. Further investigation/correction requires approval under the new persistent-failure gate. No assertion/timeout/skip weakening.
- Original3 SQLite and61 P3b backend/package hashes all match (`preservation.json`).
- Final full frontend/backend/security/lint/types/build/artifact/connected/native200 checks have NOT run for this new design. Earlier milestone results are historical, not substituted as current acceptance. Manual screen reader unverified.

Next bounded proposal: inspect the pending-month DOM/test timing, add appropriate asynchronous waits without weakening expected alignment/date assertions, run the failing new test once; if green, complete fidelity, one focused review and required final gates. No further source/test retry performed after the second failure. Stop; P4c/P4d not started.
