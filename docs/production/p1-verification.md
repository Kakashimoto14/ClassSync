# Bounded local P1 verification — PASS

21 October 2026. HEAD remains `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`, main. Initial working tree was clean; no applicable AGENTS.md was found in the repository/checked parents. All changes below are uncommitted P1 work. No database migration, original database write, solver/authentication change, Firebase settings change, dependency upgrade, commit, push, deployment or provisioning occurred. P2 was not started. No synchronized sources/ file was edited.

## Checkpoint results

| Checkpoint | Changed modules | Executed checks / result |
|---|---|---|
| 1 — operating mode | app-mode resolver/tests, runtime-config, Vite integration, before-edit execution contract | 442 matrix/configuration tests and typecheck: PASS |
| 2 — boundaries | Preview/sample/sandbox compatibility exports, route guard, academic/scheduling/calendar/publication/generic clients and raw fetch sites; shared truthful descriptions | Targeted 472 tests; final full frontend suite and backend gates: PASS |
| 3 — release | Vite release emitter, build/preview scripts, shared static server, artifact tests, package script and Quality CI | 4 actual-build/HTTP test groups, 9 rejected configs and 3 valid artifact variants: PASS locally. GitHub Actions and public deployment were not triggered |
| 4 — preservation | Backend boundary tests, plan/decision/advisory registers, architecture/security/R1 corrections, evidence | Full available regression and browser checks below: PASS. Security/cloud limitations remain explicit |

The definitive before-edit configuration matrix, precedence, file scope, acceptance criteria and rollback are in `p1-execution-contract.md`. Revised P1–P10 sequence, owner decisions, future publication transaction/Firebase database boundaries and exact skill-use evidence are in `reconciled-master-plan.md`.

## Acceptance evidence

| Command/check | Actual result |
|---|---|
| `npm run lint` | PASS, zero warnings |
| `npm run typecheck` | PASS |
| `npm run test:web` | PASS, 36 files / 664 tests, final run 156.54 s |
| `.venv/Scripts/python.exe -m ruff check services packages` | PASS |
| `.venv/Scripts/python.exe -m pytest` | PASS, 92 tests / 77.56 s; existing Starlette/httpx TestClient deprecation |
| `.venv/Scripts/python.exe -m pip check` | No broken requirements; this is not a vulnerability scan |
| `npm run build` | PASS, institutional default |
| `npm run build:presentation` | PASS, explicit read-only presentation |
| `npm run test:artifacts` | PASS, 4 top-level groups / 75.89 s final run; zero skipped checks |
| `git diff --check` | PASS; Windows LF/CRLF notices are not whitespace failures |
| Protected source/asset/lock diff | No changes to Academic/Gateway/Scheduling application code, API contracts, sample data, public artwork, theme.css, Firebase modules or package-lock.json |

Pytest used environment database paths under disposable `C:/Users/lenovo/AppData/Local/Temp/classsync-p1-regression-1b4712453ed746369454ca91cadb2a15`, plus existing tmp_path fixtures. Original databases were never passed to services/tests. No weakened assertions or changed solver limits.

Initial failures were investigated: one existing calendar lazy-load expectation timed out while builds competed with the frontend suite; a new institutional-route mock referenced an import before initialization. The mock was corrected using dynamic import; its assertions stayed intact. The calendar test passed unchanged in isolation and subsequent full runs. Serial final suites passed. Existing CPU-sensitive solver tests should not run alongside build-heavy workloads.

### Operating/security contract

Only `presentation | sandbox | institutional` is accepted. Vite loadEnv precedences are preserved, with process environment overriding files. Any build command rejects sandbox, including development NODE_ENV and Vite mode. Presentation target rejects contradictory flags instead of overriding them. Browser storage/query/preview role never selects operating mode. Legacy role/sample true remains a safe read-only presentation alias on builds; explicit contradictory true/false rejects.

Presentation forces the unchanged versioned bundled sample and blocks live requests before fetch/streaming, including writes. Live failure never triggers sample substitution. Institutional mode denies preview roles, displays honest unavailable access and sends no live requests. Sandbox remains local development only and all server gates remain independent. Frontend capabilities never grant backend authorization. P0 storage keys/schema, eight-hour expiry, explicit switching and Exit remain intact.

Release metadata retains schemaVersion 1 and presentation `mode: "read-only-presentation"`, sampleVersion, commit and dirty fields. It adds `appMode` and capabilityVersion 1; ordinary artifacts also emit metadata into the actual output directory. Supplied SHA must match checkout when available. Local manifests truthfully report dirty=true; clean CI asserts false and exact GITHUB_SHA. No local dirty artifact is represented as a committed release.

