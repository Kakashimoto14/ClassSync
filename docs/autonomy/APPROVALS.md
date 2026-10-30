# ClassSync autonomy — authority and approvals

Historical evidence must not be construed as live permission. This file is a *local workflow record*, not an institutional delegation.

| Action | Initial authority | Boundary |
|---|---|---|
| Read/inspect source and run local non-destructive checks | Yes | Preserve user files and secrets |
| Create/update this orchestration harness in local workspace | Requested in October 2026 | Check existing files before merging |
| P1 bounded local source/tests/docs | Approved in prior ClassSync conversation | Preserve SQLite data; no deployment |
| P2–P8 local implementation | Owner authorization, 26 October 2026 (mission message in current engineering session) | Local source, tests, documentation, disposable test data and emulator-only implementation; advance only after prior acceptance gates PASS; no side effects below |
| PostgreSQL test instance using disposable local data | Requires explicit P2 approval | No original DB mutation or cloud cost |
| Real SQLite-to-PostgreSQL data migration/cutover | No | Separate rehearsed migration authorization |
| Git commit, push, merge, deployment, hosted changes | No | Separate explicit approval |
| Firebase production settings/rules or real claims | No | Separate explicit approval |
| Cloud provisioning, charges, external API credentials | No | Separate explicit approval |
| Real people/academic records, roster imports, messaging | No | Institutional privacy/data authority required |
| Declare institutional production release | No | Meets P9/P10 gates + authorized owner/institutional approval |

When the product owner explicitly expands local phase authorization, record precise phase range, allowed operations, date and supporting message here, without broadening authority to cloud/data/Git operations.

## 26 October 2026 — scoped owner authorization

The owner explicitly confirmed bounded P1 local work and granted one scoped authorization for P2–P8 local source-code, tests, documentation, disposable test data and emulator-only implementation. Disposable local PostgreSQL qualification is included after dependency gates pass. This supersedes the historical statement that grouped phase approval was absent; it does not waive any acceptance or security gate.

Original databases, real records/imports, production Firebase/IAM/claims, credentials, cloud resources/spending, commits/push/merge, deployment/cutover, real messages, destructive operations, institutional policy decisions, security risk acceptance and production release remain separately gated. No exception to the unresolved dependency advisory is authorized.

## 30 October 2026 — P4a/P4b owner authorization

Owner explicitly requests connected application recovery and Student experience refinement in the current session. Allowed: local frontend/integration code, tests, documentation, existing local launcher, disposable synthetic/emulator identities and test databases, rendered screenshots and one independent focused milestone review. P3b remains intact. Stop after P4a/P4b acceptance; Teacher/Admin redesign P4c/P4d excluded. Existing Git/cloud/real-data/original-database restrictions remain.

### 30 October 2026 — one bounded P4 qualification retry

After repeated owned disposable initdb 45-second timeouts, owner explicitly selected “Approve one serial retry” in response to the persistent-failure stop gate. Finish current independent checks first, then permit exactly one further connected Student Auth/PG/browser qualification with unchanged limits. This is not approval to relax gates, reuse original databases, or retry indefinitely. Stop PARTIAL if that remaining qualification cannot pass.

## 30 October 2026 — P4a/P4b stability recovery task

Owner explicitly reopened P4a/P4b diagnosis, smallest confirmed repair, focused Student polish and final acceptance in the “STABILITY RECOVERY AND FINAL ACCEPTANCE” task. The earlier one-retry allowance remains consumed; it is not reused. Current scope excludes P4c/P4d and all existing Git/cloud/original-data restrictions. Working bound: use retained logs first, make the evidenced correction, then one instrumented connected verification; stop and seek a new decision if an unexplained persistent failure remains. No timeout, PostgreSQL connection limit, RLS, privilege or acceptance gate relaxation is authorized.

## 30 October 2026 — Student experience refinement authorization

Owner explicitly authorizes the bounded Student refinement task using two supplied illustrative mockups. Scope: Home, Schedule, Rooms, Alerts, presentation mapping, isolated richer synthetic fixture, relevant tests/browser acceptance and one focused independent review. Preserve the completed P4 stability repair and all security/data boundaries; no Teacher/Admin redesign. Prior stability PASS supersedes historical persistent failures; no retry counter is reset. Acceptance: multiple daily classes; correct ongoing/upcoming/tomorrow/empty calculation; consistent dashboard/calendar; working date/class/room/alert navigation; no technical IDs in primary content; four destinations; all five widths/native200; honest denied/unavailable/recovery and demo separation; applicable final gates and original database hashes. Stop on a new persistent unexplained failure.

## 30 October 2026 — Campus Companion visual milestone authorization

Owner explicitly authorizes Student-scoped visual refinement of shared chrome, Home, Schedule, Rooms, Alerts and Announcements. Acceptance: preserve all source and role/security behavior; concise global preview provenance; responsive 360/390/768/1024/1440 and native 200%; working keyboard, routes and controls; focused tests then applicable regression/security/build checks; actual before/after captures; unchanged original SQLite hashes. No Teacher/Admin redesign, production changes, commits or deployment.

## 30 October 2026 — selected Claude redesign and bounded recovery approval

Owner explicitly approves restoring institutional `Student · University` and demonstration `Student · Demo`, and exactly one run of the previously failing institutional Student route test. If that test passes, proceed directly with selected Claude design implementation across shell, Home, Schedule, Rooms and Alerts using current React providers and verified security/data boundaries. Capture phase screenshots, focused tests and final acceptance. No new Goal, further research, alternatives, backend rewrite, Teacher/Admin redesign, commit/push/deployment/production changes. A new persistent failure requires a new owner decision; prior attempt history remains intact.
