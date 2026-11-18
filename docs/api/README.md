# ClassSync API qualification

Import `ClassSync.postman_collection.json` and the environment template into Postman.
Regenerate with `.venv/Scripts/python.exe scripts/build_mvp_postman.py`.

Set only local current values: Gateway base URL, an approved account's current Firebase
ID token, its granted workspace, a permitted academic period and increasing ISO dates
within that term. Obtain the token from an approved signed-in Firebase SDK session;
never export a populated environment, refresh token or service-account key. These
core read folder does not mutate accounts or schedules. Additional opt-in folders are
for disposable/synthetic acceptance only; they can create emulator accounts, submit/
approve claims, accept faculty invitations, scan/delete synthetic documents and publish
an approved fresh draft. Never run the entire collection against institutional data.

Run the core folder against the Auth Emulator/disposable PostgreSQL qualification or
an explicitly approved environment. Missing token must return401. Valid membership
returns only permitted periods, classes, rooms and audience notices. Revoke access and
repeat: institutional reads must return403. Do not use an unrelated person's token.

The cloud folder intentionally requires `approved_cloud_qualification=true`. It is
not qualified locally: real approved Firestore, Storage and Gemini configuration and
credentials are missing. Disabled services return503 and are NOT a passing cloud test.
After separate approval, use a fresh demonstration account's preference record and
synthetic text only. Run create/read/update/delete in order; preserve both revision and
generation for edits/deletion. Recreating a record changes its generation, rejecting old
clients. File IDs are opaque; downloads require the same currently authorized owner.
No public Storage URL is generated. The advisory accepts two fixed topics, no documents
or arbitrary prompt, and cannot change memberships, enrollment or publication.

Gateway documentation: `/docs`, `/redoc`, `/openapi.json`. Swagger has Firebase bearer
authorization and a server-verified workspace header. Every HTTP operation has a unique
operation ID; the underlying service authorization remains unchanged.

Offline tests in `services/gateway/tests/test_coursework.py` verify contract/authorization,
private bucket refusal, ownership, stale-generation denial and slow-stream cancellation.
They use stubs and do not establish cloud qualification or Postman-run evidence.

Local runner status: the evaluated isolated Newman6.2.3 dependency audit failed,
including a critical finding. It was not executed and was removed; do not treat this
version as a qualified runner. Final qualification used signed portable Postman CLI1.86.0
without installer/login/cloud reporting.6November focused publication2/2 and complete
35requests/39assertions PASS. The corrected harness generates/saves fresh authorized
drafts with current academic/publication revisions; duplicate fixtures remain rejected409.
See `../autonomy/M5_RELEASE_QUALIFICATION.md`; cloud integration remains unqualified.

The local pending folder requires explicit disposable approval and loopback Gateway/Auth
Emulator URLs. A separate pending token prevents shadowing Administrator credentials.
Selected Admin/Student folders require synthetic-journey approval. Supply current academic
revision and a complete PublicationCommand with owned fresh draft/calendar/version and
unique idempotency key; stale/already-published controls must remain rejected. Never
export populated environments, invitation secrets or bearer tokens. `--postman` on the
existing emulator qualifier runs HTTP acceptance without repeating browser acceptance.
