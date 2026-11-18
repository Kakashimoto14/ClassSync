# ITELECT3 tutorial traceability and qualification

6November: full core connected Postman39/39assertions PASS after focused publication2/2,
using fresh authorized server drafts/current revisions. Denied writes/history/role views
and denied HTTP guard checks PASS. See M5_PUBLICATION_QUALIFICATION.md. Native Linux/remote
CI and real providers remain unqualified;7moderate npm nodes still block release.

Final qualification update5November:1063backend/security19PASS; signed Postman CLI actual
core/pending13PASS and expanded35requests/39assertions38PASS/1publication-harness409.
Pending approval for fresh-draft correction, not full collection PASS. Linux OCR source
implemented/tested at portable boundaries; native containers blocked by disabled firmware
virtualization. Seven npm moderate nodes and external-provider/Actions qualification remain
open. Current final detail overrides historical availability claims below; see
M5_RELEASE_QUALIFICATION.md and M5_STAGING_ACCEPTANCE.md. No cloud/Git deployment occurred.

The supplied `fastapi-firebase-microservices-tutorial.pdf` was read locally (four pages).
Its examples are reference material, not authority to change PostgreSQL ownership,
create live accounts, upload academic evidence or spend/deploy cloud resources.

| Tutorial requirement | Implemented source / API | Evidence and actual status |
|---|---|---|
| FastAPI/Pydantic | Existing three services; Gateway coursework_schema.py, coursework.py, onboarding/registration/announcements | Offline contract/authorization tests pass; full exit results in STATUS.md |
| Swagger/OpenAPI | Gateway openapi.py, `/docs`, `/redoc`, `/openapi.json`; bearer entry and distinct IDs per HTTP operation | Generated schema tests pass, including all verbs; browser/cloud Swagger staging check remains open |
| Firebase token and401 | Existing token_verification/request_authorization plus every course route's current-membership check | Missing-token401, untrusted-authority denial and existing actual Auth Emulator/PG/browser journey pass; live cloud identity qualification remains separate |
| GET/POST/PATCH/DELETE | `/api/v1/coursework/preferences`; existing announcements also implement all four | Offline request/schema/ownership tests and generated Postman sequence; no real Firestore CRUD qualification claimed |
| Firestore CRUD | coursework_cloud.py; only owner-scoped calendar-view/compact/revision/generation | **IMPLEMENTED-UNVERIFIED cloud**. ADC/project/database approval/configuration missing. Generation protects delete/recreate; CAS uses server update time. No institutional records duplicated |
| Private Cloud Storage | POST `/coursework/files`, GET/DELETE `/files/{uuid}`; project/tenant/UID prefix, synthetic text, bounded attachment | **IMPLEMENTED-UNVERIFIED cloud**. Private bucket refusal/ownership/size tests pass; actual IAM, enforced PAP/uniform access and retention qualification missing. No public URLs or registration-form integration |
| Gemini | POST `/coursework/advisory`; fixed topic enum,10s total deadline,64KB response,160 output tokens,1200 chars | **IMPLEMENTED-UNVERIFIED cloud**. Slow-stream cancellation and input/quota denial tests pass. Approved model/key/budget/provider quota missing; no enrollment/role/schedule decisions |
| Postman | docs/api/ClassSync.postman_collection.json and environment; reproducible generator | Two offline artifact tests pass. Tokens blank; core folder read-only; cloud folder throws until explicitly approved. Postman/Newman execution not claimed |
| Environment/CORS/secrets | Settings exact HTTPS/loopback origins, secret fields, per-service Compose env templates | CORS negative tests/pip check/source review pass; no cloud secret/IAM/settings changes |
| Docker/Cloud Run | Dockerfile, compose.yaml, .dockerignore, validated container_entrypoint.py, CLOUD_RUN_STAGING.md | Seven entrypoint tests pass; **image/run UNVERIFIED**, Docker absent. No cloud deployment. Linux OCR unsupported; digital PDF/manual available. IAM transport/networking and approved same-origin frontend proxy require staging qualification |

M1–M4 local acceptance remains separate from cloud production certification. The actual
final connected M5 control is `../production/mvp-20261104/m5-connected-final.json`:
144697ms, all three roles/publication/request/rollback/notices/rooms/profile/recovery/
revocation and SQL controls pass, errors0/healthy503=0/outbound0; Auth/PG stopped.
These are synthetic owned environments, not imported rosters or live publications.

## Security and CI constraints

Python's exact-version audit now covers77 third-party versions, zero findings; four
pyasn10.6.4 advisories were fixed by the compatible0.6.5 constraint/runtime patch.
Scanner name identity now follows PEP503 (including Windows OCR dotted names) and
respects requirement platform markers; complete coverage/no-skip guards remain intact.

`m5-npm-audit.json` reports seven moderate development-tool findings, no high/critical.
The affected TypeScript-ESLint parent currently8.71.1 and inspected latest8.72.1 both
require minimatch^10.2.2. The [official advisory](https://github.com/advisories/GHSA-g3hv-75wg-m249)
requires11.0.1 or newer for its fix. No supported parent-range fix was identified; no
forced major downgrade, unsupported override, exclusion or raised audit threshold was
applied. **Dependency-security/release gate remains BLOCKED**, even though the observed
affected package path is development tooling. No browser exploit claim is made.

Read-only GitHub connector checks for base SHA aea9494db46153672a31a2161070e5e4ff713966
returned an existing Vercel success status and no PR-filtered workflow runs. This does
not prove push-triggered GitHub Actions status or qualify the dirty current source.
The connector lacks an unrestricted workflow list, `gh` is absent, and public REST
fallback was inaccessible. **Remote Actions status UNVERIFIED**. No workflow was
triggered, commit pushed, deployment performed or settings/secrets changed.

Process-local course quotas reset/restart and do not enforce a distributed daily spend
cap. External quotas, budgets, edge limits and IAM/privacy evidence are mandatory before
any actual cloud qualification. See CLOUD_RUN_STAGING.md for the bounded approval checks.

An isolated Newman6.2.3 runner was considered for core collection execution. Its
dependency audit failed (19 findings, including1 critical); lifecycle scripts had been
disabled and the runner was never executed. The newly created tool directory was
removed after exact resolved-path/ownership checks; its audit/install evidence is
retained as `m5-newman-audit.*`/`m5-newman-install.log`. Application dependencies were
not changed by that attempt. Postman runtime verification is therefore still blocked;
no CLI result is substituted for the two static artifact checks.