Artifact tests use real Vite builds and the repository Vercel rewrites, with known role/auth routes fetched twice for direct navigation/refresh. JS, logo, favicon, font and manifest serve real assets. Missing API/assets remain non-HTML 404; POST/PUT/DELETE to a missing publication API remain 404. Invalid modes/flags, conflicting presentation target and mismatched SHA reject. Temporary artifact root from final tests: `C:/Users/lenovo/AppData/Local/Temp/classsync-p1-artifacts-qBSZ9L`. Local emulation is not hosted Vercel certification.

## Browser and accessibility

Browser plugin/skill was unavailable; used existing bundled Playwright and installed Chrome 155 without installation. Flow: welcome → explicit role selection → Home → refresh → Schedule/date selection/details, or Admin Conflict Center → sample calendar. Ephemeral loopback artifact servers were closed afterward.

All 15 combinations (three roles × 360/390/768/1024/1440 widths) passed meaningful content/title checks, no framework overlay, loaded logo assets, no horizontal overflow, no relevant console/page errors and zero API requests. Refresh retained the same preview session without extending it. Student/Teacher dialogs had names, initial focus, inert background, seven Tab containment checks, Escape close and focus restoration. Admin write controls were absent from the read-only tool state.

Additional checks passed institutional forged storage/query/role denial across three roles at 390/1440 and refresh; invalid and expired sessions; mounted eight-hour expiry; and a 390×400 dialog with reachable Close action. Changed institutional screen contrast: paragraph 4.97:1 and title 15.55:1 against white, with visible solid focus outline.

Native 200% Chrome zoom was verified using a temporary isolated QA extension calling tabs.setZoom/getZoom: result 2, innerWidth 1424→712, DPR 1→2, visualViewport.scale 1 and CSS zoom 1. Card/title/text/action bounds fit; keyboard action stayed reachable. No user profile or application source was changed. Initial preference-only/extension-startup probes did not apply zoom and were not counted as passes. An isolated instance needed extension support enabled. CDP viewport screenshot was used because Playwright's clipped capture at native browser zoom showed only part of the physical viewport; DOM bounds and full native capture verified reflow.

Structured evidence: `p1-browser-evidence.json`. Scripts, JSON and PNGs: `C:/Users/lenovo/AppData/Local/Temp/classsync-p1-browser/`. Screenshot names include `p1-student-390.png`, `p1-teacher-390.png`, `p1-administrator-1440.png`, corresponding other widths, `p1-details-student-390.png`, `p1-schedule-student-390.png`, `p1-short-dialog.png`, `p1-institutional-390.png`, and `p1-native-200-percent.png`. Browser-tested presentation artifact is byte-for-byte identical to final apps/web/dist.

Prior baseline images remain at `C:/Users/lenovo/.codex/visualizations/2026/10/18/01a14e48-eb6b-7620-a8fa-0d5b6a108c65/p1-reconcile-student-390.png` and matching other role/width files. This phase preserves dashboard design. These engineering checks are not human screen-reader testing, participant usability research, a complete contrast audit or WCAG certification.

## Performance, vulnerabilities and preservation

An intermediate object-valued injected config prevented constant folding and grew main JS to approximately 611.95 kB. Injecting the validated mode literal and deriving compatibility booleans directly corrected it. Final ordinary main: 519.34 kB / 154.27 gzip, baseline 518.64 / 154.09. Final presentation main: 524.26 / 155.60, baseline 523.67 / 155.47. CSS stays 84.64 / 15.87; sample chunk stays 31.91 / 2.00. Existing 500 kB warning remains unsuppressed. These are bundle-size measurements, not Web Vitals or cloud performance results.

Fresh emitted presentation graph: 173 modules, zero Firestore/compat/grpc or listed affected build/test modules. Dependency audit still reports 14 affected-package entries (2 critical, 9 high, 3 moderate), arising from seven distinct GHSA advisories. No upgrade/risk acceptance occurred. No public exploit chain was established; that is not a clean security finding. Python scanners pip_audit/safety are unavailable, so Python vulnerability status is unknown. Full triage and immediate response/release gates: `dependency-advisory-register.md`; raw npm evidence preserved separately.

All three SQLite SHA256 values match their before-edit contract, including schemas. Original handles were immutable/read-only, copied into memory for integrity/checksum checks. Academic: four periods/567 records/319 references/one calendar. Scheduling: 13 runs/12 immutable drafts/no existing published versions. Backup: six runs/six drafts. All 604 stored payload checksums passed; all integrity checks ok and zero FK errors. Full hashes and aggregate payload-hash evidence: `p1-database-preservation.json`.

## Final gates

