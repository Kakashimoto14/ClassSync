# P1 cumulative review and P2 readiness

21 October 2026. Review base: `main` at `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`. The starting tree contains **67 cumulatively changed/untracked files**, including the original P1 implementation, dependency/security work, historical evidence and the latest researched remediation. This is not a review of only the previous six-file task. No original work was reset. The complete per-file inventory, hashes, review classification and fresh command evidence are in [p1-cumulative-review-evidence.json](p1-cumulative-review-evidence.json).

No commit/push/deploy, Firebase setting/rule change, provisioning, PostgreSQL work, migration or P2 implementation occurred. P2 sections below are proposals awaiting explicit approval.

## Decisions and scope

| Gate | Recommendation | Required interpretation / outstanding conditions |
|---|---|---|
| **P1 local engineering acceptance** | **GO** | Mode, role continuity, API/artifact boundaries, functional regressions and preservation pass. This accepts the bounded engineering implementation, **not** the unresolved dependency security risk or hosted deployment |
| **P1 repository commit** | **CONDITIONAL GO** | Review the exact cumulative file set and explicitly authorize the commit. Resolve/explicitly disposition braces with an accountable owner; current strict audit CI remains red. No clean security/release completion may be asserted from a snapshot commit. This is not commit permission |
| **Presentation candidate deployment** | **NO-GO** | Security disposition, verified project settings, exact clean candidate SHA, staging/rollback and separate deployment authorization are absent. Public alias deep links/release metadata fail |
| **P2 local implementation** | **CONDITIONAL GO** | The bounded plan is implementable. Before execution: explicit P2 approval and security disposition; before P2b: local PostgreSQL version/driver/test-target/privilege qualification. Hosted presentation success is **not** a dependency of isolated local contracts. Nothing starts automatically |
| **Institutional production release** | **NO-GO** | Institutional identity/current membership, tenant-scoped persistence, privacy/policy, shared backend, concurrency, operational/restore/release evidence remain unverified |

**P1 dependency-security gate remains FAIL**: one high braces advisory across five package entries, no patch or approved exception. Therefore not every possible P1/release gate is satisfied. Functional engineering GO must not be presented as security PASS. Owner approval is separate from a recommendation at every gate.

## Cumulative diff review

Reviewed tracked changes against HEAD and all untracked additions, including documentation/evidence and the lockfile's resolved-package changes. Existing backend application/solver/contracts, SQLite contents, branding and theme were not modified by the cumulative P1 diff. Relevant unchanged authorization call sites were also traced.

| Area / cumulative files | Assessment and evidence |
|---|---|
| `src/config/app-mode.ts`, `runtime-config.ts`, Vite and `.env.example` | One validated immutable mode; environment files then process-environment precedence. All builds reject sandbox, including development NODE_ENV/Vite mode. Ordinary builds default to unavailable institutional access; explicit presentation target rejects contradictions. Browser query/storage never selects a mode. Documented development legacy behavior is intentionally more permissive only within sandbox, without backend authority |
| `preview-session.ts`, `presentation-sample.ts`, `RouteGuard.tsx` | P0 schema/key/eight-hour expiry preserved; presentation uses the same lazy versioned sample. Institutional rejects preview identity before role screens and cannot load sample data. No new institutional sign-in claim |
| Academic/scheduling/publication/sample-calendar/generic clients, three direct-fetch page sites | Live requests guarded before network; raw mutation sites use the common wrapper. Immutable mode prevents a browser preference from re-enabling clients. Samples never replace live API failures |
| AppShell/ProductScreen capability copy | Truthful central capability descriptions; no dashboard/nav redesign. Existing brand, touch targets and focus styles retained |
| `R1Presentation.test.tsx` | Positive agenda assertion retained and awaited after asynchronous date change. This repairs test synchronization; it does not weaken the expected content or accept an empty agenda |
| Build/release/preview scripts, `release-metadata.ts`, artifact server, `vercel.json` | Removed duplicate metadata writer in favor of one Vite emitter; preserves legacy mode field while adding capabilities/mode and truthful dirty state. Preview uses shared loopback static-server helper. Exact design-system rewrite covers an existing static client route; it does not expose protected APIs. API/static exclusions remain intact |
| Root/web manifests and lock | Patched Vitest/grpc/parser tree is justified by advisories and compatibility tests; no forced broad upgrade. Unused resolver removal avoids changing ESLint's required AJV 6. Full graph clean. Remaining braces not hidden |
| Four Python requirements, constraints, scanner, tests | Three qualified security targets pinned; OR-Tools pin unchanged. Scanner covers exact installed third-party union, verifies internal editable provenance, fails on incomplete/failed scans. Not a complete platform/hash lock; future deployment image still requires its own scan |
| CI | Read-only token, checkout without persisted credentials, complete-tree/security/static/web/Python/build/artifact assertions. Full npm advisory job intentionally remains blocking; no ignore list, continue-on-error or exception mechanism. Hosted Actions execution is not claimed |
| Documentation and JSON/PNG evidence | Architecture corrected from placeholders to actual capabilities; old reports retained as dated snapshots. Evidence is not executable functionality. Repeated reports/local temporary screenshot paths are a maintenance/portability concern, not justification to delete history. Current review is the status index |

