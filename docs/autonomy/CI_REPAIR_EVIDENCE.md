# CI repair checkpoint — 31 October 2026

Base/current HEAD: aea9494db46153672a31a2161070e5e4ff713966. Working tree was clean at entry; this is the actual SHA in all three jobs of GitHub run41184643255. GitHub connector job logs inspected: web124488949210, python124488949348, dependency-security124488949372. No remote rerun, commit, push or deployment.

## WEB — PARTIAL

Root cause: StructuredCalendarPage.test.tsx built a tomorrow fixture using the uncontrolled real clock while the month grid still displayed today's month. At Manila2026-10-31, the test asked the October grid for Nov1. Application calendar behavior is correct.

Reproduced once with Date fixed at2026-10-31T08:00+08:00:1 failed/3 passed, exact reported missing Nov1 button. Correction: fixed Oct30 test date, fake Date only (real async timers preserved), restore real timers after every test. Added separate explicit Oct31/Nov1 and Dec31/Jan1 forward/backward navigation, date persistence and agenda assertions. Clocks are UTC16:15 on the previous UTC date, proving real Asia/Manila date semantics. Synthetic fixture range includes2027. No production component/calendar logic changed or assertions removed.

Focused6 PASS19.15s. Fresh-source full npm run test:web attempted once with the unchanged300s guard: process ETIMEDOUT,750 passing case records and no delivered failing assertion; no final suite acceptance. All6 corrected calendar cases passed in this run. Missing result files: publication-api.test.ts, AcademicFixtureImport.test.tsx, RouteGuard.test.tsx (4 cases). Do not count750 records as a passing full suite. Logs: web-boundary-reproduction.log, web-focused.log, web-full-clean.log.

## PYTHON — PARTIAL

Root cause: console `pytest` + importlib mode + configured package-only pythonpath excludes repository root. `scripts/` is a tracked implicit namespace package (no __init__.py required); its modules are present in the checkout. Console entry reproduced17 collection errors/598 collected. Root `python -m pytest --collect-only -q` collected all947 tests without those errors in4.51s. Change only quality.yml invocation to `python -m pytest`; no widespread import or Python application edits.

Full execution and Python security scan remain NOT RUN. A clean Python3.12 environment was created, then the first service's cold dependency install exceeded a local180s setup limit. One cached continuation with the SAME180s limit built both editable packages but timed out during third-party installation. Stop after this repeated qualification failure; no third retry, timeout increase or hidden fallback. This does not establish a new application/Python assertion defect. Existing validated root Python is3.12.14; GitHub log used3.12.15. Resume only after owner approval of the recorded stop gate, preferably serial checks with the existing compatible runtime rather than another cold install.

## DEPENDENCY SECURITY — BLOCKED

Exact audit at this SHA:12 moderate/0 high/0 critical, GHSA-g3hv-75wg-m249, minimatch<11.0.1. Existing lock contains3.1.5 and10.2.6. Actual npm explain minimatch inspected. Paths:
- eslint9.39.5 → minimatch3.1.5;
- eslint → @eslint/config-array0.21.2 → minimatch3.1.5;
- eslint → @eslint/eslintrc3.3.7 → minimatch3.1.5;
- typescript-eslint8.71.1 → @typescript-eslint/typescript-estree8.71.1 → minimatch10.2.6.

Official advisory inspected: https://github.com/advisories/GHSA-g3hv-75wg-m249 (updatedOct30). Official stable npm metadata inspected and saved in upstream-parent-metadata.json:
- latest ESLint10.14.0 still requires minimatch^10.2.6;
- latest TypeScript-ESLint8.72.1 / typescript-estree8.72.1 still requires minimatch^10.2.2;
- latest config-array0.23.5 requires^10.2.4;
- latest eslintrc3.3.7 requires^3.1.5;
- patched minimatch latest11.0.3 is outside those supported ranges.

Thus no supported stable upstream upgrade removes this advisory throughout the chain. An ESLint major upgrade would still leave the finding. npm's force suggestion was an obsolete TypeScript-ESLint downgrade and was NOT applied. No blanket override, advisory exclusion, severity reduction, audit removal or security exception. Package manifests/lockfile unchanged; no gratuitous regeneration. A compatible upstream release or separate owner-approved security-policy decision is required. Exposure is development glob-processing tooling; do not claim runtime exploitability or dismiss the blocking audit.

## Clean install / platform / preservation

