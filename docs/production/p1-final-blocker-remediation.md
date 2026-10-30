# P1 final blocker remediation and release verification

21 October 2026. This is a bounded continuation of P1, not P2. The earlier gate-closure report/evidence remain unchanged historical records; this report supersedes their AJV disposition. **Local security and hosted release are separate gates.**

## 1. Exact starting state

- Branch `main`, HEAD `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`. The worktree was already dirty with the mode/release implementation and preceding 23-file security closure. Every prior closure-file hash matched its recorded evidence before editing (the evidence file excludes its own self-referential hash). No reset or checkout was performed.
- Task-start source hashes, complete status, original database hashes and dependency tree were saved under `C:/Users/lenovo/AppData/Local/Temp/classsync-p1-final/`. No applicable AGENTS.md was found in the repository or checked parent locations. Synced `sources/` files remain read-only.
- Node 22.23.1, npm 10.9.8, Python 3.12.14, Vite 6.4.4, Vitest 4.1.11, Tailwind 3.4.19. npm lockfile v3 and the four Python service requirements/security constraints remain the dependency mechanisms.
- Reconfirmed initial tree failure: `@hookform/resolvers@5.9.1` optionally expects AJV `^8.12.0`, but sees ESLint's AJV 6.15.0. Initial registry audit confirms five high affected-package entries from one braces advisory, no critical/moderate findings. Python scan was rerun rather than trusting the previous clean result.
- Before any tests, all three original SQLite/backup hashes matched the preceding report. Full backend tests use newly created disposable paths, not `var/`.

Current raw results and the exact task delta are in [p1-final-blocker-evidence.json](p1-final-blocker-evidence.json). The preceding `p1-gate-closure-evidence.json`, report, saved screenshots and all prior functional/security work are retained.

## 2. Braces root cause and disposition

**UNRESOLVED — not ignored, not risk-accepted, not declared fixed.**

[GHSA-vfj7-8cjw-p6xm / CVE-2026-93687](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) is high severity: deeply nested patterns can exhaust recursive AST processing. The current advisory range is `<=3.0.3`, with no patched release listed. Fresh npm metadata also reports latest braces **3.0.3**. Downgrading within that range would not fix it.

There is one resolved vulnerable copy at `node_modules/braces`, reached by all three paths below:

| Dependency path from web workspace | Installed versions | Exposure |
|---|---|---|
| Tailwind → chokidar → braces | 3.4.19 → 3.6.0 → 3.0.3 | Development/watch glob handling |
| Tailwind → micromatch → braces | 3.4.19 → 4.0.8 → 3.0.3 | Build/watch pattern handling |
| Tailwind → fast-glob → micromatch → braces | 3.4.19 → 3.3.3 → 4.0.8 → 3.0.3 | Production build-time content expansion |

Tailwind is a direct dev dependency; all others are transitive. The five npm entries are these packages, not five distinct advisories. Development dependencies execute in CI and production builds even when absent from browser runtime. Tailwind's installed `lib/lib/content.js`, CLI build plugin and watcher import the real glob/matching libraries, so these are executable tooling paths, not merely unused manifest entries.

ClassSync's current content patterns are fixed in `apps/web/tailwind.config.ts`: `./index.html` and `./src/**/*.{ts,tsx}`. No public arbitrary-pattern endpoint or request-derived glob input was found. This narrows demonstrated application exposure; it does not make the vulnerable library safe for untrusted patterns. The production browser graph is checked separately. A bounded synthetic probe of compile/expand in isolated Node child processes reached the four-second timeout and was terminated; it did not establish a deterministic RangeError and is **not** counted as a passing test or a proven public exploit. No probe was sent to ClassSync or Vercel.

### Upstream and compatibility investigation

