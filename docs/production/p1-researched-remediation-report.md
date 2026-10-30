# ClassSync P1 researched remediation — 21 October 2026

## Decisions

| Gate | Decision | Evidence |
|---|---|---|
| **DEPENDENCY SECURITY** | **RISK ACCEPTANCE REQUIRED** | Full npm audit exits 1: one HIGH advisory propagated through five package entries. No patched `braces` release or approved exception. This is **AWAITING OWNER ACCEPTANCE**, not FIXED. |
| **LOCAL P1 ENGINEERING** | **PASS** | Clean install, AJV tree, 664 frontend and 105 backend tests, lint, typecheck, Ruff, both builds, four artifact groups and browser checks passed after the narrow changes below. This does not override the security gate. |
| **HOSTED PRESENTATION RELEASE** | **FAILED** | Hosted role deep links and `/release.json` return 404. Deployed SHA and project settings are unverified. |
| **P2 ENTRY** | **NOT RECOMMENDED — OWNER APPROVAL REQUIRED** | P1 security and hosted release gates remain open; P2 was not started. |
| **INSTITUTIONAL PRODUCTION RELEASE** | **NO-GO** | Identity/current membership, durable authorized backend, privacy/operations and release gates remain unclosed. |

No commit, push, deployment, cloud-setting change, database migration, provisioning or P2 work was performed. No advisory was suppressed, risk-accepted or relabeled as fixed.

## Sources checked and exact baseline

