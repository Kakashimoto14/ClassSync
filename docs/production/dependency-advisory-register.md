# Dependency advisory register — current closure status

**Final-blocker continuation, 21 October 2026:** [current remediation report](p1-final-blocker-remediation.md) and [fresh evidence](p1-final-blocker-evidence.json). The optional AJV tree defect is now **FIXED**: unused `@hookform/resolvers@5.9.1` (no application imports) and its unused helper were removed; actual ESLint consumers retain AJV 6.15.0. Clean `npm ci` and complete `npm ls --all` pass. No surviving dependency version changed. CI now checks the complete tree explicitly before its strict audit. References below to the original AJV failure describe the preceding snapshot.

Fresh upstream checks still identify **no patched braces release** (latest 3.0.3, affected `<=3.0.3`). Compatible Tailwind 3/micromatch/fast-glob parents retain it; changing only chokidar does not remove all paths and changes glob APIs. Tailwind 4 is a separate migration candidate, not an applied safe override. **B1 remains UNRESOLVED**, five high package entries / one advisory; no exception or advisory suppression. The Python rescan remains clean across 62 exact third-party versions. P1 local security stays FAIL independently of hosted release failures. The original six JS/eight Python fixes remain intact.

21 October 2026. The historical initial triage below is retained unchanged. It is superseded by the following results and [P1 gate-closure report](p1-gate-closure-report.md), with raw before/after responses in [the evidence file](p1-gate-closure-evidence.json).

| ID | Original affected node | Final disposition / evidence |
|---|---|---|
| G1 / GHSA-m9gg-hp2v-232j | grpc-js 1.9.16 through Firebase | **FIXED**, exact override 1.14.5, installed API/Firestore-load smoke, audit cleared |
| G2 / GHSA-f596-whhp-79r4 | Same | **FIXED**, same patched branch |
| V1 / GHSA-82fw-gwwq-j7x9 | Vitest/mocker 3.2.7 | **FIXED**, both 4.1.11; 664 tests pass, Vite remains 6.4.4 |
| B1 / GHSA-vfj7-8cjw-p6xm | braces 3.0.3 | **UNRESOLVED**, latest available version still affected; five high package entries remain. No risk acceptance |
| P1 / GHSA-rj75-hqrm-r3gf | selector-parser 6.1.4 | **FIXED**, 7.1.6, real Tailwind/nested processing and unchanged CSS verified |
| T1 / GHSA-5gmw-xhrv-c9v3 | tinypool 1.1.1 | **FIXED**, removed by tested Vitest upgrade |
| T2 / GHSA-85c8-ppgw-ccpr | Same | **FIXED**, removed |

Original npm count: **14 affected-package entries / seven distinct advisories**. Final: **five high entries / one distinct advisory** (braces, chokidar, fast-glob, micromatch, Tailwind); nine original entries clear. Six advisories fixed, none accepted as risk. Production-only audit has zero findings, but the full dependency gate **FAILS**. Trusted build globs, minimal CI permissions and verified browser exclusion reduce exposure; they do not close B1. A broad Tailwind major migration was not attempted. Remediation/risk ownership remains unassigned; only the owner can approve an exception.

Registry vulnerable ranges: G1/G2 grpc-js `<1.13.6`; V1 Vitest/mocker `>=2.1.0 <4.1.11`; B1 braces `<=3.0.3`; P1 selector-parser `<7.1.6`; T1 tinypool `<=2.1.0`; T2 tinypool `<2.1.2`. Installed original/final versions and all propagated dependency paths appear in the historical 14-entry table and current closure matrix. These are audit-reported affected ranges, not a claim that every installed path is exploitable.

Python scanner limitation is closed: isolated **pip-audit 2.10.1** initially returned 15 raw records, deduplicated to eight advisories across certifi, pip and pytest. All eight are fixed by certifi 2026.10.19, pip 26.2.2 and pytest 9.0.3. Four service manifests reference shared security constraints. The final exact-installed scan covers **62 third-party packages, zero findings/skips**; internal editable contracts are provenance-verified and source-reviewed. The report lists all eight identifiers, affected paths and fixes. Scanner/network/incomplete-coverage errors fail closed. This does not certify an unbuilt future cloud image or establish a full Python deployment lock.