### Findings and bounded remediation in this review

1. **Medium, fixed — hosted HTTP gate could overstate success.** `scripts/verify-hosted-presentation.cjs` allowed a reported SHA to pass without an independently supplied approved SHA and allowed an HTML shell with no JS/CSS references. It also lacked focused tests. The verifier now fails these cases, bounds each request to 15 seconds, and exports its verification function without running network calls on import. Five local HTTP fixture tests cover missing/wrong SHA, missing application assets, dirty metadata and valid boundaries. `npm run test:security` includes them through the existing CI step. No HTTP test is labeled full browser proof.
2. **Low, fixed — contradictory current architecture text.** The architecture still described rate-limit enforcement as current while security documentation described it as planned. It now states the implemented gateway functions and future rate limiting accurately. Deployment guidance no longer calls the ordinary institutional-unavailable build a connected build.
3. **High, open — braces.** All three dependency paths remain; see the advisory decision section. This is the only currently scanned dependency advisory, not a newly introduced application authorization defect.
4. **Release blocker, open — hosted/settings evidence.** Actual project access is unavailable; role routes and release metadata fail publicly. Local emulation and an asset name do not establish deployed SHA/configuration.
5. **Non-blocking maintenance gaps.** Historical reports can contain superseded counts; follow this index/raw current evidence. Full Linux CI/image, manual screen-reader/participant testing and future hash-locked Python deployment are not established by local tests. Do not assert WCAG certification or production readiness.

No remaining new application regression, unguarded P1 mutation path or unrelated feature removal was identified in this bounded review. This is not a certification that all existing backend architecture is institution-ready. Current backend claim/UID authorization must still be replaced/extended by current-membership/tenant enforcement in later approved phases.

## P1 acceptance checklist