- Latest Tailwind 3 release remains 3.4.19; latest micromatch remains 4.0.8 with `braces ^3.0.3`; latest fast-glob remains 3.3.3 with `micromatch ^4.0.8`. A compatible parent update cannot currently remove this copy.
- Latest chokidar 6.0.0 has no braces dependency and requires Node >=22.22, satisfied by this workstation. Nevertheless [the upstream major changes remove glob support](https://github.com/paulmillr/chokidar#upgrading); blindly overriding Tailwind 3's watcher changes its contract. More importantly, the two micromatch paths remain, so that override alone does not close the finding.
- The audit proposes Tailwind 4.3.3 as a semver-major fix candidate. Its separate `@tailwindcss/postcss` package brings node/oxide tooling and a different plugin integration. ClassSync currently configures Tailwind 3 directly as a PostCSS plugin and uses its TypeScript configuration. This is a styling/build migration requiring output and watch-mode qualification, not a safe transitive pin. No Tailwind major was installed.
- No drop-in patched braces release, compatible parent removal or reviewed replacement API was established. No invented version, renamed vulnerable package, advisory exclusion, force update or peer suppression was used.

Owner alternatives: (a) wait for and qualify an upstream patched release; (b) separately authorize an isolated Tailwind-major/toolchain remediation with CSS, plugin, watcher and all-role regressions; (c) separately review a maintained security patch/fork with all public APIs and depth/resource bounds, ongoing ownership and honest scanner treatment; or (d) explicitly decide a time-bounded risk exception with named owner, trusted-input restrictions and expiry. Only the owner can choose/approve an exception. Current CI still fails the advisory gate; no exception exists.

## 3. AJV resolution

**FIXED by removing an unused optional-peer declarer, not by upgrading AJV.**

The installed resolver package declares AJV `^8.12.0` optional, for its separately exported AJV adapter. ESLint 9.39.5 and eslintrc require AJV 6; changing their resolved AJV to 8 would violate their API contract. Repository searches found no `@hookform/resolvers`, `zodResolver` or `ajvResolver` use in any application/shared source or build script—only the web manifest declaration. No feature depends on this package.

Removed only the unused direct `@hookform/resolvers` dependency. npm also pruned its now-unused `@standard-schema/utils@0.3.0`. Compared with the preceding full dependency tree, there are **no added versions and no changed surviving versions**. AJV remains 6.15.0 for its actual ESLint consumers. No AJV override, new unnecessary AJV runtime dependency or optional-peer suppression was introduced.

`npm ls --all` now exits zero with no invalid, missing or extraneous nodes. A fresh real `npm ci --ignore-scripts --no-audit --no-fund` completed successfully (412 packages). Lint and the full frontend suite pass on that clean install. CI now runs `npm ls --all` before the existing strict vulnerability audit so this class of dependency inconsistency remains visible. No application imports or UI were changed.

## 4. Vercel root cause analysis

Target: `https://class-sync-bhiv.vercel.app/`. All requests and browser interactions were read-only; no hosted write action or settings change occurred.

| Classification | Evidence | Disposition |
|---|---|---|
| **A — repository/configuration defect** | Root `vercel.json` already declares Vite, `npm ci`, `npm run build:presentation`, `apps/web/dist`, and explicit SPA route-prefix rewrites. Vite uses root-relative assets; React Router owns role paths. API/static prefixes are not caught by the frontend rewrites | No proven source defect; configuration left unchanged |
| **B — local artifact defect** | Ordinary and presentation builds emit `release.json` directly in the actual output directory. Existing tests exercise real builds, metadata, direct role routes, refresh, static resources and missing API paths | Verified by the fresh artifact suite; see results below |
| **C — hosted settings defect** | Actual project Root Directory/build/output/environment values cannot be read without authorized project access. No project link/credential is available; the prior unauthenticated project query returned 403 | **Unverified**, not asserted as the cause. Owner must inspect settings read-only |
| **D — hosted artifact stale/different/unverified** | Public JS remains `/assets/index-CbQh0kvf.js`; `/release.json` is 404; Student/Teacher make unavailable live requests, while local presentation blocks all such requests | Demonstrably different from the intended local presentation behavior. Earlier-build age/commit cannot be proven; SHA remains **unknown** |

Fresh hosted observations:

- `/` returns 200. Client-side entrance and role selection work.
- `/student/dashboard`, `/teacher/schedule`, `/admin/dashboard`, `/dev/role-preview` return 404 plain text on direct navigation. Actual browser refresh after selecting each of the three roles also returns 404.
- `/release.json` returns 404 at the correct expected path. No alternate SHA was invented from asset names or old GitHub deployment history.
- Student and Teacher issue `GET /api/v1/timetables/periods`, which returns 404; their Home displays a load error. Administrator displays the connected scheduling prompt, not the local frozen-sample overview.
- Main JS/CSS, Inter, favicon sizes and manifest return 200. Unknown route, missing asset and API path retain 404 rather than an HTML success response.

[Vercel's Vite SPA documentation](https://vercel.com/docs/frameworks/frontend/vite#using-vite-to-make-spas) requires explicit deep-link handling. The existing repository implementation uses that mechanism scoped to known frontend prefixes so missing API routes remain errors. Local emulation does not prove that hosted project settings consumed it. No rewrite widening or application workaround was introduced for a hosted discrepancy.

**Hosted release verification remains FAIL/BLOCKED independently of the P1 local security gate.** Proving resolution requires authenticated settings inspection and, if this reviewed configuration/artifact is not deployed, a new separately authorized staging/deployment followed by actual public checks. No deployment was performed here.

## 5. Exact changes and critical self-review

| File | Purpose |
|---|---|
| `apps/web/package.json` | Remove unused resolver dependency causing optional AJV mismatch |
| `package-lock.json` | Deterministically prune that package and its unused helper; retain surviving versions |
| `.github/workflows/quality.yml` | Add strict complete-tree verification before the existing unsuppressed advisory check |
| `docs/production/dependency-advisory-register.md` | Record current AJV fix and unchanged braces finding; preserve previous triage |
| `docs/production/p1-final-blocker-remediation.md` | This evidence-based continuation report |
| `docs/production/p1-final-blocker-evidence.json` | Fresh audit, tree, browser, artifact, hosted and preservation evidence, exact task-delta hashes |

No application, auth, mode, solver, validator, API contract, database, branding, theme, router or deployment configuration source changed. No source from `sources/` was edited. The full current Git diff still contains prior P1 work; the machine-readable inventory isolates this task's delta using the saved task-start hashes. Previous closure evidence/reports/screenshots remain historical and unchanged.

Review checks cover no security exceptions/continue-on-error, no lost features/imports, lock resolution, actual emitted browser graph, CI parser/policy, existing mode/server gates and data preservation. No security control/test assertion was weakened. The npm audit gate remains red honestly. Initial restricted npm metadata access returned EACCES; the authorized read-only retry succeeded, so the failed attempt was not counted as a clean query.

## 6. Fresh verification results

| Command / area | Result |
|---|---|
| Fresh `npm ci --ignore-scripts --no-audit --no-fund` | PASS, 412 packages installed; no force or legacy-peer-deps |
| `npm ls --all` | PASS, no graph problems; AJV peer blocker resolved |
| `npm audit --json` | FAIL, five high entries / one unresolved braces advisory; zero critical/moderate |
| `npm audit --omit=dev --json` | PASS, zero findings; does not close the full gate |
| Isolated pip-audit 2.10.1 | PASS, 62 exact packages, zero findings/skips; all four service manifests covered |
| `pip check` | PASS |
| `npm run lint` / `npm run typecheck` | PASS / PASS |
| `ruff check scripts/security services packages` | PASS |
| `npm run test:security` | 3 passed, zero skipped |
| `npm run test:web` | 664 passed / 36 files; zero failed/skipped, 141.78s Vitest duration |
| Full backend `pytest` | 105 passed, zero failed/skipped, 87.09s; disposable database paths |
| Ordinary and presentation builds | PASS / PASS; main 519.95 / 524.87 kB, gzip 154.28 / 155.61 kB; existing chunk warning retained |
| All production artifact groups | 4 passed, zero skipped; nine rejected configs and three actual valid artifact variants; 73.85s Node-test duration |
| Production-artifact browser journeys | 15/15 passed: all three roles at 360/390/768/1024/1440; refresh, dates, details, logos, no overflow/errors/API requests |
| CI parsing and strict tree/audit assertions | PASS locally; hosted Actions NOT RUN |
| Hosted direct routes/refresh/release | FAIL; project settings and SHA unverified |
| Final preservation/diff review | PASS; original/backup hashes unchanged, 604 payload checksums, no FK/integrity error; task delta checked against start snapshot |

Existing warnings remain visible: deprecated whatwg-encoding; npm's newly reported ESLint 9 support/deprecation notice; Starlette/httpx TestClient deprecation; Vite's existing large-chunk warning when emitted. No broad ESLint/HTTP/test stack migration was undertaken to hide warnings. pip-audit's no-deps/hash-lock recommendation remains explicit; installed exact pins are scanned, but this is not a complete hashed deployment lock or a certification of a future Linux cloud image. No application test failure was hidden through repeated reruns.

The installed frontend-testing-debugging skill was read in full at `C:/Users/lenovo/.codex/plugins/cache/openai-curated-remote/build-web-apps/0.1.2/skills/frontend-testing-debugging/SKILL.md`. Browser plugin/skill is absent; existing bundled Playwright and installed Chrome are used. The role flow under test is entrance → explicit role selection → meaningful dashboard → schedule/details → refresh, with presentation no-API enforcement. React Best Practices SKILL.md in the same bundle was read; no React component edit or Next.js pattern was needed. No other executed-skill or human-participant/WCAG-conformance claim is made.

Browser checks also passed seven-Tab dialog containment, Escape/focus restoration, inert background, visible focus, short 390×400 Close access, invalid/expired session recovery and mounted eight-hour expiry. Forged storage/query/preview roles fail institutional access on all role routes at 390/1440 and after refresh. Native Chrome 200% is verified through tabs.setZoom/getZoom=2, DPR 1→2, width 1424→712, CSS zoom=1; the tested unavailable-access screen reflows and its keyboard action remains reachable. Reduced-motion preference is enabled for the role journeys. Sampled contrast remains secondary text 4.97:1, title 15.55:1 and rouge action 8.34:1. This is scoped engineering verification, not full WCAG certification or a manual screen-reader study.

The fresh browser presentation graph has 173 emitted modules, with zero matches for Firestore/grpc, the affected build/test tools, `@hookform/resolvers` or AJV. CSS SHA256 remains `3817d76d0ddb2a3799e3dfba586c4a125989414b38a9059c01603ae11cafcc50`. All protected runtime/branding/contract/service application files match their task-start hashes. The output `release.json` accurately records HEAD with `uncommittedChanges=true`, presentation mode, capability version 1 and sample v1. It is not represented as a clean deployable commit. Hosted Actions, operational cloud checks, Web Vitals and representative participant testing were **NOT RUN**.

## 7. Data preservation

Before and after SHA256 must match the following protected originals:

| File | Before = after SHA256 | Payloads / integrity / FK issues |
|---|---|---|
| `var/academic.sqlite3` | `4cd5f60de21bd365c914ac01e5be692b3bea1c7a56a7f17a76c6953ef8668738` | 567 / ok / 0 |
| `var/scheduling.sqlite3` | `1848377cc9a9eb656e12b5e58436e81198fef92f18dd71c1fea2f6f8b482e400` | 25 / ok / 0 |
| `var/backups/scheduling-before-s2b-20261018074057.sqlite3` | `9ec149413d69c1165b74a75e366fa262417c1ecbf41e7029fdd0d86ac96f395d` | 12 / ok / 0 |

Fresh immutable read-only SQLite handles were copied into memory for integrity, foreign-key and payload checksum checks. All **604** payloads pass with zero checksum errors. Original academic counts remain four periods/567 records/319 references/one calendar. Scheduling retains 13 runs/12 drafts; backup retains six runs/six drafts. No original schedule was published or modified. Existing persistence/conflict/history tests ran in a disposable database directory recorded in the evidence. No PostgreSQL or migration work occurred.

## 8. Remaining risks

| Risk | Severity / exposure | Mitigation and owner action |
|---|---|---|
| Braces recursive-pattern DoS | High; reachable tooling, not demonstrated from current public inputs; present in build/CI | Trusted current globs, minimal read-only CI permissions, no public dev server; owner must select compatible upstream fix, separately reviewed toolchain/patch work, or explicit time-bounded exception. **Still unresolved** |
| Unsupported/deprecated tooling notice | Maintenance risk; clean installs warn about ESLint 9 support status | Track supported toolchain migration separately, without claiming an additional scanner finding or upgrading blindly |
| Hosted routes/metadata/backend mismatch | High release reliability; observed 404/load errors | Authenticated project-settings review, approved candidate/staging/rollback and later authorized deployment; no local fallback can prove hosted closure |
| Institutional readiness | Critical before real institutional data | Production identity/current membership, authorized durable backend, tenant/data/privacy and operational prerequisites remain unverified; preserve institutional unavailable access |

No risk exception is approved by this report. Security/release owners remain unassigned where the product owner has not designated accountable people.

## 9. Required owner actions and safe reproduction

Minimum next security action: select one of the braces alternatives in section 2. A risk exception would need explicit scope, responsible owner, expiration and compensating-control evidence; this task does not create one or alter CI to accept it. A toolchain migration/maintained fork requires separate bounded review because it changes build APIs and CSS risk. P2 is not a workaround for this P1 gate.

Hosted owner checklist, without implying authorization to execute deployment now:

1. Inspect Vercel project `class-sync-bhiv` read-only: linked repository/branch, current deployment SHA, Root Directory, framework, install/build/output overrides, mode flags and deployment alias. Share configuration names/settings, never secret values. Compare with root `.`, Vite, Node 22, `npm ci`, `npm run build:presentation`, `apps/web/dist`.
2. Confirm canonical `VITE_CLASSSYNC_MODE=presentation` or the reviewed presentation build target; unset conflicting legacy flags, never allow distributable sandbox. No server/Firebase secret belongs in a frontend environment variable. No localhost backend target belongs in public hosting.
3. After the security decision and explicit release authorization, prepare an exact clean candidate commit, verify staging and a known rollback deployment, and separately authorize commit/push/deployment. This task supplies no such approval and performs none of these actions.
4. On the approved deployed SHA, verify `/release.json`: matching commit, `uncommittedChanges=false`, `appMode=presentation`, legacy `mode=read-only-presentation`, capabilityVersion 1 and sample v1. Confirm all three roles' direct entry/refresh, valid sample schedules, logo/font/favicon/static 200s, missing API/static non-HTML errors, zero scheduling API requests/mutations, keyboard/mobile/zoom and rollback evidence.
5. Keep institutional production NO-GO until its identity/backend/data/operations gates are independently verified. A presentation release is not an institutional release.

Reproduction (PowerShell, repository root):

```powershell
npm ci --ignore-scripts --no-audit --no-fund
npm ls --all
npm audit --json                         # currently exits 1 for braces
npm audit --omit=dev --json
npm run lint
npm run typecheck
npm run test:security
npm run test:web
npm run build
npm run build:presentation
npm run test:artifacts

$qaRoot = Join-Path $env:TEMP ('classsync-p1-final-tests-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $qaRoot
$env:ACADEMIC_DATABASE_PATH = Join-Path $qaRoot 'academic.sqlite3'
$env:SCHEDULING_DATABASE_PATH = Join-Path $qaRoot 'scheduling.sqlite3'
.venv/Scripts/python.exe -m ruff check scripts/security services packages
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe scripts/security/python_audit.py --tool-python "$env:TEMP/classsync-p1-gate-tools/Scripts/python.exe" --output-dir "$env:TEMP/classsync-p1-final/python-audit"
Get-FileHash var/academic.sqlite3, var/scheduling.sqlite3, var/backups/scheduling-before-s2b-20261018074057.sqlite3 -Algorithm SHA256
git diff --check
git rev-parse HEAD
```

The isolated scanner is the existing pip-audit 2.10.1 tool venv; if missing, use the documented isolated setup in the preceding closure report, not a global install. Network/tool failure is not a clean scan. Browser scripts/logs/screenshots are under `%TEMP%/classsync-p1-final/browser/`; set `P1_ARTIFACT_ROOT` to the new artifact-test output directory and run the four existing QA helpers with the workstation's bundled Playwright/Chrome. Temporary paths are local reproduction aids; persisted machine evidence distinguishes assertions from screenshots.

## 10. Final gate decisions

**P1 LOCAL SECURITY GATE: FAIL.** The AJV graph defect is fixed, but the remaining high braces advisory is not fixed or accepted as risk. A clean production-only scan does not close build/CI exposure. This decision does not depend on pretending the hosted site was verified.

**P2 ENTRY RECOMMENDATION: NO-GO.** Obtain a defensible security closure/owner decision first, then request separate P2 authorization against its own prerequisites. No P2 work has begun.

**INSTITUTIONAL RELEASE: NO-GO.** Hosted refresh/metadata fail and SHA/settings are unknown, in addition to the unresolved advisory and unverified institutional authentication, persistence and operational prerequisites. No commit, push, deployment, Firebase/cloud change or migration occurred.

## Actual screenshot evidence

Fresh screenshots and interaction/console/network assertions are linked in `p1-final-blocker-evidence.json`; screenshots alone are not interaction verification. The screenshots below are local artifacts from this run, not images of a new public deployment. Full role/width/detail captures and native zoom/hosted error captures remain in the documented temporary QA directory.

![Fresh Student production artifact, 390px](/C:/Users/lenovo/AppData/Local/Temp/classsync-p1-final/browser/p1-student-390.png)

![Fresh Administrator production artifact, 1440px](/C:/Users/lenovo/AppData/Local/Temp/classsync-p1-final/browser/p1-administrator-1440.png)

![Native Chrome 200% zoom](/C:/Users/lenovo/AppData/Local/Temp/classsync-p1-final/browser/p1-native-200-percent.png)

![Existing hosted Student load failure](/C:/Users/lenovo/AppData/Local/Temp/classsync-p1-final/hosted-student-390.png)
