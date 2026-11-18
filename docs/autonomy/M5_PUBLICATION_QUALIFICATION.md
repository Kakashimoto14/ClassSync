# M5 publication qualification — 6 November 2026

Publication/Postman **PASS**. Overall M5 **PARTIAL**, release **BLOCKED** by the remaining
security/native-Linux/remote-CI/provider gates. Base/current HEAD remains
`aea9494db46153672a31a2161070e5e4ff713966`; no commit, push or deployment.

## Diagnosis and smallest correction

The fixture had already published its draft/calendar at head1. The failed command reused
that draft/calendar with expected_version1 and a new idempotency key. Authentication,
ownership and academic/head revision checks succeeded; review200 did not commit. Publish
correctly returned409duplicate_publication. A new key cannot override duplicate semantics.
The old control was reproduced against a new disposable fixture, with unchanged history.

Only the qualification harness changes publication behavior: generate a fresh server run
through Gateway, require feasible/optimal/independent valid result, save a new authorized
draft201, then use current academic revision/publication head/calendar and new keys. No
application publication, solver, schema, RLS, role, deadline or response assertion changed.

One initial focused CLI invocation rejected folder-path selection before any HTTP request.
Selection was corrected by copying the two original requests, auth and guard scripts into
an owned temporary collection. The actual focused retry then passed2requests/2assertions,
including successful HTTP200 publication. Only after that passed did the original full
35-request/39-assertion collection run: **39PASS/0FAIL**,5.5seconds. These are39assertions,
not39HTTP requests. No full frontend/backend/browser suite was repeated.

## Evidence and security boundaries

- Focused publication advanced head1→2, full set advanced2→3; each added exactly one row
  to API-visible history and used a different saved draft. Old history summaries remain
  unchanged except expected published→superseded status. This is not a new raw-database
  checksum audit; existing database immutability/RLS infrastructure was unchanged.
- Same-command replay200 returned the original publication and added no history. Missing
  token401, Student/Teacher publication403 and stale-key/head409 produced no new versions.
- Full-set Student and Teacher timetables contained assigned sessions and both matched
  current publication3. Signup/verification/linking/invitation/replay, term matching,
  synthetic PDF review/delete, wrong term and role denials passed unchanged assertions.
- Actual denial-only Postman guard run:6denied folders,0HTTP receiver hits, effective
  variable override denied. No cloud login/reporting, real data, exported credentials,
  public document URLs or retained populated environment; private env deleted on exit.
- Official Auth Emulator, Gateway/Academic/Scheduling and new disposable PostgreSQL were
  used. Owned Auth/PostgreSQL stopped; emulator denied-outbound counter0 is scoped to that
  process, not whole-machine telemetry. Existing cross-tenant/RLS checks also ran in the
  reused setup. No original SQLite connection/import/migration/write occurred.

Receipts: `../production/m5-publication-20261106/postman-final-02.json`, focused/full console
logs, `postman-guard-final.log`. Earlier failed selection receipt is retained, not erased.
Fresh targeted checks: security19PASS; container contracts7PASS/0.27s; Ruff PASS. Workflow
parsed with installed js-yaml; extracted bash passed Git Bash `bash -n` (syntax only).
Prior1063backend/804frontend/browser/build acceptance is historical, not rerun evidence.

## Exact source/config changes in this continuation

- `scripts/postman_local_qualification.py`: fresh-run/draft/current-head setup, duplicate
  diagnostic, focused-before-full runner, immutable history/replay/denial/current-role checks.
- `scripts/linux_runtime_probe.py`: bounded fixed-localhost service communication/401 and
  controlled Academic outage503/recovery checks for execution inside the Linux Gateway.
- `.github/workflows/quality.yml`: bounded20minute Ubuntu container job; three existing
  images built locally, native probes/solver/OCR, internal service network, read-only/
  non-root/capability-dropped containers,1CPU/1GiB limits, temporary cleanup. No image
  publication, host ports, host data mounts, cloud secrets or deployment. Existing jobs
  and security gates remain intact. No trigger added; future authorized push/PR only.
- Approval/acceptance/status/evidence and API/staging notes updated for current results.

## Outstanding release gates

**Dependency security:** fresh npm audit still7moderate affected nodes, high/critical0,
one [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249). Current
TypeScript-ESLint8.72.1 still requires minimatch^10.2.2; latest10.x is10.2.6; fixed11.0.1
is outside that supported range. No compatible parent fix is available. Lockfiles and
dependencies unchanged; no force fix/major override/waiver/threshold relaxation. Prior
assessment/exposure/mitigation in M5_RELEASE_QUALIFICATION.md remains applicable. Low
audit gate continues failing until supported fix or explicitly approved disposition.

**Linux/Actions:** owner confirmed no approved Linux runner exists and requests prepared
checks for a later approved push. Local virtualization is disabled; no Docker/WSL/BIOS
changes attempted or planned. Container/native OCR and new job remain IMPLEMENTED-
UNVERIFIED. YAML/bash/static checks are not Linux runtime or remote Actions PASS. After
separate checkpoint/push approval, require exact-SHA GitHub Actions results, image build/
dependency/native package scans and runtime receipts. Existing dirty source was not sent
to any external runner or cloud service.

**Connected staging:** follow M5_STAGING_ACCEPTANCE.md for variable names/descriptions,
separate Firebase staging Auth/domain/trusted provisioning, same-origin connected frontend,
three services/internal ingress and invocation identity, least-privilege managed PostgreSQL/
verified TLS/migrations/restore, private scanner temporary storage/retention and optional
non-authoritative Firestore/Storage/Gemini credentials/quotas. Region/budget/IAM/service
transport still require owner configuration/approval. No cloud resources/providers were
configured or called; the complete synthetic provider checklist remains required.

**Reviewed Git checkpoint:** source/config/curated docs only, explicit allowlist and staged
diff/secret review after owner approval. Exclude all private academic staging, original
forms/DBs/backups/keys/populated envs, raw test receipts/screenshots and portable binaries.
No index/branch/HEAD change. Use current worktree review and existing checkpoint plan;
do not stage wholesale or treat the audit blocker as waived.

## Preserved original SHA-256

| File | SHA-256 |
|---|---|
| var/academic.sqlite3 | `4cd5f60de21bd365c914ac01e5be692b3bea1c7a56a7f17a76c6953ef8668738` |
| var/scheduling.sqlite3 | `edd232195a1fcf79389bf633ce3fbdc8120705923c5d1441810069a878c1d88d` |
| var/backups/scheduling-before-s2b-20261018074057.sqlite3 | `9ec149413d69c1165b74a75e366fa262417c1ecbf41e7029fdd0d86ac96f395d` |

All three freshly match the owner-confirmed checkpoints, including the intentional Demo
save. Evidence contains synthetic data only; original academic documents remain excluded.