Primary sources read on 21 October 2026: [GitHub advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm), [upstream report #70](https://github.com/micromatch/braces/issues/70), [maintainer discussion #84](https://github.com/micromatch/braces/issues/84), [advisory-database PR #10132](https://github.com/github/advisory-database/pull/10132), and [OSV](https://osv.dev/vulnerability/GHSA-vfj7-8cjw-p6xm); [Vercel Vite guidance](https://vercel.com/docs/frameworks/frontend/vite), [rewrites](https://vercel.com/docs/routing/rewrites), [vercel.json reference](https://vercel.com/docs/project-configuration/vercel-json), and [404 diagnosis](https://vercel.com/kb/guide/why-is-my-deployed-project-giving-404). Vercel documents explicit SPA rewrites and routing metadata; a Ready build or homepage 200 does not establish deep-route success. The upstream maintainer disputes the advisory, and PR #10132 is closed. The official GitHub advisory remains published HIGH, CVE-2026-93687, affected range `<=3.0.3`, patched versions **None**. The dispute is not a scanner fix.

The required earlier local records were read first: [p1-verification.md](p1-verification.md), [p1-gate-closure-report.md](p1-gate-closure-report.md), [p1-final-blocker-remediation.md](p1-final-blocker-remediation.md), [p1-final-blocker-evidence.json](p1-final-blocker-evidence.json), [dependency-advisory-register.md](dependency-advisory-register.md), and [reconciled-master-plan.md](reconciled-master-plan.md). They remain historical evidence; this report uses the current tree and fresh commands.

Initial branch was `main`; local HEAD and the read-only `git ls-remote origin refs/heads/main` both returned `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`. The worktree was already dirty with the prior uncommitted P1 implementation. At task start, tracked modifications were: `.github/workflows/quality.yml`, `apps/web/.env.example`, `apps/web/package.json`, `apps/web/src/auth/preview-session.ts`, `apps/web/src/components/layout/AppShell.tsx`, `apps/web/src/lib/{academic-api,presentation-sample,publication-api,sample-calendar-api,scheduling-api}.ts`, `apps/web/src/pages/{AcademicCalendarEditor,AcademicFixtureImport,ProductScreenPage,PublicationPanel}.tsx`, `apps/web/src/routes/RouteGuard.tsx`, `apps/web/src/services/api-client.ts`, `apps/web/vite.config.ts`, `docs/{architecture.md,security.md}`, `docs/infrastructure/vercel-backend-deployment-plan.md`, `docs/releases/r1-public-presentation.md`, `package-lock.json`, `package.json`, `scripts/{build-presentation,preview-presentation}.cjs`, and all four service requirements files. Untracked prior P1 paths were `apps/web/config/`, `apps/web/src/config/`, `docs/production/`, `scripts/lib/`, `scripts/security/`, `scripts/tests/`, two scheduling security/boundary tests, and `services/security-constraints.txt`. None was replaced with an older remote copy.

Node `v22.23.1`, npm `10.9.8` (invoked as `npm.cmd` because PowerShell blocks `npm.ps1`), Python `3.12.14`. The npm workspace uses lockfile v3. [quality.yml](../../.github/workflows/quality.yml) has least-privilege `contents: read`, full-tree `npm ls --all` and unsuppressed `npm audit --audit-level=low`; no security exception mechanism. [vercel.json](../../vercel.json) is at repository root. No local `.vercel/project.json` link or Vercel project connector was available, so private project settings could not be inspected.

## `braces`: dependency, reachability and disposition

`npm ls braces --all` and `npm explain braces` identify one physical installed `node_modules/braces@3.0.3`, reached through **three complete chains** from the web workspace:

| Root and chain | Use and exposure |
|---|---|
| `@classync/web` devDependency `tailwindcss@3.4.19 → chokidar@3.6.0 → braces@3.0.3` | Tailwind watch/development file handling. |
| `@classync/web → tailwindcss@3.4.19 → micromatch@4.0.8 → braces@3.0.3` | Tailwind matching during build/watch. |
| `@classync/web → tailwindcss@3.4.19 → fast-glob@3.3.3 → micromatch@4.0.8 → braces@3.0.3` | Build-time content discovery. |

Tailwind is necessary for the current CSS pipeline; removing it would change required styling. These dependencies execute in development/CI/build even though they are absent from the browser runtime. The production-only `npm audit --omit=dev --audit-level=high` returned exit 0 with zero findings. Full `npm audit --json` returned exit 1 with five HIGH affected-package entries from this one advisory, zero critical/moderate/low. Its complete normalized JSON is [p1-researched-npm-audit.json](p1-researched-npm-audit.json); no findings were filtered from that file. The CI audit remains blocking.

[tailwind.config.ts](../../apps/web/tailwind.config.ts) contains only repository-controlled `./index.html` and `./src/**/*.{ts,tsx}` patterns. No public request path, role selection, scheduling input or hosted frontend operation passes arbitrary glob patterns to Tailwind. The affected `braces` behavior requires a deeply nested *pattern*, not merely a file name matching a fixed pattern. A contributor who can alter build configuration/CI can influence patterns, and CI availability remains a residual risk. This evidence limits demonstrated exploit reachability; it does not prove the library safe. The locally emitted presentation artifact contains no deployed `braces` runtime dependency. Its controlled build still executes Tailwind.

The advisory identifies recursive AST walkers in `parse`, `compile` and `expand`; the existing character limit does not establish a depth bound. Upstream #70 describes the failure, while #84 and PR #10132 document the maintainer's dispute and competing interpretations. There is no published patched `braces` version to install. npm's reported Tailwind 4.3.3 fix candidate is a major CSS/PostCSS/toolchain migration, not a compatible transitive patch. Replacing only chokidar would leave both micromatch paths. No maintained drop-in replacement with reviewed API, dependencies, maintenance and license evidence was established. No fork, tarball, private patch, arbitrary override or Tailwind major migration was installed. **Outcome: AWAITING OWNER ACCEPTANCE.**

### Proposed exception, not approved

If the owner elects temporary acceptance, the proposed scope is only GHSA-vfj7-8cjw-p6xm / CVE-2026-93687, `braces@3.0.3`, the `@classync/web` workspace of ClassSync, and the three Tailwind dependency paths above. Production runtime audit is clean; build/CI tooling exposure remains. Controls are fixed repository-owned content globs, no public pattern endpoint, no production dev server, read-only CI token and no cloud credentials in the presentation build. Residual risk is build/CI availability if an untrusted pattern reaches a tooling API or repository configuration is changed.

**Responsible named person is not yet supplied**; the project owner must designate a security owner before any acceptance. Proposed mandatory review: 6 November 2026; proposed expiry: 20 November 2026 at 23:59 UTC, or earlier when an upstream fix becomes available. A future approved mechanism must match the exact advisory/package/version/workspace, retain the complete raw audit as a CI artifact, fail on every other advisory and on scanner errors, and automatically fail after expiry. Track upstream advisory, releases, issue #70/#84 and PR #10132 at review. **No exception mechanism was implemented or approved.**

## AJV and dependency integrity

The prior removal of unused `@hookform/resolvers` remains intact. Fresh `npm ci --ignore-scripts --no-audit --no-fund` installed 412 packages and exited 0. `npm ls --all` exited 0; `npm ls ajv @hookform/resolvers --all` shows only `ajv@6.15.0` through ESLint/eslintrc and no resolver package. ESLint and TypeScript pass. No AJV upgrade, optional-peer suppression, lockfile edit or new dependency was made in this task.

## Vercel: repository artifact versus hosted evidence

[vercel.json](../../vercel.json) specifies Vite, `npm ci`, `npm run build:presentation`, `apps/web/dist` and explicit role/auth rewrites to `/index.html`. [build-presentation.cjs](../../scripts/build-presentation.cjs) selects the presentation target; [vite.config.ts](../../apps/web/vite.config.ts) emits metadata into the actual build directory through [release-metadata.ts](../../apps/web/config/release-metadata.ts). [app-routes.tsx](../../apps/web/src/routes/app-routes.tsx) includes the three role route sets and `/dev/design-system`. The latter route lacked an exact Vercel rewrite, a proven local config gap; an exact rule was added. No wildcard rewrite was added. API, unknown and missing asset paths remain outside the frontend rewrite set.

The design-system page uses representative static component examples and local dialog/drawer state; it has no privileged data or API operation. The new exact rewrite permits direct navigation to a route already present in the client router and does not alter role authorization.

The fresh ordinary and presentation builds both exit 0. The final presentation `apps/web/dist` has 20 files and is byte-for-byte identical to the independently tested presentation artifact. It has `index.html`, actual JS/CSS/fonts/branding/manifest and `release.json` at the static root. Parsed metadata is schema 1, `mode: read-only-presentation`, `appMode: presentation`, capability version 1, sample version `classsync-presentation-v1`, commit `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`, and `uncommittedChanges: true` (correct for this tree). The mode resolver rejects sandbox builds and contradictory presentation/institutional flags; real artifact tests exercise nine invalid combinations and three valid variants. Browser journeys confirm no API calls or writable admin controls in presentation mode; forged preview roles are denied in institutional mode. No dirty local artifact is represented as an approved clean release.

[production-artifacts.test.cjs](../../scripts/tests/production-artifacts.test.cjs) now fetches `/dev/design-system` in addition to actual Student, Teacher and Administrator deep links twice, equivalent to direct navigation and refresh. Four groups pass. It also checks release JSON identity, JS/font/logo/manifest content, 404 non-HTML for missing assets/API, and 404 for missing API POST/PUT/DELETE. The new route assertion would fail against the previous [vercel.json](../../vercel.json) rewrite list because the local artifact server returned 404 for that path. This emulator follows the repository rewrite rules; it is not Vercel routing certification.

Read-only GET results from [p1-researched-hosted-http.json](p1-researched-hosted-http.json), captured with status, content type, cache header, ETag, Vercel request ID, byte count and SHA256:

| Hosted path | Result and identity |
|---|---|
| `/` | 200 `text/html`, the ClassSync HTML shell. |
| `/student/dashboard`, `/teacher/schedule`, `/admin/dashboard`, `/dev/role-preview`, `/dev/design-system` | 404 `text/plain`, Vercel `NOT_FOUND`. |
| `/release.json` | 404 `text/plain`; no JSON/schema/SHA can be validated. |
| Hosted main JS/CSS, Inter font, icon and manifest | 200 with appropriate static content types. Hosted main JS is `/assets/index-CbQh0kvf.js`, different from the new local artifact name; an asset hash is not a commit SHA. |
| `/api/v1/timetables/periods`, missing JS and an unknown path | 404 `text/plain`, not a misleading HTML 200. |

Prior hosted browser evidence in [p1-final-blocker-remediation.md](p1-final-blocker-remediation.md) also records direct refresh failures and Student/Teacher unavailable live API requests. This task's new HTTP checks reproduce the route and metadata failures; private Vercel root, framework preset, commands, output, deployment branch/environment, deployment SHA and actual deployed rewrite manifest are **not verified**. The observed site differs from the reviewed local presentation artifact, but whether an old SHA or project-setting override caused it cannot be proven without authenticated read-only access. No local application refactor or deployment was used to conceal that uncertainty.

[verify-hosted-presentation.cjs](../../scripts/verify-hosted-presentation.cjs) records GET evidence and exits 1 if role/deep links, metadata, static assets or API boundaries fail. It accepts an expected approved commit SHA as its fourth command-line argument. The current public check exited **1**, failing the five deep links above and release metadata. A 200 login shell where JSON is expected would also fail.

## Fresh validation, preservation and change review

All results below were executed in this task. Exit 0 is a pass; failures remain visible.

| Command/check | Exit and result |
|---|---|
| `npm.cmd ci --ignore-scripts --no-audit --no-fund` | 0, 412 packages. An earlier sandbox attempt stalled on restricted registry access and was interrupted; the authorized retry completed. |
| `npm.cmd ls braces --all`; `npm.cmd explain braces`; `npm.cmd ls --all`; `npm.cmd ls ajv @hookform/resolvers --all` | 0 each; paths and AJV tree above. |
| `npm.cmd audit --omit=dev --audit-level=high` | 0, zero vulnerabilities; first restricted-network attempt exited 1, authorized retry passed. |
| `npm.cmd audit --json` | 1, five HIGH entries / one GHSA; full JSON saved. |
| `npm.cmd run test:security` | 0, 3 passed, zero skipped. |
| `npm.cmd run lint`; `npm.cmd run typecheck` | 0 each, rerun after edits. |
| `npm.cmd run test:web` | First and second full runs: exit 1, 663/664 due immediate agenda assertion after date selection. Targeted file before edit: exit 0, 5/5. After waiting for the rendered agenda without weakening the result or network assertion: targeted 5/5 and full 664/664 across 36 files, exit 0. |
| `C:/Projects/ClassSync/.venv/Scripts/python.exe -m pytest` | 0, 105 passed, 1 pre-existing TestClient deprecation warning. `ACADEMIC_DATABASE_PATH` and `SCHEDULING_DATABASE_PATH` pointed at a fresh temporary QA directory. |
| `C:/Projects/ClassSync/.venv/Scripts/python.exe -m ruff check scripts/security services packages`; `... -m pip check` | 0 each. |
| Pinned `scripts/security/python_audit.py` with pip-audit 2.10.1 | 0 after authorized network retry: 62 exact third-party versions, zero findings/skips, all four declared service environments covered. First sandbox scan exited 1 due blocked PyPI socket and was not counted as a pass. Evidence: [p1-researched-python-audit/](p1-researched-python-audit/). |
| `npm.cmd run build`; `npm.cmd run build:presentation` | 0 each. Ordinary main 519.95 kB / 154.28 gzip; presentation main 524.87 / 155.61. Existing 500 kB chunk warning remains visible. |
| `npm.cmd run test:artifacts` | 0; four groups, no skipped checks; invalid modes, metadata, deep links, refresh, static/API boundaries. |
| Local production-artifact Playwright journeys | 0; 15/15 combinations (three roles × 360/390/768/1024/1440). Role entry → dashboard → refresh → schedule/details or admin conflicts/sample calendar; no overflow, missing branding, page errors or API requests. Student/Teacher dialogs passed focus entry, seven-Tab containment, Escape and focus restore. Institutional forged-role/refresh, invalid/expired session, mounted eight-hour expiry, 390×400 Close access all passed. |
| Native Chrome zoom | 0; `tabs.setZoom/getZoom=2`, DPR 1→2, width 1424→712, visible keyboard action and no overflow. |
| Hosted verifier | 1, required hosted routes and metadata failed as detailed above. |
| `git diff --check` | 0; Git printed Windows line-ending notices, no whitespace failures. |

Browser plugin was unavailable; the existing pinned Playwright/Chrome runtime and isolated temporary profile were used per frontend testing guidance. The flow under test was welcome → role selection → meaningful dashboard → refresh → schedule/details or conflict sample. Screenshots and machine results are under the new temporary QA directory `C:/Users/lenovo/AppData/Local/Temp/vscode-agent-codex-sandbox-65NhhC/classsync-p1-researched-browser/`. These are engineering checks, not human screen-reader or WCAG certification.

Protected original SHA256 hashes at task end exactly equal the prior [p1-database-preservation.json](p1-database-preservation.json) and [p1-final-blocker-evidence.json](p1-final-blocker-evidence.json) baselines:

| Original file | Unchanged SHA256 |
|---|---|
| `var/academic.sqlite3` | `4cd5f60de21bd365c914ac01e5be692b3bea1c7a56a7f17a76c6953ef8668738` |
| `var/scheduling.sqlite3` | `1848377cc9a9eb656e12b5e58436e81198fef92f18dd71c1fea2f6f8b482e400` |
| `var/backups/scheduling-before-s2b-20261018074057.sqlite3` | `9ec149413d69c1165b74a75e366fa262417c1ecbf41e7029fdd0d86ac96f395d` |

Because all three files are byte-identical to the previously verified originals, their schemas and all 604 previously checked payload checksums are unchanged; earlier immutable read-only validation recorded integrity OK and zero FK/checksum errors. This task did not reopen originals for mutation or rerun each payload query. Backend tests used only new isolated databases.

Task-specific source changes are exactly: [vercel.json](../../vercel.json) adds the one missing exact route rewrite; [production-artifacts.test.cjs](../../scripts/tests/production-artifacts.test.cjs) adds that route to the real HTTP artifact regression; [R1Presentation.test.tsx](../../apps/web/src/pages/R1Presentation.test.tsx) waits for the same positive agenda assertion after the asynchronous date change; [verify-hosted-presentation.cjs](../../scripts/verify-hosted-presentation.cjs) adds an owner-runnable read-only HTTP gate and raw response evidence; this report plus npm/HTTP/Python audit evidence files. The first two build configs and all runtime, scheduling, UI, database, manifest and lockfile source remain as found at task start. No dependency churn, CI bypass, exception, rewrite of `/api/*`, privileged route expansion, sample-mode substitution or scheduling-rule change was introduced.

## Reproduction and owner release procedure

From the repository root, using Node 22.x, Python 3.12 and the configured `.venv`:

```powershell
git status --short --branch
git rev-parse HEAD
git ls-remote origin refs/heads/main
npm.cmd ci --ignore-scripts --no-audit --no-fund
npm.cmd ls braces --all
npm.cmd explain braces
npm.cmd ls --all
npm.cmd ls ajv @hookform/resolvers --all
npm.cmd audit --omit=dev --audit-level=high
npm.cmd audit --json
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run test:security
npm.cmd run test:web
npm.cmd run build
npm.cmd run build:presentation
npm.cmd run test:artifacts
C:/Projects/ClassSync/.venv/Scripts/python.exe -m ruff check scripts/security services packages
C:/Projects/ClassSync/.venv/Scripts/python.exe -m pip check
$qaRoot = Join-Path $env:TEMP ('classsync-p1-research-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $qaRoot | Out-Null
$env:ACADEMIC_DATABASE_PATH = Join-Path $qaRoot 'academic.sqlite3'
$env:SCHEDULING_DATABASE_PATH = Join-Path $qaRoot 'scheduling.sqlite3'
C:/Projects/ClassSync/.venv/Scripts/python.exe -m pytest
C:/Projects/ClassSync/.venv/Scripts/python.exe scripts/security/python_audit.py --tool-python C:/Users/lenovo/AppData/Local/Temp/classsync-p1-gate-tools/Scripts/python.exe --output-dir docs/production/p1-researched-python-audit
node scripts/verify-hosted-presentation.cjs https://class-sync-bhiv.vercel.app docs/production/p1-researched-hosted-http.json APPROVED_COMMIT_SHA
git diff --check
```

The scanner command requires a separately installed, pinned pip-audit 2.10.1 tool environment; the path above is this workstation's existing isolated scanner, not a portable project path. `npm audit --json` and the hosted verifier are **expected to exit 1 in the current state**. A clean future deploy should pass the hosted verifier with the actual approved 40-character SHA. The exact browser QA scripts used here were copied from the previous P1 evidence into a new temporary directory; no old screenshots or source files were overwritten.

Owner-executable release and rollback checklist, **not authorized in this task**:

1. Review the complete uncommitted local diff and this report, including prior P1 work; explicitly decide the HIGH advisory with a named owner. Do not call acceptance a fix.
2. Confirm the intended read-only presentation mode and that no institutional/sandbox flag or secret is injected into the frontend build.
3. Separately authorize a specific commit and push. Build from the resulting clean SHA; require `release.json.uncommittedChanges === false`.
4. Read Vercel project settings: repository root directory, Vite preset, install `npm ci`, build `npm run build:presentation`, output `apps/web/dist`, deployment branch, production deployment and environment variables. Compare with reviewed [vercel.json](../../vercel.json). Inspect deployment routing/rewrite metadata.
5. With separate authorization, deploy the reviewed revision to a controlled candidate/staging target; confirm its deployment SHA and `/release.json` schema/mode/sample/SHA match.
6. Navigate directly to and hard-refresh Student, Teacher and Administrator dashboard/schedule routes and the role-preview entry at supported widths. Check actual role behavior, no live API calls or write controls in presentation mode.
7. Require real JS/CSS/fonts/logo/manifest responses and non-HTML 404 for absent assets and `/api/*` paths. Run the verifier with the approved SHA; require exit 0. A homepage 200 alone is insufficient.
8. Only after candidate checks and separate release approval, attach the production alias. Monitor the actual alias and re-run the same SHA, route, asset and API checks.
9. If any check fails, restore the previous known-good Vercel deployment/alias and verify it again. No database migration is part of this presentation release.

**Next decision:** the owner must choose a reviewed upstream/toolchain remediation or explicitly sign the bounded `braces` exception with a named accountable person and expiry. Separately, a Vercel project owner must inspect settings read-only and authorize a candidate deployment of reviewed code. Until both gates have evidence, dependency security is not passed, the hosted presentation is failed, and institutional production remains NO-GO.
