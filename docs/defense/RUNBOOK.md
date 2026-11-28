# ClassSync defense runbook — accounts and 3-role demo

Owner-run steps for the isolated defense environment: tenant `cdm`, Firebase project
`classsync-8af14`. The assistant never runs these commands. Each live step needs explicit owner
action, as recorded in `docs/autonomy/APPROVALS.md`.

The seeded AY 2026–2027 BSIT data is an owner-authorized demonstration dataset. It is not
Registrar- or Facilities-verified. Use one Teacher login and one Student login only. The existing
Administrator account is never modified by these steps.

## 0. Prerequisites

- The migration head is current (`0030_facility_issue_reports`). Apply it with section 0a
  **before** deploying services built for Slice C3. The deployed services never migrate. Use the
  migration owner role (`classsync_migrator`), never the runtime role.
- The Administrator who will approve requests is the same Administrator who publishes the
  timetable. Publication heads are owner-scoped, and a different Admin's approval returns a clear
  409 `publication_owner_conflict`.
- Run from the repository root in PowerShell, using the project virtual environment.

```powershell
$env:PYTHONPATH = "packages/api-contracts;packages/persistence;."
```

## 0a. Apply migration 0030 and check grants (no seed, no data writes)

The URL must name the migration owner and include the port (`:5432`). Take a Neon branch or restore
point first. Upgrading to `0030` also applies `0029` if it is still pending. The command prints the
connected role and new head, then the Slice C2 privileges, then the Slice C3 grant checks. **Every
value on the second and third lines must be `True`.** The third line checks that `classsync_app` has
only `SELECT`/`INSERT` on issue reports, only `SELECT` on their events, `EXECUTE` on the transition
function, and that both new tables have forced row-level security.

```powershell
$env:PYTHONPATH = "packages/api-contracts;packages/persistence;."
$env:MIGRATION_DATABASE_URL = "postgresql://classsync_migrator:<password>@<neon-host>:5432/<database>"
```

```powershell
@'
import os, certifi
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.engine import make_url
from classync_persistence.configuration import postgres_configuration
from classync_persistence.database import postgres_engine
from classync_persistence.schema import migrate

target = make_url(os.environ["MIGRATION_DATABASE_URL"]).set(drivername="postgresql+psycopg", query={})
url, options = postgres_configuration(
    SecretStr(target.render_as_string(hide_password=False)), transport="verify-full",
    environment="production", firebase_project_id="classsync-8af14", tenant_id="cdm",
    application_name="classsync-migrate", tls_root_cert=certifi.where())
engine = postgres_engine(url, connect_args=options, pool_size=1, max_overflow=0)
with engine.begin() as db:
    migrate(db, target="0030_facility_issue_reports")
with engine.connect() as db:
    print(db.execute(text("SELECT current_user, version_num FROM public.alembic_version")).one())
    print(db.execute(text('''SELECT
        has_table_privilege('classsync_app','classsync_scheduling.room_restrictions','INSERT'),
        has_table_privilege('classsync_app','classsync_scheduling.room_restrictions','UPDATE'),
        has_table_privilege('classsync_app','classsync_academic.period_metadata','UPDATE'),
        has_table_privilege('classsync_app','classsync_academic.announcements','UPDATE'),
        has_function_privilege('classsync_app',
            'classsync_scheduling.audit_roster_import(text,bigint)','EXECUTE'),
        has_function_privilege('classsync_app',
            'classsync_scheduling.room_restriction_windows(text)','EXECUTE')''')).one())
    print(db.execute(text('''SELECT
        has_table_privilege('classsync_app',r,'SELECT'),
        has_table_privilege('classsync_app',r,'INSERT'),
        NOT has_table_privilege('classsync_app',r,'UPDATE'),
        NOT has_table_privilege('classsync_app',r,'DELETE'),
        has_table_privilege('classsync_app',e,'SELECT'),
        NOT has_table_privilege('classsync_app',e,'INSERT'),
        NOT has_table_privilege('classsync_app',e,'UPDATE'),
        NOT has_table_privilege('classsync_app',e,'DELETE'),
        has_function_privilege('classsync_app',
            'classsync_scheduling.transition_facility_issue(uuid,integer,text,text,text)',
            'EXECUTE'),
        (SELECT bool_and(relrowsecurity AND relforcerowsecurity) FROM pg_class
            WHERE oid IN (r::regclass, e::regclass))
        FROM (VALUES ('classsync_scheduling.facility_issue_reports',
                      'classsync_scheduling.facility_issue_events')) AS t(r,e)''')).one())
engine.dispose()
'@ | .venv\Scripts\python.exe -
```

If any value prints `False`, stop and review the runtime grants before deploying. The migration
grants `classsync_app` itself when that role exists at upgrade time; if the runtime role was created
or renamed later, grant exactly the privileges listed above as `classsync_migrator`. Roll back by
restoring the Neon restore point; the Alembic downgrade is refused once any facility issue report,
restriction cancel, period archive or clone, or roster import has been recorded. After applying,
deploy backend and web together.

## 1. Seed (or re-seed) the defense dataset

