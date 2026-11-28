# Seeded Teacher and Student logins (defense/sandbox)

`scripts/provision_seeded_logins.py` gives the **existing** seeded faculty and student records real
sign-ins. Approved 28 November 2026 (`docs/autonomy/APPROVALS.md`, Phase E). These are
owner-authorized synthetic records, not Registrar-verified identities, and their
`verification_source` stays `unverified`.

It is owner-run. Nothing calls it at startup, and it has not been run against a hosted project.

## What it does

| Step | Effect |
| --- | --- |
| Select | Only rows that match the defense seed exactly (record ID, person ID and, for students, the seeded email) and are still in the period. Edited, imported and hand-made rows are ignored. |
| Firebase | Creates the user with `email_verified=true` (the Admin SDK sends no email), or reuses an existing one. |
| Membership | One active single-role membership per account, linked to the exact record. The audit actor is your Administrator UID. |
| Students | Sets `password_configured`. With `--activate-enrollment`, marks `unverified` enrollments active through the audited roster path. `inactive` students are left alone. |
| Credentials | Written only to `.local/seeded-logins.csv` (git-ignored). Passwords are never printed. |

It never creates a roster or faculty row, never changes an Administrator account, never re-points a
record another account already holds, and does not run migrations.

## Before you start

1. The defense seed has been applied (`scripts/seed_campus_data.py --apply`) and the database is at
   the current migration head.
2. In Firebase console, the **Email/Password** sign-in method is enabled (you change this yourself).
3. You have the Firebase service-account JSON file for the same project, stored outside the repository.
4. You know your Administrator's Firebase UID (Firebase console → Authentication → Users). Use the
   same UID that seeded the data, because it owns the academic period.
5. The database URL uses the same non-superuser, non-`BYPASSRLS` role you migrate with. It must
   include the port, and its only query parameter may be `sslmode=require` or `sslmode=verify-full`.
   Remove extras such as `channel_binding=require`.

## Order matters: activate before you publish

`--activate-enrollment` advances the academic period revision, exactly like the Admin **Mark
active** action. An already published timetable stays readable. However, a draft saved before the
change no longer matches the records, so publishing it again (including approving a Teacher room
change request) is refused with `academic_input_changed`.

- **Preferred:** apply with `--activate-enrollment` first, then generate, save and publish.
- **Already published:** after activating, generate a new draft and publish it before any request
  approval or republication.

Without `--activate-enrollment` the run creates logins only and does not change the revision.

## Set up the shell (Windows `cmd`)

Run from the repository root in a `cmd` window you will close afterwards.

```bat
cd /d C:\Projects\ClassSync
set "MIGRATION_DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=verify-full"
for /f "usebackq delims=" %i in (`.venv\Scripts\python.exe -c "import json,sys;print(json.dumps(json.load(open(sys.argv[1],encoding='utf-8'))))" "C:\secrets\classsync-service-account.json"`) do set "FIREBASE_SERVICE_ACCOUNT_JSON=%i"
set "FIREBASE_AUTH_EMULATOR_HOST="
set "ADMIN_UID=PASTE-ADMINISTRATOR-UID"
```

(Inside a `.bat` file, write `%%i` instead of `%i`.)

## Dry run (default, writes nothing)

A focused set: one section's students and the teachers who teach it.

```bat
.venv\Scripts\python.exe scripts\provision_seeded_logins.py --dry-run --tenant-id cdm --operator-uid %ADMIN_UID% --section BSIT-3A --faculty-email-domain faculty.example.edu --activate-enrollment
```

Everything seeded (57 teachers and up to 432 students):

```bat
.venv\Scripts\python.exe scripts\provision_seeded_logins.py --dry-run --tenant-id cdm --operator-uid %ADMIN_UID% --all-seeded --faculty-email-domain faculty.example.edu --activate-enrollment
```

Check the counts and every listed skip. A dry run cannot see records already held by a *different*
account (row-level security hides them); `--apply` detects and skips those.

## Apply

```bat
.venv\Scripts\python.exe scripts\provision_seeded_logins.py --apply --confirm-defense-tenant cdm --tenant-id cdm --operator-uid %ADMIN_UID% --section BSIT-3A --faculty-email-domain faculty.example.edu --activate-enrollment
```

```bat
.venv\Scripts\python.exe scripts\provision_seeded_logins.py --apply --confirm-defense-tenant cdm --tenant-id cdm --operator-uid %ADMIN_UID% --all-seeded --faculty-email-domain faculty.example.edu --activate-enrollment
```

Replace `faculty.example.edu` with the domain you want in teacher sign-in addresses
(`faculty.maria.santos@<domain>`). There is no default. Keep it the same between runs: changing it
later does not rename accounts, and affected teachers are reported as conflicts.

`--all-seeded` makes hundreds of throttled Firebase calls and takes several minutes. It is safe to
rerun after an interruption: finished accounts are reported `unchanged`.

## Targeting

| Flags | Selects |
| --- | --- |
| `--all-seeded` | Every seeded teacher and student. Cannot be combined with the others. |
| `--program BSIT` | That program's students and the teachers of its sections. |
| `--section BSIT-3A` | That section's students and teachers. |
| `--teachers 5` | The first 5 seeded teachers by record ID, and no students. |
| `--students 10` | The first 10 seeded students by student number, and no teachers. |
| `--section BSIT-3A --teachers 0` | `0` leaves that role out; give the other role's count if you need it. |

Combining `--teachers` and `--students` selects both. `--period-id` overrides the default period
titled `AY 2026-2027 · 1st Semester`.

## Signing in

Open `.local\seeded-logins.csv` (close it again before the next run, or the script stops).

- **Teachers:** email and password.
- **Students:** email and password. Student-number sign-in also works once the enrollment is active
  (`--activate-enrollment`).

## Passwords

The default is a random 20-character password per account. To use one shared password instead, set
it before `--apply` (12–128 printable characters), then clear it:

```bat
set "CLASSSYNC_SEEDED_LOGIN_PASSWORD=choose-a-long-shared-password"
```

```bat
set "CLASSSYNC_SEEDED_LOGIN_PASSWORD="
```

An existing Firebase account keeps its password unless you pass `--rotate-passwords`; its CSV row is
blank with a note. `--rotate-passwords` sets a new password on every selected non-Administrator
account, including ones people are already using. New rows are merged into the CSV; a stored
password is replaced only when a new one is set.

## Reading skips

| Message | What to do |
| --- | --- |
| `protected: … Administrator account` | Nothing. Administrator accounts are never changed. |
| `conflict: another account already holds this record` | Someone already claimed it. Review in Admin → Account administration. |
| `conflict: this account is already linked to a different record` | The email belongs to another person's membership. Review it manually. |
| `conflict: membership is inactive/revoked` | Reactivate deliberately in Admin if intended. |
| `an unverified account already uses this email` | Someone registered it but never verified. `--rotate-passwords` takes it over. |

## After the run

- Delete `.local\seeded-logins.csv` when it is no longer needed, and close the `cmd` window.
- The CSV is owner-readable only where the OS supports it. On a shared Windows machine, restrict it:

```bat
icacls .local\seeded-logins.csv /inheritance:r /grant:r "%USERNAME%:F"
```

- There is no removal mode. To stop an account signing in, disable the user in Firebase console.
