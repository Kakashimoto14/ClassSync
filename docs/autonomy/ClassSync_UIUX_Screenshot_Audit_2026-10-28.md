# ClassSync — Evidence-Based UI/UX and Runtime Review
**Date:** 2026-10-28  
**Evidence:** 15 screenshots supplied by the owner, showing `localhost:5173` Student, Teacher and Administrator routes, including mobile preview overlay.  
**Scope:** Screenshot-based review, not a live DOM, API, assistive-technology or source-code audit. GitHub repository documentation checked separately; Codex must reconcile its newer local working tree.

## Executive assessment
The current Soft Rouge design has workable branding, cards, responsive navigation, forms, a teaching calendar and dialogs. Its main defects are weak information hierarchy, overexposed operational/development language, inconsistent data-source messaging, sparse dashboards, overlapping navigation categories and some low-density repetitive lists. A backend connection problem is a separate issue from visual design.

**Critical distinction:** `localhost:5173/student/dashboard` showed a failed timetable request. Screens with `?mode=presentation` showed an explicitly synthetic read-only sample. Neither proves that a real PostgreSQL-backed institutional timetable is running.

## Observed findings
| Priority | Surface | Evidence from screenshots | Recommended action / pass condition |
|---|---|---|---|
| P0 | Student live view | “Couldn't load your timetable. The timetable service is unavailable.” | Diagnose actual failed request and service chain, distinguish stopped service vs wrong proxy/auth vs no timetable. Never silently replace with demo. Accessible actionable recovery. |
| P0 | Teacher read-only presentation | “Updates interrupted. Last confirmed timetable shown; reconnecting.” while labeled “Read-only sample” | Trace whether there is any genuine connection attempt. Do not display live-reconnection language in truly offline presentation mode. Add regression test. |
| P1 | Student Home | Large Next Class card, little else in visible area | Distinct next class, compact today's agenda, weekly peek and real schedule-change indicators; render legitimate no-classes vs unavailable states. |
| P1 | Teacher Home | Next Class dominates, request/activity area below initial viewport; status message above task | Prioritize next teaching session, day's teaching, pending legitimate requests and affected-room alerts with actual source. |
| P1 | Navigation | Primary Rooms/Notifications plus grouped Rooms/Communication; planned scanner prominent | One canonical route per purpose; progressive disclosure; no duplicate competing nav entry; planned screens not in primary task path. |
| P1 | Admin Academic Management | Sample explanation and provenance copy dominate; CTA far from context | Readiness stepper showing real period/scope, imported record coverage, blockers, Generate/Review/Publish state; no invented metric. |
| P1 | All role screens | Long labels repeated: Read-only sample, synthetic, provenance, preview, data-source details | One persistent concise environment/sample indicator; source specifics via disclosure; safety caveats near affected decisions. |
| P2 | Student registration scanner | Full “coming soon” screen with a planned workflow | Remove from prominent nav or label planned and keep brief; do not imply upload/extraction exists. |
| P2 | Room finder / directory | Search and filters below warnings; 59 provisional rooms; repeated condition unverified pills | Search/results first; filter by known attributes, grouped room/building, clear Unverified/Unknown vs Available distinction. Never infer physical occupancy or capacity. |
| P2 | Announcements | Repetitive generic text and large cards | Compact feed, meaningful hierarchy and timestamps; disclose demo fixtures and avoid impersonating real notices. |
| P2 | Teacher timetable | Week grid is promising but event titles truncate; detail modal verbose with synthetic IDs | Visible times/room/class, accessible full details, compact modal or drawer, hide internal IDs behind technical details. |
| P2 | Teacher request cards | Large repeated blocks and full-width View request | Compact rows/cards with meaningful statuses, affected class and dates; show action only if real. |
| P2 | Mobile navigation | Bottom tabs plus secondary drawer is recognizable | Verify consistent destinations, drawer focus trap/restore, touch targets, visibility above safe-area, no accidental duplication. |
| P2 | App shell | Search prominent on desktop; screenshots do not establish whether it is functional | Search must work within authorized role dataset or be removed/disabled with honest explanation. |
| P2 | Accessibility | Mobile view visually small due to inset; cannot establish physical readability | Test at 360/390/768/1024/1440 CSS px, native 200% zoom, contrast, keyboard, focus, screen reader tasks on representative journeys. |

