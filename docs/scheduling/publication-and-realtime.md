# Publication and real-time schedules

## Scope and deployment boundary

C1 and C2 implement the local Gateway → Academic service → OR-Tools → immutable draft
→ validated published version → role projection → server-originated update flow.
No automatic publication occurs on generation, saving, preview-role selection or import.
Existing working databases were not seeded or reset during QA; all browser scenarios
used separate databases in the task evidence directory.

The frontend remains a preview application with production sign-in unavailable. The
backend publication boundary verifies Firebase ID tokens (including revocation), an
Administrator claim and institutional tenant/owner scope. Configuring real Firebase
identities, trusted faculty claims and actual student enrollment records is necessary
before institutional use. Client role/section selections authorize no production reads
or writes. Anonymous development publication is deliberately absent.

Synthetic fixtures/publication are separated by dataset and owner namespace. Sandbox
read/import/generation routes require both `CLASSSYNC_ENV=development` and
`ENABLE_SCHEDULING_SANDBOX=true`. Synthetic publication additionally requires verified
Administrator credentials. These routes must remain disabled on the public demo.

## Persistence and validation

The Academic SQLite schema adds a calendar table through migration v3. Existing period,
record and revision data are retained. Calendar edits require the expected source
revision, increment it, and leave saved drafts unchanged. Midterm and Final Term are
effective date phases inside one semester; they do not duplicate offerings or minutes.

Publication uses the existing scheduling SQLite connection and `BEGIN IMMEDIATE`:

1. Authorize the saved draft's owner/source and refresh academic readiness, revision
   and normalized scheduling-input hash. Reject mismatched semester, instructional
   weekdays and out-of-period effective dates.
2. Revalidate the complete immutable solver result and dataset purity. Expand dated
   occurrences, cancellation/move exceptions, teaching windows and resource rules.
3. Within the publication transaction, reread the immutable draft, check the expected
   publication head and idempotency key, and check active resource/section/teacher/
   irregular-student overlaps, buffers, teacher workloads and room restrictions.
4. Insert a checksummed immutable version containing the full draft snapshot and dated
   calendar, then advance the publication head atomically. The sequence is the durable
   event cursor. A rollback leaves neither a partial head nor a partial version.

Unique constraints and serialized writers prevent competing requests from silently
overwriting a version. Identical retries return the committed acknowledgement;
different commands sharing a key fail. Duplicate draft/calendar publication fails.
Update/delete triggers protect published history. Audit summaries retain actor,
timestamp, draft, dataset, revision, scope counts and calendar. Prior payloads remain
recoverable in the database. There is no destructive rollback button: restoring a
prior timetable requires a new reviewed version.

The newest version wins only for its effective dates. An older version may continue
to supply earlier dates even when the history labels it Superseded. Different periods
remain isolated for display but are checked together for resource conflicts in the
same tenant/dataset. Cancellation exceptions suppress occurrences; moved occurrences
retain their original stable identity and use their actual date/time for collisions.
All intervals are half-open, with Asia/Manila offsets. Queries are limited to 63 days;
publication expands bounded chunks and rejects scopes exceeding 100,000 occurrences.

Academic readiness is fetched from a separate service before the SQLite publication
transaction. There is no distributed transaction across the two services. Production
infrastructure should co-locate revision coordination or provide a transactional
publication lease before allowing simultaneous institutional academic edits and
publication at scale. SQLite and the measured small scenarios establish local behavior,
not school-wide throughput or a distributed deployment guarantee.

## API and delivery

Gateway forwards these `/api/v1/timetables` endpoints to Scheduling:

| Endpoint | Purpose |
| --- | --- |
| `POST /review` | Authoritative readiness and affected-scope counts; no publication |
| `POST /publish` | Verified Administrator publication with expected revisions/key |
| `GET /history/{period}?dataset=…` | Authorized retained version/audit summaries |
| `GET /periods`, `/calendar/{period}` | Identity-derived institutional projections |
| `GET /events/{period}` | Authenticated finite SSE stream with ordered version metadata |
| `GET /availability` | Published occupancy/restrictions, unknown suitability |
| `PUT /restrictions/{id}` | Administrator operational restriction/reservation with revision check |
| `GET /sandbox/{periods,calendar/{period},events/{period},availability}` | Explicitly gated synthetic read equivalents |

Production Students are filtered by their verified UID and explicit offering enrollment
in the version supplying each occurrence, including cross-section enrollment. Teachers
are filtered by the trusted faculty identity. Administrator scope is tenant-wide.
Unpublished drafts never feed published personal projections. Sandbox clients explicitly
select a mock section or teacher; pre-publication selectors expose metadata, no draft
assignments. Occupancy responses expose counts/status, not other users' class details.
Uncovered dates return Unknown. Unverified capacity/equipment remain Unknown regardless
of whether a room is unoccupied.

SSE polls the committed database sequence and emits only version ID, sequence and period
ID. The gateway forwards the streaming response without buffering. Each stream ends
after about 20 seconds, forcing token revalidation on reconnect. The browser reconnects
with exponential backoff and an ordered cursor, ignores stale/duplicate sequence IDs,
and refetches the authoritative projection on version, online and visibility-resume
events. Core schedule data stays visible during interruptions. A concise update notice
appears only when the selected identity's occurrences change. The client never sends
a publication notification as evidence of a committed version.

## Verification evidence

The C1 gate ran before C2: persisted academic import, readiness, real generation,
immutable save, and Student/Teacher occurrence browsing at 390px/1440px. Two offerings
produced four validated weekly sessions. Increasing-scope measurements are recorded in
`../academic/sample-data-provenance.md`; they do not claim institution-wide readiness.

C2 browser testing used three independent Chrome contexts, real local services, isolated
SQLite databases, a BSIT 3A mock student and an explicitly eligible mock teacher. A
test-only process outside the repository supplied deterministic Firebase verification
claims. It was not live institutional authentication and adds no shipped auth bypass.
The Administrator UI reviewed/published the initial version, then reviewed/published a
room exception. Both connected personal calendars changed without reload. Additional
offline/recovery evidence and final test counts are recorded in the task QA report.
`c2-cross-client.json`, `c2-recovery.json` and `c2-*.png` retain the observations.

Public deployment requires durable shared persistence, a reachable authenticated API,
trusted identity/enrollment provisioning and a host/proxy supporting streaming. A
frontend-only Vercel deployment cannot share these local SQLite files. No commit, push,
deployment, public sandbox endpoint or production authentication setup was performed.
Public real-time capability is not claimed.
