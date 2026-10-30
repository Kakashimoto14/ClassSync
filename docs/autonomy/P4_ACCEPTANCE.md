# P4a/P4b acceptance cases — 30 October 2026

Before implementation: preserve HEAD 39200a4f2ef3ec7557bc3c86127e674e260ca4fc and all prior dirty work; originals match all three SHA256 baselines.

1. Institutional Student routes require current verified Student membership; preview storage/query strings cannot grant access. Teacher/Admin workflows retain their current boundary.
2. Configured Firebase sign-in/session restore/role choice/logout reach authorized Student Home. Unconfigured provider is honest; no credentials sent in preview.
3. Read-only timetable API uses token/current role, bounded timeout and cancellation. No sample fallback, writes or arbitrary endpoints. Failed/denied loads hide previous classes.
4. Home prioritizes Next Class, chronological today, grouped weekly durations, actual changed occurrences, and rooms with unknown occupancy. Published version is visible; no fabricated classes/updates.
5. Loading, no publication/no period, no classes, unassigned/denied/revoked, offline and retry recover predictably. Presentation remains offline/read-only.
6. Home → timetable/class details/rooms, deep refresh, keyboard navigation, drawer focus and logout; 360/390/768/1024/1440 widths, native200% zoom if available, no overflow/framework errors.
7. Targeted tests during edits, final frontend lint/types/tests/build and relevant backend authorization regressions; one independent review. Real browser/emulator/PostgreSQL evidence required for connected acceptance, with unrun cases explicitly open.

Initial prioritized defects from current source: P0 institutional RoleRoute rejects all users; P0 all institutional timetable calls disabled; P1 login submit never calls configured Auth; P1 Student dashboard lacks weekly overview/updates/room discovery and inherits sample-oriented errors; P1 primary navigation exposes planned destinations. Runtime diagnosis and screenshots follow.

## Stability recovery acceptance — 30 October 2026

Retain attempt06 failure. Correlate its PostgreSQL FATAL connection-slot rejections (02:24:55/57) with navigation503 before shutdown02:25:29. Identify fixture/provider connection owners; release setup-only resources without changing production pools or server limits. New evidence must retain timestamp/method/path/query/request ID, service-level status, provider lifespan/pool state, health and actual failure payloads. Healthy flow must have no503; explicitly labeled outage must503 and recover. Complete login/role/navigation/back/forward/details/rooms/refresh/logout, real revoked/unassigned/unauthorized denial, all five widths, native200 and focus/safe-area checks. Refine version disclosure, period label, Next Class density, event hierarchy, empty days and user-facing copy. Final full frontend and affected backend/security/static/build/artifact gates, preservation and one independent focused review. No P4c/P4d.


## Final stability exit — 30 October 2026

P4a/P4b PASS for bounded local acceptance. All requested connected cases, five-width Home/real room action, keyboard/focus/bottom-nav clearance, actual Chrome200 and genuine outage/recovery pass on Vite6.4.5 in attempt09. Presentation Home/calendar five-width zero-API separation passes. Final731 frontend/125 affected backend/17 security/artifact4/static/build/audit gates pass; all original hashes preserved. One independent review completed and its actual-room action finding resolved. Exact traceability, historical forensic limits, screenshots and exclusions are in P4_STABILITY_EVIDENCE.md. Stop; no P4c/P4d.

## Student refinement traceability — 30 October 2026

| Acceptance | Evidence | Exit |
|---|---|---|
| Readable Home; complete today; compact linked week; no primary raw IDs/term selector | StudentHome; presentation mappings; controlled-clock/model/Home tests; final five-width screenshots | PASS local |
| Week/Day/Month, previous/next/Today, dates/history, class/room details, pending new month and midnight geometry | StudentSchedule; edge/navigation11; full web739; final rendered artifact journey | PASS local |
| Rich isolated fixture; multiple daily classes; empty days; separate room change | Exporter/domain validator; calendar/fixture6; Home change UI10; no DB access by exporter | PASS synthetic only |
| Connected access, publication, negatives, outages/recovery, logout and mode separation | Final owned Auth/PG/TCP result; zero healthy503; no presentation API requests | PASS local |
| Responsive/native200/keyboard/fixed navigation, independent review and preservation | All five widths; native zoom/focus evidence; one review4 fixes;64 preserved hashes | PASS oriented checks; manual screen reader/production unverified |

Full evidence and remaining Teacher/Admin backlog: [STUDENT_REFINEMENT_EVIDENCE.md](STUDENT_REFINEMENT_EVIDENCE.md). Stop here.
