# ClassSync defense runbook — accounts and 3-role demo

Owner-run steps for the isolated defense environment: tenant `cdm`, Firebase project
`classsync-8af14`. The assistant never runs these commands. Each live step needs explicit owner
action, as recorded in `docs/autonomy/APPROVALS.md`.

The seeded AY 2026–2027 BSIT data is an owner-authorized demonstration dataset. It is not
Registrar- or Facilities-verified. Use one Teacher login and one Student login only. The existing
Administrator account is never modified by these steps.

## 0. Prerequisites

- The migration head is current (`0027_roster_audit_events` at the time of writing). Both scripts
  run `migrate(head)` and fail closed on drift. The deployed services never migrate. Without
  `0027`, every roster add, edit, **Mark active** and delete fails; the seed `--apply` in step 1
  applies it. Use the database owner (migration) role.
- The Administrator who will approve requests is the same Administrator who publishes the
  timetable. Publication heads are owner-scoped, and a different Admin's approval returns a clear
  409 `publication_owner_conflict`.
- Run from the repository root in PowerShell, using the project virtual environment.

```powershell
$env:PYTHONPATH = "packages/api-contracts;packages/persistence;."
```

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

## Known limits (honest scope)

- Requests are one-date room swaps only. Faculty availability is edited by Administrators.
- Room reservations (restrictions) are visible only to Administrators. Teacher and Student
  occupancy reflects published classes, and approval enforces reservations.
- `/teacher/report-issue` and the Admin reports, utilization and buildings pages are not connected
  in the institutional workspace.
- Email goes only to the requesting Teacher. Students receive in-app updates only.