| Criterion | Evidence / result |
|---|---|
| Supported modes / legacy compatibility | Exhaustive resolver matrix + real artifact configurations; PASS. Development sandbox legacy behavior follows the approved matrix; distributable contradictions/sandbox reject |
| Safe build defaults / immutable mode | Ordinary institutional-unavailable artifact and explicit presentation artifact; no browser-selected privileged mode; PASS |
| Presentation consistency/read-only | All three roles use unchanged sample v1; clients reject before fetch; zero API traffic in browser checks; PASS |
| Institutional preview denial | Role guards + API no-fetch tests and forged role/storage/query browser checks at 390/1440; PASS. Real institutional login is not implemented |
| Backend independence | Gateway, Academic and Scheduling retain their own sandbox gates and Firebase identity/Administrator checks. Default production and client role headers/query reject; missing credentials fail closed; PASS in backend tests |
| P0 sessions | Refresh, role boundaries, invalid/future/expired sessions, mounted eight-hour expiry; existing tests and browser boundary checks; PASS |
| Metadata | Actual dist root contains `release.json`, legacy `mode`, `appMode`, capability/sample version and truthful source/dirty status; PASS locally. Current dirty artifact is not an approved clean commit |
| Direct routes/static/API | All four artifact test groups, three actual valid artifacts, nine rejected configs and repeated route fetches; design-system route included. Missing API/static paths remain non-HTML errors; PASS locally only |
| JavaScript quality | Lint and typecheck PASS; 664 frontend tests / 36 files; 8 security/tooling tests, zero skipped |
| Python quality | Ruff PASS; 105 backend tests using disposable databases; pip consistency PASS; existing Starlette/httpx deprecation retained |
| Security scanning | Python: pip-audit 2.10.1, 62 exact versions, zero findings/skips; PASS. npm graph PASS. Full npm audit **FAIL**, five high entries/one advisory |
| Responsive/keyboard/reflow | Fresh production-artifact browser matrix at 360/390/768/1024/1440, dialogs, focus, reduced motion, refresh, short height and native 200%; see final evidence. Automated interaction checks and inspected screenshots are not participant testing |
| Original data/history | Three hashes unchanged; immutable read-only → memory integrity/FK/payload verification. 604 checksums, zero errors; history/draft regression tests isolated; PASS |
| Hosted release/configuration | FAIL/BLOCKED; not substituted by the local results |

Both ordinary and presentation builds pass; existing >500 kB warning remains unsuppressed. No dependency reinstall/upgrade was necessary in this review: manifests/lock resolutions match the clean-install-qualified preceding baseline. CI syntax/policy and `git diff --check` pass locally. Exact fresh command exits, timings, output and browser records are in the evidence JSON. No skipped or unavailable hosted check is marked passed.

Preserved original SHA256 (before = after):

| File | SHA256 |
|---|---|
| `var/academic.sqlite3` | `4cd5f60de21bd365c914ac01e5be692b3bea1c7a56a7f17a76c6953ef8668738` |
| `var/scheduling.sqlite3` | `1848377cc9a9eb656e12b5e58436e81198fef92f18dd71c1fea2f6f8b482e400` |
| `var/backups/scheduling-before-s2b-20261018074057.sqlite3` | `9ec149413d69c1165b74a75e366fa262417c1ecbf41e7029fdd0d86ac96f395d` |

## Verified Skill Usage Evidence Matrix

Installed bundle provenance: `C:/Users/lenovo/.codex/plugins/cache/openai-curated-remote/build-web-apps/0.1.2/.codex-plugin/plugin.json`, OpenAI bundle 0.1.2, repository `https://github.com/openai/plugins`, MIT package metadata. This does not independently establish each upstream file's license/commit; upstream source commit is unavailable. All skill/rule files actually read this review have exact paths and SHA256 in the evidence, providing a reproducible content snapshot. Skill content is guidance, not proof that tests executed.

