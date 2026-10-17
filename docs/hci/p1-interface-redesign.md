# P1 — Mobile task hierarchy and interface refinement

18 October 2026 · ClassSync · ITHUMCI presentation preparation.

## Scope and source

Refined the existing React/TypeScript/Vite interface in checkpoint order A–E.
Preserved existing uncommitted work, working P0 session architecture, route ownership,
preview gating, sample data, and functionality. No backend changes, new features,
dark mode, dependency additions, commit, or push.

The actual local course source was found and read:
`C:/Users/lenovo/Downloads/ITAPPSD/WEEK 6/ITHUMCI_Detailed_Student_Book_Complete.pdf`
(70 pages; Colegio de Montalban, ITHUMCI, Ms. Cherilyn C. Lamadora, LPT).
Relevant extracted pages: Module 2 pp. 6–7; Module 3 pp. 9–10; Module 6 pp. 18–19;
Module 7 pp. 21–22; Module 11 pp. 31–32; Module 12 pp. 34–35. The worked cases
use Notice → Explain → Improve → Validate; the following decisions follow that
sequence. This is an engineering inspection and scripted task evaluation, not a
human-participant usability study.

## Users, tasks, and contexts

| Role | Primary task | Relevant context |
| --- | --- | --- |
| Student | Identify next subject, time, professor, section, and location; open schedule or that room | Phone use while moving between classes; limited attention and viewport space |
| Teacher | Identify next teaching assignment, review the agenda, find pending requests | Between teaching sessions; completed decisions should not compete with pending work |
| Administrator | Identify a blocking conflict or pending decision, open details, reach schedule management and CDM rooms | Operational triage on phone; comparison and efficient use of space on desktop |
| Visitor | Recognize ClassSync and enter a clearly identified sample preview | No real university authentication is connected; no account or credentials should be implied |

All primary destinations already had short working paths after P0. P1 improves
recognition, grouping, and prioritization; it does not claim a measured reduction
in task time, error rates, or primary-task tap counts.

## Before-state observations and defensible iteration

Fresh captures preceded edits. Inspected Student, Teacher, Administrator, entrance,
role picker, desktop sidebar, bottom navigation, schedule and directory landings.
Severity below reflects anticipated impact and task frequency, not participant data.

| Priority / Notice | Explain | Improve | Validate |
| --- | --- | --- | --- |
| High: Next-class room, building and floor occupied one metadata line; subject/time/location competed without a strong location grouping | Modules 2 and 11: recognition and meaningful grouping support the frequent “where next?” task | Featured schedule entry puts subject first, groups time, emphasizes room, separates building/floor, and labels Professor and Section | Actual Home displays all seven required fields at every requested width; same class appears once |
| High: Schedule and Room Details were separated vertically, with uneven emphasis and spare whitespace | Modules 3, 6 and 7: clear signifiers and adjacent task choices make the next action easier to identify | Paired icon-and-label actions; concise visible labels retain descriptive accessible names | Schedule and exact room open in one activation from Home; both actions meet the inspected 44px target minimum |
| High: Teacher pending and declined requests occupied similar default space | Modules 2, 7 and 11: completed decisions compete with work requiring action | Pending requests remain visible; Recent decisions uses a native collapsed disclosure; All requests remains available. Compact requests include their actual reason | Pending detail opens directly; expand Recent decisions to recover the correct declined record. This adds one intentional disclosure action for history |
| High: Administrator pending decisions followed actions and metrics; conflict review looked like a secondary text link | Modules 6, 7 and 11: triage should lead with actionable issues | Conflict and pending-decision area precedes tools/metrics; room/location/affected-class time contextualize the actual conflict; Review conflict is a button-styled link | Correct conflict ID and request ID reached. Pending decisions precede action navigation in DOM order. Desktop uses two priority columns; narrow layouts stack them |
| Medium: Mobile entrance repeated promotional purpose and role-exploration copy before its working action | Modules 2 and 11: competing messages delay recognition of the working path | Retain identity, one main heading, one short purpose, Explore, honest sample-access note, and disclosed unavailable sign-in | Explore remains in the upper first viewport; two actions reach a selected workspace (Explore → explicit role choice) |
| Medium: Preview indicator had no disclosure cue and its explanatory paragraph/link were not one positioned panel | Modules 3 and 7: predictable signifiers and recovery | Chevron, grouped popover, visible open state, Escape dismissal with focus restored to summary | Opening does not expand the header; link remains valid; Escape closes and restores focus |
| Medium: Directory cards and schedule filter spacing consumed unnecessary vertical space | Modules 2 and 11: density should preserve readable grouping and comfortable targets | Scoped 12px directory-card padding, smaller gaps, removal of double toolbar spacing; retained status wording, field labels, validation and unavailable states | Directory and schedule remain usable at all widths, correct record/return paths work, no horizontal overflow observed |