The seed is idempotent and preserves Administrator edits. It also creates one
`classsync_identity.faculty` identity per seeded faculty record. Teacher provisioning needs these
rows. They are not users and not memberships.

**If the seed was applied before this change, run `--apply` once more** so the faculty identities
exist.

```powershell
$env:CLASSYNC_SEED_ENV = "defense"
$env:DATABASE_URL = "<Neon URL with sslmode=verify-full>"
$env:INSTITUTIONAL_TENANT_ID = "cdm"
$env:FIREBASE_PROJECT_ID = "classsync-8af14"
$env:CLASSYNC_SEED_ADMIN_UID = "<existing Administrator Firebase UID>"
```

```powershell
.venv\Scripts\python.exe scripts\seed_campus_data.py --dry-run
```

```powershell
.venv\Scripts\python.exe scripts\seed_campus_data.py --apply --confirm-defense-tenant cdm
```

## 2. Prepare the Student roster row (Admin UI, no SQL)

1. Sign in as the Administrator and open **Academic Setup → Students** (`/admin/students`).
2. Filter **Section → BSIT-3A**. The first seeded row is `24-00101` (Aira Garcia).
3. Click **Edit 24-00101** and set **Email** to an inbox the owner controls. Click
   **Save Student**. Changing the email marks the row unverified again; this is expected.
4. Click **Mark 24-00101 active**.

## 3. Choose the demo Teacher

Seeded faculty IDs are stable UUIDv5 values. `faculty-01` is
`2e758a04-03ec-5e53-bbdd-7d134e4f42d1` (Maria Santos). Confirm under **Academic Setup → Teachers**
that this teacher has published classes after step 4. If not, choose a teacher who does and use
their record ID.

## 4. Generate and publish (Admin UI)

Go to **Academic Setup** and check that readiness passes. Then **Generate timetable** (expect
54/54 offerings scheduled), review the draft (optionally use **Draft edit** or the **AI
Advisor**), and **Publish reviewed timetable**.

## 5. Provision the Teacher and Student logins

This step creates Firebase users and memberships for exactly the two named people. Without
`--admin-email`, no Administrator account is touched. Leave passwords off to use the secure
prompt, or generate them.

```powershell
$env:DATABASE_URL = "<Neon URL with sslmode=verify-full>"
$env:FIREBASE_SERVICE_ACCOUNT_JSON = Get-Content -Raw "<path to classsync-8af14 service account JSON>"
Remove-Item Env:FIREBASE_AUTH_EMULATOR_HOST -ErrorAction SilentlyContinue
```

```powershell
.venv\Scripts\python.exe scripts\provision_live_accounts.py --tenant-id cdm --confirm-tenant-id cdm --confirm-live-provisioning "PROVISION LIVE CLASSSYNC ACCOUNTS" --operator-uid "<existing Administrator UID>" --teacher-email "<teacher inbox>" --teacher-faculty-id 2e758a04-03ec-5e53-bbdd-7d134e4f42d1 --student-id 24-00101 --student-email "<the email saved in step 2>"
```

## 6. Demo sequence (Admin → Teacher → Student)

1. **Teacher**, signed in: open **My Teaching Schedule**, then **Change requests → Request a
   classroom change**. Pick a class. Rooms are labelled *Available* or *Occupied* for that class
   time, and occupied rooms cannot be selected. Submit with a reason.
2. **Admin**: open **Requests** (`/admin/requests`, also linked from the publication panel). The
   pending card checks live conflicts automatically. Enter a note and click **Approve and publish
   change**. Approval re-validates every hard constraint, publishes a new immutable version and
   fulfils the request in one transaction. If a conflict appeared since submission, approval is
   blocked with the reason. Show **Decline request** on a second request as well; it only stores
   the note.
3. **Teacher**: **Notifications** lists the decision and the note. If Resend is configured, a short
   email arrives. A failed email never blocks the decision.
4. **Student**, signed in: **My schedule** shows the class in the new room. **Notifications** lists
   the changed class. **Rooms → Check room availability** shows which of the 41 schedulable rooms
   have a published class at any 30-minute slot. The 12 excluded spaces never appear.

5. **Facility issue** (needs migration `0030`): **Teacher** opens **Report Issue**
   (`/teacher/report-issue`) and submits a room report. **Admin** opens **Requests → Issue reports**,
   starts work, follows **Add a restriction** if the room must be closed, links it, and resolves with
   a note. The Teacher sees the new status under **Notifications**.
6. **Calendar file:** on a published schedule, **Export .ics** downloads the selected day, week or
   month.

## Known limits (honest scope)

- Requests are one-date room swaps only. Faculty availability is edited by Administrators.
- Room reservations (restrictions) are visible only to Administrators. Teacher and Student
  occupancy reflects published classes, and approval enforces reservations.
- Issue triage does not show who reported an issue, and no email is sent for issue updates.
- The `.ics` file is a one-time snapshot. It does not update when the timetable changes.
- Classroom request history shows only the submission time, the current state and its last change.
- Email goes only to the requesting Teacher. Students receive in-app updates only.