Node22.23.1/npm10.9.8. Clean snapshot from `git archive HEAD` plus the two bounded repair files, fresh node_modules (not linked to existing install). Location in isolation.json. npm ci exit0:411 added/414 audited,12 moderate. npm ls --all exit0: no invalid required peers; optional tsx/yaml not installed. Exact low-threshold audit exit1 remains blocking. Default working directory is checkout root; service install working directories remain step-scoped. Workflow still Node22/Python3.12 and unchanged presentation validation/security gates. No usable local Linux distribution/Docker was available; this Windows snapshot is NOT Ubuntu or remote CI acceptance. Final GITHUB_SHA/clean-commit release assertion cannot be certified for an uncommitted patch.

A temp-folder ACL prevented the first disposable venv creation; setup was moved into ignored var/ for shared workspace access. No original data was used. Fresh Python install remains partial and is not a qualified runtime. Clean snapshots/caches remain ignored local evidence, not release artifacts.

70 hashes match before/after: all3 original SQLite databases,61 P3b backend/package files,6 Student Rooms/routing/class-detail files. Original Student Rooms implementation and backend contracts unchanged. No production/institutional access, source resets, DB writes, migrations or cloud changes.

## Stop / remaining checks

AGENTS.md gate: “Persistent test failures ... resource usage beyond defined budget.” Repeated isolated setup timeouts plus incomplete whole-suite qualification are treated conservatively as this gate; no further qualification commands after the second180s failure. Only log inspection, preservation and checkpoint documentation followed.

Completed: clean npm ci, npm ls --all, blocking npm audit --audit-level=low, focused calendar6, complete Python COLLECTION947, single attempted full frontend run (incomplete).
Pending fresh acceptance: complete frontend PASS, complete Python EXECUTION, lint, typecheck, test:security, both builds, test:artifacts, Python lint/pip check/pinned security audit and final release metadata. Prior Rooms results are not reused as new CI-repair evidence.

Requested bounded continuation: owner approval to finish remaining checks serially with existing Node22/Python3.12 runtimes and unchanged test guards, without a third cold-install attempt. Security remains BLOCKED independently until a compatible parent update or separately approved policy decision. Overall not ready to promise a green GitHub workflow. No GitHub Actions PASS claimed.

## 31 October 2026 — approved bounded qualification outcome (latest)

Owner reopened only one serial run per outstanding full suite, unchanged guards, existing valid environments, no general reviewers/reinstalls/security exceptions. This section supersedes the prior pending-check status while preserving every earlier attempt. No new application source edits in this continuation.

Preflight: Node22.23.1, Python3.12.14; no stale Vitest/pytest/pip workers; all prior review agents completed. Existing preview servers idle and preserved. Approximately1.4GB free RAM/8.26GB total,31% sampled CPU. No concurrent suites or dependency installs launched. No processes killed. Existing academic-review working-tree changes preserved.

### WEB — PASS locally

Exactly one approved `npm run test:web` in existing root environment:754/754 tests,46/46 files,219.68s Vitest time,231.28s command wall time,exit0, unchanged300s guard. No retry. Prior isolated cold-install run's timeout did not recur. Its precise cause remains unproven; a deterministic single-test hang was not demonstrated. Do not claim a newly proven contention root cause just from serial success.

Fresh serial remaining checks: lint exit0; typecheck exit0(25.45s wall); test:security17 PASS(11.32s command); root build exit0(47.78s); test:artifacts4 PASS(104.58s command/102.41s test report); presentation build exit0(46.64s). Release metadata identifies read-only-presentation/presentation, current HEADaea9494db46153672a31a2161070e5e4ff713966, uncommittedChanges=true as expected locally. GitHub's clean committed-source check remains a future remote requirement. Existing build warnings remain nonblocking. Prior clean npm ci/npm ls results remain applicable to the unchanged lock; neither was needlessly repeated.

### PYTHON — PARTIAL; runner-path mistake and new audit findings

Exactly one approved full execution:947 collected/executed,934 passed,13 failed,0 skipped,120.08s pytest/128.22s command wall. No collection errors; python-m invocation fix remains verified. No dependency reinstall or second full Python run.

I selected `--basetemp C:/Projects/ClassSync/var/ci-py-approved-867745730aa74de4ad50f278d5148ece` plus a sibling cache directory. That was a qualification setup mistake. `services/academic/app/provider.py:51` and `services/scheduling/app/provider.py:18` explicitly require test SQLite paths to be beneath `tempfile.gettempdir()`. Workspace var/ is outside the OS temp directory, so the intended fail-closed guard returns503. The13 failures are the protected Academic/Gateway/Scheduling ownership, identity-stream/projection and provider-fixture cases listed in python-approved-serial.log; their tmp_path values show the rejected workspace prefix. This does not prove an application503 regression or justify relaxing that guard. Source and tests remain unchanged. Evidence metadata records the actual extra arguments and invalid-qualification reason.