| Exact skill/source | Status, version and loading proof | Specific instructions used → ClassSync evidence | Limitations |
|---|---|---|---|
| `C:/Users/lenovo/.codex/plugins/cache/openai-curated-remote/build-web-apps/0.1.2/skills/react-best-practices/SKILL.md` | Installed, Vercel metadata 1.0.0; complete SKILL read this review; SHA256 `cc7d03309817f392c419a203e1bc1f1759ef94831f7dbedf39d91a35ac5bc86a` | `rules/bundle-conditional.md` and `rules/rerender-derived-state-no-effect.md` actually read: preserve lazy presentation import; review immutable derived capabilities instead of effect-based mode state → `presentation-sample.ts`, `app-mode.ts`, runtime/API tests and emitted graph | Selected rules only; no full 64-rule execution or Next.js/RSC patterns claimed |
| `C:/Users/lenovo/.codex/plugins/cache/openai-curated-remote/build-web-apps/0.1.2/skills/frontend-testing-debugging/SKILL.md` | Installed bundle 0.1.2; complete instructions read; SHA256 `03724620cf7e7de425b607a5492f572d867b1cf5d9c92c74bf50d057d7415e0b` | Production artifact → meaningful page → interaction → console/network/overflow/focus/refresh checks, separate screenshots from assertions; `production-artifacts.test.cjs`, hosted verifier tests and temporary role/browser helpers | Browser plugin/skill absent; existing bundled Playwright/Chrome used for application QA. CUA was used separately only to check existing Vercel dashboard access; it redirected to login |
| `C:/Users/lenovo/.codex/plugins/cache/openai-curated-remote/build-web-apps/0.1.2/skills/supabase-best-practices/SKILL.md` | Installed, Supabase metadata 1.1.0; complete SKILL read; SHA256 `cfc4da3ed47c14f4fb24c5b4db4be443fa200e12e71d674fb1270eecce87a302` | Actually read `references/lock-deadlock-prevention.md`, `lock-short-transactions.md`, `security-privileges.md`, `security-rls-basics.md`: consistent locks, short transactions/no network, least privilege, FORCE RLS → proposed P2b tests and retained P7 transaction protocol | **Design review only**, no database commands/schema/query implementation or Supabase hosting decision. Initial incorrect `rules/` paths failed; correct `references/` files were then loaded |
| Vercel Composition Patterns / Web Design Guidelines | Reference-only in the existing plan; no applicable installed full SKILL loaded | Preserve shared components/tokens and existing useful patterns during review | No executed-skill claim |
| [W3C modal dialog APG](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/), WCAG 2.2 target | Official reference, not a software skill. APG page read this review; WCAG target retained from project standards | Initial focus, containment, Escape, restoration/inert background and reflow criteria applied to browser verification | No complete WCAG or assistive-technology audit claimed |
| ITHUMCI handbook `C:/Users/lenovo/Downloads/ITAPPSD/WEEK 6/ITHUMCI_Detailed_Student_Book_Complete.pdf` | Prior project report identifies examined source; **not reloaded in this review** | Existing documented attention/mental-model/feedback/IA/accessibility mappings inform preservation of truthful status and role/task continuity | Reference to prior evidence, not a new handbook read or invented grading assessment |

No skill installation, remote script execution or app-generation workflow occurred.

## Braces decision options and recommendation

