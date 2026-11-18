# M5 final qualification and reviewed checkpoint

Status: PARTIAL locally; release/deployment NO-GO until the blockers below close.
Base HEAD: `aea9494db46153672a31a2161070e5e4ff713966`. All implementation remains
uncommitted. Existing M1–M4 acceptance is preserved; no redesign/solver rewrite.

6November update: publication blocker resolved, actual focused2/2 and full39/39assertions
PASS using fresh drafts/current revisions; see M5_PUBLICATION_QUALIFICATION.md. Historical
failed receipts below are retained. Remaining release gates are npm, actual Linux/Actions
and approved cloud configuration/provider acceptance. No further publication approval
is pending; no Git/cloud authorization was added.

## Docker/Linux result

BLOCKED runtime execution. Read-only prerequisite inspection found Windows10Pro22H2,
build19045.6466, Intel i3-6006U,4logical processors,7.88GiB RAM (~1.21GiB free),12.17GiB
free C: disk. CPU supports SLAT/VM monitor extensions, but firmware virtualization is
disabled and HypervisorPresent is false. Docker is absent; WSL is an unusable install stub.
No BIOS/Windows features, software installer, PATH, global agent settings or restart was
performed. Owner now directs NO Docker/WSL/firmware changes. No approved Linux runner
exists; the existing workflow now has a prepared container/OCR/health job for a later
separately authorized push. Native qualification remains pending actual runner execution.
References: [Docker Windows prerequisites](https://docs.docker.com/desktop/setup/install/windows-install/).

IMPLEMENTED-UNVERIFIED native Linux OCR: Gateway-only Poppler/Tesseract/English/fonts;
digital extraction first, dimension/page/TSV/time/resource bounds, private temp cleanup,
no shell/no cloud upload. Independent review found orphan-child cleanup; fixed owned
POSIX group termination even after leader exit, with portable regressions.10Linux-adapter
boundary tests plus18existing scanner tests pass28total; native OCR is not inferred.
Synthetic image generation is portable; `scripts/linux_runtime_probe.py` imports each
service, independently validates an OR-Tools control and checks four document types plus
unsafe-file denial/cleanup. Container memory/CPU enforcement still needs actual execution.

After a compatible approved runtime exists, from repository root, use unique local image
tags per service and build `Dockerfile` with `--build-arg SERVICE=gateway`, `academic`,
`scheduling`. Run each image read-only/non-root, dropped capabilities, no-new-privileges,
private tmpfs and no network for `python -m scripts.linux_runtime_probe`. Record platform,
digests, native package versions and results; run native package vulnerability scans.
Then use the existing Compose contract with independently granted disposable PostgreSQL
roles/TLS and ignored per-service environment files. Only Gateway binds loopback. Check
all `/health`, Gateway `/api/v1/services/{academic,scheduling}/health`, protected401 and
current-membership reads; stop a dependency, require503, recover and require200.
Never mount `var`, personal Downloads or original databases. No automatic migration/seed.

## Postman result

Official portable Postman CLI1.86.0 downloaded into ignored `var/m5-postman-portable`;
Authenticode signature VALID, signer Postman, Inc.; SHA256
`00ccc2a2f64a4efe65bd4e492d541bbe860467be8d446205dabfa2548b307f7f`.
Installer script was read only, never executed (it also modifies global agent instructions
and sends installer telemetry). No global installation/login or cloud collection linking.
The previously rejected vulnerable Newman tool was not reinstated.

Initial actual local run:13requests/13assertions PASS, two folders: authorized core reads/401 and
emulator signup/pending status/no institutional identity/unverified claim/faculty escalation/
scanner denial. Runner uses isolated profile, no-report-events, local unlinked collection,
loopback services, no real credentials, no environment/response export. Temporary token
environment is deleted in finally. First harness attempt stopped before requests on a
host-versus-URL validation mismatch; fixed without weakening guards.

Expanded focused execution:35requests,39assertions,38PASS/1FAIL. Actual Student claim/
Admin approval, faculty invitation/Teacher acceptance/replay denial, academic inputs,
readiness/generation, publication review, Student/Teacher assigned published views, PDF
upload/read/manual correction/matched enrollment/wrong-term/delete404 and role denials
passed. Duplicate signup400, missing token401, forbidden403, conflict409, created201 and
deleted204 were exercised. Publication expected200 but received409 using the existing
fixture draft. The initial expanded attempt had pending-token shadowing of the Admin
token; correcting session separation resolved those failures. Do not change the expected
publication response to hide this harness problem. Persistent-failure approval requested
before fresh-draft correction/retry; full Postman acceptance remains PARTIAL.

Independent exit review also found that throwing pre-request errors does not guarantee
request cancellation, and environment-only URL checks miss effective-variable overrides.
Denied guards now call `pm.execution.skipRequest()` and check effective destinations.
Actual Postman guard qualification:6denied folders,0HTTP receiver hits, including an
iteration-data destination override. This separate denial-only check does not retry or
close the gated publication journey. See `scripts/postman_guard_qualification.py` and
[Postman skipRequest](https://learning.postman.com/v11/docs/tests-and-scripts/write-scripts/postman-sandbox-reference/pm-execution).
Actual connected application acceptance separately covers full roles/publication/scanner/
matching/requests/recovery. Optional Firestore/Storage/Gemini actual-provider folder remains
BLOCKED until approved credentials/configuration; static tests are not cloud evidence.
[Postman local-run/reporting contract](https://learning.postman.com/docs/postman-cli/postman-cli-collections).

## Seven-node npm security assessment

Fresh `npm audit --json` reports moderate7, low/high/critical0. One advisory propagates
through seven nodes: [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249),
globparts amplification DoS, affected minimatch>=7,<11.0.1; fixed11.0.1.

| Affected installed node | Version | Dependency route |
|---|---|---|
| typescript-eslint |8.71.1| frontend development dependency |
| @typescript-eslint/eslint-plugin |8.71.1| typescript-eslint → plugin → parser/utils |
| @typescript-eslint/parser |8.71.1| typescript-eslint → parser → typescript-estree |
| @typescript-eslint/type-utils |8.71.1| plugin → type-utils → typescript-estree |
| @typescript-eslint/utils |8.71.1| plugin/parser parent graph → utils → typescript-estree |
| @typescript-eslint/typescript-estree |8.71.1| typescript-eslint → typescript-estree → minimatch |
| minimatch |10.2.6| node_modules/@typescript-eslint/typescript-estree/node_modules/minimatch |

`npm ls minimatch --omit=dev` is empty; exposed environments are lint/build tooling/CI,
not installed production dependencies. The observed estree call uses `{dot:true}` without
the advisory's optimizationLevel>=2 trigger. This limits observed reachability, not audit
coverage. ESLint's separate minimatch3.1.5 lies outside this advisory range.
Current reviewed upstream typescript-estree8.72.1 still requests minimatch^10.2.2:
[upstream manifest](https://raw.githubusercontent.com/typescript-eslint/typescript-eslint/main/packages/typescript-estree/package.json).
No supported compatible parent update closes it. `fixAvailable:true` is not compatibility
proof. No force fix, unqualified major override, advisory exclusion or threshold change.

Mitigation proposal pending owner disposition: keep CI runner isolated/no deployment
credentials for untrusted PRs, restrict supplied glob configuration to reviewed repository
files, await supported parent fix or separately qualify a11.0.1 override. Existing low
audit gate remains failing; production is NO-GO. No exception has been approved.

## Reviewed Git checkpoint plan — no staging/commit/push performed

Generate exact changed/untracked inventory with `scripts/m5_checkpoint_review.py` into
new local evidence. It classifies source/tests, config, generated versioned contracts/
Postman and excluded private/raw evidence; hashes candidate bytes and flags narrow secret
indicators without printing values. This is not a comprehensive secret certification.

Exclude and preserve ALL `docs/academic/**`, private workbook/source photos, personal PDFs,
`var/**`, databases/backups, populated environment/keys and raw `docs/production/**` logs,
screenshots/diagnostics. Only separately reviewed `CLOUD_RUN_STAGING.md` is a production-doc
candidate. Supplied personal registration PDF remains outside the repository. Inspect the
packaged curriculum catalog as curriculum-only review data; it does not contain student
enrollment/identity and does not authorize institutional offerings. Provenance review of
original private inputs remains a separate owner process, not a claim of portable tests.

For an approved future checkpoint: create `codex/m5-release-qualification`, stage only an
explicit reviewed path allowlist; inspect staged names/diff/secrets and generated contract
reproducibility. Do not use `git add .` or include local evidence wholesale. User must
approve exact checkpoint content before commit. After separate push permission, open a
minimal PR describing final functionality, synthetic tests and unresolved security/native/
provider checks; keep deployment disabled. No current index/branch/HEAD change is intended.

## CI and clean-checkout readiness

CI uses Node22/npm lock, Python3.12, pip26.2.2, pytest9.0.3, pinned security constraints;
current requirements include bounded ranges as well as exact pins, so container resolution
is not a fully transitive Python lock. Preserve the qualified exact-version audit and
record actual image dependency resolutions before releasing immutable digests.

Fixed portable tests: two academic test modules now create invented39-source/2062-course
CSV/catalog/OOXML and12-code-review inputs under pytest tmp_path, preserving inventory/
reconciliation/provenance/alias-negative assertions. They no longer read local academic
staging or overwrite original review reports. Additional workbook/hash/page negative
cases are maintained; runtime packaged-catalog structural checks stay independent.
Focused21tests PASS; lint/format PASS. Final full backend1063PASS/107.08s, one existing
Starlette deprecation warning. Scanner-focused28PASS/3.37s; security19PASS; full Ruff and
pip check PASS. Frontend source/lock were unchanged by this final qualification task;
prior804frontend tests/both builds/artifacts4 remain historical evidence, not newly run.
No tests skipped/xfail or guards relaxed. The later Postman-only harness addition is
separately exercised; the full backend was not wastefully repeated for test tooling.

After authorized push, Actions must run at the exact release-candidate SHA: locked npm
install, peer tree, audit(low gate), lint/typecheck/security/frontend/builds/artifacts;
Python install/Ruff/full tests/exact dependency audit on Linux. Add actual three-image
build/native probe/health acceptance once runtime results are available. An old SHA's
Vercel status cannot qualify uncommitted source. Read-only GitHub inspection returned
Vercel success and an empty PR-filtered run list; unrestricted Actions/dirty candidate
verification remains UNVERIFIED. No remote workflows were triggered.

## Remaining approval/runtime boundaries

1. Execute prepared native image/communication/OCR checks on a later approved Linux CI
   runner/push. Owner prohibits local Docker/WSL/firmware changes; no runner is available now.
2. npm advisory fix or explicitly approved disposition; current low gate remains blocked.
3. Postman fresh-draft correction/qualification PASS6November; optional actual provider
   checks remain open.
4. Authorized reviewed Git checkpoint/push, then exact-SHA remote Actions qualification.
5. Staging region/budget/identity/network-IAM/TLS/grants/migration/retention configuration,
   credentials and explicit provisioning/deployment approval; then execute full checklist
   in `M5_STAGING_ACCEPTANCE.md`. No production cutover authorization is implied.