## Checkpoints and design decisions

**A — Student and Teacher.** Reused ScheduleEntry through an explicit featured
variant; other agenda entries retain their normal list layout. Same-day dates are
established once by the dashboard heading, while next-day assignments still show
their date. Current/next/overlap and unavailable-state handling remains. The
featured class is not repeated in the remaining agenda. Teacher publication badges
remain on timetable views; the published-only featured card avoids a redundant badge.

**B — Administrator.** Pending decisions now share the highest-priority area with
conflicts. The duplicate View all issues link was removed because Conflict Center
already provides that destination; no route was deleted. A maximum of two preview
decisions is shown with an All pending requests path when more exist. Metrics still
represent all supplied demo records. The short timetable preview and provisional
CDM resource overview retain their independent, accurate scopes.

**C — Entrance and navigation.** Mobile entrance removes the second promotional
block; desktop retains its established brand panel. The role picker puts choices
before detailed session information, which remains available in About preview
access. Existing preview lifecycle, explicit switching/Exit and authorization were
not changed. Student bottom navigation is exactly Home · Schedule · Rooms · Alerts.
The existing drawer, sticky navigation, safe-area CSS and deep-link behavior remain.

**D — Shared presentation.** Retained Soft Rouge colors (#F7F8FA, #FFFFFF, #20242C,
#667085, #872E49, #F8EBF0, #E9E9ED), self-hosted Inter, existing controls and semantic
status icons/text. A small scoped refinement stylesheet complements the existing
system. Added semantic featured/subtle surface, action text, focus-independent
target size, compact spacing, radius and shadow tokens. Future appearance work can
override these tokens; no dark appearance or switching was implemented. Existing
unused alternate stylesheets were not adopted or rewritten.

**E — Evidence and regression.** Current screenshots, scripted outcomes and focused
component regressions support the observations rather than subjective success claims.

## P1 files and components changed

Paths below are relative to `apps/web/src/`:

- `components/scheduling/ScheduleEntry.tsx`: featured semantic entry.
- `components/scheduling/NextClassSummary.tsx`: context-aware dates and paired actions.
- `components/scheduling/AttentionQueue.tsx`: issue context and emphasized review link.
- `components/scheduling/RequestSummary.tsx`: concise request reason in compact views.
- `pages/dashboards/TeacherDashboard.tsx`: pending-first content and disclosed decisions.
- `pages/dashboards/AdministratorDashboard.tsx`: priority area and bounded decision preview.
- `pages/AuthPage.tsx`, `pages/DevelopmentRolePreviewPage.tsx`: concise entrance hierarchy.
- `components/layout/AppShell.tsx`: preview panel and keyboard dismissal.
- `theme.css`: semantic refinement tokens, retaining the palette.
- `interface-refinements.css` (new): scoped layout, hierarchy and density rules.
- `styles.css`: refinement import and semantic action-text color.
- Tests: `components/scheduling/NextClassSummary.test.tsx`,
  `components/layout/AppShell.test.tsx`, `pages/dashboards/Dashboards.test.tsx`,
  `pages/dashboards/OperationsDashboards.test.tsx`.

StudentDashboard, ResourceOverview, StatusBadge, buttons and filters benefit from
shared presentation refinements without replacing their data or functionality.
Other dirty files existed before P1 and were preserved.

## Screenshots and execution evidence

All screenshots are outside the repository in:
`C:/Users/lenovo/.codex/visualizations/2026/10/17/01a14b83-8f79-7a40-82da-d3d7b664de7f/`.

- Comparable full-page pairs at 390 and 1440px:
  `p1-before-{student,teacher,administrator,entrance,picker,schedule,rooms}-{width}.png`
  and `p1-after-{same screen}-{width}.png`. Width, 900px capture viewport, fixed
  demonstration date and role match. Full-page heights differ with content density;
  the fixed bottom bar appears at its captured viewport position, not page end.
- First-viewport after evidence for all roles and requested widths:
  `p1-after-{student,teacher,administrator}-viewport-{360,390,768,1024,1440}.png`.
- Interaction/accessibility captures: `p1-after-preview-menu-390.png`,
  `p1-after-short-390.png`, `p1-after-short-1024.png`, `p1-after-zoom-200.png`.
- `p1-before-observations.json`, `p1-after-observations.json`: page/control observations.
- `p1-browser-results.json`: URLs, roles, headings, active navigation, task checks,
  target and contrast checks. Scripts: `p1-capture.cjs`, `p1-qa.cjs`.
- Intermediate checkpoint captures are retained with `p1-checkpoint-a/b/c-` prefixes.
  One intermediate C capture was interrupted by navigation during live development;
  final comparisons are captured after edits stabilize.

## Actual workflow results

Browser plugin was unavailable. Used the existing bundled Playwright package and
installed Chrome, at `http://127.0.0.1:5182`. No browser dependency was downloaded.
The final task run passed **178 page checks and 50 task checks**, including all
three roles at 360, 390, 768, 1024 and 1440px. Action counts start on the role's Home
screen and exclude scrolling; they are scripted path counts, not user-study metrics.

| Workflow | Actions / correct destination | Confusion addressed / observed result |
| --- | --- | --- |
| Student identifies next assignment | 0; Home shows Database Management Systems, 10:00–11:30, SCI-218, Science Building, Level 2, Prof. Maria Santos, BSIT 2A | Explicit groups and labels; location visible in first viewport |
| Student opens schedule | 1; `/student/schedule` | Paired Schedule action with familiar label; correct route |
| Student opens next room | 1; `/student/rooms/detail?id=room-sci-218` | Named record preserved; refresh and back/forward retain role and page |
| Teacher identifies next assignment and opens schedule | 0 to identify; 1 to `/teacher/schedule` | Next assignment precedes secondary tools; correct teaching route |
| Teacher opens pending request | Scroll to Requests & decisions, then 1; `/teacher/change-requests/detail?id=request-room-access` | Pending status and actual reason visible; completed decision initially collapsed |
| Teacher recovers declined decision | 2; Recent decisions → selected request `/teacher/change-requests/detail?id=request-equipment` | Native disclosure makes the lower-priority history recoverable |
| Administrator reviews highest-priority conflict | 1; `/admin/conflicts/detail?id=conflict-science-overlap` | Room, problem and review action clear; correct conflict ID |
| Administrator reaches management | 1; `/admin/schedule-manager` | Schedule Manager retained as a familiar operational action |
| Administrator browses CDM rooms | 1; `/admin/rooms` | CDM provisional inventory selected; PRRC 101 detail and directory return correct |

No unexpected logout, incorrect primary destination, missing featured fields,
duplicate featured assignment, horizontal overflow, Vite overlay or runtime
exception was observed in the final task run. An initial automation locator was
corrected to match the Inventory combobox's accessible name; this was a test locator
issue, not a product navigation failure. Existing favicon 404 remains outside P1.

## Accessibility checks and limitations

- Inspected primary Home/header/bottom navigation links and enabled buttons meet
  a 44×44px minimum at every requested width. This is a scoped inspection, not a
  claim that every control in every screen meets a WCAG target-size criterion.
- Native heading/region structure and definition-list labels support recognition
  and programmatic grouping. Status icons and explicit text remain; color is not
  the only status indicator. Decorative icons are hidden from assistive technology.
- Keyboard activation of Schedule, visible focus, drawer initial focus/containment,
  Shift+Tab/Tab, Escape closure/focus restoration, and preview-menu Escape passed.
- Short screens at 390×480 and 1024×480: scrolling exposes the room action above
  sticky controls; activation reaches the correct room. Existing safe-area padding
  is retained; physical-device notches and browser chrome were not tested.
- Tested 200%-equivalent reflow using 720×450 CSS pixels at DPR 2, corresponding to
  a 1440×900 physical viewport at 200% zoom. Mobile navigation, readable featured
  title, no horizontal overflow and correct room activation passed. This does not
  claim native browser-menu zoom or a comprehensive text-spacing audit. An earlier
  CSS-zoom-only test was rejected after screenshot inspection showed unreadable
  columns: CSS zoom leaves desktop media queries active and is not an accurate
  substitute for browser-zoom reflow. Its screenshot was replaced by the verified
  reflow capture; the targeted rerun is `p1-zoom.cjs`.
- Reduced-motion context verified zero computed transition duration on the inspected
  primary action. No new decorative animation was introduced.
- Computed foreground/background pairs checked against 4.5:1: main text, secondary
  text on surface and canvas, primary action, warning and danger badges. Exact
  measured ratios are in `p1-browser-results.json`; disabled controls are not used
  as a contrast-pass claim.

| Checked pair | Contrast ratio |
| --- | --- |
| Main text on surface | 15.55:1 |
| Secondary text on surface / canvas | 4.97:1 / 4.68:1 |
| Action text on brand accent | 8.34:1 |
| Warning text on warning tint | 4.65:1 |
| Danger text on danger tint | 5.93:1 |

- No screen-reader session, representative-user study, physical-device study,
  localization/long-content review, full focus-obscuration audit, or full WCAG 2.2
  conformance evaluation was conducted. Scripted automation is not participant data.

## Required checks

| Check | Final result |
| --- | --- |
| `npm run lint` | Passed, no warnings |
| `npm run typecheck` | Passed |
| `npm run test:web` | Passed: 154 tests across 19 files |
| `npm run build` | Passed: 1,692 modules; CSS 56.32 kB / 11.01 kB gzip; JS 465.17 kB / 138.93 kB gzip |
| `git diff --check` | Passed |

Focused regressions cover featured information and next-day dates, exact role-owned
room links, nonduplicated assignments, pending visibility and recoverable approved/
declined decisions, Administrator priority order, and keyboard dismissal of preview
options. The full suite retains P0 role-continuity, authorization and navigation tests.

## Selected visual evidence

Same 390×900 viewport and Student preview, before and after. The featured room and
labelled Professor/Section fields have a stronger visual grouping; Schedule and Room
Details are adjacent comfortable targets. The feature card trades a little height
for that explicit grouping, rather than claiming every individual card got smaller.

![Student before](C:/Users/lenovo/.codex/visualizations/2026/10/17/01a14b83-8f79-7a40-82da-d3d7b664de7f/p1-before-student-390.png)
![Student after](C:/Users/lenovo/.codex/visualizations/2026/10/17/01a14b83-8f79-7a40-82da-d3d7b664de7f/p1-after-student-390.png)

Same 1440×900 viewport and Administrator preview, before and after. Pending decisions
move into the priority area; the timetable and provisional resources occupy separate
desktop columns. The status remains explicitly textual and icon-supported.

![Administrator before](C:/Users/lenovo/.codex/visualizations/2026/10/17/01a14b83-8f79-7a40-82da-d3d7b664de7f/p1-before-administrator-1440.png)
![Administrator after](C:/Users/lenovo/.codex/visualizations/2026/10/17/01a14b83-8f79-7a40-82da-d3d7b664de7f/p1-after-administrator-1440.png)

## Remaining improvements

- Validate hierarchy and terminology with representative students, teachers and
  administrators using a consented usability protocol and realistic tasks.
- Run screen-reader and physical-device safe-area/keyboard testing, native browser
  zoom and broader accessibility tooling before making compliance claims.
- Larger real datasets, long subject names, several simultaneous conflicts and
  request-history browsing deserve separate testing. Bounded previews retain full
  destination links rather than implying the shown samples are the complete system.
- Official CDM inventory verification and real authentication/scheduling services
  remain future work. No demonstration role grants backend authority.
- P2 appearance work is not started. Theme tokens provide a foundation only.
