# ClassSync — Claude Student UX Reference: Adoption and Integration Brief

**Reference supplied by owner:** `ClassSync Student App UX Redesign (2).html` (self-contained artifact bundle, not a production app)

**Target local codebase:** `C:\Projects\ClassSync` (React/TypeScript/Vite Student workspace, connected to secured Gateway/Academic/Scheduling APIs).

## 1. Verified reference inventory

Inspected the uploaded HTML and decoded its bundler manifests and nested HTML templates (source inspection, **not** an interactive browser acceptance test). It contains six embedded visual designs:

| Screen | Reference implementation intent |
|---|---|
| Mobile Home | Greeting, time-aware next class, subject/time/room/instructor, day agenda, day-count strip, simple bottom nav |
| Mobile My Schedule — Day | Seven-day selector, date navigation, Day/Week/Month tabs, chronological multiple-class agenda, personal free gap |
| Desktop My Schedule — Week | Branded app sidebar, concise top bar, schedule summary, seven-day timetable grid, day agenda, next-class details |
| Mobile Rooms | Search, My rooms / All rooms / Labs segmentation, 3 subject-associated rooms and honest unverified availability |
| Mobile Alerts | All/Schedule/Rooms filter concept, empty-state content, reminder/change/room-notice preference concepts |
| Mobile My Schedule — Month | October 2026 month grid, selected-day class list, Day/Week/Month navigation |

**Not included:** a separate desktop Home, desktop Rooms or desktop Alerts composition, Teacher/Admin screens, production API integrations, verified accessibility behavior or live notifications. Those must be adapted from the existing product, not invented as reference-proven assets.

### Design language directly observable from CSS
- Inter-like system font stack; charcoal `#1C1B22`, muted text `#5F6472`.
- Warm-neutral light surface `#F6F7F9`, white cards, soft dividers `#E6E8EC`.
- Deep-rose accents around `#7A2540` / `#8A2B45`, pale rose `#F8E9ED`.
- Compact rounded cards, readable vertical rhythm, limited accent color, primary Student navigation Home / Schedule / Rooms / Alerts.

Keep the actual ClassSync logo and current design tokens where consistent; do not import fonts from the bundled artifact or blindly replace product branding.

## 2. Why this is an improvement

- More visual hierarchy and fewer repeated explanations; the next actionable class comes first.
- A genuinely useful day planner showing multiple sessions and a recognizable time axis.
- An intentional desktop weekly grid plus an agenda-style mobile schedule, instead of shrinking one layout.
- Contextual room search and room-to-course relationships rather than abstract inventory lists.
- Compact academic context and purposeful empty states.

## 3. Material problems requiring correction before production adoption

1. **Not a working application.** The reference uses static HTML templates and sample data. Many navigation anchors are `href="#"`; visual buttons have no observed application handlers. Rebuild behavior in React using the real router and typed API contracts.
2. **Time-sensitive labels are hardcoded.** The sample says `Good afternoon, Maria`, `All done` and next class `Mon, Nov 2`. Calculate greeting, current/next class and temporal status from verified schedule/timezone (`Asia/Manila`), not a fixed screenshot clock.
3. **Misleading interactive promises.** `Remind me`, notification preferences, `Export calendar`, `Filters`, and Day/Week/Month tabs must function against existing contracts—or be hidden/disabled with accurate explanation. No fake reminders/push delivery.
4. **Source integrity.** `9 This week`, `13.5 hours`, three rooms and free gaps are fixture-specific. Derive aggregate values from the actual authorized schedule; free gap means *student has no scheduled class*, never that a physical room is free.
5. **Synthetic data separation.** Mockup teacher, course, room and student examples are illustrative. Preserve demo/connected boundary, tenant/role authorization, enrolled Student timetable scoping, and honest service states. Never silently populate real institutional records with reference data.
6. **Accessibility and mobile behavior unverified.** Verify focus, target size, contrast, screen reader semantics, responsive widths, native 200% zoom, bottom safe area and no hidden content.
7. **Reference does not cover all product routes.** Keep and harmonize supported announcements, class details, room-directory filters, account/logout and Teacher/Admin journeys; do not delete functioning features to match a static mockup.