Local dependency compatibility tests, lint/typecheck, 664 web tests, 105 backend tests, both builds and artifact security checks pass. Full `npm ls --all` still fails on a **pre-existing** optional AJV peer mismatch (@hookform/resolvers 5.9.1 vs hoisted AJV 6.15.0), confirmed unchanged against the original lock. No forced upgrade or ignored assertion was used. CI now runs unsuppressed npm and Python security gates; the npm advisory job intentionally remains red while B1 is unresolved. No hosted Actions run is claimed.

## Historical initial triage — before this closure task

Evidence: fresh `npm audit --json`, preserved in `dependency-audit-2026-10-21.json`, and package-lock versions. The first restricted-network request failed; a subsequent authorized read-only registry query succeeded. No install, lockfile edit, override or forced upgrade occurred.

**14 is affected-package entries, not distinct vulnerabilities:** 2 critical + 9 high + 3 moderate entries arise from **7 distinct GHSA identifiers**, including one low advisory propagated through the high grpc entry. Parent-package severity reflects transitive dependencies. All owners remain **unassigned**; suggested responsible teams are frontend/build maintenance and security review. Classification is not risk acceptance.

## Advisory definitions and candidate mitigations

| ID | Advisory | Condition / proposed reviewed action |
|---|---|---|
| G1 | [GHSA-m9gg-hp2v-232j](https://github.com/advisories/GHSA-m9gg-hp2v-232j), high | grpc getAuthContext certificate authorization under affected server configurations. Qualify patched 1.13.6 or 1.14.5 branch with a compatible Firebase dependency; do not blindly override Firestore's `~1.9.0` constraint. |
| G2 | [GHSA-f596-whhp-79r4](https://github.com/advisories/GHSA-f596-whhp-79r4), low | grpc server error disclosure. Same compatible patched branch and server configuration review as G1. |
| V1 | [GHSA-82fw-gwwq-j7x9](https://github.com/advisories/GHSA-82fw-gwwq-j7x9), moderate | Vitest mock redirect path traversal/file read. Candidate fixed Vitest/mocker 4.1.11; qualify Node/Vite/API compatibility in a separately scoped remediation. |
| B1 | [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm), high | Deeply nested untrusted brace patterns exhaust stack. Audit reports affected through 3.0.3; no patched braces version is established by this evidence. Restrict patterns to trusted inputs pending compatible upstream remediation. |
| P1 | [GHSA-rj75-hqrm-r3gf](https://github.com/advisories/GHSA-rj75-hqrm-r3gf), moderate | Untrusted flat CSS selectors can exhaust CPU. Candidate selector-parser 7.1.6, requiring parent compatibility review. |
| T1 | [GHSA-5gmw-xhrv-c9v3](https://github.com/advisories/GHSA-5gmw-xhrv-c9v3), critical | Worker-options prototype-pollution gadget to code execution; requires a reachable pollution/input path. Fixed starting 2.1.1 for this advisory alone. |
| T2 | [GHSA-85c8-ppgw-ccpr](https://github.com/advisories/GHSA-85c8-ppgw-ccpr), critical | run-options pollution gadget. Cover both T1/T2 with compatible tinypool 2.1.2+, not 2.1.1 alone. |

## All affected-package entries

`web` means the web workspace; other names below are transitive nodes in root node_modules. Every entry is open: triaged, no remediation applied, owner unassigned.

| Package / installed version | Dependency path(s) | Advisory / severity | Affected environment / reachability | Fix or mitigation |
|---|---|---|---|---|
| firebase 11.10.0 | web → firebase | G1/G2 propagated, high | Installed runtime SDK; current app initializes Firebase app/auth, not Firestore server | Compatible SDK review; audit's 9.14.0 downgrade is not accepted automatically |
| @firebase/firestore 4.8.0 | firebase → firestore | G1/G2 propagated, high | Firestore unused by current application source; Node grpc code is not evidence of browser exploitation | Same as G1/G2 |
| @firebase/firestore-compat 0.3.53 | firebase → compat → firestore | G1/G2 propagated, high | No compat API imported by application | Same as G1/G2 |
| @grpc/grpc-js 1.9.16 | firestore → grpc-js | G1/G2, high | Node Firestore dependency; no application Node grpc server found | Patched compatible branch; qualify transitive constraint |
| @vitest/mocker 3.2.7 | web → vitest → mocker | V1, moderate | Test/dev tooling; no browser production API | Qualify 4.1.11+ compatible toolchain |
| braces 3.0.3 | tailwind → chokidar → braces; tailwind → micromatch → braces | B1, high | Dev/build pattern processing. No public arbitrary-pattern endpoint identified | Trusted patterns; upstream compatible fix required |
| chokidar 3.6.0 | web → tailwind → chokidar | B1 propagated, high | Development watcher/build tooling | Review parent upgrade; no forced Tailwind 4 migration |
| fast-glob 3.3.3 | tailwind → fast-glob → micromatch → braces | B1 propagated, high | Build glob expansion | Compatible transitive fix after qualification |
| micromatch 4.0.8 | tailwind → micromatch → braces | B1 propagated, high | Build pattern matching | Same as B1 |
| postcss-nested 6.2.0 | tailwind → nested → selector-parser | P1 propagated, moderate | CSS build inputs | Qualify parser/parent upgrade |
| postcss-selector-parser 6.1.4 | tailwind → parser; nested → parser | P1, moderate | Build selector input | Qualify 7.1.6+ |
| tailwindcss 3.4.19 | web → tailwind | B1/P1 propagated, high | Development/build only | Audit suggests 4.3.3, a major styling/toolchain change requiring separate review |
| tinypool 1.1.1 | web → vitest → tinypool | T1/T2, critical | Test worker execution. No public production endpoint; exploit chain in trusted suite not demonstrated | Qualify compatible 2.1.2+ with Vitest |
| vitest 3.2.7 | web → vitest → mocker/tinypool | V1/T1/T2 propagated, critical | Tests/CI execute code; untrusted tests already carry code-execution risk | Audit suggests 5.0.5; separately qualify migration, never force |

Browser exclusion must be verified on each release's emitted module graph; source non-use alone does not certify a bundle. P1 actual emitted-module graph: 173 modules, zero matches for Firestore/grpc and each listed test/build tool (evidence `p1-browser-evidence.json`). This is evidence for this presentation build only, not every future artifact. Absence from a browser bundle does not remove CI/supply-chain risk.

## Immediate action and gates

If a critical/high issue has a confirmed exploitable application/CI input path: stop release and affected privileged execution; isolate untrusted inputs/jobs from secrets, document reproduction without attacking live infrastructure, obtain narrowly scoped containment/remediation and re-run affected tests and advisory queries. Do not run `npm audit fix --force`. No cloud changes are authorized by this triage.

No exploitable public chain has been established here; no claim of safety follows. Institutional release remains blocked pending remediation or accountable security-owner acceptance with exposure evidence. P1 includes triage and gating, not broad remediation.

## Python

`pip check` reports no broken requirements; this is dependency consistency, **not a vulnerability scan**. Neither `pip_audit` nor `safety` is installed in the project venv. No scanner was installed. Python vulnerability status is **unknown/scanner unavailable**, not zero findings. Qualification of pinned deployment requirements and an approved vulnerability scan remains a release gate. Existing broad requirements and OR-Tools pin remain unchanged.

Observed Python versions (inventory, not scan): FastAPI 0.143.3, Starlette 1.8.0, Uvicorn 0.54.0, OR-Tools 9.15.6755, firebase-admin 7.7.0, cryptography 50.0.2, httpx 0.28.1, protobuf 6.33.6, grpcio 1.84.0, Pydantic 2.14.1. Existing Starlette TestClient/httpx deprecation was reported by pytest; no dependency was altered.