### Additional observations
- Dates and local time should be consistently formatted in Asia/Manila, with explicit “today,” next class and no-class cases.
- The screenshot overlays a simulated phone on desktop, obscuring parts of the actual desktop UI: don't label that overlap a CSS defect without independent browser reproduction.
- Preview personas, synthetic room IDs, and “unverified” labels are legitimate metadata; move technical details out of the primary experience, not out of the system's truth model.
- Changing presentation/live mode via query strings or browser storage should never bypass backend mode/authorization controls.

## Proposed role-specific home information architecture
**Student:** personal greeting/current period and trustworthy mode status → next class (time/room/building/teacher) → remaining today’s agenda (including no-classes state) → weekly schedule preview/link → relevant changes/alerts → small quick destinations to schedule/room lookup.

**Teacher:** next teaching assignment → today’s teaching list → active requests/recent decisions → assigned room/location and actionable issue-report link → full calendar.

**Administrator:** period selector / data readiness (real counts only) → prioritized blockers and latest draft status → guided workflow [Academic setup → Check readiness → Generate → Validate → Approve → Publish] → conflicts, approvals and publication history. Visible source truth and authorization state; never imply synthetic drafts are official.

## Engineering safeguards
1. Current Codex Goal is working on PostgreSQL publication. Do not interleave unrelated edits to files it currently owns. At a safe checkpoint, register this audit as a UX milestone and schedule bounded changes in dependency order.
2. Before source changes, inspect current local router, shell, pages/components, tokens, API adapters and `docs/autonomy` quality gates. Create baselines and render before-screenshots.
3. Never change backend scheduling rules, tenant/role access controls or database state merely to improve presentation. Use real data, truthful sample or explicit empty states.
4. No fake statistics, alerts, success actions, persistence, role access or connected statuses.
5. Repair high-severity source-mode messaging first. Implement one screen family at a time and run targeted + regression tests, visual comparisons and keyboard checks.
6. For Student Home, include empty, loading, error, demo, unassigned, no-classes, multiple-classes and outdated-data scenarios.
7. Make active tasks easier to complete, not just aesthetically pleasing. Validate actual CTA behavior end-to-end.
8. No commits/pushes/deployments, real Firebase changes, original DB migrations or destructive operations without owner's separate authorization.

## Runtime runbook (reconcile current local implementation)
The repository documents `npm run dev` as the verified single-command launcher for Gateway 8000, Academic 8001, Scheduling 8002 and Vite 5173. `npm run dev:web` starts only the frontend. Port occupancy must be inspected before launching: Codex may already own local processes. An isolated QA instance can use `npm run dev -- --base-port 8830 --web-port 5190` with `ACADEMIC_DATABASE_PATH` and `SCHEDULING_DATABASE_PATH` pointed to fresh disposable files in `%TEMP%`. Never import sample records into original DBs while preservation hashes are an acceptance gate.
The launcher does not seed records or publish timetables. In the isolated QA sandbox, follow Administrator → Academic Setup → Sample Academic Scenario → Review Sample Setup → Import sample period; review readiness/generate/save. Synthetic Student/Teacher review and real authorized publication are different paths. Don't claim a new sample draft is published.

## Required exit evidence
- Annotated before/after screenshots per role at desktop/mobile and native 200% zoom.
- No P0 source-mode or connection error misrepresentation.
- Student Home demonstrates real navigation to agenda, schedule, details and room lookup using an authorized source.
- Teacher requests statuses and Administrator setup actions grounded in actual service data.
- Focus-visible, accessible names, keyboard tab order, dialog/drawer focus containment, contrast and reduced-motion review.
- All links/buttons/filters/search either functional or clearly unavailable.
- React lint/types/frontend and applicable Python tests pass; backend authorization remains enforced.
- Zero source-mode regressions; sample fixture cannot silently replace failed institutional API.
- Append file-level findings, tests and remaining concerns to `docs/autonomy/STATUS.md`; retain independent critical review.