A plain `.venv/Scripts/python.exe -m pytest` with its normal OS temp location is the correct next full invocation. A second full execution is outside the owner's one-run cap, so none was made. This is a single new failed qualification, not an invented repeated-failure counter reset. No assertion was skipped/suppressed and no source workaround was added.

Existing Python environment: pip check PASS; exact workflow Ruff command PASS0.60s. Reused an existing owned pinned pip-audit2.10.1 environment; no tool/app dependency install. Audit covered68 exact installed third-party versions and found4 distinct advisories in pyasn10.6.4; audit exits1 in13.89s. All list0.6.5 as fix:
- CVE-2026-119196 / GHSA-2qm8-x737-gmw5
- CVE-2026-119194 / GHSA-fm9c-5rcf-2q5p
- CVE-2026-119197 / GHSA-mm57-4v3p-rchx
- CVE-2026-119195 / GHSA-9m75-vc3g-4x39

Official first advisory checked: https://github.com/advisories/GHSA-2qm8-x737-gmw5. It describes high-severity decoder CPU exhaustion for sufficiently large attacker-controlled ASN.1 input and fixes<=0.6.4 in0.6.5. Application exploit reachability was not established here; do not confuse installed-runtime dependency presence with a demonstrated unauthenticated ClassSync exploit. This local environment audit is not a claim that a fresh remote resolve necessarily selects the same vulnerable version. No exclusion, policy exception or automatic patch applied in this qualification-only approval. Controlled next step is a separately approved compatible pyasn10.6.5 environment/security-floor assessment and correctly configured full Python qualification/audit.

### DEPENDENCY SECURITY — BLOCKED; single compatibility assessment completed

Actual installed affected paths:
- web dev eslint9.39.5 → minimatch3.1.5
- eslint → @eslint/config-array0.21.2 → minimatch3.1.5
- eslint → @eslint/eslintrc3.3.7 → minimatch3.1.5
- web dev typescript-eslint8.71.1 → @typescript-eslint/typescript-estree8.71.1 → minimatch10.2.6

One bounded current official npm metadata check reconfirmed latest eslint10.14.0(^10.2.6), estree8.72.1(^10.2.2), config-array0.23.5(^10.2.4), eslintrc3.3.7(^3.1.5). Patched minimatch latest11.0.3 remains outside these supported ranges. Official https://github.com/advisories/GHSA-g3hv-75wg-m249 still lists<11.0.1 affected. Prior exact low-threshold audit remains12 moderate; unchanged manifests/lock and matching tree, no advisory suppression. No compatible supported stable parent upgrade identified; no pointless major upgrade or blanket override applied.

Exposure assessment: all installed minimatch nodes have lockfile dev=true; `npm ls minimatch --omit=dev --json` reports an empty dependency graph (exit1 is expected for no matching installed production dependency, not a passed audit). Application imports and generated presentation JavaScript have no minimatch/firstPhasePreProcess/globParts signatures. This supports development/CI tooling exposure rather than an observed deployed-browser runtime path; string checks alone are not an exploitability proof. ESLint uses reviewed fixed repository glob patterns, not Student request parameters. Practical containment: keep glob/config changes reviewed, avoid attacker-supplied dynamic patterns, retain least-privilege/no-production-secret CI, consider owner-approved job resource caps. These reduce exposure but do NOT clear the advisory/audit. Controlled next step: wait for supported parent releases adopting patched minimatch, then make a minimal lockfile update and requalify. Any policy exception requires separate explicit approval; none implemented.

### Preservation / review / stop

All70 hashes match the pre-repair baseline:3 original SQLite,61 P3b backend/package files,6 Rooms/routing/class-detail files. No original DB connection/migration, PostgreSQL policy change, source discard, commit, push, deployment or cloud modification. Student Rooms visual/function source unchanged. CI source diff remains exactly quality.yml Python invocation and StructuredCalendarPage.test.tsx deterministic/boundary tests; this continuation only appends evidence/authorization. Self-review checked clock restoration, unchanged assertions, server guard preservation, actual metadata/logs and the two-file diff; no new review agents.

Machine-readable latest outcome: ../production/ci-repair-20261031/approved-qualification-summary.json. Individual command logs/results have approved names; previous failed attempts retained. WEB PASS, PYTHON PARTIAL, DEPENDENCY SECURITY BLOCKED. Not ready to claim a green-CI commit/push; corrected Python qualification and both advisory paths remain unresolved. No GitHub Actions PASS claimed. STOP at this bounded qualification; additional Python full execution/dependency changes need fresh authority under the owner's one-run scope.