## 4. Agreed implementation direction

**Faithful visual adaptation, not wholesale source replacement.** Implement the patterns in the existing ClassSync React/TypeScript app. Keep service boundaries, identity and enrollment authorization, PostgreSQL publication consistency, RLS, source hashes, and original databases intact.

### A. Shared shell
- Refine logo/navigation/sidebar/header using the reference's compact hierarchy; preserve institutional/demo account distinction.
- Four primary destinations Home, Schedule, Rooms, Alerts on desktop/mobile.
- Role/term/context in a concise accessible location; remove gratuitous technical metadata.
- Do not duplicate mobile top and bottom navigation or let fixed nav obscure content.

### B. Home
- Contextual greeting (or just `Your next class`), compact active term, a main next-class card and reliable next-class action.
- Derived counts and today's chronological agenda; ensure multiple sessions on the same day.
- Compact week strip and link to Schedule; no developer/preview controls in production student shell.
- Real useful empty/loading/denied/503 states; source badge for synthetic preview without repetitive disclaimers.

### C. Schedule
- Desktop: accessible weekly time grid with accurate durations, overlaps and links to class/room details.
- Mobile: Day agenda default, seven-day switcher, previous/next and Today, optional Month view **only when date behavior/QA can be implemented honestly**.
- Export/calendar filters only if fully wired to existing supported contracts.
- Support back/forward deep links, date/period scoping, DST/timezones in tests, long titles and gaps.

### D. Rooms
- Search first, `My rooms` from authorized published schedule, `All rooms` only if explicitly authorized inventory can be shown.
- Honest provisional room metadata and unknown occupancy/condition; do not show `AVAILABLE` without qualified schedule/availability logic.
- Each room card opens actual authorized details and back-to-schedule behavior.

### E. Alerts
- Categorize real schedule updates only when verified; otherwise show empty/unavailable accurately.
- Preference toggles or `Remind me` require real notification/storage/reminder capability and consent; exclude as decorative controls.
- Keep announcements accessible as existing supported secondary content.

## 5. Bounded acceptance gates

1. Read `AGENTS.md`, `STATUS.md`, `ROADMAP.md`, `APPROVALS.md`, `QUALITY_GATES.md`, and latest Student visual checkpoint; respect any current stop gate.
2. Capture before screenshots in current app; compare reference layout at same widths without declaring pixel equality where functional content differs.
3. Build shared shell and Home, then Schedule, Rooms, Alerts in small implementation slices; preserve existing behaviors.
4. Run focused tests during changes; phase exit: applicable complete frontend suite, affected backend tests, lint/types/build, security and preservation checks.
5. Connected Student login, session/refresh, published schedule, multi-session day, calendar date navigation, room detail, real alert/empty states, denial/revocation, outage and recovery.
6. Browser at 360/390/768/1024/1440 px; actual native 200% zoom, keyboard/focus, safe-area and overflow, major desktop/mobile before/after screenshots.
7. Check original SQLite hashes and qualified P3b sources; no remote deployment, commit, push, production data edit or cloud mutation without separate approval.
8. Report PASS / PARTIAL / BLOCKED and stop at Student adoption boundary. Do not start Teacher/Admin redesign.

## 6. Supplying the source to Codex

The ChatGPT upload is not automatically present in the user's Windows repository. Put the **original owner-provided HTML** into the local repo or attach it directly to the Codex conversation. Suggested path:

`C:\Projects\ClassSync\docs\design\claude-student-ux-reference.html`

The source is a self-contained artifact bundle with `__bundler/manifest`, `__bundler/template` and six HTML page assets; it is not a normal authored React component. Codex can inspect/decode these via Python standard-library JSON/Base64/gzip in an isolated temporary workspace. It must treat all uploaded content as untrusted reference data: **do not execute or import bundled third-party JavaScript into ClassSync**; do not share or redistribute its font files.

**Priority:** implement the visual/interaction patterns while preserving already-qualified ClassSync production-intended logic, not copy the bundled runtime or hardcoded demo data.