Fresh official [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) remains HIGH, affected `<=3.0.3`, patched version none. Fresh npm metadata remains 3.0.3. The [maintainer discussion](https://github.com/micromatch/braces/issues/84) and [advisory PR](https://github.com/github/advisory-database/pull/10132) record a dispute, not a patched dependency or approved exception.

One installed copy is reached through Tailwind 3.4.19 → chokidar 3.6.0; Tailwind → micromatch 4.0.8; and Tailwind → fast-glob 3.3.3 → micromatch, all ending at braces 3.0.3. Tailwind is a direct dev dependency. Compatible parent releases retain the copy. A chokidar-major override changes glob APIs and leaves the micromatch paths; it is not a complete fix. Tailwind 4 changes the PostCSS/CSS toolchain and requires separate qualification. No reviewed drop-in fork has been established. No forced update, advisory suppression or private patch was applied.

Residual exposure is build/CI availability if untrusted nested patterns reach glob APIs. Current globs are repository-controlled, not public scheduling input; the browser artifact excludes these tools. Those controls narrow exposure, but do not approve risk or erase the high finding. CI retains its full raw scan and fails normally. Previous bounded synthetic probes are not proof of a public exploit.

**Safest recommendation:** separately authorize a limited P1 toolchain-remediation investigation, first evaluating an official patched release if one appears, otherwise a compatible complete removal through a qualified parent/toolchain migration. Require actual CSS equivalence or reviewed visual differences, watcher/build behavior, complete graph/audit and full role regressions. Do not adopt an unmaintained renamed package simply to turn the audit green. An independently reviewed maintained fork requires explicit ownership and ongoing security review.

Temporary risk acceptance is an alternative **only if the owner explicitly chooses it**, names an accountable person, approves exact advisory/package/workspace scope, expiry/review date and controls, and separately authorizes a fail-closed policy mechanism retaining raw findings. Dates proposed in older reports are not approved. No mechanism/exception was implemented here. Do not treat “awaiting owner acceptance” as the only available option or as acceptance already granted.

## Read-only Vercel diagnosis

| Setting/evidence | Repository expectation | Actually verified hosted/project state |
|---|---|---|
| Root Directory | Repository root `.` | **Unknown**; no project settings access |
| Framework / install / build / output | Vite / `npm ci` / `npm run build:presentation` / `apps/web/dist` | **Unknown settings**, locally built outputs verified |
| Deployment SHA / immutable target | Exact owner-approved clean commit; release metadata match | **Unknown**; public `/release.json` 404 |
| Deployment alias | User-provided `class-sync-bhiv.vercel.app` | Alias responds at `/`; backing immutable deployment unknown |
| Rewrite metadata | Explicit role/auth/design-system routes → index; exclude API/static | Actual deployed routing metadata unavailable; known nested GETs return 404 |
| Mode | Presentation with compatible fields/sample v1 | Hosted exact enum unverified; prior browser behavior is connected preview, not local presentation |

Exact access blocker: no `.vercel/project.json`, Vercel CLI, VERCEL_TOKEN/project/org environment credential or Vercel connector is available. Environment checks printed presence booleans only, no values. Available browser inventory had no authenticated Vercel session. A read-only `https://vercel.com/dashboard` attempt timed out then visibly redirected to `https://vercel.com/login?next=%2Fdashboard`. No login/credential submission was attempted. Private Root Directory/build/output/deployment/alias/rewrite settings therefore cannot be compared as observed values.

Fresh public HTTP diagnostic: homepage, main JS/CSS, favicon and manifest 200; known role/preview/design-system paths and `/release.json` 404; missing API/asset/unknown paths non-HTML 404. Font request timed out under the bounded verifier and is **NOT VERIFIED**, not classified as a 404 or silently retried to PASS. No approved clean candidate SHA exists, so diagnostic mode also reports `approved-commit-required`. Hosted verifier exits nonzero correctly. Existing prior public browser/refresh records remain historical; this review does not claim a fresh authenticated project or public browser release PASS.

Owner next steps: supply authenticated read-only project settings evidence (names/settings, never secrets), compare the expected root/preset/commands/output/mode/route metadata, then separately approve the exact commit and candidate/staging release only after the security decision. Verify staging and rollback before public alias promotion. On any authorized candidate, run the verifier with its independently approved 40-character SHA and actual three-role browser checks; compare `/release.json` and deployment metadata. A frontend flag never becomes backend authorization. No hosted setting was changed and no deployment was triggered.

## Bounded P2 acceptance plan — not implementation

### Dependencies and authority

1. **P2a:** identity contracts and isolated test/emulator adapters, without PostgreSQL or real account provisioning.
2. **P2b:** isolated local PostgreSQL tenant/membership foundation implementing those interfaces, synthetic identities only.
3. **P3a:** integrate cryptographically verified Firebase identity with the **current PostgreSQL membership** repository after institution-approved provisioning policy.
4. **P3b:** migrate remaining academic/scheduling repositories through separately approved dry runs, hash/count comparisons and rollback. No silent dual writes or authority switch.

PostgreSQL remains the future authoritative institutional academic/timetable store and membership authority. Existing SQLite stays intact; P2 does not import or migrate it. The intermediate PostgreSQL foundation is test-only until integrated authorization and later readiness gates pass. No browser role, Firebase projection or temporary claims-only membership authority fills the gap. No real institutional data enters the intermediate state.

### P2a: identity contract vertical slice

- **Entry:** explicit bounded P2 approval, reviewed interface scope and advisory disposition. A working public Vercel alias is not needed. Real pilot roster/invitation/approval policy can remain pending because inputs are synthetic.
- **Scope:** immutable verified-principal contract, tenant context, current-membership lookup interface, exactly Student/Teacher/Administrator role labels, denied/unavailable/error taxonomy, dependency injection for synthetic/emulator test adapters. Stable UID is distinct from academic person/enrollment IDs. Role grants and mutually exclusive/multiple-role institutional policy must not be guessed; test fixtures can exercise permitted grants without creating production policy.
- **Likely modules:** existing `packages/api-contracts/classync_contracts/scheduling_security.py` plus new identity contracts/tests and service adapter boundaries, only after approval. Do not rewrite OR-Tools or enable institutional UI.
- **Acceptance:** missing/bad/expired/revoked/wrong issuer/audience identity denied; verified UID alone never supplies tenant membership; forged client role/tenant/enrollment fields cannot grant access; all three role labels and unknown-role denial tested. Emulator/test identity adapters cannot load or authorize in production settings. No live Firebase configuration/rules/provisioning changes; no adapter fallback after verification failure. P0/presentation regressions stay green.
- **UX:** no new login fiction; existing unavailable state remains. Errors use existing truthful accessible status/denied states; keyboard/focus/role navigation unaffected. Browser smoke validates unchanged public presentation.
- **Rollback/DoD:** unused adapter/contract feature can be reverted without data changes. Contract and backend security tests pass; production entry-point exclusion tested. Owner approves this exit before P2b. Estimate 2–4 implementation days, medium risk, assuming no external policy wait.

### P2b: disposable PostgreSQL tenant/membership foundation

- **Entry:** P2a accepted, separate explicit local DB/schema/driver authorization, approved disposable database target and least-privilege setup. Qualify a supported PostgreSQL major, Python 3.12 driver/pool/test-tool compatibility and candidate-provider support before pinning a production target. Existing client version is not proof of server/provider compatibility. No cloud provider or paid resource is selected here; unresolved production provider choice must stay explicit.
- **Scope:** isolated tenant, membership/status/revision and role-grant records with stable IDs, composite tenant keys, uniqueness/FKs and explicit revocation. No academic/scheduling migration, historical import or production provisioning. Retain current SQLite repositories and production unavailable frontend.
- **Proposed modules:** new local PG repository/test-fixture modules under the existing service/contracts structure; separate local test dependency/qualification record. This document creates none of them.
- **Acceptance:** real isolated PostgreSQL integration tests with two tenants, two UIDs and all three role types; cross-tenant reads/writes denied; inactive/revoked memberships denied; grants cannot be self-assigned; stale revisions reject; two-connection concurrent membership edits have defined revision outcomes. Constraints tested against duplicates/orphans/invalid roles. Missing DB/network failure must deny/unavailable, not fallback to synthetic identity or another membership store.
- **Isolation:** test harness must reject any DSN outside the approved local test namespace and every preserved SQLite path; no public bind or automatic import. Migration/setup privileges are separate from runtime. Runtime is non-superuser, non-owner, no BYPASSRLS/schema DDL. FORCE RLS, parameterized queries and transaction-local trusted tenant/actor context; absent context denies. Pool reuse/rollback must clear context. RLS supplements current-membership checks; no browser-supplied context is trusted.
- **Transactions:** common tenant guard and deterministic membership-row order; short transactions, no network inside locks. Test atomic grant/revocation/audit revision and conflict outcomes. Publication transaction ownership stays future Scheduling `PublicationCoordinator`; P2 does not change local publication behavior or implement the full outbox.
- **UX:** current unavailable/dependency errors are truthful and announced; presentation stays available without PG. No user-visible partial migration or technical DSN selector. Existing five-width/reflow/focus regression applies; a backend-only change must explain any UI non-applicability.
- **Rollback/DoD:** destroy only the explicitly disposable test database through approved local tooling; originals remain hash-identical. Identity-contract, PG isolation/concurrency/privilege, existing backend/frontend/artifact and preservation tests pass. No real accounts, schema migration of originals or institutional authority is enabled. Estimate 3–6 implementation days, high risk, excluding permissions/version qualification.

### Future Firebase database coursework feature — separate authorization

Firebase Authentication, Cloud Firestore, Firebase Realtime Database and existing SSE are distinct capabilities. Authentication/SSE do **not** demonstrate database-course compliance. [Firebase's official comparison](https://firebase.google.com/docs/database/rtdb-vs-firestore) distinguishes document/collection Firestore with snapshot listeners from the JSON-tree Realtime Database with its own listeners/rules. Select the actual required product from the institution's final rubric; do not implement both speculatively. The existing course PDFs do not establish that final-project requirement, so product/assessment criteria remain **unverified** and are not a blocker to contract-only planning.

Optional later feature: minimal per-user notification/read-state projection. PostgreSQL owns notifications, acknowledgments and all academic/timetable data. A committed PostgreSQL outbox projects only tenant/UID-scoped IDs, type, version/cursor and timestamps—no names, enrollment, timetable payloads or private text. Firebase is rebuildable, never authority for membership or publication.

Use Firestore `onSnapshot` on a scoped collection **or**, if the rubric requires that separate product, Realtime Database `onValue`/child listeners on a scoped JSON path. Server-only projection writes; clients read only their approved tenant/UID and acknowledge through the authorized Gateway → PostgreSQL → outbox. Rules/IAM and revocation-lag/retention approval are future explicit work; stale replicated membership cannot become authoritative. Before real data, define maximum revocation delay and offline-cache policy; until enforceable, keep the feature synthetic/emulator-only. Retention of seven days is only a proposal, not approved policy.

Events are idempotent/version ordered; reconnect refetches authoritative PG data; projection outages show stale/unavailable notification state without inventing publication failure/success. Emulator acceptance: cross-tenant/UID denied reads, forged writes, revoked access, duplicate/out-of-order delivery, reconnect, expiry, missed-event replay and PG availability during Firebase outage. This feature is not P2 implementation or an excuse to enable a Firebase database now.

### Owner decisions and release separation

Required now: advisory remediation/exception choice, accountable security owner, review/commit scope approval, any future P2 authorization. Required before P2b: local test DB/version/driver/privilege qualification. Required later: institutional pilot/data permission, provisioning and roster authority, approval policy, cloud budget/hosting, retention/recovery/privacy, Firebase rubric/product and release/cutover authorization. None is silently marked approved. Public Vercel settings/rollback evidence blocks presentation deployment, not the logical design of P2a. All production data/auth/release prerequisites still block institutional release.

## Review artifacts and stopping point

Changes made in this review are limited to the hosted verifier, five regression tests and their existing security command; two factual documentation corrections; the reconciled plan status note; and this report/evidence. No app runtime source, dependency resolution, backend business logic or database changed. Exact review-only file hashes and all cumulative paths are in the evidence. Screenshots remain in the temporary QA directory and earlier repository evidence is preserved. Native zoom/keyboard checks are engineering assertions, not human usability or screen-reader certification.

| Review-only file | Purpose |
|---|---|
| `scripts/verify-hosted-presentation.cjs` | Require approved SHA and application JS/CSS; bound HTTP requests; expose testable read-only verifier |
| `scripts/tests/hosted-verification.test.cjs` | Five focused positive/negative local HTTP tests |
| `package.json` | Include those tests in the existing security/CI command |
| `docs/architecture.md` | Correct current versus planned rate limiting and independent authorization wording |
| `docs/infrastructure/vercel-backend-deployment-plan.md` | Correct ordinary-build versus local-sandbox API description |
| `docs/production/reconciled-master-plan.md` | Link current gates, correct Python scanner status and separate hosted/P2 dependencies |
| `docs/production/p1-cumulative-review-and-p2-readiness.md` | This cumulative review, skill matrix, acceptance/gates and bounded plan |
| `docs/production/p1-cumulative-review-evidence.json` | Per-file cumulative/review-only hashes, actual checks and preservation evidence |

Stop here. Await explicit owner decisions before a commit, release or P2 implementation action.

### Local production-artifact screenshots

These are fresh local screenshots, not evidence of a new Vercel deployment. Interaction assertions, native zoom, all role/width captures and console/network results are recorded separately in the evidence JSON.

![Student, 390px](/C:/Users/lenovo/AppData/Local/Temp/classsync-p1-readiness/browser/p1-student-390.png)

![Administrator, 1440px](/C:/Users/lenovo/AppData/Local/Temp/classsync-p1-readiness/browser/p1-administrator-1440.png)