- **Bounded local P1: PASS / GO for completion.** Required local acceptance checks pass, with explicit security/tooling limitations above.
- **P2 entry: NO-GO now.** Separate authorization required; identity/membership contracts and provider/driver/version qualification remain future work.
- **Institutional release: NO-GO.** Identity/current membership, shared persistence, privacy/policy/budget/hosting, advisory disposition/Python scan, staging/restore/rollback and hosted Vercel root/settings/SHA/deep-route checks remain gates. No VERCEL PASS is claimed.

## Exact changed-file inventory

Paths below are relative to `C:/Projects/ClassSync`. Existing work was preserved; initial worktree was clean. The source diff remains uncommitted for review.

| File | Reason |
|---|---|
| `.github/workflows/quality.yml` | Expose artifact checks and assert metadata in CI |
| `apps/web/.env.example` | Document canonical mode and safe legacy compatibility without changing actual settings |
| `apps/web/config/release-metadata.ts` | Compatible mode/version/commit/dirty release manifest |
| `apps/web/src/auth/preview-session.ts` | Preserve public/session APIs while deriving behavior from validated mode |
| `apps/web/src/components/layout/AppShell.tsx` | Shared truthful capability descriptions; no navigation redesign |
| `apps/web/src/config/api-boundaries.test.ts` | Mode, authorization-boundary or production-artifact regression coverage |
| `apps/web/src/config/app-mode.test.ts` | Mode, authorization-boundary or production-artifact regression coverage |
| `apps/web/src/config/app-mode.ts` | Single validated operating mode and truthful frontend capabilities |
| `apps/web/src/config/institutional-routes.test.tsx` | Mode, authorization-boundary or production-artifact regression coverage |
| `apps/web/src/config/runtime-config.ts` | Single validated operating mode and truthful frontend capabilities |
| `apps/web/src/lib/academic-api.ts` | Block connected API calls before fetch outside local sandbox |
| `apps/web/src/lib/presentation-sample.ts` | Preserve public/session APIs while deriving behavior from validated mode |
| `apps/web/src/lib/publication-api.ts` | Block connected API calls before fetch outside local sandbox |
| `apps/web/src/lib/sample-calendar-api.ts` | Block connected API calls before fetch outside local sandbox |
| `apps/web/src/lib/scheduling-api.ts` | Block connected API calls before fetch outside local sandbox |
| `apps/web/src/pages/AcademicCalendarEditor.tsx` | Block connected API calls before fetch outside local sandbox |
| `apps/web/src/pages/AcademicFixtureImport.tsx` | Block connected API calls before fetch outside local sandbox |
| `apps/web/src/pages/ProductScreenPage.tsx` | Shared truthful capability descriptions; no navigation redesign |
| `apps/web/src/pages/PublicationPanel.tsx` | Block connected API calls before fetch outside local sandbox |
| `apps/web/src/routes/RouteGuard.tsx` | Institutional access unavailable regardless of preview-selected role |
| `apps/web/src/services/api-client.ts` | Block connected API calls before fetch outside local sandbox |
| `apps/web/vite.config.ts` | Resolve configuration before serving/building; emit immutable mode and release metadata |
| `docs/architecture.md` | Correct stale implementation and release assumptions |
| `docs/production/dependency-advisory-register.md` | Execution/decision/security/verification evidence; no application data |
| `docs/production/dependency-audit-2026-10-21.json` | Execution/decision/security/verification evidence; no application data |
| `docs/production/p1-browser-evidence.json` | Execution/decision/security/verification evidence; no application data |
| `docs/production/p1-database-preservation.json` | Execution/decision/security/verification evidence; no application data |
| `docs/production/p1-execution-contract.md` | Execution/decision/security/verification evidence; no application data |
| `docs/production/p1-verification.md` | Execution/decision/security/verification evidence; no application data |
| `docs/production/reconciled-master-plan.md` | Execution/decision/security/verification evidence; no application data |
| `docs/releases/r1-public-presentation.md` | Correct stale implementation and release assumptions |
| `docs/security.md` | Correct stale implementation and release assumptions |
| `package.json` | Expose artifact checks and assert metadata in CI |
| `scripts/build-presentation.cjs` | Explicit build target and shared Vercel-config static artifact serving |
| `scripts/lib/artifact-server.cjs` | Explicit build target and shared Vercel-config static artifact serving |
| `scripts/preview-presentation.cjs` | Explicit build target and shared Vercel-config static artifact serving |
| `scripts/tests/production-artifacts.test.cjs` | Mode, authorization-boundary or production-artifact regression coverage |
| `services/scheduling/tests/test_mode_boundaries.py` | Mode, authorization-boundary or production-artifact regression coverage |
