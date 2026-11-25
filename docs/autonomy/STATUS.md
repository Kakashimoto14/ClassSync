# ClassSync — autonomy status ledger

## 23 November 2026 14:26 SGT — Phase 5 deployment and CI polish

Worktree: `C:\Projects\ClassSync`, branch `main`, base/current HEAD
`f8b85d0084669bc6bc3886be42093d187c9817b4`. Worktree was clean before this phase; no
database, provider, hosted setting, or running dev server was changed.

Gateway now rejects an HTTP or loopback `CLASSSYNC_WEB_URL` during production app startup;
Render exposes the frontend origin and email-provider settings for operator configuration.
Reset, verification, and student-code email sends share an IP bucket. At login-bucket
capacity, oldest non-locked buckets may be evicted while active lockouts remain protected.
Render forwarded-header trust stays disabled by default and accepts only explicit IP/CIDR
allowlists (not hostnames, `*`, or default-route networks). Scheduling contract export now
supports a read-only `--check` mode and CI runs it. Docker build context excludes unrelated
test trees while retaining the two synthetic helpers imported by the in-image qualification
probe. Dockerfile dependency-layer changes were left untouched because Docker is unavailable
for the required image validation.

Files changed: `.dockerignore`, `.env.example`, `.env.gateway.example`,
`.env.notification.example`, `.github/workflows/quality.yml`, `apps/web/.env.example`,
`docs/security.md`, `render.yaml`, `scripts/export_scheduling_contracts.py`,
`scripts/render_entrypoint.py`, `services/gateway/app/main.py`,
`services/gateway/app/onboarding.py`, and focused Gateway tests for contracts, production
origin, proxy trust, and rate limits.

Fresh checks:

- `python scripts/export_scheduling_contracts.py --check` — PASS, generated TS and JSON
  schema match current Pydantic models without writing files.
- Focused Gateway tests — **60 passed**, one existing Starlette/httpx deprecation warning.
- `\.venv\Scripts\python.exe -m pytest` — **1,194 passed**, one existing deprecation warning.
- `\.venv\Scripts\ruff.exe check scripts services packages` — PASS.
- In `apps/web`: `npm run lint`, `npm run typecheck`, `npm test` (**883 passed across 69
  files**), and `npm run build` — PASS. Build largest chunks: React vendor 318.51 kB,
  Firebase vendor 243.92 kB; no build error.
- `git diff --check` — PASS. Render/CI YAML parser check was not available because PyYAML is
  not installed; Docker image build was not run because Docker is not installed.

Remaining manual deployment steps: enter the approved HTTPS `CLASSSYNC_WEB_URL` in Render;
choose the configured email provider and enter its API key and approved sender; leave
`TRUSTED_PROXY_IPS` empty unless the platform's proxy IP/CIDR ranges are verified. No commit
or push was performed. Next: independent YAML/image deployment qualification in an enabled
CI/container environment, then manual Render configuration review.

## 20 November 2026 10:48 SGT — branded password reset and login polish

Worktree: `C:\Projects\ClassSync\var\feature-auth-onboarding-saas`, branch
`feature/auth-onboarding-saas`, base HEAD `2f18ad6e7346f6870e3d9b05fbb9b6a693d320ca`.
Main was inspected and remained clean at `e6c892cd1e8ed1b9361b7f2775cbe842275d9284` before
merge. Port 5173 was not touched. Temporary frontend-only Vite servers on 5207 and 5208 were
stopped after local Chrome/Playwright checks. No live Firebase, Turnstile, email provider, hosted
database, or production data was used.

Password reset now follows the unauthenticated Turnstile-protected Gateway endpoint
`POST /api/v1/auth/request-password-reset`. Gateway sends the generic accepted response before
generating a Firebase Admin password action link and dispatching the notification task; it
extracts the action code and gives Notification only a clean ClassSync reset URL.
Notification validates the configured frontend origin and reset route, then sends a branded HTML
message through the existing Resend or Brevo provider selection. Account-not-found and delivery
failures return the same generic accepted response; internal logs omit user email and reset URLs.
Dispatch currently uses FastAPI's in-process background task, so process termination can lose an
accepted reset email; a durable queue/outbox is required for a production reliability guarantee.
The login recovery and authenticated profile recovery screens both use this flow and require a
fresh challenge token. Login errors now use an alert pill, long Gateway calls announce the
connecting state, and desktop form/showcase spacing is balanced without changing mobile rules.

Files changed include `services/gateway/app/main.py`, `services/gateway/app/onboarding.py`,
`services/notification/app/main.py`, `services/notification/app/email_templates.py`, related
Gateway/Notification tests, `apps/web/src/auth/account-actions.ts`,
`apps/web/src/pages/InstitutionalEntrance.tsx`, `apps/web/src/pages/AccountProfilePage.tsx`,
their tests and `apps/web/src/styles/pages/auth.css`, plus `.env.example` and `README.md`.

Fresh local verification (all serial):

- `\.venv\Scripts\python.exe -m pytest` — **1,137 passed**, one existing Starlette/httpx
  deprecation warning, 137.06 seconds on the final backend implementation.
- `npm run test:web` — **853 passed across 65 files** after updating the profile recovery flow.
- `npm run lint` — PASS; `npm run typecheck` — PASS; `npm run build` — PASS.
  Build emitted no chunk-size or Firebase mixed-import warnings; largest JavaScript chunk was the
  app entry at 334.84 kB (gzip 85.93 kB).
- `\.venv\Scripts\ruff.exe check` — PASS. Focused Gateway/Notification pytest — **33 passed**,
  one existing Starlette/httpx deprecation warning.
- `git diff --check` and final `git diff --cached --check` — PASS.
- Real Chrome via Playwright on temporary local Vite: at 1366×640, the card is 980×600 at y=20,
  document height is 640, Google button ends at y=560, showcase feature card spans y=273–484,
  and first-time callout spans y=500–564. At 390×844, the one-column card is 358px wide, the
  showcase is hidden, and document width/height match the viewport. No page errors were captured.
  This is rendered local UI verification, not live authentication or provider delivery.

Remaining gates: actual Firebase password-reset settings, live Turnstile verification, Resend or
Brevo sender configuration and delivery, native browser zoom, screen-reader testing, and hosted
PostgreSQL qualification remain UNVERIFIED. Production readiness is not claimed. No live data or
hosted configuration changed.

The implementation was committed on the feature branch as `bbdaa487`, merged into `main` as
`f9195f70`, and `git push origin feature/auth-onboarding-saas main` reported both branch updates
successfully. The initial sandboxed `git ls-remote` verification could not connect to GitHub; push
output is the available remote confirmation. This final evidence correction is being committed on
the feature branch and will be merged/pushed as a documentation follow-up.

## 20 November 2026 09:41 SGT — authentication polish, Turnstile stability, and transactional email

Worktree: `C:\Projects\ClassSync\var\feature-auth-onboarding-saas`, branch
`feature/auth-onboarding-saas`, base HEAD `af834b95c5a3ce7a5310249b7e1ab5044a93f9d4`.
The main worktree was inspected and remained clean at `90a21802b16d7880aab995f0be41364addc21fac`.
Port 5173 was not touched. A temporary Vite preview on port 5201 was stopped after browser
inspection. No live Firebase, Turnstile, email provider, hosted database, or production data was
used.

Updated the responsive sign-in experience, keeping the existing mobile rules intact. On desktop,
the first-time login callout now lives at the bottom of the right campus panel, the password
recovery link sits beside its label, and duplicate Turnstile success text is removed. The widget
stores callbacks in refs, survives parent renders without resetting, and is reset only after a
failed login attempt; student-number sign-in sends its single-use challenge token once to Gateway.
Successful Firebase sign-in refreshes the server-authorized university session, which owns the
role-specific redirect. Added the reusable six-rule password checklist to student account
creation, post-OTP portal-password setup, and password-reset completion. Reset links are verified
and completed through Firebase Auth SDK actions. Gateway validation and HTTP error envelopes now
mask raw request/database/provider diagnostics while preserving the Registrar's generic identity
message. Notification email delivery now renders an escaped table-based ClassSync verification
email and supports configured Resend or Brevo transactional APIs; provider configuration remains
fail-closed.

Changed files include `apps/web/src/pages/InstitutionalEntrance.tsx`,
`apps/web/src/styles/pages/auth.css`, `apps/web/src/auth/TurnstileWidget.tsx`,
`apps/web/src/auth/PasswordStrengthChecklist.tsx`, `apps/web/src/auth/password-strength.ts`,
`apps/web/src/auth/account-actions.ts`, `services/gateway/app/main.py`,
`services/notification/app/main.py`, `services/notification/app/email_templates.py`, tests,
`.env.example`, and `README.md`.

Fresh local verification:

- `\.venv\Scripts\python.exe -m pytest` — **1,133 passed**, one existing
  Starlette/httpx deprecation warning, 110.49 seconds. This is the repository-configured service
  suite; it does not run hosted-provider or disposable PostgreSQL qualification.
- Focused auth/notification pytest — **31 passed**, one existing Starlette/httpx deprecation
  warning.
- Focused auth component Vitest — **29 passed** across five files.
- `npm run test:web` — **853 passed across 65 files**.
- `npm run lint` — PASS; `npm run typecheck` — PASS; `npm run build` — PASS. Production build
  emitted no Firebase mixed-import or oversized-chunk warnings; largest JavaScript chunk was
  `react-vendor` at 318.51 kB (gzip 101.36 kB).
- `.venv\Scripts\python.exe -m ruff check services packages` — PASS.
- Real Chrome through Playwright against isolated local Vite on port 5201: at 1366×640, the
  desktop card measures 980×600 at y=20, the document remains 1366×640 without scrolling, both
  panels report no content overflow, the Google button ends at y=576, and the desktop helper ends
  at y=603. At 1440×900 all card contents remain in bounds. At 390×844 the existing one-column
  layout remains 358px wide with no horizontal/vertical page overflow and the showcase is hidden.
  This qualifies rendering only; it is not real provider sign-in or native browser zoom testing.
- `git diff --check` — PASS before this status update; final diff check remains required.

Remaining gates: live Firebase/Turnstile/Registrar verification, actual Resend/Brevo delivery and
sender approval, Firebase password-reset action URL settings, native Chrome zoom, screen-reader
testing, and external PostgreSQL qualification remain UNVERIFIED. P4d/production readiness is not
claimed complete. No live data or hosted configuration changed.

## 20 November 2026 05:06 SGT — responsive sign-in and container import path

Worktree: `C:\Projects\ClassSync\var\feature-auth-onboarding-saas`, branch
`feature/auth-onboarding-saas`, base HEAD `750aa8ac04a505c12de6a5b3f734c3291199ff45`.
The existing development server on port 5173 was not touched. Temporary Vite preview servers
started for browser checks were stopped. The main worktree was not modified. No credentials,
provider calls, hosted services, or database writes were used.

Updated the responsive login entrance and its actual imported page stylesheet, Turnstile's
unconfigured visual state, Docker's container `PYTHONPATH`, README guidance, and login tests.
Below 768px the form is a single-column card with the campus showcase hidden; 768–959px remains
single-column; desktop uses a two-panel card. The unavailable Turnstile state no longer reserves a
large blank region. The production/container code change is `ENV PYTHONPATH=/app`.

Fresh local verification:

- `npm run lint` — PASS.
- `npm run typecheck` — PASS.
- `npm run test --workspace=@classync/web -- --run src/pages/InstitutionalEntrance.test.tsx` —
  PASS, 10 tests.
- `npm run test:web` — PASS, 846 tests across 63 files.
- `npm run build` — PASS; no Vite chunk-size or mixed Firebase import warnings. Largest reported
  JavaScript chunks: app 329.71 kB, React 318.51 kB, Firebase 243.27 kB, Motion 125.02 kB.
- Real Chrome via Playwright against isolated local Vite preview (ports 5197 and 5198): login and
  account creation UI checked at 360×800, 390×844, 767×900, 768×1024, 959×900, 960×800,
  1024×768, 1366×768, and 1440×900. No horizontal overflow. At 360–767px the access surface
  filled the available card width and the showcase was hidden; 768–959px remained centered and
  single-column. At 1366×768 and 1440×900, the 700px-tall desktop card and all form/showcase
  content fit without page scrolling. Account creation used a local UI fixture with a synthetic
  authentication response; no account was created. This is responsive UI evidence only, not a
  live provider/authentication test.

Not run: Docker image build, Python tests (no Python application source was changed), live
Firebase/Turnstile/Registrar checks, native browser zoom control, or screen-reader testing. P4d
and production readiness remain partial; provider-backed authentication and deployment gates remain
open. No production data was touched.

Git integration: feature commit `a325b843786421267c998cbf315a802375dbe043`; merge commit
`4010055` on `main`. `git push origin feature/auth-onboarding-saas main` succeeded and updated
both refs (`750aa8a..a325b84` and `aa780fe..4010055`).

## 20 November 2026 03:05 SGT — institutional login lock, visual refresh, and operator provisioning CLI

Worktree: `C:\Projects\ClassSync\var\feature-auth-onboarding-saas`, branch
`feature/auth-onboarding-saas`, base HEAD `795546fca1a894e59e2ce70944eb3ae9dea2ba24`.
The separate `main` worktree was inspected and clean at `9d2a16c`; port 5173, ignored
virtual environments, and databases were not touched. Institutional/distributable builds now
ignore legacy preview flags, and `/auth/login` always renders the real account form; preview
sampling remains available only through the explicit preview route/build. The sign-in page uses a
light architectural split layout with reduced-motion-aware Motion entrance transitions. Added an
operator-only `scripts/provision_live_accounts.py` that requires repeated live-write confirmation,
TLS PostgreSQL, a matching existing tenant/Firebase project, attributable Administrator grants,
and existing active Registrar/faculty records. It does not invent roster, faculty, or tenant data.
Added regression tests for these guards, corrected stale production-artifact expectations, and
resolved Ruff findings in the OTP paths and migrations without changing behavior.

Fresh local evidence:

- `.venv\Scripts\python.exe -m pytest` — **1,128 passed**, one existing Starlette/httpx
  deprecation warning, 101.34 seconds. Pytest's configured `testpaths` is `services`; this count
  covers service tests.
- `.venv\Scripts\python.exe -m pytest scripts/tests/test_provision_live_accounts.py -q` —
  **13 passed**. These are unit tests only; the operator CLI was not invoked against live services.
- `npm run test:web` — **846 passed across 63 files**, 180.86 seconds.
- `npm run test:artifacts` — **5 passed**. It built and inspected ordinary institutional,
  explicit presentation, connected institutional, and legacy-flag institutional artifacts; old
  preview flags did not enable preview behavior in the standard distributable build.
- `npm run lint` — PASS, zero warnings; `npm run typecheck` — PASS.
- `npm run build` — PASS with no Vite chunk-size or mixed Firebase import warnings. Largest
  JavaScript chunks: app `330.19 kB`, React `318.51 kB`, Firebase `243.27 kB`, Motion `125.02 kB`.
- `.venv\Scripts\python.exe -m ruff check services packages scripts` — PASS, all checks passed.

`docs/autonomy/APPROVALS.md` and the explicit owner request authorize local implementation,
commit, merge and push. No account provisioning, real database migration, Firebase mutation, hosted
configuration, or deployment was performed. The CLI has no distributed transaction across Firebase
and PostgreSQL: on a later database failure, newly created Firebase accounts are deleted best-effort;
an existing Firebase password change cannot be rolled back automatically. Live target, backups,
operator authority, Firebase tenant, roster/faculty evidence, PostgreSQL migration/RLS execution,
provider-backed browser flow, native 200% zoom and keyboard-only use remain external or manual gates.
Production readiness and P4d remain **PARTIAL**. Preserve all hosted-data, provider, and release gates.

Files changed in this milestone: `README.md`; frontend app-mode/runtime, preview-session, login
page, styles, Vite chunk config and tests under `apps/web`; OTP import/format cleanup and tests under
`services/gateway`; formatting-only updates to migrations `0019`/`0020`; production artifact test;
new operator CLI and tests. Final staged review passed (`git diff --cached --check`); commit
`9cfb86771f4db3030632c2855bc1298bc1cf2c07` was created on the feature branch, merged into `main` as
`711083d85f074b0b1a8717b2c5640c0ab7fee57c`, and both refs were pushed successfully by `git push
origin feature/auth-onboarding-saas main`. The post-push `git ls-remote` read-after-write check was
blocked by unavailable GitHub connectivity; both local worktrees are clean.

## 19 November 2026 01:06 SGT — student portal password setup and local qualification

Worktree: `C:\Projects\ClassSync\var\feature-auth-onboarding-saas`, branch
`feature/auth-onboarding-saas`, base HEAD `981d654058ab5b05f2dc0285d4a797efce63c7cd`.
The main worktree remains clean at `fa248229eef753297fbc9a49a884a475e6920ea5`; port 5173 was
not touched. Implemented the post-OTP password step: the browser links/updates the Firebase
password provider, then the Gateway verifies the provider and the OTP challenge before marking
`password_configured` and granting student membership. Student-number/password login now resolves
the roster email only inside the Gateway, verifies Turnstile, authenticates through Firebase
Identity Toolkit, checks active membership and returns only a Firebase custom token. Missing roster
and invalid credential responses share a generic message. Added migration `0020_student_portal_password`
and regression coverage. `FIREBASE_WEB_API_KEY` is documented in the ignored-environment examples.
README, security guidance and the traceability row now reflect the implemented flow and its limits.

Fresh serial checks:

- `.venv\Scripts\python.exe -m pytest` — **1,128 passed**, one existing Starlette/httpx
  deprecation warning, 121.57 seconds. Pytest's configured test paths are `services`; the separately
  targeted PostgreSQL migration qualification regression file was also run. After the
  missing-roster Firebase credential request was added to reduce a timing signal, the final full
  serial rerun was **1,128 passed**, one deprecation warning, 101.94 seconds.
- `.venv\Scripts\python.exe -m pytest services/gateway/tests/test_onboarding.py
  services/gateway/tests/test_turnstile.py scripts/tests/test_postgres_qualification_regressions.py -q`
  — **33 passed**, one Starlette/httpx deprecation warning.
- `npm run test:web` — **847 passed across 63 files**. The first full run exposed a React warning in
  the test-only Turnstile mock; the mock was moved to an effect and the complete suite was rerun.
  The rerun passed with no React warning; after the final Gateway timing-path change, the full Web
  suite was rerun again and passed **847 tests across 63 files**.
- `npm run lint`, `npm run typecheck`, and `npm run build` — PASS. Build emitted no Firebase
  mixed-import or oversized-chunk warning; largest JavaScript chunk: `index` 328.65 kB.
- `.venv\Scripts\python.exe -m ruff check services packages scripts` — NOT RUN successfully:
  Ruff is not installed in the isolated worktree environment (`No module named ruff`). No network
  installation was attempted.
- `git diff --check` — PASS. PostgreSQL migration/RLS execution, Auth Emulator, Resend delivery,
  provider-backed login and connected browser acceptance were not run.

The authorized local-only bootstrap still creates synthetic academic setup records in its guarded
SQLite sandbox. This change does not import a student roster or set canonical CdM room capacities,
and does not create a published revision. A synthetic roster and solver output must not be presented
as an official student identity roster, Facilities verification or authoritative published
timetable. Production seed/publication remains blocked on verified institutional data and a
successful independent validation path. P4d remains **PARTIAL**; local unit/build gates do not
qualify external identity, PostgreSQL or browser behavior. The work was committed on feature as
`a2ae4217a337d1d1a8316d15d3dabde289c1d22f` (`feat(auth): complete student portal password
onboarding`) and merged into main as `9b2fd1045ce6583b95c8414ea46d9cce51b03b58`. The merge tree
matches the feature worktree; both worktrees were clean after integration. `git push origin
feature/auth-onboarding-saas main` reported updates from `49e1b69` to `a2ae421` and from `fa24822`
to `9b2fd10`. A subsequent `git ls-remote` could not connect to GitHub, so remote read-after-write
verification is unavailable in this session. Preserve the separate external qualification and
production-readiness gates.

## 19 November 2026 00:01 SGT — local checkpoint and stale-ref cleanup

Committed the feature-worktree implementation/evidence from the preceding checkpoint as
`9b5cde2cefebdd18a3df8a38e8c9699f9db6d89c` (`feat(auth): add Turnstile and student email
verification`). The focused auth, bootstrap, validation and build evidence is in the entry below.
The branch remains local-only; feature/main were not merged or pushed because the complete Python
and Web suites are not green, and student-number/password login plus post-OTP password creation
remain unimplemented. Port 5173, the `main` worktree, ignored environments and databases remain
untouched.

Performed the explicitly authorized stale-ref cleanup after confirming only `main` and
`feature/auth-onboarding-saas` were checked out: deleted remote
`origin/codex/classsync-main-checkpoint-20261114` (GitHub returned `[deleted]`), local
`codex/classsync-main-checkpoint-20261114`, and local `release/mvp-staging-qualification`; expired
local reflogs and ran `git gc --prune=now`. The named local/remote-tracking refs are absent. GC
reported zero loose/pruneable objects but warned of an empty worktree `refs` directory as garbage;
no data was manually removed. A subsequent `git ls-remote` could not reach GitHub, so there is no
second remote read-after-delete receipt. `git worktree prune --dry-run --verbose` reported no
prunable worktrees. Branch-local unique old commits were intentionally made unreachable under the
owner's cleanup instruction; GitHub's server-side unreachable-object retention is outside this
local verification.

The final README now describes the private Notification verification endpoint and clearly says
provider delivery is unqualified. Do not represent this local checkpoint as merged, pushed,
production-ready or fully qualified. Next gate: diagnose the unchanged-limit solver `UNKNOWN`
result and resolve/retest the complete local suites; then complete missing password setup and
student-number sign-in before reconsidering merge/push.

## 18 November 2026 23:52 SGT — authentication and bootstrap continuation checkpoint

Worktree: `C:\Projects\ClassSync\var\feature-auth-onboarding-saas`, branch
`feature/auth-onboarding-saas`; base/current committed HEAD before this change is
`49e1b69f414bffcd455848eb34a24b7fc15580a4`. The worktree has the authorized local changes listed
in Git status; the separate `main` worktree at `fa248229eef753297fbc9a49a884a475e6920ea5` is
clean. Port 5173 and ignored databases/evidence were left untouched.

This change adds a Cloudflare Turnstile widget and Gateway Siteverify boundary, a CdM campus login
layout, tenant/UID-scoped OTP storage and delivery, a PostgreSQL migration at
`0019_student_email_challenges`, updated onboarding/API qualification checks, a synthetic local-only
`scripts/seed_bootstrap_cdm.py`, and README/security/traceability notes. The seed refuses non-sandbox
SQLite filenames and does not create student identity records, set room capacities, assert official
availability or publish a timetable. OTP email delivery requires an explicitly configured Resend
sender and private service token; no code is emitted to logs. Exact Google-roster mismatch text is
preserved.

Fresh checks in this turn:

- Focused Python: `.venv\\Scripts\\python.exe -m pytest scripts/tests/test_bootstrap_cdm.py
  services/gateway/tests/test_onboarding.py services/gateway/tests/test_turnstile.py
  services/notification/tests/test_email_verification.py
  services/persistence/tests/test_identity_qualification_inventory.py -q` — **35 passed**, one
  Starlette/httpx deprecation warning.
- Focused Web: `npm run test -- --run src/pages/InstitutionalEntrance.test.tsx
  src/auth/AccountOnboardingPanel.test.tsx` — **13 passed across 2 files**.
- Web `npm run lint` and `npm run typecheck` — both exit 0.
- Web `npm run build` — PASS; chunks: React 318.51 kB, Firebase 243.27 kB, UI 47.83 kB, app
  325.20 kB; no mixed-import or chunk-size warning.
- `.venv\\Scripts\\python.exe -m pip check` — PASS, no broken requirements.
- `.venv\\Scripts\\python.exe -m ruff check services packages scripts` — unavailable: `ruff` is not
  installed in this environment.
- `git diff --check` — PASS.

The last full Python suite at the pre-correction snapshot reported 1,119 passed and 2 failed. The
stale identity-inventory expectation was corrected and the affected focused regression now passes;
the scheduling draft regression returned solver `UNKNOWN` at its unchanged 8-second limit. The last
full Web suite reported 843 passed and one timeout; its test file passed when run alone. The full
suites have not been rerun to a clean result and are not green evidence. Do not alter solver limits
or weaken constraints to mask this. No actual PostgreSQL migration/RLS run, Auth Emulator, Resend,
Cloudflare Siteverify, connected login/browser journey, password setup, student-number/password
login, native 200% zoom, or keyboard-only end-to-end check was performed. Direct browser calls to
Firebase Auth can bypass the current Gateway Turnstile check, so it is not a hard auth boundary.

The feature branch is four commits behind `main` and currently shares its history ancestor; the
feature diff contains no unique committed feature work relative to `main` yet. The working tree
contains the planned implementation and focused tests. Because a full-suite solver failure remains
and production auth gates are unverified, do not call this release-ready. Next: finish review of the
changed files and retain this as a feature checkpoint; only merge/push after the regression gate is
resolved or an explicit quality-gate disposition is recorded. The stale branch deletion and local
GC are separately authorized but should be done only after verifying the final target refs and
worktree safety.

## 18 November 2026 22:26 SGT — final target-branch rewrite and remote verification

The final pre-ledger-push rewritten refs were `feature/auth-onboarding-saas`
`4625db465899dd1c2b899c6897bf47f37c5f63e9` and `main`
`e58ecfd4c0a1beb75be14dcc255d707851c63c2c`. Both were force-pushed using explicit leases and
fetched from `origin`; the fetched OIDs matched those local refs. The two filter-branch backup refs
created by this rewrite were removed after that verification. Branch-scoped source/history checks
for the removed personal identifiers found no matches, and the last five feature commits use the
repository-local GitHub noreply identity. The docs-only ledger update in this commit follows those
verified pushed refs; it contains no former personal identifier values.

This does **not** scrub every repository ref. Automatic review rejected rewriting the remote
`codex/classsync-main-checkpoint-20261114` branch and local `release/mvp-staging-qualification`
branch because the explicit Git rewrite scope named feature/main. The checkpoint branch remains
on origin and the release branch remains local. They retain older history and need separate owner
authorization before any rewrite. No other refs or user files were changed.

## 18 November 2026 22:10 SGT — Production hardening and PII cleanup checkpoint

Base feature HEAD: `345bcbc65bb18f20c83947efddfd4a8582019cb4`. The source cleanup was committed
as `9dfc16a` and merged locally to `main` as `7e757ca` before rewriting history. Current rewritten
heads are `feature/auth-onboarding-saas` at `7d56ebd54743ba00f931030a43ceba40904358f8` and `main`
at `1d545013f58ebbe6c5d2d3f69b17634523cbbd03`. Local changes are on
`feature/auth-onboarding-saas`; the separate `main` worktree and its untracked
`.codex-attachments/` remain preserved. Replaced the exposed personal student-email example in
README, onboarding/auth source and tests, Gateway tests, and audit documentation with the neutral
institutional example `juan.delacruz@student.pnm.edu.ph`. Changed the Vercel build command from
the presentation target to `npm run build`; kept the SPA rewrite so a direct role-preview URL is
handled by the guarded client route, while institutional mode redirects to sign-in. Updated
README to state that provider-backed production sign-in remains unqualified. Set repository-local
Git identity to `Kakashimoto14 <Kakashimoto14@users.noreply.github.com>`; global Git config is
unchanged.

Fresh checks:

- Focused onboarding UI tests — **12 passed across 2 files**.
- Scanner account-switch regression — **9 passed** after correcting its race-prone setup
  expectation; it now waits for the replacement account's onboarding read and retains the
  private-field-clearing assertions.
- Full `npm run test:web` — **843 passed across 63 files**.
- `npm run lint --workspace=@classync/web` — PASS.
- `npm run typecheck --workspace=@classync/web` — PASS.
- `npm run build` — PASS; institutional build emitted no Firebase import or oversized-chunk
  warnings (largest chunk 322.13 kB).
- `npm run test:artifacts` — **5 passed** across institutional, connected, presentation and
  legacy-flag deployment artifact checks.
- Feature `.venv` full `pytest -q` — **1,115 passed**, one Starlette/httpx deprecation warning.
- `git diff --check` — PASS. Current working-tree scan for the removed personal identifiers returns
  no matches. Ruff is unavailable in the isolated `.venv` and no wheel is cached; `ruff check` is
  therefore unverified. A first artifact run caught the removed Vercel SPA rewrite for direct
  role-preview URLs; restoring the rewrite made all five artifact tests pass. The guarded route
  itself remains unavailable in institutional mode.

The authorized `feature/auth-onboarding-saas` and `main` refs have been rewritten: tracked source
blobs and commit messages replace the personal examples, and commits use the repository-local
GitHub noreply identity. Branch-scoped Git history and source searches for the removed identifiers
return no matches. The two refs were force-pushed with explicit leases, then fetched; local branch
and `origin/*` object IDs match (`feature/auth-onboarding-saas` `0accd84`, `main` `0d1f955`). The
automatic review rejected rewriting the local and remote checkpoint branch and local release
branch because they were outside the specifically named feature/main refs. Those branches still
retain the old history and were not changed. Filter-branch backup refs for feature/main were
removed after verification. GitHub HTTPS later became unavailable again; the successful push and
fetch outputs are the evidence for the two target refs. Do not call every repository ref scrubbed
until the checkpoint and release refs are separately authorized and rewritten. Cloudflare
Turnstile credentials/server-side configuration,
six-digit OTP delivery, the account-password-by-student-number mapping, and an authorized
Registrar roster/faculty/capacity/schedule dataset are absent. No seed script was created because
the requested sample capacities, student/faculty identities and published timetable would invent
institutional facts. No production deployment, live data, database migration, cloud setting or
port-5173 process was changed.

Next safe action: commit and merge this corrected status entry, then verify the final two target
refs. Ask separately before rewriting the checkpoint and release branches. Production
OTP/Turnstile and seeding remain blocked pending institution data and secrets/configuration.

## 15 November 2026 14:29 SGT — Administrator task-flow and screen audit

Base/current HEAD remains `7165fa130e413f8dc8893b85d30ecbe530ef8173` on
`feature/auth-onboarding-saas`; preserved the prior dirty worktree. Reviewed the two supplied
screenshots as evidence of `/admin/academic` and `/admin/offerings` before period selection,
then cross-referenced the Administrator route registry and page dispatch. Added
`docs/hci/admin-workspace-audit.md` with a screen-family inventory, source evidence, screenshot
findings, statuses and open verification gates.

Implemented a bounded Admin UX slice: the no-period Academic Setup entry describes all setup
areas before period selection, opens period creation directly when no period exists, keeps the
sandbox/data qualification visible, and moves synthetic scenario import below the primary setup
flow. Period-scoped academic categories now use one sidebar entry while remaining available from
the workspace and destination search. Renamed the deterministic CP-SAT screen to Schedule
Generation; conflict validation now explicitly identifies itself as deterministic, and its empty
state and the generation no-period state link to their next actions. Added a no-period readiness
outline to the Administrator dashboard. Updated `README.md`, `docs/audit/MASTER_ROADMAP.md`,
`docs/autonomy/ROADMAP.md`, and `TRACEABILITY.md`.

Fresh checks:

- `npm run test --workspace=@classync/web -- src/pages/AcademicManagementPage.test.tsx
src/pages/ConflictCenterPage.test.tsx src/components/layout/AppShell.test.tsx` — **31 passed
  across 3 files**.
- `npm run typecheck --workspace=@classync/web` — PASS.
- `npm run lint --workspace=@classync/web` — PASS.
- `npm run build --workspace=@classync/web` — PASS; Vite retained the existing Firebase mixed
  static/dynamic import warning and emitted a 713.55 kB minified chunk warning (>500 kB).
- Targeted Prettier check — PASS; `git diff --check` — PASS.

The first test run exposed one stale test expectation about period auto-selection; corrected it to
assert the intentional explicit-choice state. The second run passed. No browser automation was
available: rendered before/after screenshots, 360/390/768/1024/1440 widths, keyboard walkthrough,
200% zoom and screen-reader checks remain UNVERIFIED. Institutional providers/data, Admin
preview-only routes and production operation remain unqualified. No backend, database, external
provider, cloud, production data, main worktree or Git publication changed. Phase 1.3 and the Admin
UX recovery remain PARTIAL.

## 15 November 2026 04:53 SGT — catalog-backed program selection

Continued Phase 1.3 on the same feature worktree and unchanged HEAD
(`7165fa130e413f8dc8893b85d30ecbe530ef8173`); all existing dirty files remain preserved.
New program records now select from the shared supplied catalog
`packages/api-contracts/classync_contracts/catalogs/programs.json` through the frontend
adapter `apps/web/src/data/academic-program-catalog.ts`. Program acronyms, names, institutes
and section policy are populated from the selected entry rather than typed. Entries already
present in the selected academic period are excluded from new-record choices. Existing
non-catalog records retain their current editable fields to avoid stranding legacy data.
The UI clearly says the local list is supplied data that still needs Registrar confirmation;
catalog selection alone does not claim that a program is active this term.
New-program creation is disabled when every supplied catalog entry is already saved.
Subtle inline-form and selection transitions are implemented in CSS and are enabled only
when `prefers-reduced-motion: no-preference`.

The combined Admin input checks were rerun after this change:

- `npm run test:web -- src/pages/AcademicManagementPage.test.tsx
src/pages/LockedAssignmentsEditor.test.tsx` — **17 passed across 2 files**. Covers the
  one-workspace period overview, duplicate-free catalog program menu and completed-catalog
  guard, section selectors,
  day-checkbox window mapping, blank window defaults, 30-minute time menu and fixed
  assignment duration filtering.
- `npm run typecheck --workspace=@classync/web` — PASS.
- `npm run lint --workspace=@classync/web` — PASS.
- `npm run build --workspace=@classync/web` — PASS; known Firebase mixed-import warning
  remains and the largest minified chunk is 710.86 kB (above 500 kB).
- Targeted Prettier checks on the test files and README — PASS; `git diff --check` — PASS.

No backend/API contract, academic database, schedule solver, production data, cloud setting,
or Git publication changed. Browser screenshots, responsive widths, native 200% zoom and
manual assistive-technology checks remain UNVERIFIED due unavailable browser automation.
Phase 1.3 remains PARTIAL; continue with structured selectors in the broader scheduling
generation/review surfaces and obtain rendered browser acceptance when tooling is available.
README, the Phase 1.3 roadmap progress, and requirements traceability were synchronized.

## 15 November 2026 04:47 SGT — structured scheduling time and day entry

Base/current HEAD: `7165fa130e413f8dc8893b85d30ecbe530ef8173` on
`feature/auth-onboarding-saas`. Preserved the existing dirty work. Continued Phase 1.3 by
changing the shared Admin `WeeklyWindows` control in `AcademicRecordEditor.tsx`: each
window begins with no days or times selected; operators select one or more weekdays using
checkboxes and choose start/end from 30-minute menus. Only complete, explicitly selected
windows enter the academic record. This shared control serves faculty availability,
resource availability/blocked windows and operating hours. The copy states these controls
do not establish approved campus hours.

Updated `LockedAssignmentsEditor.tsx` to use a start-time menu and restrict end-time choices
to durations present in the selected offering's saved subject pattern. Day, offering,
eligible faculty and eligible room remain menu-selected. No scheduling contract, solver
constraint or persisted schema changed. Added focused acceptance tests for blank window
defaults, multi-day mapping, 30-minute choices and offering-pattern end-time constraints.
Updated GitHub `README.md`, `MASTER_ROADMAP.md` and `TRACEABILITY.md`.

Fresh local verification:

- `npm run test:web -- src/pages/AcademicManagementPage.test.tsx` — **14 passed**.
- `npm run test:web -- src/pages/LockedAssignmentsEditor.test.tsx` — **1 passed**.
- `npm run typecheck --workspace=@classync/web` — PASS.
- `npm run lint --workspace=@classync/web` — PASS.
- `npm run build --workspace=@classync/web` — PASS; the existing mixed Firebase import
  warning remains and the largest minified chunk is 708.44 kB (over Vite's 500 kB advisory).
- `npx prettier --check apps/web/src/pages/AcademicManagementPage.test.tsx
apps/web/src/pages/LockedAssignmentsEditor.test.tsx README.md` — PASS.
- `git diff --check` — PASS.

The initial acceptance run failed before implementation because the expected day checkboxes
did not yet exist; final focused suites passed after implementation. Browser visual/responsive
and manual accessibility checks remain UNVERIFIED because available browser automation did
not initialize in the prior slice. These are form-component tests using isolated synthetic
academic data, not an institutional service or Registrar acceptance. No API/backend,
database, migration, saved record, provider configuration, cloud setting, production data,
or Git publication was touched. Phase 1.3 remains PARTIAL. Next dependency-ready work:
continue selection-first coverage across the Administrator schedule generation/review
surfaces, then complete rendered keyboard/responsive QA when browser tooling is available.

## 15 November 2026 04:30 SGT — Administrator academic-period setup workspace

Base/current HEAD: `7165fa130e413f8dc8893b85d30ecbe530ef8173` on
`feature/auth-onboarding-saas`; local changes remain uncommitted and all pre-existing
dirty work is preserved. Implemented the bounded Phase 1.3 slice: the `/admin/academic`
period overview now keeps the calendar and seven academic input categories in one
workspace, supports inline record create/edit, quick-jump links, first-record summaries,
saved-record counts, and links to complete category lists. Counts explicitly do not assert
source accuracy or scheduling readiness. Existing category routes and the separate
**Validate Readiness** action remain available. Section year and letter use fixed menus.
Added responsive Soft Rouge layout rules and documented the workflow in `README.md`.

Fresh local checks:

- `npm run test:web -- src/pages/AcademicManagementPage.test.tsx` — **14 passed, 1 file**;
  covers one-screen setup, inline subject form, catalog-derived room/activity selection,
  fixed section menus, period creation and readiness behavior.
- `npm run typecheck --workspace=@classync/web` — PASS.
- `npm run lint --workspace=@classync/web` — PASS.
- `npm run build --workspace=@classync/web` — PASS. Existing warning persists: Firebase is
  both statically and dynamically imported, and the largest minified chunk is 706.71 kB
  (above the 500 kB advisory threshold).
- `npx prettier --check apps/web/src/pages/AcademicPeriodSetup.tsx
apps/web/src/pages/AcademicManagementPage.test.tsx README.md` — PASS. New CSS keeps
  the file's existing compact style rather than reformatting its unrelated baseline rules.
- `git diff --check` — PASS.

The first typecheck/build attempt caught two local TypeScript issues in this slice; they
were corrected and all final checks above were rerun successfully. Browser visual checks
were not completed: no Playwright package/browser plugin was available, and the CUA
browser initialization failed because its kernel assets path was missing. Thus rendered
responsive behavior, keyboard/focus movement and 200% zoom remain UNVERIFIED. No API,
database, provider, migration, institutional record, original DB, `main` worktree or cloud
setting was changed. This does not complete Phase 1.3 or certify the Admin product flow;
full browser QA and structured schedule-level inputs remain open. See the matching
`TRACEABILITY.md` row. Next: continue the same phase with selection-first scheduling forms
and a real browser acceptance pass when browser tooling is available.

## 15 November 2026 03:33 SGT — Scheduling import startup failure

Reproduced the import-resolution cause from the user's startup log. The worktree `.venv`
has an editable `classync-api-contracts` finder targeting
`C:\Projects\ClassSync\packages\api-contracts` (the separate primary checkout), where
`classync_contracts/cloud_run.py` does not exist. The feature worktree's file does exist.
The local launcher previously inherited that stale editable mapping, so Academic could
start while Scheduling failed on `from classync_contracts.cloud_run import service_headers`.

Updated `scripts/dev.py` to put this worktree's `packages/api-contracts`,
`packages/persistence`, and root ahead of inherited `PYTHONPATH` for all child services.
Updated `README.md` with the launcher/manual-Uvicorn explanation. Verification with an
explicit path containing both the feature package and the stale primary-checkout path
successfully imported `classync_contracts.cloud_run` from
`C:\Projects\ClassSync\var\feature-auth-onboarding-saas\packages\api-contracts\classync_contracts\cloud_run.py`
and `services.scheduling.app.main` from this feature worktree. Targeted Ruff, README
Prettier, and `git diff --check` passed. No service was launched against default local
databases; the startup import failure is resolved at the same module import boundary,
but a complete local three-service/browser launch has not been requalified here. No
package reinstall, database mutation, production configuration or cloud change occurred.

If manually launching Uvicorn, set `PYTHONPATH` to the active worktree's
`packages/api-contracts`, `packages/persistence`, and repository root first. The
supported one-command `npm run dev` launcher now does that automatically.

## 15 November 2026 03:05 SGT — CdM room catalog implementation

Base/current HEAD: `7165fa130e413f8dc8893b85d30ecbe530ef8173` on
`feature/auth-onboarding-saas`; implementation is uncommitted and `main` is untouched.
Preserved all prior dirty work, including the seven-document audit set. Updated the
GitHub README to report the implemented catalog and local evidence without claiming
Facilities verification.

Implemented the November 2026 row-mapped catalog in
`packages/api-contracts/classync_contracts/catalogs/cdm-spaces.json`, versioned it in
`apps/web/src/data/cdm-room-inventory.ts`, and extended
`packages/api-contracts/classync_contracts/{scheduling,academic}.py` plus generated
`packages/api-contracts/schemas/scheduling-v1.json` and
`packages/shared-types/src/scheduling.ts` with allowlisted room activity types. Updated
`services/academic/app/record_rules.py`, `services/scheduling/app/academic_input.py`, and
`services/scheduling/app/readiness.py`: canonical identity includes restrictions and
schedulability, offerings pass activity type through, and restricted rooms fail solver
readiness until both operational condition and room-type verification are recorded.
`apps/web/src/pages/AcademicRecordEditor.tsx` now provides structured room-type/activity
selectors and filters offering room choices by source schedulability, activity and
program; it labels unverified candidates and explains that selection is not availability.
Inventory consumers and fixtures/tests were updated, including
`apps/web/src/pages/AcademicManagementPage.test.tsx` selection coverage.

Acceptance evidence (all fresh in this worktree):

- `npm run test:web -- src/data/cdm-room-inventory.test.ts src/pages/StudentRooms.test.tsx src/pages/RoomNavigation.test.tsx src/pages/dashboards/OperationsDashboards.test.tsx` — **54 passed, 4 files**.
- `npm run test:web -- src/pages/AcademicManagementPage.test.tsx` — **12 passed, 1 file**, including activity/program/schedulability filtering and excluded-room rejection.
- With `PYTHONPATH` explicitly rooted at this worktree's `packages/api-contracts`, `packages/persistence`, and root: `python -m pytest services/scheduling/tests/test_engine.py::test_cdm_inventory_and_program_policy services/scheduling/tests/test_engine.py::test_restricted_inventory_rooms_require_matching_activity_and_verified_type services/academic/tests/test_academic.py::test_catalog_and_empty_readiness_and_restart services/scheduling/tests/test_api.py -q` — **14 passed**. One existing Starlette/httpx TestClient deprecation warning.
- `npm run typecheck --workspace=@classync/web` — PASS; `npm run lint --workspace=@classync/web` — PASS; targeted `ruff check` on changed Python modules/tests — PASS; `npm run build --workspace=@classync/web` — PASS with the existing Firebase dynamic/static import warning and a minified 701.26 kB chunk warning; Prettier checks on README, the audit directory, changed short docs and the inventory/editor test files — PASS; `git diff --check` — PASS.

During verification an initial test exposed strict Pydantic enum parsing at internal Python
construction boundaries. Valid allowlisted activity strings now normalize to enum values;
unknown values remain rejected by the enum validator. A selector test was added, stale
room-number expectations corrected, and checks rerun successfully. This was focused
catalog/readiness/API verification only: no full suite, browser rendering, live service,
hosted provider, Facilities source reconciliation, migration, or dependency scan ran.
The DOCX still has the 37/16 summary vs. 41/12 row discrepancy, visual rendering remains
unavailable, and capacities/equipment/current availability remain unknown. The known
8-second CP-SAT `UNKNOWN` failure is still an open gate and was not rerun unchanged.
No database or real institutional data was accessed or modified; no Git publication,
cloud setting, spending, migration, merge, or deployment occurred.

Next: review `docs/audit/ROOM_INVENTORY_UPDATE.md` against the DOCX row text and preserve
the Facilities verification gate; then continue dependency-ready work without altering
the solver's constraints/time limit. Student roster verification forms and ID/email
validation remain unimplemented and are not implied by the README examples. The signup
email and Student claim ID fields now show the requested examples as placeholders only;
8 account/onboarding tests assert them. No regex enforcement or roster match was added.
The post-change production build completed with the Firebase import/chunking warning and
701.26 kB chunk warning still present. A broad Prettier check also reported seven
long-form docs with noncanonical formatting; the changed README/audit/core short docs
and targeted inventory/editor test files passed bounded formatting checks. Large
historical documents were not reformatted solely to silence that broad check.

## 15 November 2026 — authority reconciliation and GitHub README

Base/current source SHA: `7165fa130e413f8dc8893b85d30ecbe530ef8173` on
`feature/auth-onboarding-saas`; no source revision occurred. Completed roadmap task 0.1
and the owner's README maintenance request. Updated `README.md`, `docs/architecture.md`,
`docs/production/firestore-authority.md`, `docs/autonomy/APPROVALS.md`,
`docs/autonomy/ROADMAP.md`, and `docs/autonomy/TRACEABILITY.md`. The current authority is
PostgreSQL for identity membership, academic data, schedules and publication; Firebase
Auth proves identity; Firestore is optional unless a verified rubric or later owner
decision requires it. The old Firestore proposal and qualification receipts are retained
as explicitly superseded/historical evidence.

Acceptance: the README reports the stack and readiness without claiming production
qualification, links the audit and updated inventory, and states the student form examples;
architecture/authority/traceability/approval records agree; no app behavior, DB or provider
settings changed. Verification: Prettier write/check on `README.md` and
`docs/architecture.md` PASS; README local-link script PASS (15 links); current-authority
source review PASS; `git diff --check` on changed tracked docs PASS (line-ending notices
only). No application tests were applicable to this documentation milestone. Dirty audit
documents from the preceding approved plan were preserved. No external changes, real data,
original database writes, Git publication or deployment occurred.

Next: diagnose the existing CP-SAT `UNKNOWN` regression from retained inputs/model/test
evidence. Do not rerun the failing test unchanged or alter its 8-second limit/constraints.

## 15 November 2026 — room inventory and student input-plan revision

Target remains `feature/auth-onboarding-saas` at `7165fa130e413f8dc8893b85d30ecbe530ef8173`; `main` and application source were not changed. Revised the audit set under `docs/audit/` and consolidated `MASTER_IMPLEMENTATION_PLAN.md` / `MASTER_ROADMAP.md` for the uploaded November 2026 room inventory and owner-confirmed student ID/email formats. Added `ROOM_INVENTORY_UPDATE.md` with row-to-ID mapping.

DOCX table text was extracted from the supplied attachment; LibreOffice was unavailable, so visual rendering was not completed. Followed the individual room rows per owner direction: 53 physical spaces, 41 schedulable and 12 excluded (PRRC 27 / 18 / 9; New Building 24 / 21 / 3; Court/Oval 2 / 2 / 0). Preserved the DOCX aggregate discrepancy (37/16), recorded absent capacities/equipment/availability, and classified special-use rooms by activity. Added ID pattern `^[0-9]{2}-[0-9]{5}$` and lowercase dotted-name student email at exact `student.pnm.edu.ph`; formatting is not identity proof, and active roster/email match remains required. The clean restrained UX, accessible motion evaluation, and hard $0/month launch block are now consistent across documents.

Documentation-only revision. Updated `PROJECT_STATUS.md`, `FUNCTIONALITY_AUDIT.md`, `BUGS_AND_ISSUES.md`, `SECURITY_AUDIT.md`, `MASTER_ROADMAP.md`, `MASTER_IMPLEMENTATION_PLAN.md`, `TESTING_STRATEGY.md`, `DEFINITION_OF_DONE.md`, and `ROOM_INVENTORY_UPDATE.md`; appended this evidence. No application source, migration, database, provider, real-data, or `main` worktree change. Existing focused test/build evidence was not rerun or represented as new evidence; the scheduling UNKNOWN failure and unverified provider/release gates remain open. Validation: `node_modules/.bin/prettier --check docs/audit` PASS; `git diff --check -- docs/autonomy/STATUS.md` PASS (Git emitted only a working-copy LF-to-CRLF notice). No application tests were required for this plan-documentation revision. Next: owner review of the consolidated plan, then only dependency-ready authorized local roadmap work.

## 15 November 2026 — static audit and master implementation plan

Target: `feature/auth-onboarding-saas`, baseline/current HEAD
`7165fa130e413f8dc8893b85d30ecbe530ef8173`; clean at audit start. The separate `main`
worktree was not modified. Added the seven audit/acceptance documents and consolidated
`docs/audit/MASTER_IMPLEMENTATION_PLAN.md` / `MASTER_ROADMAP.md`. These are planning
deliverables only; application source, migrations, provider settings and real data were
not changed.

Fresh focused checks on this exact commit:

- Frontend auth/routes/schedule/calendar: 6 files, 55 tests PASS.
- Gateway onboarding/token/provider lifecycle plus Scheduling engine:
  67 PASS, 1 FAIL, 1 Starlette TestClient deprecation warning. The existing
  `test_complete_multi_program_batch_and_independent_minutes_check` returns solver
  `unknown` under its unchanged 8-second limit. No unchanged retry or guard change.
- `npm run typecheck --workspace=@classync/web`: PASS.
- `npm run lint --workspace=@classync/web`: PASS.
- `npm run build --workspace=@classync/web`: PASS with Firebase dynamic/static import
  warning and 692.33 kB minified chunk warning.
- `git diff --check -- docs/audit`: PASS (untracked audit files were also reviewed by
  status and file inventory; this command alone does not inspect untracked content).

No full suites, service/browser journey, migration, database connection, external
dependency scan or hosted provider check was run. No original DB was opened or modified;
their hashes were not independently checked in this audit. New risk record: current
solver UNKNOWN is an observed release gate. Authority conflict (PostgreSQL vs Firestore)
is resolved by the owner's instruction for this plan: PostgreSQL is authoritative and
Firestore optional absent verified rubric approval. Free-tier pricing was checked against
provider-published pages, but is volatile and carries no zero-cost/availability promise.

Next: review `docs/audit/MASTER_IMPLEMENTATION_PLAN.md` and `MASTER_ROADMAP.md`; first
implementation gate is authority-document reconciliation and exact-candidate evidence,
then diagnose solver UNKNOWN without changing limits/constraints. No merge, commit, push,
deployment, cloud setup, real-record import or original-data cutover authorized.

## 6 November 2026 — release candidate portability review

Local checkpoint `a54b53343bed00fbbdfdeacf511889213f3eac98` on
`release/mvp-staging-qualification`. The six identified paths belonged to manual
qualification. Four browser scripts now resolve Playwright locally or through
`CLASSSYNC_PLAYWRIGHT_MODULE`. These checks use installed Chrome. The cohort browser
accepts a local synthetic fixture JSON as its first argument. The two Python launchers
store screenshots in their owned run directory.

The Windows cohort qualifier requires `--preservation-receipt` and supports
`--database-root` for relative receipt paths. Supply a current, reviewed local receipt
covering the original databases. It accepts `original_database_sha256` mappings and
legacy `file`/`sha256` rows. It verifies all listed files before execution and checks
them again before writing success evidence. The receipt and output remain local.

Source-only export collected 1,063 tests. Targeted module resolution and receipt
checks passed with synthetic files and a stubbed qualification run. Node syntax,
Ruff, `git diff --check` and 19 security checks passed. The three original SQLite
hashes match the checkpoint. Older diagnostic scripts outside these six retain
workstation paths. The portability edits await a separate local commit. Native Linux
and remote Actions qualification remain pending.

## 6 November 2026 — release candidate prepared locally

The `release/mvp-staging-qualification` worktree uses base
`aea9494db46153672a31a2161070e5e4ff713966`. The proposed snapshot includes 193 reviewed
additions and updates and omits 744 inherited raw evidence paths. The original files and
shared history are preserved. Original SQLite SHA-256 values match the accepted baseline.

Node 22.23.1 installed the committed npm lockfile from cache. The presentation build
passed with read-only metadata. Python 3.12.14 collected all 1,063 tests via
`python -m pytest --collect-only` at the root. The 26 focused fixture, OCR boundary and
container contract tests and 19 security checks passed in the source-only worktree.
The prior full suite and 39 Postman assertions remain the accepted evidence for their
respective scopes. The registry audit failed the existing low threshold with seven
moderate findings linked to GHSA-g3hv-75wg-m249.

Native Linux and GitHub Actions qualification require an approved push. The public
GitHub origin has an active Vercel integration. Current Vercel branch and build settings
require confirmation before publication of the candidate branch. The local index remains
unstaged. Commit, push, deployment and provider staging require separate authorization.

## 6 November 2026 — publication/Postman PASS; release BLOCKED by external/security gates

Owner explicitly reopened bounded publication diagnosis/correction; no Docker/WSL/BIOS,
commit/push/cloud changes authorized. Base/current HEAD remains
aea9494db46153672a31a2161070e5e4ff713966, main/index unchanged. All prior candidate hashes
matched at entry; original three database SHA-256 checkpoints matched before/after.

Confirmed exact cause: fixture's already-published draft/calendar correctly triggered409
duplicate_publication after successful auth/revision/review. Reproduced409 on a new
disposable fixture with no history writes. Corrected only
scripts/postman_local_qualification.py: Gateway fresh generation/independent valid result,
new server draft201/current academic and publication revisions/new keys; focused run then
another fresh draft for full set. No backend/solver/authorization/RLS/schema/guard changes.
First focused CLI selection failed before HTTP; exact two-request temporary subset fixed
selection while preserving source requests/auth/scripts/HTTP200 assertions.

Actual focused2requests/2assertions PASS475ms. Then original35requests/39assertions PASS,
5.5s. History head1→2→3, exactly one version per actual publication; old API-visible
immutable summaries preserved except expected supersession. Replay200/no additional rows;
missing token401, Student/Teacher403 and stale409 produce no history writes. Both current
role timetables reference final publication and contain assigned sessions. Actual guard
qualification6denied folders/0HTTP hits/effective override denied PASS. Full connected
browser not repeated; existing service setup reused Auth Emulator and disposable PG/RLS.
Owned Auth/PG stopped; temp token environment deleted; no cloud reporting/real users/data.
Receipts `../production/m5-publication-20261106/postman-final-02.json` and focused/full
console logs; failed selection retained. Independent source review agrees; raw publication
DB checksums not re-audited because application storage implementation is unchanged.

Fresh security19PASS, container contracts7PASS0.27s, affected Ruff PASS. js-yaml workflow
parse and Git Bash `bash -n` PASS (syntax only). No redundant full suites/builds. Prior
1063backend/804frontend/full browser/builds are historical evidence, not new runs.

Fresh npm audit still7moderate nodes/one GHSA-g3hv-75wg-m249, high/critical0. Registry
current TS-ESLint8.72.1 still requires minimatch^10.2.2; latest10.x10.2.6 affected, fixed
11.0.1 outside supported range. No compatible fix, major override, force fix, suppression
or gate waiver; lock/dependencies unchanged. Release security remains BLOCKED.

Owner confirms no existing approved Linux runner, prepare checks for later approved push.
Added bounded Ubuntu container job to existing .github/workflows/quality.yml and fixed-
localhost health/auth/Academic outage/recovery checks in scripts/linux_runtime_probe.py.
Future job builds all3existing images/native probes/OCR with internal/no-network phases,
non-root/read-only/capability-dropped containers and1CPU/1GiB budgets; no images pushed,
host ports/mounts/secrets or deploy. No new trigger. Native Linux/OCR/remote Actions remain
IMPLEMENTED-UNVERIFIED pending separate checkpoint/push approval and actual execution.

M5_PUBLICATION_QUALIFICATION.md records exact changes, current results, preserved hashes,
checkpoint exclusions and remaining gates; M5_STAGING_ACCEPTANCE.md contains variable
NAMES/descriptions, resource/cost/IAM/TLS/migration/retention prerequisites and synthetic
provider checklist. API notes/evidence updated. Production/staging cutover remains NO-GO.
Next bounded action is reviewed Git checkpoint authorization and supported security fix/
disposition, followed by approved Linux Actions and separate staging configuration/provider
acceptance. No pending publication failure/approval gate remains.

## 5 November 2026 15:21 SGT — M5 final qualification PARTIAL; bounded gates open

Exit security review: Postman denied guards now explicitly skipRequest and validate
effective destinations, preventing script-error fallthrough and iteration-data redirects.
Actual Postman denial-only check6folders/0HTTP receiver hits PASS, independently of the
gated publication harness retry. No approval flags, thresholds or assertions relaxed.

Base/current HEAD `aea9494db46153672a31a2161070e5e4ff713966`, branch main/index unchanged.
Owner approved prerequisite inspection/bounded Docker preparation and synthetic fixture
replacement. Read-only host checks: Windows10Pro22H2/19045.6466,7.88GiB RAM (~1.21free),
12.17GiB disk free, SLAT/VM monitor supported, firmware virtualization DISABLED, no active
hypervisor/Docker/usable WSL. No privileged install/features/BIOS/restart or cloud changes.
Manual virtualization/restart decision pending; actual Linux/container execution BLOCKED.

Implemented local Linux OCR using Gateway-only Poppler/Tesseract, fixed native arguments,
bounded dimensions/TSV/files/CPU/address space/deadline, private cleanup and no cloud path.
Independent review found orphan native-child cleanup; stop_worker now terminates owned
POSIX groups even after worker exit. Portable regressions cover this, not native execution.
Dockerfile/native probe/portable synthetic raster generation updated. More stringent new
Linux FS/FD limits; existing solver/512MiB/15CPU/20wall/page/file guards not raised.

Clean-checkout fixture dependency fixed: test_cohort_curriculum.py,
test_real_academic_readiness_review.py and new synthetic_review_inputs.py use invented
CSV/catalog/OOXML/review inputs and outputs in pytest temp storage. No private staging
reads/original report writes; structural runtime catalog check remains separate. Focused21
PASS. Final full backend `python -m pytest`1063PASS107.08s, existing Starlette warning.
Scanner-focused28PASS3.37s; security19, full Ruff/pip check/diff check PASS. Later changes
are Postman-only qualification tooling, checked separately without another full suite.
Frontend/lock unchanged in this final scope; prior804/frontend/builds/artifact4 are retained
historical acceptance, not new executions. No skipped tests or guard relaxations.

Signed official portable Postman CLI1.86.0 used without installer/login/global settings;
reviewed binary SHA/signature in M5_RELEASE_QUALIFICATION.md. Core/pending13requests/
13assertions PASS inside actual Auth/Gateway/Academic/Scheduling/new disposablePG journey.
Connected browser172082ms under180s guard PASS, includes publication/rollback/scanner/
requests/notices/room/profile/revocation/SQL/5width/native200. Auth and PostgreSQL stopped,
owned emulator outbound-denied count0; that counter is not whole-machine network telemetry.

Expanded focused Postman mode reuses those service fixtures without browser rerun.
Latest35requests/39assertions:38PASS,1FAIL publication expected200 got409 using already
published fixture draft. Verified Student linking, faculty invite/accept/replay, generation,
review, actual Student/Teacher published classes, PDF/review/match/wrongterm/delete404 and
role denials passed. Earlier pending-token shadowing was corrected to separate tokens.
Persistent-failure approval requested before further fresh-draft correction/retry; no
publication assertion changed. Not full Postman PASS. All receipts retained, no tokens
or populated environment exported; private runtime environment deleted on exit.

Fresh npm audit7moderate nodes from GHSA-g3hv-75wg-m249/minimatch10.2.6 via TS-ESLint8.71.1;
production dependency projection empty. Reviewed current parent still needs10.x; no
supported compatible fix applied/major override/waiver/threshold relaxation. Low audit gate
BLOCKED. Python dependencies unchanged; prior77-version0-finding audit retained, fresh
pip check PASS. Remote connector shows old Vercel success and empty PR-filtered runs;
remote Actions/dirty current candidate UNVERIFIED. No Git/cloud publishing or CI trigger.

Read-only checkpoint review410paths/191candidates/219private-or-raw exclusions; narrow
secret indicators0, no tracked PDF/DB/workbook/key/populated-env candidates. Exact hashes
and classifications in `../production/m5-final-20261105/worktree-review.json`. Exclude
private docs/academic and raw logs/screenshots; preserve all uncommitted work. Original
three DB hashes freshly match owner-confirmed baselines, including intentional Demo save.
No original DB connections/migrations/writes, live users, real forms/rosters or deployments.

Deliverables: M5_RELEASE_QUALIFICATION.md (runtime/security/CI/checkpoint/blockers),
M5_STAGING_ACCEPTANCE.md (variable NAMES/descriptions, resources/budget/IAM/prerequisites
and15-step actual-provider checklist), updated API collection/README/CLOUD_RUN_STAGING.
Next: owner-authorized focused Postman harness correction; manually enabled virtualization
and separately confirmed OS installation; supported npm fix/disposition; approved Git
checkpoint/push then Actions; separate cloud configuration/deployment/provider acceptance.

## 5 November 2026 14:10 SGT — M5 local implementation qualified; cloud/release BLOCKED

M1–M4 remain PASS for bounded local acceptance. M5 source/delivery work implemented:
new Gateway coursework.py/coursework_cloud.py/coursework_schema.py, strict CORS/secret
settings, explicit optional-cloud disable, owner-hashed preference CRUD with revision+
generation CAS, private synthetic-text Storage and fixed-topic bounded Gemini advice.
No academic/identity/enrollment/publication authority moved from PostgreSQL. No scanner
document is sent to cloud. GET/POST/PATCH/DELETE /api/v1/coursework/preferences;
POST /coursework/files, GET/DELETE /coursework/files/{uuid}, POST /coursework/advisory.
Bearer Swagger metadata and unique operation IDs added without changing route authority.
Postman artifacts/generator, Docker/Compose/non-root entrypoint/per-service env templates,
staging instructions and tutorial map in MVP_M5_TRACEABILITY.md. No deployed changes.

Independent security review identified/fixed absolute advisory deadline, stale generation
after preference recreation and shared Compose credentials. New regressions and narrow
source confirmation pass. Instance-local quota/restart limitations and unsupported Linux
OCR are documented; no cloud readiness is inferred. Cloud providers default disabled.
Final source/evidence/data hashes: `../production/mvp-20261104/m5-exit-manifest.json`.

Final full backend1048/95.49s; frontend804/58files/274.89s under unchanged300s guard;
typecheck/lint/Ruff/security19; both builds and artifacts4/79.27s PASS in m5-*-final logs.
Actual Auth/Gateway/Academic/Scheduling/new-PG browser `m5-connected-final.json`
PASS144697ms under unchanged180s child guard: all M3/M4 role/request/publication/
rollback/readiness/notices/rooms/profile/recovery/revocation/SQL cases,5widths/native200,
errors0/healthy503=0/outbound0; owned services stopped. Cloud not called. Original DB
checkpoints preserved, including owner's confirmed Demo save. Solver/constraints unchanged.

Python exact-version audit initially could not normalize dotted Windows OCR names;
corrected to PEP503 names, respected platform requirement markers, retained complete
installed-package/no-skip coverage. Four pyasn10.6.4 advisories fixed with compatible
0.6.5 runtime/security constraint. Final77 exact versions/0 findings, pip check PASS.
Npm audit remains BLOCKED:7 moderate development-tool findings, high0/critical0; inspected
current/latest TypeScript-ESLint parent still requires affected minimatch^10.2.2.
No unsupported override, advisory exclusion, threshold change or policy exception.

Postman static artifact2 checks pass and are included in security19. Evaluated isolated
Newman6.2.3 had19 dependency findings including1 critical; lifecycle scripts disabled,
runner never executed. Removed only its verified newly created var tool directory;
audit/install evidence retained. Application dependencies unchanged by that attempt.
Postman runtime execution NOT qualified. Docker CLI absent: image/run NOT qualified.
Cloud ADC/project/bucket/model/key/privacy/IAM/retention/quota and staging approval absent:
Firestore/Storage/Gemini cloud integration IMPLEMENTED-UNVERIFIED. Remote Actions status
UNVERIFIED (connector PR-filtered only; Vercel success is not Actions/current worktree
qualification; gh absent, public REST inaccessible). No production readiness claim.

All local source work remains uncommitted, HEAD aea9494db46153672a31a2161070e5e4ff713966;
pre-existing work preserved. No commit/push/production or staging deployment, live account,
cloud IAM/rules/resources/secrets changes or original-data migration. M5 overall PARTIAL,
not accepted as complete. Next bounded action requires an approved credentialed staging
target and secure execution environment for actual cloud/Postman/container qualification;
release also requires the unresolved npm/remote-CI gates. Do not weaken them to proceed.

## 5 November 2026 — M4 PASS for bounded local acceptance

New room directory/details, announcements, own profiles/settings and published-change
screens are connected. Exact source/routes inventory in MVP_EVIDENCE.md and source/data
hashes in `../production/mvp-20261104/m4-exit-manifest.json`. Current original checkpoints
match M3 owner-confirmed Demo save; no restoration/migration of originals. All dirty
user work retained, HEAD unchanged. Requests/decisions retain M3 qualification.

Actual `m4-connected-02.json` PASS122007ms with complete M3 journey plus announcement
CRUD/audience/stale/unauthorized checks; all-role directory whitelist/wrong-term denial,
Teacher profile confirmed SDK200 and restoration, actual emulator reset email, room
detail navigation, three-role revocation,5widths/native200 and five new SQL role/tenant/
provenance/directory controls. Errors0/healthy503=0/outbound0; owned Auth/PG stopped.
Independent review's dual-role directory finding corrected and reviewed; unit regression
and actual SQL selected-role control pass. First01 SQL harness wrapper mismatch preserved
and corrected without changing the intended23514 guard. No unresolved failure.

Full backend1020/82.50s; frontend804/58files/188.21s; typecheck/lint/Ruff/security17;
both builds and artifacts4/80.41s PASS (`m4-*-final.log`). Minor final link-spacing/retry
and honest update-copy changes covered by full frontend/build checks. Manual screen
reader/cloud/real-institutional provisioning remain unqualified. No remote CI/advisory
refresh or production certification claimed. Next authorized task M5 tutorial-scoped
API/cloud adapters/Postman/container/docs and dependency/CI status; actual cloud calls
remain separately gated by credentials/configuration/approval.

## 5 November 2026 — M4 implemented, connected qualification in progress

Implemented room metadata GET /api/v1/timetables/rooms/{period}, selected-role current
assignment/enrollment eligibility and verified-only capacity/type/equipment. Student
Rooms connects its directory/Labs to this data; Teacher/Admin rooms, details, exact-ID
class links and preserved term/date context connect through new shared hook/page.
New announcements migration0016, Gateway router/repository reuse existing PG pool:
GET/POST/PATCH/DELETE /api/v1/community/announcements, audience/current-role/tenant/
project RLS, revision CAS, archive, immutable creation provenance and bounded create rate.
New connected notices/profile/settings/update pages and navigation; own SDK name edit,
recovery/logout and actual published changes; no fake alert-delivery setting.

Independent review found dual-role Admin RLS could expose unrelated room directories
when selecting Teacher/Student. Added explicit current-snapshot eligibility and negative
tests; reviewer inspected correction, no remaining narrow finding. Focused backend45,
existing affected frontend47, new notice/directory6 and profile3 PASS; Ruff/typecheck/lint
pass before final qualification. Full M4 regression/build exit not yet run.

Connected01 complete browser PASS127352ms: actual notices CRUD/audience/stale denial,
own profile update/restoration, actual Auth Emulator reset email, all-role directories,
Teacher rooms5widths and native200 announcement keyboard submission (controls5,
clipped0), existing M3 journey/revocations, errors0/healthy503=0. Overall01 FAILED only
after browser exit: SQL provenance attack correctly raised23514, but qualification caught
DBAPIError outside a service context that translates it to HTTP503. Corrected only the
test SQL boundary to direct runtime transaction with identical UID/tenant/project/role;
intended constraint unchanged. Fresh02 includes extra5width captures for notices/profile/
Student directory; currently running. No original/cloud/Git changes; owner-confirmed
EDD232195A… checkpoint unchanged. M4 is IMPLEMENTED-UNVERIFIED until exit gates pass.

## 5 November 2026 — M3 PASS for bounded local acceptance

Owner confirmed the unexpected03:42 original SQLite write was their intentional Demo
save. No restoration or source workaround; preserved owner-confirmed EDD232195A…
checkpoint and prior historical hash/diagnosis. Current source/qualification manifest
`../production/mvp-20261104/m3-exit-manifest.json`. HEAD unchanged; dirty work retained.

Actual connected `m3-requests-final.json` PASS: Administrator calendar/readiness/
generation/draft/review/publish; invited Teacher and approved Student see matching
current published data; Teacher request/replay/foreign-class/role denials, Admin approve
or reject, validated room-change publication/fulfillment, version4 restoration,
incomplete readiness blocks generation/review/publish, revocation403, seven independent
SQL role/tenant/evidence/transition controls. All5widths/native200; errors0/healthy503=0,
outbound0, Auth/PG stopped. Current-original checksums unchanged since owner checkpoint.

Final full backend1003/91.94s (`m3-backend-final-03.log`); frontend795/55files/229.33s
(`m3-frontend-final-02.log`); exit typecheck/lint, full Ruff, security17, both builds
and artifacts4/87.74s PASS. Existing Starlette/bundle warnings retained. First backend
1002/1 synthetic8s failure then isolated unchanged PASS; final serial suite PASS. First
frontend794/1 stale blanket institutional403 expectation corrected to explicit unsigned
401 with zero-fetch and all sandbox403 checks retained; focused3/final795 PASS. No
solver/constraint/timeout/guard changes. Independent correction review found no defect.

Source/API inventory in MVP_EVIDENCE.md; request routes plus existing academic,
generation/draft/publication/calendar endpoints are connected. Manual screen reader,
cloud staging, institutional data/provisioning remain unqualified; dependency advisories/
actual remote CI status require M5 refresh. This is local acceptance, not production
certification. Next authorized bounded task M4 existing supported features, acceptance
cases in MVP_M4_ACCEPTANCE.md. No additional routine approval required.

## 5 November 2026 — database stop resolved by owner confirmation

Owner confirms the03:42 Demo save was intentional. This explains the new original
SQLite run/draft and hash change; no application/test defect or restoration is required.
Preserve the owner's new data. Historical SHA1848377C… remains in prior evidence;
current owner-confirmed preservation checkpoint is EDD232195A1FCF79389BF633CE3FBDC8
120705923C5D1441810069A878C1D88D. Academic/backup remain unchanged. Resume M3
disposable-only backend qualification and pending frontend/build gates; no release,
cloud, original-data migration or Git authority expanded.

## 5 November 2026 — approved read-only diagnosis; attribution pending

Owner approved bounded read-only diagnosis/correction/qualification with no original DB
overwrite/restoration. Inspection uses SQLite URI mode=ro&immutable=1 plus query_only;
SHA256 unchanged before/after. `m3-readonly-schema-diagnostic.json` and
`m3-readonly-data-diagnostic.json` contain counts/structural evidence, no personal payload.
One new run03:42:22 and one draft03:42:34 (SGT) in academic-sandbox, all stored payload
checksums valid, zero publication rows. The new draft's period already exists in original
academic.sqlite3; its period does not match retained disposable Auth browser fixtures.
Long-running local Demo service tree started4 November22:51 and its default sandbox
generation/save paths write this original SQLite file. Caller attribution is NOT proven;
there is no retained per-request audit establishing user versus automation. No confirmed
test isolation defect, source correction or original-data restoration is claimed.
Asked owner whether this was an intentional Demo save; DB-sensitive qualification and
M3 acceptance remain paused pending that clarification. Independent full frontend run
started (does not use original DBs). Original historic hash is retained; do not silently
replace its preservation baseline with the changed hash. No existing process was stopped
during diagnosis; the bounded source search was interrupted after including too broad
an apps tree, then repeated only scripts/apps/web/src/docs/autonomy.

## 5 November 2026 — M3 STOP: original database preservation mismatch

HEAD remains aea9494db46153672a31a2161070e5e4ff713966; all dirty work retained.
Final actual connected qualification `../production/mvp-20261104/m3-requests-final.json`
PASS: request/replay/isolation/approval/publication/fulfillment/rejection, rollback4
with matching Student/Teacher rooms, incomplete-readiness generation/review/publish
denial, revocation, five widths/native200 (clipped controls0), browser errors0,
healthy503=0, seven SQL RLS/integrity controls. Auth/PG stopped, outbound0.
Earlier03 rollback409 diagnosed historical duplicate guard; narrowed both adapters
to current-head duplicate only, preserving CAS/idempotency/readiness/validation.
04 browser passed, subsequent SQL synthetic tenant-B control insertion failed audit
RLS because setup retained tenant-A context; corrected test context, final PASS.
Independent review found no regression. Focused backend19/frontend18, Ruff,
typecheck02, lint and security17 PASS. New test role-query unsupported exact option
corrected without changing assertions. Full backend1002 PASS/1 FAIL (8s synthetic
solver); isolated unchanged failing case then PASS8.59s. Full backend02 was interrupted
when the preservation gate below was detected; no PASS claimed. Full frontend/build
and artifact checks remain pending; M3 is NOT accepted.

Preservation check found var/scheduling.sqlite3 SHA256
EDD232195A1FCF79389BF633CE3FBDC8120705923C5D1441810069A878C1D88D,
different from recorded original
1848377CC9A9EB656E12B5E58436E81198FEF92F18DD71C1FEA2F6F8B482E400.
File last-write metadata reports5 November03:42:34; cause unqualified.
Academic and backup hashes still match. Current hashes preserved in
`../production/mvp-20261104/m3-data-preservation-stop.json`. No repair/restore/write
to the original was attempted. AGENTS.md mandates explicit approval for unexplained
data changes; stopped owned full-suite session13988 via Ctrl+C. Process inventory via
Get-CimInstance was denied; no unidentified process was stopped. Pending owner decision:
bounded read-only provenance diagnosis and disposable-only source/test correction,
without overwriting original DB or relaxing guards. M4–M5 have not started.

## 5 November 2026 04:08 SGT — M3 core connected journey PASS, requests in progress

HEAD unchanged; all prior dirty work retained. Actual Auth/Gateway/Academic/Scheduling/
new-PG browser control `../production/mvp-20261104/m3-connected-03.json` passes:
pending Student/Admin approval, faculty invitation/activation, calendar PUT, readiness,
generation, immutable draft, independent publication review and version2 publish; both
role projections have identical session/room/faculty/version data,5widths/refresh,
cross-role denial and immediate403 reads after both revocations. Services stopped.
Earlier01 asserted wrong pending copy;02 actual server log proved exhausted connections.
Shared bounded DATABASE_POOL_SIZE setting preserves default5/max5/overflow0; qualification
uses2 per service under unchanged PG max_connections10. Lifecycle/auth95 and focused
frontend29 + later route/input16 (overlap, not summed) pass; reviewer inspected transport
and removed-period stale-data correction. Full M3 exit not run/accepted.

Implemented current-role routes, bounded same-origin clients, Teacher projection without
mock request summary, Admin inputs/calendar/drafts/conflicts/publication/history. Now
implementing required classroom requests: migration0015 and Scheduling module plus
Gateway Teacher POST exception, own-current-class/eligible-room checks, idempotency,
RLS/revisions/Admin decisions, approved-change prefill and publish-then-confirm UI.
New request code IMPLEMENTED-UNVERIFIED, security review/tests/PG/browser pending.
No original migration, cloud/users/deployment/Git actions. M3 remains PARTIAL until
requests and full applicable gates pass; M4–M5 remain planned. Next: finish request
qualification (add disposable alternate room/runtime grants), independent security
review, negative paths and actual Teacher request→Admin decision→validated publication.

## 5 November 2026 03:34 SGT — M2 PASS for bounded local acceptance

Owner approved bounded diagnosis. Failed timetable assertion expected course codes,
while actual UI renders course names. Corrected assertion verifies HTTP200/publication
version/exact subject codes and visible corresponding subject-name buttons, then hidden
loading. No application loading workaround, solver/constraint/limit or guard change.
Actual connected final journey PASS: `../production/mvp-20261104/m2-connected-scanner-final.json`.
Signup/verification, private PDF, corrections/restoration, pending claim/Admin approval,
published matching/timetable, wrong-term/unmatched, photo OCR correction, deletion and
keyboard action pass.5widths pass; native200 actual width720/ratio2/clipped-controls0,
viewport screenshot visually inspected (full-page native screenshot issue avoided).
Expected403 pending membership only; no browser errors/healthy503, outbound0; services stopped.

Fresh final backend986/94.62s and frontend776/51files/211.68s pass, unchanged guards.
Typecheck/lint/full Ruff/security17/both builds/artifact4 pass. Existing framework and
bundle/split warnings remain. Logs `m2-*-final.log`; source/qualification/original hashes
in `m2-exit-manifest.json`. All3 original SQLite hashes unchanged. Independent corrections
reviewed; four-format synthetic actual worker passes. Personal PDF inspected locally
without copies/fixtures/logged values/cloud uploads. Exact files/routes/limits/history in
MVP_EVIDENCE.md. No commit/push/cloud/settings/deployment/original migration or real users.

M2 locally accepted; Windows OCR qualified, Linux OCR/manual screen reader/cloud not
qualified. Per-instance ephemeral extracted drafts can disappear on restart; explicit UI
recovery provided. No institutional identity or schedule authority derived from forms.
Next authorized bounded work: M3 connect Teacher/Admin journeys to existing APIs and
prove publication shared by authorized Student/Teacher. M4–M5 remain planned.

## 5 November 2026 03:06 SGT — M2 PARTIAL, persistent-browser-failure gate

Base/current HEAD `aea9494db46153672a31a2161070e5e4ff713966`; prior dirty work retained.
Private scanner/source/routes and exact limits/files are recorded in `MVP_EVIDENCE.md`.
Digital PDF + bounded local Windows PDF/PNG/JPEG OCR implemented; private review/manual
correction, pending verification and exact published enrollment matching implemented.
No real form copies/fixtures, personal logging or cloud upload. Actual synthetic worker
four-format qualification passes (`m2-local-ocr-02.json`); OCR I/O ambiguity explicitly
requires correction. Fresh Gateway scanner18 and frontend scanner8 tests pass, focused
Ruff/diff checks pass. Independent review corrections inspected, including deferred-match
discard across authorization loss/restoration. Full M2 regression/static/build exit not run.

Actual connected browser reached signup/email verification, PDF extraction, corrections,
pending claim, trusted Admin approval, restored corrections, authorized matching, wrong
term/unmatched denial and all5 matching-screen widths. Still NOT accepted: timetable
assertion timed out in attempts05 and06 at unchanged30s limit.05 opened empty partial
first term week; scanner link now uses earliest actual matched published class date,
covered by passing regression.06 opens Oct5 week and reports2 classes but captured body
still says Loading your schedule. Expected subject-code assertion also needs diagnosis
against actual timetable rendering. No complete timetable/photo/native200/deletion journey
PASS claimed. No more unchanged retries or implementation until bounded approval.

Evidence: `../production/mvp-20261104/m2-connected-06-{failure-dom.txt,
failure-network.json,auth-cleanup.json,pg-cleanup.json}`. Sanitized request paths/types/
timings only; no bearer headers/bodies. Auth stopped=true, outbound0; PostgreSQL stopped.
Original academic/scheduling/backup SHA256 all match M1 exit manifest; no originals
migrated. All source/tests/evidence uncommitted. No cloud/Git/deployment action.
Per AGENTS persistent-failure gate, requested bounded diagnosis of connected timetable
rendering and scanner qualification with all existing guards/constraints preserved.
M1 local PASS remains dated evidence; M2 PARTIAL; M3–M5 PLANNED. Manual screen reader,
Linux OCR and cloud qualification remain open. Next bounded action awaits that approval.

## 4 November 2026 23:24 SGT — M1 PASS for bounded local acceptance

Owner explicitly approved bounded diagnosis/qualification. Read current state before
resuming; HEAD unchanged, prior work preserved. Instrumented CP-SAT run found a validated
feasible incumbent with unchanged8s limit (satisfaction2.985s under existing4.8s allocation;
optimization UNKNOWN safely retained incumbent). Synthetic-faculty flag produces identical
model hashes; prior missing traces prevent exact historical attribution. No solver/model,
constraint, time limit or test guard changes. Unchanged isolated regression passed; final
serial backend **968 passed**,88.21s, existing framework warning. Final frontend **768 passed/
50 files**,203.17s, unchanged300s guard. Focused post-copy UI17 passed. Typecheck caught one
unused new-test parameter; underscore rename only, final typecheck/lint/full Ruff pass.
Security17, institutional/presentation builds and artifact4 all pass; existing build warnings.

Final actual emulator/current-PostgreSQL/Gateway/browser acceptance PASS:
`../production/mvp-20261104/m1-onboarding-browser-final.json`. Includes email/password
signup/OOB verification and recovery, no implicit grant, pending claim/admin approval,
Student and Teacher revocation, duplicate linked-record rollback, expired/invalid/replayed/
revoked/email-bound invitations, RLS and SQL approval-reference denial. Actual browser
refresh restoration, Administrator approval/private invitation, Teacher activation and
keyboard logout; verification/Student-claim/Admin-invitation forms at all5 widths and
native200. Images visually inspected. Healthy503=0; expected403 membership denials only;
Auth/PG stopped, outbound0. Manual screen reader and live Firebase/MFA remain unqualified.

Current source/qualification hashes and all3 matching original DB hashes are in
`../production/mvp-20261104/m1-exit-manifest.json`. No real users, cloud/settings/messages,
original migrations/imports, commit/push or deployment. Earlier failures retained. M1
is accepted locally, not production/cloud certification. Next authorized task: M2 private
registration extraction/review with published-only authorized matching; existing local
Windows OCR en-US availability confirmed without cloud calls. M3–M5 remain planned.

## 4 November 2026 22:58 SGT — functional MVP M1 PARTIAL, mandatory stop

Current owner request authorizes local M1–M5. Base/current HEAD remains
`aea9494db46153672a31a2161070e5e4ff713966`; pre-existing dirty work preserved.
Acceptance written first; supplied registration/tutorial PDFs read locally, personal
values suppressed, no source copy/real-data fixture/cloud upload. Local M1 changes
implement Firebase signup/verification/recovery, pending claims, private faculty
invitations, current-Administrator decisions/revocation, email attestation, recent
privileged sign-in, bounded throttle and PostgreSQL migration0014 with existing audit/RLS.
Exact files/routes/traceability and limitations: `MVP_EVIDENCE.md`.

Fresh Gateway169 + new API4 tests, frontend account/session19 + panel2 tests, security17,
typecheck/lint/build and focused Ruff passed. Existing build/framework warnings retained.
Actual Auth Emulator/Gateway/disposable PostgreSQL API journey PASS in
`../production/mvp-20261104/m1-onboarding-04.json`; Auth/PG stopped, outbound0.
Independent reviewer found four issues; all fixed, covered, and correction-inspected.
Browser acceptance NOT PASSED: first load timeout, then instrumented signup/verification
hit missing temporary emulator iconv-lite files/500. That test-tool installation was
repaired and UTF-8 decoding checked; no successful post-repair browser run claimed.

Full backend **959 passed/9 failed**; eight portable conflict-fixture failures corrected
by constructing an explicit synthetic solver DTO, preserving conflict assertions and
the actual qualifier's normal readiness path. Affected serial check **34 passed/1 failed**:
the same solver test again returned UNKNOWN at its unchanged eight-second limit.
Logs: `../production/mvp-20261104/m1-backend-regression.log` and `m1-backend-affected.log`.
This is a persistent test failure; implementation/qualification stopped under AGENTS.md
and explicit bounded diagnosis/resumption approval requested. No assertion/limit/constraint
or solver change, no green full-suite/M1 claim, no M2–M5 implementation yet.

All3 original SQLite hashes freshly match P1/pre-work values. Latest owned Auth stopped
and PostgreSQL server_state:stopped; existing user processes preserved. No real accounts,
original migration, live record import, cloud action, messages, commit/push or deployment.
Next only after approval: diagnose recurring UNKNOWN without weakening guards, then
complete M1 browser/final acceptance and continue the authorized five-milestone sequence.

## Current session — 26–28 October 2026

Latest checkpoint: 29 October00:30 — shared workload/room-move invariants fixed; backend829 prior checkpoint; actual PG per-resource matrix and bounded scale25/250 pass. Remaining adapter race: conflicting publication/restriction winner/loser, then final regressions/review. P3b PARTIAL.

Latest checkpoint: 28 October23:15 — publication transaction probes passed on actual disposable PostgreSQL; backend829/security16/Python68-0/wheel16. Full adapter acceptance and P3b remain PARTIAL pending resource/conflicting-writer/scale matrix, provider and history rehearsal. See appended checkpoint; earlier counts below are historical.

Local main/HEAD remains `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`; pre-existing dirty work preserved. **P1, P2a, bounded local P2b and bounded emulator/local P3a PASS. P3b PARTIAL: academic adapter/migration/provider/restore, Scheduling draft adapter/provider/generated migration/restore, shared publication rules/workload correction and publication-state schema foundation are locally qualified. Publication application adapter/provider/restrictions, history migration/restore and complete P3b exit remain outstanding.** Latest bounded foundation exit: backend678/678, security16/16, portable28, actual PG18.6 state/ownership-collision/deferred-orphan/reconnect/rollback proof, independent review, fresh exact Python68/0, wheel15 byte equality, Ruff/pipcheck/diff0 and original hashes preserved. Twelve recorded owned clusters stopped/closed ports; one older cluster never started. Previous frontend709/40/lint/types/builds/artifact/browser evidence remains dated unchanged-input evidence, not freshly rerun. Existing chunk-size/Starlette/audit hashing warnings remain. PostgreSQL publication stays unavailable; no approval, complete institutional workflow, production/provider/TLS, cross-host recovery or manual screen-reader acceptance is claimed. Goal ACTIVE/incomplete; production NO-GO.

**This initial record is based on historic conversation and the GitHub default branch inspected 25 October 2026, NOT a current audit of `C:\Projects\ClassSync`.** Codex must reconcile local files, commit and uncommitted changes before implementation.

## Last known evidence (historical)

- Previous verified HEAD reported as `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`, `main`, clean (21 October). Reverify.
- Prior Codex reconciliation: 216 frontend tests and 78 backend tests passed serially; two earlier scheduling backend tests failed during overlapping workload. Reverify intermittent behavior.
- Existing presentation experience verified locally for three roles; live institutional production behavior not verified.
- P1 bounded local source implementation was approved but had not started in the last report. Do not assume this is still true.
- PostgreSQL selected as future relational authority; existing SQLite still used; migration/cutover not verified.
- Firebase production identity and institutional deployment not verified; current Vercel deep routes/manifest historically failed. Recheck deployed state if expressly authorized to inspect.
- GitHub default branch README/architecture docs still include outdated solver/publication statements. Reconcile with actual code rather than deleting working features.
- Root `AGENTS.md` was not found on GitHub on 25 October; inspect local workspace before copying this harness.

## Current verified state

See the dated current-session checkpoints below and [requirements traceability](TRACEABILITY.md). Historical counts and approvals above are not current acceptance evidence.

## Required checkpoint entry schema

For each checkpoint append:

```
### YYYY-MM-DD HH:MM local — <phase/task>
- Git branch/base HEAD/current SHA and `git status` summary:
- Authorization/decision reference:
- Goal and acceptance tests:
- Changed files and change rationale:
- Automated commands, exit codes and concrete result counts:
- Browser/service/integration evidence and artifact paths:
- Original SQLite/file preservation hashes (where applicable):
- Security/accessibility/solver risks:
- Remaining requirements and honest status:
- Independent review findings and how resolved:
- Gate: PASS | CONDITIONAL | FAIL | BLOCKED
- Next authorized dependency-ready task:
```

Do not overwrite prior checkpoint entries; append evidence and maintain a brief current summary at the top.

### 2026-10-26 03:44 Asia/Singapore — P1 route gate and dependency remediation (interim)

- Branch/base/current SHA: main, `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`. At entry substantial tracked modifications plus existing untracked AGENTS/config/docs/scripts/tests (inventory retained in session tool output). No reset/stash/rebase/commit/push. Existing cumulative changes are not claimed as new work.
- Authority: owner's current mission confirms bounded P1 and explicitly grants conditional P2–P8 local source/tests/docs/disposable-data/emulator work. Recorded in APPROVALS; no cloud, originals, identity-policy or security-risk exception authority implied.
- Acceptance written before edits: `docs/production/local-20261026/acceptance.md`. Newly exposed false release verification: 200 HTML login/error shells and redirects passed the hosted verifier; three omitted role schedule/dashboard/calendar paths were not probed. Five new negative tests all failed before source change, then passed. Fix extends route probes, disallows redirect following and compares shell hashes. Positive/missing SHA/wrong SHA/missing bundle/dirty metadata tests retained.
- Changed this session: `scripts/verify-hosted-presentation.cjs`, `scripts/tests/hosted-verification.test.cjs`, `scripts/tests/dependency-security.test.cjs`, web manifest and lock, APPROVALS/STATUS plus dated evidence. No application UI, solver, auth behavior or database source changed. Narrow package patch: Vitest 4.1.11→4.1.12 and eight related package updates; unused direct zod removed after repository source search. npm 10 install crashed with `edgesOut`; already installed npm 11.13.0 completed install with scripts disabled (log retained). No force/legacy-peer-deps, advisory suppression or exception.
- Executed: `npm run lint` exit 0; `npm run typecheck` exit 0; `npm run test:security` 13/13 exit 0 before and after dependency patch; `npm run build` and `npm run build:presentation` exit 0 (existing >500 kB warning retained). `ruff check scripts/security services packages` exit 0; `pip check` exit 0.
- Python: initial `pytest` under overlapping frontend/build workload 103 passed/2 failed (both CP-SAT UNKNOWN; not accepted). After stopping overlapping own workloads, full isolated serial pytest **105 passed**, 76.48s, unchanged constraints/limits, original Starlette deprecation warning. Disposable DB roots printed in session; serial root `%TEMP%/classsync-serial-20261026-b03debe679904ad0a3827d8ab159914a`. Original DBs never selected for tests.
- Security: first restricted npm/Python audit attempts could not reach registries; retained as failures, not passes. Network-enabled exact Python audit: pip-audit 2.10.1, **62 exact versions, zero findings/skips**. Fresh npm before patch: zod high + Vitest/mocker moderate (3 entries); historical braces finding no longer in registry result. After patch: `npm audit --json` exit 0, **zero findings**; `npm ls --all` exit 0. Evidence in dated directory. Official advisories reviewed: https://github.com/advisories/GHSA-qxg6-89mg-rqv8 and https://github.com/advisories/GHSA-mrhx-c7xc-m3w5.
- Browser: Browser plugin absent; installed bundled Playwright/Chrome fallback per frontend-testing-debugging skill. `browser-check.cjs` exit 0; **15/15 role×width journeys** at 360/390/768/1024/1440. Role button → dashboard → heading → reload; title/URL/heading, no horizontal overflow, no console/runtime errors, zero API requests. Current production artifact fails clean-release metadata only, correctly, because dirty. `browser.json` and browser.log retained; screenshot paths in JSON. Inspected Student390 and Administrator1440 screenshots; truthful sample labels, legible logo/navigation; no layout defect observed on those two views. No UI change, so no before/after appearance difference claimed. Native 200%, keyboard/screen-reader and deeper live workflows not newly verified.
- Independent review: second agent found no actionable route gate defect; ran hosted fixtures **10/10** independently. It diagnosed default web worker stall: bounded direct threads/one-worker app-mode test **442/442 passed**, 5.98s. Full standard web run and expanded-access retry stalled before reporting suites, were interrupted (NOT PASS). Full thread-pool regression and artifact retry pending; no tests removed/weakened. Dependency review pending.
- Preservation: before/after SHA256 identical: academic `4cd5f60de21bd365c914ac01e5be692b3bea1c7a56a7f17a76c6953ef8668738`; scheduling `1848377cc9a9eb656e12b5e58436e81198fef92f18dd71c1fea2f6f8b482e400`; backup `9ec149413d69c1165b74a75e366fa262417c1ecbf41e7029fdd0d86ac96f395d`. No migration/live imports/cloud/Git writes. `git diff --check` exit 0.
- Gate: **PARTIAL, not P1 PASS**. Await full frontend/artifact gates and dependency review; P2 remains unstarted. Hosted deployment, real identity/membership, live role journeys, institutional rubrics and production release remain unverified/separately gated.
- Next task: finish current verification; investigate any repeatable runner/solver failure without weakening tests; enter P2a only after independent P1 acceptance.

### 2026-10-26 04:02 Asia/Singapore — P1 local gate closure

- Same branch/HEAD and protected dirty tree; no original data/Git/cloud side effects.
- Exact revised `npm run test:web`: **exit 0, 664/664 tests, 36/36 files, 221.22s** (`web-harness-final.log`). Full direct run independently retained: 664/664, 230.66s (`web-direct.json`). Earlier interrupted variants remain NOT PASS. Root command uses `scripts/test-web.cjs`, reproducing the qualified direct child invocation (web cwd, verbose, one thread). stdout/stderr and failure codes preserved; overall 300s watchdog fails on timeout, no individual test timeouts changed. Underlying Windows/npm/reporting cause remains undiagnosed; this workaround is bounded and reproducible, not a root-cause claim.
- Independent review verified full discovery/config and fail-closed harness; invalid CLI flag produced exit 1. No actionable source/dependency finding. Reviewer confirmed all eight Vitest packages installed/locked at 4.1.12, workspace manifest/lock agree and no unused zod remains. `npm ci --dry-run --ignore-scripts --no-audit --no-fund`: exit 0.
- Artifact retry: **exit 0, 4/4 groups**, 120.39s; nine unsafe builds rejected and ordinary/presentation/legacy artifacts served/probed. Earlier restricted artifact attempt was interrupted, not accepted. Current artifacts: `%TEMP%/classsync-p1-artifacts-lkRoDe`.
- Current browser evidence: 15/15 role/width journeys as above; native 200% checked against current ordinary artifact using an isolated temporary extension/profile. Chrome tabs.setZoom/getZoom=2; DPR 1→2, innerWidth 1424→712, CSS zoom=1, visual scale=1; keyboard Return-to-access focus and no overflow. Screenshot inspected. Native evidence/helper/profile retained under this session's visualization output; no user profile changed. This does not certify all screens or manual assistive technology.
- All applicable local automated categories now green: lint, types, full web, full serial backend, Ruff, security smoke, npm/Python scans, peers, lock dry-run, both ordinary/presentation builds and current artifact matrix. Earlier builds preceded the patch; artifact matrix rebuilt all three configurations after patch. Manual screen-reader/participant, future Linux image, institutional/hosted deployment and actual rubric acceptance remain open; no production PASS.
- Gate: **PASS — bounded P1 local engineering only**, following independent review. No advisory risk accepted, no hosted release declared. Next dependency-ready scope: P2a immutable identity/current-membership contracts with synthetic-only tests; no real identities, original DB or service authority integration.

### 2026-10-26 04:06 Asia/Singapore — P2a internal current-membership contract slice

- Base/current SHA unchanged: `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`, main. P1 PASS recorded before source edits; scoped owner authorization in APPROVALS applies. All earlier dirty work preserved.
- Before-edit acceptance: `docs/production/local-20261026/p2a-acceptance.md`. Implementation: `packages/api-contracts/classync_contracts/identity.py`; tests: `services/gateway/tests/test_identity_contracts.py`.
- New internal frozen models distinguish verified UID from academic person and membership, with immutable role grants. Lookup protocol and authorization helper query current membership each call, require matching tenant+UID, active state and exact required role; missing/revoked/inactive/wrong grants deny. Repository exception or malformed response produces typed unavailable; no token-role/sample fallback. Extra authority fields on principals and malformed IDs/revisions/roles reject. Returning a snapshot is not permission for a later write; record-level and transactional rechecks explicitly remain future caller duties.
- Targeted tests: **30/30**, exit 0; independent reviewer repeated **30/30**, 0.51s. Initial Ruff import-order finding corrected; final `ruff check scripts/security services packages` exit 0. No test weakened/skipped. Full final serial `.venv/Scripts/python.exe -m pytest`: **135 passed**, 58.92s, exit 0, one existing Starlette/httpx deprecation warning (`pytest-p2a-full.log`). Disposable DB root `%TEMP%/classsync-p2a-20261026-be6410420d0e4424b0514157d0c35b00`; no overlapping solver run.
- Negative evidence: wrong tenant/UID, no membership, inactive/revoked/no/wrong grants, lookup outage, malformed adapter output, unknown role, forged principal fields, mutable grants and stale cached authority are covered. Revocation is observed on the next authorization call because there is no helper cache.
- Independent adversarial review: no actionable blocker in this intentionally internal slice. Principal models are **not token verification**. No service/endpoint imports this module; source search finds only the new tests importing it. No synthetic runtime identity provider, real account, claim, policy, route or database was added/changed. Existing service authorization is not silently certified as current-membership authorization.
- UI relevance: no frontend source, API contract used by the browser, route, rendered state or entry-point behavior changed in this backend-only slice. Fresh P1 presentation role/width and native-zoom evidence remains applicable to the unchanged UI; no new institutional UI acceptance claimed.
- Preservation: final three SHA256 values still match entry/historical baselines (`database-hashes-final.json`); no original database open for writing, migration, roster import, cloud provisioning, credentials, messages, Git commit/push or deployment. `git diff --check` exit 0.
- Gate: **PASS for this internal contract slice; P2a phase PARTIAL**. Token verification/provider interfaces and error cases (missing/bad/expired/revoked/wrong issuer/audience), production exclusion of test/emulator adapters, dependency integration and later real database-backed membership remain unimplemented/unverified. **Do not enter P2b yet.** PostgreSQL 18 binaries were discovered read-only; server, privileges, driver and disposable test target have NOT been qualified or modified.
- Resumable next authorized action: implement the next P2a identity-verification port/test-adapter boundary with explicit production exclusion and token failure taxonomy; keep existing institutional-unavailable UI and service entry points unchanged until its acceptance passes. Then complete P2a integration/security acceptance before P2b. No background run or automation is active.

### 2026-10-26 04:38 Asia/Singapore — P2a local phase exit PASS

- Goal remains active for the full P2–P8 objective. Previous goal turn classified as progress (P1 closure and P2a contracts); this turn implemented the remaining local P2a boundary. HEAD/main unchanged; all original dirty work preserved. Authority: scoped owner P2–P8 local authorization, reconfirmed by active goal. No new institutional policy, users, real credentials, Firebase configuration, cloud/Git/deployment changes or original database modifications.
- Before-edit acceptance: `docs/production/local-20261026/p2a-token-acceptance.md`. New runtime modules: `classync_contracts/token_verification.py` and `request_authorization.py`; expanded immutable membership links in `identity.py`. Shared `scheduling_security.py` now composes verified identity and fresh current membership. Gateway auth/me, proxy and stream, Academic/Scheduling guards and publication routes use that boundary. `docs/security.md` reconciled to actual implementation; earlier braces-only statements marked historical.
- Firebase port uses explicit configured project/app and SDK `check_revoked=True`, returns UID only; role/tenant/record claims are discarded. Emulator environment blocks institutional verification. Synthetic/emulator adapters exist only in test support; explicit test environment+opt-in required, production/staging/ordinary development reject them. Default membership port always unavailable until P2b/P3; no claims/sample fallback. Server-configured tenant, current grants and explicit student/faculty record links determine scope. Multi-role selection must match a current grant; no implicit role precedence. The legacy general development setting no longer fabricates an authenticated identity.
- Typed errors: absent/invalid identity401 (Bearer challenge), denied membership/record/role403, provider/configuration/repository unavailable503. Historical missing-credential test intentionally updated to valid JWT syntax and exact generic503, replacing misleading401 semantics; no weakening of identity or membership enforcement. Existing positive generation/ownership and forbidden-role/publication assertions retained; claims-only fixtures upgraded to current-membership test adapters.
- Publication now authorizes before constructing/migrating repository. Student projections use explicit student_id rather than assuming Firebase UID is enrollment ID. Teacher links remain explicit. Gateway forwards role selector only if supplied, and downstream independently rechecks membership. Blocking verification is offloaded from async handlers. Open institutional streams reverify each iteration and stop on revocation, outage or changed binding/revision; this conservative strategy is not production load/cost qualification.
- Fresh commands/results: initial targeted88/88; expanded follow-up64/64; institutional projection+ownership targeted6/6. Initial full regression191 passed/2 failed because two older fixtures referenced removed SDK monkeypatch hooks; corrected their fixtures, preserved all assertions. Full corrected203/203. Two additional negative tests then added; final isolated serial full **205/205**,64.45s, exit0 (`p2a-phase-exit.log`), one pre-existing Starlette/httpx warning. Ruff exit0. No solver constraint/time-limit changes, no concurrent solver execution.
- Final root `npm run test:web`: **664/664**,36 files,268.93s, exit0 (`p2a-web-regression.log`). Fresh browser smoke: **15/15** role-entry/dashboard/refresh journeys across360/390/768/1024/1440, zero API/console/runtime errors and no horizontal overflow (`p2a-browser.json`, `p2a-browser-retry.log`). New Student390/Admin1440 screenshots inspected; unchanged truthful presentation UI. No production identity or full live role journey claimed. Native200% and manual assistive technology were not rerun for this backend-only change; prior checked-screen zoom evidence retained, manual screen-reader remains OPEN.
- Verification dispositions: expanded-access follow-up pytest hit shared temp/cache permission errors (48 passed/4 setup errors), not application failures; fresh unique basetemp/cache retry **52/52** passed. Browser helper initially raced on a still-mounted role-picker heading; strengthened to wait for exact role-specific heading before/after refresh, then15/15 passed. Prior evidence not overwritten or mislabeled as success.
- Real SDK offline evidence: generated in-memory RSA test material, actual SDK signature/issuer/audience/expiry parsing; public certificate/account/revocation transports stubbed. Revoked/disabled/account-outage/certificate-outage/bad signature/wrong issuer/wrong audience/malformed/expired cases covered. This proves local verifier behavior, NOT live Firebase account/provisioning or emulator service integration.
- Independent review found cached membership in open streams and missing institutional projection coverage; fixed both. Reviewer rechecked source and independently ran stream tests3/3; no remaining actionable P2a blocker. Projection fixtures are explicitly disposable institution-shaped records, independently generated/validated and published only inside temporary DBs; no synthetic fixtures represented as real institutional acceptance.
- Final disposable full-suite root `%TEMP%/classsync-p2a-exit-9ce38fd398ab4fcf84c214339141ed01`; original hashes unchanged (`p2a-token-database-hashes.json`), all three match04:06 and entry baselines. `git diff --check` exit0. Dependencies unchanged in P2a; P1 scan evidence retained as dated evidence, not a new scan claim.
- Gate: **PASS — complete locally implementable P2a contract/token/test-adapter/FastAPI boundary**, not authoritative institutional integration. P2b may begin under existing owner authorization. Production remains NO-GO: membership DB absent, SQLite is still local owner-scoped storage, institutional policy/provisioning/live identity and production qualification remain unverified. P2b/P3 must not expose these local SQLite repositories as qualified tenant persistence.
- Next authorized outcome: qualify a brand-new disposable local PostgreSQL18.6 cluster, least-privilege runtime and driver/migration compatibility without touching installed/original clusters, credentials, institutional records or live authority. PostgreSQL18.6 binaries found; no server started or driver installed yet. No background automation is claimed.

### 2026-10-26 05:03 Asia/Singapore — P2b disposable server qualification PASS / phase PARTIAL

- Full P2–P8 Goal remains ACTIVE and incomplete; no scope shrink or goal-complete claim. Main/base/current SHA remains39200a4f2ef3ec7557bc3c86127e674e260ca4fc. Existing dirty source preserved. P2b started only after recorded local P2a phase PASS under the scoped owner authorization. This entry is a resumable continuation checkpoint, not the overall objective's completion.
- Before-edit acceptance: `docs/production/local-20261026/p2b-local-acceptance.md`. Source: `scripts/postgres_disposable.py`; safety tests: `services/persistence/tests/test_postgres_disposable.py`; CI source now explicitly Ruff-checks the new script. No remote CI triggered. Generic PostgreSQL security guidance loaded from installed Supabase skill (least privilege/RLS); no Supabase service/project selected. Official PostgreSQL SSPI and Psycopg compatibility pages read; exact references in acceptance document.
- New harness always creates a unique marked direct child of temp root, refuses existing/unmarked/outside namespace, checks resolved data paths before controls, connects only explicit127.0.0.1/nondefault port/user/database, strips ambient PG connection variables and uses a nonexistent passfile. Loopback uses SSPI with exact current local OS principal map; local Unix-socket authentication rejects and network wildcard entries reject. No trust-host auth, passwords, new OS/IAM users, existing service/cluster changes or original data. bootstrap role is temporary cluster owner only, NOT a qualified runtime role.
- Failure dispositions: initial initdb rejected SSPI as a local-socket method; corrected local method to reject, retaining SSPI TCP. Sandbox pg_ctl failed restricted-token creation (no server started). Narrow expanded execution for this harness then started ONLY a new disposable cluster on61036, but captured Windows child output inherited by postmaster blocked communicate(); that attempt was NOT accepted. Verified its marker and explicitly stopped that exact cluster (pg_ctl exit0 and server log shutdown). Replaced pipe capture with unique regular-file capture/DEVNULL input while retaining command timeout. No global sandbox/security setting disabled.
- Independent review found output-overwrite and shutdown-evidence gaps. Fixed pre-start existing-output rejection plus exclusive output creation; fixed inner-finally persistence of stopped:false/cleanup_error on failed stop. Added sentinel preservation and failed-start-with-PID/failed-stop/timeout unit tests. Fresh unique test root retry **11/11 passed**; reviewer independently **11/11 passed**, no remaining actionable harness blocker. An earlier11-error test attempt omitted the parent of basetemp; corrected command creates a new parent first, no test/assertion weakening. Failure logs retained.
- Actual server qualification: command `.venv/Scripts/python.exe scripts/postgres_disposable.py --bin "C:/Program Files/PostgreSQL/18/bin" --output docs/production/local-20261026/p2b-qualification-files.json`, exit0. Fresh root `%TEMP%/classsync-pg-a2540b7e338a45bcb37564f195597e28`, port50193; SSPI positive SQL verified server18.6, exact data_directory/owner/port and1+1=2. Unmapped role authentication failed as expected (other connection failures cannot count as this denial). Harness finally stopped its own cluster, JSON stopped:true/server_state:stopped. Independent `pg_ctl -D <that exact root>/data status` exit3, "no server running" (`p2b-stopped-status.log`). No active PostgreSQL process is claimed from this work; preserve disposable data/logs, no recursive deletion.
- Additional self-review tightened project-only Firebase verifier: reject native Firebase Auth tenant identities rather than aliasing their UID to project-level identity; future explicit tenant-aware verifier/mapping required. Real offline SDK signed negative case added. Reviewer independently ran SDK suite **15/15**, no actionable concern. This is a safe denial of unsupported identity realm, no institutional identity policy invented. Default institutional membership remains unavailable.
- Final combined serial backend regression **217/217**,64.19s, exit0 (`p2a-p2b-regression.log`); one existing Starlette/httpx warning. Isolated root `%TEMP%/classsync-local-exit-5124765695cb4229adea8bb9df2be6c8`. Ruff including new harness exit0 (`p2b-final-ruff.log`); CI YAML parsed locally; diff check0. Current P2a frontend664/browser15 evidence above retained; no UI change in P2b, no new frontend/zoom/manual assistive-technology claim. P2a local exit remains PASS after the extra identity-realm regression.
- Read-only PyPI metadata qualification completed exit0 (`p2b-package-metadata.json`): psycopg/psycopg-binary3.3.6, SQLAlchemy2.1.6, Alembic1.20.1 advertise Python3.12-compatible distributions. Candidates only: none installed or added to manifests yet, no actual driver/SQLAlchemy/Alembic compatibility or vulnerability PASS claimed. Official Psycopg support documents include Windows/Python3.12/PostgreSQL18. Production provider/target selection remains unverified.
- All three original SQLite SHA256 hashes explicitly compared against entry baselines at05:02 and unchanged (`p2b-database-hashes-final.json`). No original-cluster/schema/data access, import, migration/cutover, real people data, Firebase/cloud changes, credentials/passwords, messages, commit/push/merge or deployment. No running tool/server handle remains from this checkpoint; no background continuation claim.
- Gate: **PASS for isolated server qualification/safety slice; P2b phase PARTIAL**. Schema, SQLAlchemy/Alembic migrations and rollback, least-privilege runtime, FORCE RLS/tenant and record integrity, pooling context reset, revisions, concurrent edits, backups/restore and authoritative repository are still required. No P3 entry justified yet.
- Next dependency-ready authorized action: qualify/pin/install the compatible local driver/migration candidates with dependency-graph/audit evidence, extend the disposable harness with a controlled exercise callback/runtime SSPI mapping, implement the P2b identity/membership relational schema and Alembic upgrade/downgrade in a new shared persistence boundary, then prove constraints/RLS/membership isolation/revocation/concurrency/pool cleanup on new disposable clusters. Keep production adapters unconfigured and original SQLite untouched. Continue full roadmap after P2b acceptance; do not redefine success as P2a or a server smoke test.

### 2026-10-26 05:14 Asia/Singapore — P2b driver/transaction slice PASS / phase PARTIAL

- Same HEAD39200a4f2ef3ec7557bc3c86127e674e260ca4fc; prior dirty work preserved. Added shared `packages/persistence` engine/transaction boundary and explicit service test requirements; no runtime service adoption or production fallback. Pinned Psycopg/binary3.3.6, SQLAlchemy2.1.6, Alembic1.20.1 plus Mako1.4.3/MarkupSafe3.0.4. Resolver dry-run/result retained; six third-party additions, no existing package replacements. Local editable install initially failed with no-build-isolation because setuptools absent; normal isolated build succeeded. `pip check` exit0.
- Audit explicitly verifies both local editable package paths/versions; all other packages included. New persistence requirements included in CI installation and audit manifest verification. Fresh exact scan **68 packages / zero findings**, exit0 (`p2b-driver-audit`), no advisory exclusion/risk waiver. Ruff all relevant scripts/services/packages passes; independent reviewer portable persistence tests24/24, own persistence+security audit tests36/36.
- Trusted-code callback now provisions a generated runtime SSPI role on a new marked cluster only: NOSUPERUSER/NOCREATEDB/NOCREATEROLE/NOREPLICATION/NOBYPASSRLS, public schema/database creation privileges revoked. Explicit numeric loopback, nondefault port, nonexistent passfile, SSPI requirement. Reviewer caught ambient PGHOSTADDR/service redirection in Python process (subprocess sanitization alone insufficient); fixed by rejecting ALL ambient PG* before driver connection, six negative tests and exact bootstrap driver directory/user/port/address check before first DDL. Reviewer rechecked and found no remaining actionable concern.
- First actual driver run failed address text comparison (`inet::text` includes network prefix). Failed exercise saved in its owned `qualification.json`, server stopped:true; no passing claim. Corrected to `host(inet_server_addr())`. Fresh `python -m scripts.postgres_driver_qualification ... --output .../p2b-driver-qualification-verified.json` exit0: PostgreSQL18.6 at50844, root `%TEMP%/classsync-pg-8ce55f47dfc945c296cf2333d5f9a6ee`; actual runtime privilege checks, commit visibility, exception rollback, pooled transaction-local context clearing on same backend, close rollback, schema/public/temp DDL denial and owner SET ROLE denial. Finally stopped:true; independent pg_ctl status exit3/no server (`p2b-driver-stopped.log`). No arbitrary connection URL accepted by qualification CLI.
- Complete backend serial regression **230/230**,64.28s, one existing Starlette warning (`p2b-driver-regression.log`). No frontend change or new browser/manual assistive-technology claim; previous rendered role evidence retained. `git diff --check` exit0. Three original SQLite hashes explicitly compared against baseline and unchanged (`p2b-driver-database-hashes.json`). No original PostgreSQL instance or original DB modification; no credentials/real records/cloud/Git/deployment actions.
- Gate: **PASS for shared driver/transaction/least-privilege exercise slice; P2b PARTIAL**. Alembic library installed but schema/migration execution is not yet verified; tenant/member RLS, mutation concurrency, backup/restore and production membership integration remain open. Full objective stays active/incomplete. Next authorized slice: identity relational migration and current-membership lookup with actual cross-tenant/UID/record-isolation and rollback tests, acceptance recorded before edits in p2b-local-acceptance.md.

### 2026-10-26 05:20 Asia/Singapore — P2b identity migration/isolation slice PASS / phase PARTIAL

- Added Alembic explicit-connection/caller-transaction runner, initial identity migration, current PostgreSQL membership lookup and transaction-local identity context in shared persistence package. Five FORCE-RLS tables: tenant/project binding, minimal person/student/faculty record keys, current membership. Composite tenant/person foreign keys prevent record aliasing; bounded identifiers, grants/state/revision checks reject malformed authority. These are synthetic test identity keys, no real institution/enrollment policy or production provisioning. Runtime is SELECT-only on tenant/membership; no grant mutation path. Lookup binds configured verifier project + server tenant + verified UID, uses fresh transaction every call, no cache/fallback. Services remain on existing adapters, default institutional membership unavailable until separately qualified P3 adoption.
- Real command `python -m scripts.postgres_identity_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output docs/production/local-20261026/p2b-identity-qualification.json` exit0. New marked root `%TEMP%/classsync-pg-4dcadaa94b1b47c48e0940f34e267b52`, port51280, PostgreSQL18.6/SSPI. Driver validates exact root/user/port before DDL. New generated nonlogin/non-superuser migration owner creates only local schema. Actual failed-transaction migration rollback, upgrade→seed→downgrade→upgrade, thirteen SQLSTATE-bound invalid membership cases, FORCE RLS for all five tables including actual non-superuser table owner, tenant/UID/project separation, SQL-bound injection-shaped tenant denial, linked record results, revocation/revision fresh read, runtime mutation denial, DB permission outage→typed unavailable, pool context reset all pass. Cleanup stopped:true; independent pg_ctl status exit3/no server (`p2b-identity-stopped.log`).
- Own boundary+safety+audit units **42/42**; independent reviewer persistence **30/30** and inspected relational/RLS/migration/provider code, no actionable remaining blocker. Reviewer did not execute server commands; actual-server evidence above is separate. Full serial backend **236/236**,67.59s, one existing Starlette warning (`p2b-identity-regression.log`). Ruff all touched source passes; pip check0. Package data declares migration files for future wheel packaging. No third-party version additions since fresh68/0 scan; no new scan falsely claimed. No frontend changes; prior real role/width/browser evidence retained, no manual screen-reader claim.
- Same HEAD and existing dirty work preserved. All writes target source/docs and newly marked disposable data. Original DBs never selected; last explicit hashes at05:13 match baselines (final comparison follows checkpoint). No institutional/Firebase/cloud/Git/deployment/credential actions. CI includes new source checks and portable tests; real PostgreSQL checks are explicit Windows local qualification, NOT claimed as a remote CI job.
- Gate: **PASS identity migration/read-isolation slice; P2b remains PARTIAL**. Concurrent revision mutations, backup/restore/checksum rehearsal, complete schema/adoption qualification and later identity lifecycle are not covered by this slice. Next authorized dependency-ready task: disposable PostgreSQL backup/restore rehearsal and catalog/data checksums, then optimistic revision/concurrency integrity. Full Goal remains active and incomplete; no P3 gate crossed.

### 2026-10-26 05:33 Asia/Singapore — P2b synthetic backup/restore slice PASS / phase PARTIAL

- New `scripts/postgres_restore_qualification.py`, restore-boundary tests and package README. Harness exposes only its checked-root/sanitized-env/timeout/regular-file runner for whitelisted PostgreSQL tools; newly generated archive stays inside owned root. Restore uses CREATE DATABASE with a strictly generated namespace, no IF NOT EXISTS/reuse, same verified disposable cluster. No original database/cluster selected, no deletion/overwrite of existing files or databases. Exact working tree captured in `p2b-working-tree-final.txt`; HEAD still39200a4f2ef3ec7557bc3c86127e674e260ca4fc, prior dirty work retained.
- Failed attempts preserved and NOT counted as PASS: dropped empty public schema made standard archive restore fail (corrected to retain template public and require absent identity schema); then fingerprint mismatch diagnostic proved only source explicit-owner ACL versus restored NULL/default-owner ACL on three tables. Complete default-expanded effective ACL comparison preserves grantor, grantee/PUBLIC, privilege and grant-option categories, separate from ownership/RLS/policies and information-schema grants. Official PostgreSQL ACL function docs read; independent reviewer confirmed normalization preserves checks. Added actual extra INSERT-grant negative check in restored synthetic DB; fingerprint must differ, finally revoke and require baseline equality. No privilege mismatch waived; source/restored definitions captured on diagnostic failure. All failed roots' qualification.json records server_state:stopped.
- Final actual command `python -m scripts.postgres_restore_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output docs/production/local-20261026/p2b-restore-qualification-final.json`, exit0. New root `%TEMP%/classsync-pg-891ad058aeca446a9a0cef7b4242618d`, port54462, PostgreSQL18.6/SSPI; reran all identity/migration/isolation tests, generated custom archive (SHA25631abf46393f8337bd572cd5a84e72f40bce7beb42fd31b5b846dfc26fde28c9d), restored only to generated `classsync_restore_2e49d09ba2064ff291f5f657cbfa6eec`. Ordered data and ten catalog categories match exactly: migration revision, schema owner/ACL, columns, constraints, table owners/RLS flags, indexes, table ACL, policies and effective grants. Both data hashes341e6c92cb34fa2bf826fc49085bfeb51ef3b4b8de75163ba8c4d62d379b1336; complete evidence JSON contains catalog hashes/row counts. Restored no-context runtime gets zero rows; linked membership stays revoked/revision2; extra privilege drift detected and reversed; source fingerprint unchanged.
- Cleanup stopped:true; final independent pg_ctl status exit3/no server (`p2b-restore-stopped-final.log`). Installed unrelated PostgreSQL service processes were neither controlled nor modified; this statement covers owned test clusters only. Archive/data/logs retained inside temp roots; no recursive deletion. No running tool/server handle remains from this checkpoint.
- Own portable persistence+security tests **49/49**; independent reviewer persistence **37/37**, reviewed target isolation, failure propagation, canonical ACL comparison and drift-check finally behavior, no actionable remaining finding. Full serial backend **243/243**,61.62s, one existing Starlette warning (`p2b-restore-regression.log`). Final Ruff0 and diff-check0. No web source changes, no new browser/manual screen-reader claim; previous rendered role evidence retained. No solver constraints/timeouts changed; no concurrent solver run.
- Actual persistence wheel build and file inspection passed (`p2b-wheel-verified.log`, `p2b-wheel-contents.json`), including migration env/revision/provider/schema modules. First wheel attempt failed sandbox PyPI socket access; narrow approved pip execution succeeded, no global safeguard change. Runtime versions retained (`p2b-runtime-versions.json`): Psycopg3.3.6/libpq18.4, SQLAlchemy2.1.6, Alembic1.20.1. Installed PG server/CLI18.6. Latest exact Python audit **68/0** remains current for unchanged third-party graph; Python scan is not a full embedded-library/OS-image scan.18.6 release notes reviewed for libpq differences; production native-library/transport qualification remains open, no production approval inferred.
- Final05:30 original SQLite hash comparison explicitly asserts all three equal baseline and writes matchesBaseline:true (`p2b-restore-database-hashes-final.json`). No original-data/schema modifications, real identities/records, credentials/passwords, Firebase/IAM/cloud, spending, messaging, commit/push/merge or deployment.
- Gate: **PASS synthetic identity backup/restore slice; P2b phase PARTIAL; production NO-GO.** Full P2–P8 Goal remains ACTIVE/incomplete. No P3 entry yet. Next source/test acceptance: optimistic membership revision guard and deterministic two-connection stale-update/rollback tests under least privilege, plus remaining schema/index/phase qualification. Do not confuse a current read or restore with concurrency-safe authority mutation. Follow with P3 integration only after the complete P2b exit gate; original SQLite cutover remains separately unauthorized. This is a resumable checkpoint, not full mission completion or a background-work claim.

### 2026-10-26 05:39 Asia/Singapore — P2b membership revision/concurrency slice PASS / phase PARTIAL

- Added migration0002 database BEFORE UPDATE guard: immutable tenant/UID keys, revision increments exactly once independently of application helper. Function uses fixed pg_catalog search_path and PUBLIC execution revoked; no SECURITY DEFINER privilege escalation. New transaction-level `membership_changes.change_membership_state` validates explicit tenant/UID/strict positive expected revision/known state/caller transaction, binds parameters and returns typed conflict for absent/invisible/stale rows. It does not authorize/provision grants; ordinary runtime stays SELECT-only, no service endpoint or real authority enabled. Downgrade removes only this owned trigger/function before earlier schema rollback.
- New `scripts/postgres_revision_qualification.py` first runs full updated identity and backup/restore rehearsal, then actual competing connections. New marked cluster `%TEMP%/classsync-pg-d7d8fb02765b40dda89e1edead814800`, PostgreSQL18.6/SSPI at54540; command `python -m scripts.postgres_revision_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output docs/production/local-20261026/p2b-revision-qualification.json`, exit0. Both writers scoped as nonlogin/non-superuser table owner under FORCE RLS. Monitor observes second backend blocked on first backend's exact row lock before first commit; first revision2→3/inactive commits, second expected2 returns stale conflict. Later revision3→4 candidate rollback leaves inactive/revision3. Other existing tenant row with its correct revision1 and existing target with unrelated UID context are denied; other tenant stays active/revision1. Four direct unversioned/skip-revision/UID-key/tenant-key UPDATE mutations return exact23514.
- Updated restore checks include function definitions/security/config/ACL and trigger definitions/enabled state, now13 catalog categories. Both revisions upgrade/downgrade and restore pass, catalog/data fingerprints match, restored direct unversioned UPDATE rejected23514, privilege-drift negative remains. Archive SHA2564fef618e6e30409d2b5b739d63eeeecf5e11209b9d43ee62eb9117abe09034a8; source unchanged during restore. Finally stopped:true; independent pg_ctl status exit3/no server (`p2b-revision-stopped.log`). No original service processes controlled.
- Own portable persistence+security units **57/57**; independent reviewer persistence **45/45**, inspected database guard/helper/actual lock observation/rollback/record scope and restore definitions, no actionable finding. Full backend serial **251/251**,64.18s, one existing Starlette warning (`p2b-revision-regression.log`). Ruff0 after wrapping one101-character line; no semantic change after actual server acceptance. Wheel rebuilt/verified with both migrations and state helper (`p2b-revision-wheel-contents.json`), SHA256a135362c238d8fb443b5d4615fc502c34582148b0c873ffd9d7891142e8c184b. Third-party graph unchanged; latest68/0 scan remains dated current graph evidence, not new binary assurance. No frontend/UI changes or new browser claim.
- Exact05:39 original SQLite hashes match all three baseline values (`p2b-revision-database-hashes.json`); git diff check0, HEAD unchanged, user/pre-existing dirty work preserved. Source inventory now includes packages/persistence, five PG qualification/harness scripts, persistence tests/requirements, explicit audit provenance/CI integration and acceptance/evidence docs. No original data import/migration, real people, credentials, Firebase/cloud, messages, commits/push/merge or deployment. No running tool or owned server handle remains at this checkpoint.
- Reconciled detailed bounded P2b specification in `docs/production/p1-cumulative-review-and-p2-readiness.md` rather than prematurely declaring phase PASS. Gap matrix: `docs/production/local-20261026/p2b-exit-gap-review.md`. **P2b remains PARTIAL** because atomic grant/revocation/audit revision is absent; actual PG second-UID/Administrator/inactive/missing-database negatives and final phase-exit web/artifact/browser gates are still needed. Next source acceptance: synthetic-only membership audit/grant transaction integrity (immutable history, actor provenance and rollback/conflict), plus these explicit fixture/connection failure gaps; preserve runtime SELECT-only until separately qualified P3 adoption. No institution provisioning policy is invented. Full Goal ACTIVE/incomplete, production NO-GO; this is a resumable continuation checkpoint and no background operation is claimed.

### 2026-10-26 05:49 Asia/Singapore — P2b atomic membership audit slice PASS / exit regressions pending

- Before-edit sixth acceptance in p2b-local-acceptance.md. Added migration0003 membership INSERT/UPDATE audit: tenant/subject/revision key and FK, old/new snapshots, explicit caller actor UID plus DB session identity and transaction timestamp. Missing actor or audit failure aborts the membership operation. New history table uses FORCE RLS; fixed-search-path/qualified-object SECURITY DEFINER append function is owned by nonlogin migration owner, no PUBLIC execution. DML UPDATE/DELETE/TRUNCATE guards deny audit mutation; privileged DDL/owner control/downgrade remain outside tamper-proof claims. No invented historical-actor backfill or institutional retention/provisioning policy.
- Updated state helper and added revision-safe grant helper requiring explicit VerifiedPrincipal actor (caller provenance, not identity verification or authorization). New nonowner/non-superuser/nonlogin disposable maintenance role has membership SELECT/UPDATE only; cannot directly insert/edit/remove/truncate audit. Ordinary service runtime remains SELECT-only on tenant/membership, cannot execute append function or read private audit. No new service endpoint, actor deserialization from browser or production wiring. Fixtures supply clearly synthetic actors only.
- Actual `python -m scripts.postgres_audit_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output docs/production/local-20261026/p2b-audit-qualification.json`, exit0. New marked root `%TEMP%/classsync-pg-223dc266fc28458da17d4d8449a1ebbc`, PostgreSQL18.6/SSPI at55034. Full three-revision upgrade/downgrade/transaction rollback and six-table FORCE RLS pass; actual second UID/Administrator membership accepted alongside Student/Teacher fixtures. Updated restore includes audit rows/FKs/functions/ACL/triggers, matching data and13 catalog categories and restored audit immutability; archive SHA256da2732006a0d50770104ce4b1396e61631003438093fb2c1d5684fe191d29b4b.
- Real exact row-lock concurrency rerun succeeds with audit revisions1–3 only (loser and candidate rollback add none). Nonowner maintenance grant removal/restoration produce revisions4/5 and exact old/new roles+actor/session provenance; stale grant fails. Application rollback adds no event. Injected audit CHECK failure23514 after membership UPDATE leaves BOTH current membership and history unchanged; constraint removed in finally on this synthetic table only. Missing actor42501 leaves no mutation; audited revoke yields exactly revision6/state revoked. Owner/superuser DML audit tampering and maintenance direct-write attempts reject42501, history unchanged. Actor GUC clears across pooled transactions.
- Actual inactive membership denial, missing generated database connection→OperationalError→typed unavailable, and live owned runtime-backend termination→typed unavailable tested. Fault injection obtains the actual connection PID, verifies generated runtime role/database in the already verified isolated cluster before pg_terminate_backend; no original/service process targeted. Listener removed in finally; reconnect reads current revoked/revision6, no cache/sample fallback. Runtime/member grant policy itself is still caller authorization and not institution-approved provisioning.
- Own portable persistence/security tests **66/66**; independent reviewer persistence **54/54**, inspected SECURITY DEFINER/RLS/provenance, audit rollback/tamper and termination scope, no actionable finding. Full serial backend **260/260**,64.90s, one existing Starlette warning (`p2b-audit-regression.log`). Ruff0 after wrapping3 long lines, no semantics change. All three original SQLite SHA256 values match05:39 and original baselines (`p2b-audit-database-hashes.json`); same HEAD/pre-existing dirty work preserved. Finally stopped:true, independent pg_ctl status exit3/no server (`p2b-audit-stopped.log`). No running owned server/tool handle from those checks.
- Gate: **PASS atomic membership audit and remaining actual PG failure/role cases; P2b phase PARTIAL until complete exit regressions pass.** Next: fresh root lint/typecheck/frontend/security/build/presentation/artifact checks and unchanged real browser role journeys, fresh dependency scans, wheel includes migration0003, independent phase review and final original-data preservation. No P3 entry yet; production NO-GO and full Goal ACTIVE/incomplete. No original DB modifications, real identities/records, credentials, cloud/Firebase, Git mutations or deployment.

### 2026-10-26 10:49 Asia/Singapore — P2b exit web timeout investigated / gate unresolved

- Re-polled original verified live handle62369 after continuation; terminal exit1/ETIMEDOUT from unchanged300s root test-web harness, no restart based on observation timeout. `p2b-exit-web.log` has650 passing assertion lines across32 files, no assertion-failure or complete summary; file completed05:56. Do NOT combine partial output with another run to claim fullPASS. System power metadata read did not establish a matching suspend cause; no unsupported sleep explanation adopted.
- Four unreached files independently **14/14**,24.71s (`p2b-exit-web-unseen.log`), dominated by environment10.46s/import8.46s/setup2.97s versus bodies0.286s. Prior full268.93s similarly dominated by environment/import/setup. Repair acceptance recorded before edits: eight inspected pure logic/config/serialization suites use Vitest's documented Node control-comment environment; rendered/storage/API suites remainjsdom. Shared setup conditionally loads DOM matchers/React cleanup only when window exists, keeps manual cleanup and scrolling stub forDOM. No assertion, test file, isolation, worker pool or300s bound changed; no skip/retry or ignored failure. Full root command on new handle70185 is currently running, not yet passed. Independent reviewer inspected source/environment scope/cleanup and found no actionable issue, did not compete with test execution.
- Fresh npm audit0 findings and exact Python68/0 findings (`p2b-exit-npm-audit.json`, `p2b-exit-python-audit`) exit0. Initial fresh root lint/typecheck exit0 before setup repair; rerun after current repair is still required. Browser plugin/skill absent in current inventory; following frontend-testing skill, regular bundled Playwright/Chrome fallback prepared. No new browser/native zoom claim until those checks actually run. Read-only/public builds not deployed.
- Added one adversarial real-PG test assertion: valid actor plus absent target context must fail the SECURITY DEFINER append's FORCE RLS, distinct from missing-actor failure; source reviewed, fresh actual execution pending after frontend run. P2b exit remains PARTIAL/productionNO-GO. Goal active; next safe work is complete this same web run, execute targeted real-PG addition, then remaining artifact/render/wheel/preservation gates. No original databases, real identities, credentials, cloud/Firebase or Git state modified.

### 2026-10-26 11:01 Asia/Singapore — complete bounded local P2b exit PASS

- Scope reconciled to detailed bounded P2b in `docs/production/p1-cumulative-review-and-p2-readiness.md`, roadmap and quality gates; updated `p2b-exit-gap-review.md` and TRACEABILITY, preserving failed/interim evidence. Independent security reviewer found no additional local implementation gap; final outstanding artifact/render/preservation conditions below all passed. This is local synthetic tenant/membership foundation acceptance, not P3 adoption, institutional provisioning, hosted provider qualification, native-image production security or production release. Full P2–P8 Goal remains ACTIVE/incomplete.
- Final actual PG command `python -m scripts.postgres_audit_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output docs/production/local-20261026/p2b-audit-qualification-final.json`, exit0. New root `%TEMP%/classsync-pg-d4c9e65729ff49d2a152c14352881fe5`, port56376; root/port/role verified before writes, SSPI, non-superuser owner/runtime/maintenance privilege separation. Three-revision migration rollback/downgrade/upgrade, six FORCE-RLS tables, thirteen invalid constraints, two UIDs/all3 roles, record/project/tenant isolation, inactive/revoked denial, actual stale competing row lock, state/grant/audit revisions, audit failure rollback/tamper denial, missing DB/terminated owned connection unavailable and fresh recovery all pass. New adversarial valid-actor/no-target context case specifically fails definer audit RLS42501 (not missing-actor denial). Normal runtime remains SELECT-only, no provisioning route/policy invented. Single-row lock proof only; future multi-row workflows need their own ordering tests.
- Final restore source/restored synthetic data hash e7f1e01a414a7ed5117a0d98f592e7dfee5720896dee06b09dffd517d0d327c3; archive SHA256b2b69ac10749416a6a4f6b6e796579f1de757624583f280e043553b5640063c6. Data and13 catalog categories match, including history/FKs/functions/ACL/triggers; actual privilege-drift detection and restored revision/history guards pass. Original source unchanged during restore (later concurrency/role mutations are intentional disposable fixture changes). Finally stopped:true; `p2b-exit-pg-stopped.log` independently pg_ctl exit3/no server. No original installed PostgreSQL process controlled, no recursive deletion; disposable evidence retained.
- Backend full serial **260/260**,64.90s (`p2b-audit-regression.log`), portable persistence/security66/66 and independent persistence54/54. No solver hard-constraint/time-budget changes, no overlapping solver workload. One existing Starlette deprecation warning remains. Current full root `npm run test:web` **664/664 in36 files**,195.30s (`p2b-exit-web-node-logic.log`), exit0. Previous failed300s run kept (`p2b-exit-web.log`) and separate14-file coverage not substituted. Repair only eight pure suites' Node control comments and DOM-conditional matcher/React cleanup setup; same assertions, discovery, isolation, pool/worker and300s bound. Independent review confirmed pure scope and retained DOM cleanup. Fresh root lint/typecheck after repair exit0 (`p2b-exit-lint-final.log`, `p2b-exit-typecheck-final.log`), Ruff0, `npm run test:security`13/13.
- Root `npm run build` and `npm run build:presentation` exit0; `npm run test:artifacts` **4/4 groups**,73.96s, includes actual unsafe-build rejection and ordinary/presentation/legacy metadata, SPA refresh, missing static/API correct404 tests. Existing >500kB main-chunk warnings remain disclosed for later performance work; no threshold relaxed. Presentation release metadata SHA matches HEAD39200a4…, appMode:presentation, read-only-presentation, sampleVersion:classsync-presentation-v1, uncommittedChanges:true. Dirty candidate correctly fails clean-release verification; no clean-production/release claim or hosted check/deployment.
- Fresh real Playwright/Chrome **15/15** role-entry/dashboard/deep-refresh journeys ×360/390/768/1024/1440, zero console/runtime/API requests/overflow (`p2b-exit-browser.json`, `.log`). Browser plugin absent, regular bundled Playwright fallback recorded per frontend-testing skill. Actual Student390/Admin1440 before/after screenshots inspected and independently reviewed; each pair byte-identical, no changed visual/readability/sidebar/mobile regression. Screenshot paths use `p2b-exit-` prefix in session visualization root. Native Chrome200% on ordinary unavailable screen uses isolated QA profile/extension tabs.setZoom/getZoom=2, DPR1→2, innerWidth1424→712, CSSzoom1/visualScale1; keyboard Return-to-access focus and no overflow (`p2b-exit-native.log`, visualization `p2b-exit-native/native-zoom.json`, screenshot viewed). Scope is checked public/unavailable states; full institutional journeys/manual screen-reader testing NOT claimed.
- Fresh `npm ls --all` exit0; npm audit0 (`p2b-exit-npm-audit.json`), pinned pip-audit2.10.1 exact **68 packages/0 findings** (`p2b-exit-python-audit`), pip check0. No dependency version change or advisory exclusion. Native embedded-library/OS-image/production transport scan remains separate, as documented. Wheel rebuilt (`p2b-audit-wheel-contents.json`): all9 Python source files byte-equal to current workspace, including0001/0002/0003; wheel SHA256041d8927090d5113db7d7414a5a7ff5c902a24765765f26b5e5699ce23a8a5f5. This is packaging verification, not a release.
- Final10:59 explicit comparison asserts all three original SQLite hashes equal recorded baselines, with matchesBaseline:true (`p2b-exit-original-preservation.json`); working tree captured (`p2b-exit-working-tree.txt`), HEAD unchanged, user/pre-existing changes preserved; diff check0. Source changes: shared persistence package/three migrations, six PG qualification/harness scripts, persistence requirements/tests/audit provenance/CI checks, eight pure web test annotations+DOM-aware setup, evidence/docs. No original DB import/migration/cutover, real people/accounts/data, credentials, Firebase/IAM/cloud/spending, messages, commit/push/merge/deployment. All executed tool/owned-server/browser handles terminal; no background run claimed.
- **Gate: PASS — complete bounded LOCAL P2b.** Production NO-GO. Next dependency-ready authorized outcome: P3a synthetic/emulator verified identity→current PostgreSQL membership→HTTP authorization composition and denial lifecycle. Keep default institutional service path unavailable until its own explicit configuration/gates; do not enable real institutions or invent provisioning policy. Actual academic/scheduling PostgreSQL adapter adoption is P3b and follows P3a acceptance; original SQLite remains current local storage until separately authorized cutover. No overall-goal completion or scope reduction.

## 26 October 2026 11:15 +08 - P3a first request-composition slice; phase PARTIAL

HEAD/base39200a4f2ef3ec7557bc3c86127e674e260ca4fc unchanged; existing dirty work preserved. Acceptance written before edits in `docs/production/local-20261026/p3a-local-acceptance.md`. Added `scripts/postgres_identity_http_qualification.py`; extracted existing offline SDK fixture to `services/testing/offline_firebase.py`; added forced-setup-failure cleanup regression; CI Ruff includes new script. No runtime provider/default or UI source changed.

Actual command `.venv/Scripts/python.exe -m scripts.postgres_identity_http_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output docs/production/local-20261026/p3a-identity-http-reviewed.json` exit0: new marked SSPI PostgreSQL18.6 root classsync-pg-90d979c54880473ba78a5709e9da8866, port57071, stoppedtrue. Existing Gateway ASGI TestClient plus actual SDK RSA validation (in-memory synthetic keys, certificate/account transport stubbed) plus real nonowner current-PG reads proved role/record/servertenant binding, ambiguous/unauthorized grants, invalid identity before DB, separate Administrator UID, same-token grant withdrawal/inactive/revoked/revision, real permissionoutage redacted503, missingtenant and wrongproject. These are ASGI requests, not browser/network/emulator or real institutional identity acceptance.

Independent security reviewer found two false-evidence/cleanup gaps: wrongproject checked afterrevocation and app cleanup after fallible setup. Both fixed: active audited revision7 succeeds before/after wrongprovider; helper cleanup immediately follows app initialization, forcedRSA setupfailure restores exact registry. Reviewer re-reviewed and reported no remaining actionable slicefinding. Original15 crypto assertions preserved;16/16 targetedtests pass (4.06s), Ruff services/packages/newscript0. Existing Starlette/httpx deprecation remains.

First full backend regression `p3a-backend-regression.log`:259passed/1failed81.04s; multi-program CP-SAT case returnedUNKNOWN at8s configuredbudget (incumbent phase4.8s), no acceptedsolution or constraint/test relaxation. Other qualification work overlapped part of run; isolated serial full rerun now pending in p3a-backend-serial.log. P3a slice must not be accepted with unresolved regression.

Original three SQLite files SHA256 match recordedbaselines in p3a-original-preservation.json. No sourceDB migration/liveidentity/credential/cloud/Git/deployment/messages. Frontend unaffected; prior P2b fresh rendered15/native200% evidence remains last UI verification, no P3 browser/emulatorclaim. firebase command unavailable and project firebase-tools dependency absent; emulator setup still required under local-only scope. Next: resolve fullserialregression, record disposition, qualify actual localemulator lifecycle and explicitserviceintegration before P3aPASS. P2-P8 goal remains active/incomplete; production NO-GO.

Documentation incident: a Python default-codepage write failed on the traceability arrow character and truncated TRACEABILITY.md. Reconstructed the index from preserved STATUS/evidence, explicitly labelled; prior wording not claimed verbatim recovered. No application/DB loss. Subsequent document writes use explicit UTF-8.

11:18 +08 disposition: isolated complete backend rerun passed261/261 in68.65s (p3a-backend-serial.log), including new SDK failurecleanup test. Original UNKNOWN regression retained, no solver/time/constraint changes. Targeted offlineSDK+PG ASGI composition slice accepted after independent review; overallP3a remains PARTIAL. Next actual local AuthEmulator lifecycle, retaining production refusal of emulator tokens. No frontendsource changes; P2b rendered evidence remains applicable unchanged UI, not a P3 institutionaljourney claim.

## 26 October 2026 11:40 +08 - P3a actual local Auth Emulator slice PASS; overall P3a PARTIAL

Acceptance before edits: p3a-emulator-acceptance.md. Source: classync_contracts/request_authorization.py minimal unsigned-token parser allowance exclusively under exact test runtime + true test flag + injected EMULATOR trust; ordinary/FIREBASE/TEST paths remain signed-only. Added test-only services/testing/emulator_firebase.py, gateway test_emulator_support and parser cases, scripts/auth_emulator_qualification.cjs and postgres_emulator_qualification.py, portable proxy environment test included root test:security, CI Ruff source list. No runtime emulator provider/config auto-switch shipped.

Red parser24-case matrix:23pass/1fail (sole authorized emulator case), green auth+crypto89. Reviewer requested malformed/oversize assertions; included85-case helper/boundary suite. Reviewer found SDK emulator mode skips Google expiry validation: ten time/shape tests proved red then fixed explicit strictinteger exp/iat/auth_time, expiry/future/ordering checks and malformed firebase realm invalid;95 targetedgreen. Independent final source/security review found no remaining actionable slice issue after corrections below.

Official Firebase CLI15.34.1 metadata engines compatible Node22.23.1. Initial isolated tools installation failed TLS ECONNRESET (log retained); retryinstalled633 packages in new TEMP tools root (p3a-emulator-tool-retry-root.txt), ignore-scripts/no app dependency changes. Initial tools audit5moderate across2 advisories retained in p3a-emulator-tool-audit.json. Reviewer found upstream CLI itself declares compatible overrides ignored in consumer dependencies: mirrored exact OTel2.8.0 and gaxios uuid11.1.1 in disposable root. Fresh auditfixed0 and npm ls all0; no waiver/advisory suppression. Programmatic official pinned createApp Auth server only, singleproject ERROR, demoUUID project, random127.0.0.1 port, no CLIlogin/import/export/UI/blockingfunctions. Isolated configstore and scrubbed Google/Firebase/proxy env; NO_PROXY=*; parentNode nonloopback sockets denied. Sentinel environment test proves removal without changing caller env. No passwords/serviceaccount keys created/read; anonymous demo identities only.

Command `node scripts/auth_emulator_qualification.cjs --tools-root <recorded disposable root> --postgres-bin "C:/Program Files/PostgreSQL/18/bin" --output docs/production/local-20261026/p3a-auth-emulator-reviewed.json` exit0. Actual Auth endpoint127.0.0.1:59511, demo-classsync-ece11de7b8b5, owned authroot0149077e7f4b44fe842a677b2de42d05; new PG18.6 SSPI root13761b6d556c4ad5a174ad7610b427cd port59546. Actual anonymous signup had no implicitmembership403, explicit disposablePG Student binding200, actualrefreshed forgedadmin/tenant claims could not grantAdministrator403 and currentStudent200; prod/testoptout unsigned401; institutionalFirebase verifier503 underemulatorenv; actualSDKdisabled401/re-enable200/tokenrevoke401; same unsignedtoken PG revoke403/reactivate200. Reviewer requested realoutage: freshsecond anonymousactive mappedUID200, stdoutcontrol closes onlyownNodeAuthserver and acknowledges, next actualSDKaccountlookupHTTP503 identity_unavailable nofallback. Both servers stopped, deniedOutbound0. Independent socket probes confirm both portsclosed; SQLite all3 hashes baselineequal in p3a-emulator-preservation.json. No original DB imports/schema/migration, real identity/cloud/data/Firebase settings/Git/deploy/messages.

Final full backend307/307 in60.64s (p3a-emulator-final-backend.log), root security14/14, Ruff services/packages/newPGscripts0, Node syntax0, diffcheck0. Existing Starlette/httpx deprecation remains. Earlier UNKNOWN failure and successfulserial261 disposition retained; no solver changes or limits/constraints relaxed. Frontend UI unchanged from completed P2b rendered15/native200% checks; no new browser/fullinstitutional journey or manualscreenreader acceptance claim.

Gate: this bounded actualemulator+PG+Gateway-ASGI lifecycle slice PASS, fullP3a PARTIAL. Gateway/Academic/Scheduling default production membership still unconfigured. Next: explicit Gateway-owned configured membership provider/pool lifecycle qualified with offlineSDK realPG and safe shutdown; keep legacy academic/scheduling institutional paths unavailable until tenant-qualified P3b adapter work. Authenticated frontend browserlifecycle still unverified. Goal ACTIVE/incomplete; production NO-GO.

## 26 October 2026 18:42 +08 - P3a configured Gateway identity-provider lifecycle slice PASS

Re-read AGENTS, GOALS/ROADMAP/QUALITY_GATES/APPROVALS/STATUS/TRACEABILITY, actual Git/HEAD/current source at turn entry. Earlier objective135/P2apartial counts were historical; authoritative local evidence already established P2a/P2bPASS and P3apartial. Prior turn classified progress (actual source/emulator qualification), not a wait/no-progress turn. HEAD/base39200a4f2ef3ec7557bc3c86127e674e260ca4fc unchanged; preexisting work preserved.

Acceptance written before edits: p3a-provider-acceptance.md. New services/gateway/app/authorization.py and26 portable lifecycle/config cases; main.py optional SecretStr identity URL and explicit transport settings/lifespan ownership; Gateway requirement adds existing pinned local persistence; shared postgres_engine accepts optional pool bounds with prior defaults unchanged for other callers. Added actual scripts/postgres_provider_qualification.py, CI Ruff list and configuration/persistence docs. No migration/provisioning on service startup. No direct membership adapter injection in configured qualification: actual offline SDK verifier plus source-created current PG lookup/engine. Gateway defaults unconfigured when URL absent; Academic/Scheduling providers unchanged/unconfigured, legacy tenant-unqualified repositories not adopted.

Config tests: explicit driver/host/port/user/database/project/servertenant required, no query redirection or ambient PG settings, no implicit passwordfile; generic invalid-config message and SecretStr URL. Default source transport verify-full/system roots/SCRAM, actual production provider/TLS unqualified. loopback-sspi-test restricted exact test runtime,127.0.0.1 high nondefault port/noURLpassword; all production/staging/development rejects. Conflicting configured provider fails beforeengine; unconfigured explicit tests preserved; source constructor/body/shutdown failure cleans owned pool. Red import failure retained before implementation (p3a-provider-red.log); final26 config/lifecycle plus13 persistence-boundary tests39/39.

Independent review identified unbounded query/lock/pool waits. Added trusted connect5s/statement5000ms/lock1500ms and checkout3s; explicit Gateway five physical slots/no overflow. Shared engine callers retain previous30s/5+10 defaults. First exhaustion setup tried15slots against harness max_connections10 (3reserved), failed before checkout exhaustion; preserved p3a-provider-bounds-initial-failure.json (ownedstoppedtrue). No resource/safety limit relaxed. Initial permission review timed out before execution; one explicitly permitted retry ran, no broad escalation. Subsequent qualification uses actual five heldslots and source cap, verifies real queue timeout503 then release200.

Final actual command `.venv/Scripts/python.exe -m scripts.postgres_provider_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output docs/production/local-20261026/p3a-provider-exit-qualification.json` exit0: new marked PG18.6/SSPI root89a2b3f0aba849ee848e6b196e63e5b2 port61165, stoppedtrue. Source lifespan installs current PG lookup with actual runtime non-superuser/no-BYPASSRLS roles; offline actual SDK signedUID binds student-a. Same token observes revoked4/active5; actual permission503/recovery, server SHOW confirms5s/1500ms deadlines; held ACCESS EXCLUSIVE lock produces actual SQLSTATE55P03 and generic503 under8s, release200; five actual heldpoolconnections force3s503, release200. Normal and exceptional caller exits plus restart leave zero checked-in/out or server runtime sessions and no owned adapters; restart reads committed revision5 using newpool. Independent final source/security review no remaining actionable finding, subject to finalgates below.

Fresh final full backend333/333 in72.28s (p3a-provider-backend-regression.log), scheduling serial/no overlapping solver; no solver/constraint/time changes. Root security14/14, lint/typecheck0, Ruff services/packages/newscript0, diffcheck0; pipcheck0 and pinned pip-audit2.10.1 exact68versions/0 findings including all5 service/persistence manifests. No dependency upgrades, skips/advisory exclusions. Initial no-isolation wheel build failed missing setuptools.build_meta in appenv; retained log, then isolated localwheel build0, all9 Python files byteequal current source incl migrations; wheelSHA444c1c16bae531da946faa5470ce93da7e7b87bec167898d69c31391bd9e5070 (p3a-provider-wheel-contents.json). App dependency graph unchanged. Existing Starlette/httpx deprecation remains.

Fresh exact original academic/scheduling/backup SQLite SHA256 equals all baselines; independent ownedport61165 socketclosed (p3a-provider-preservation.json). No original reads beyond hashes, schema/data writes/imports/cutover, realinstitutionrecords, credentials, Firebase/cloud/IAM/spending, messages, Gitcommit/push/merge/deploy. No UI source change; prior P2b rendered evidence remains last checked UI, not authenticatedP3 browser qualification. All tool/ownedserver handles terminal; no backgroundprocess claim.

Gate: bounded configured Gateway provider lifecycle PASS. OverallP3a PARTIAL; fullgoal ACTIVE/incomplete, production NO-GO. Next dependency-ready authorized slice: provider-agnostic frontend Firebase identity/session observation -> current /auth/me membership/role selection with explicit denied/unavailable/signout/refresh behavior, preserving preview boundaries and Soft Rouge; use emulator-only browser journeys without choosing an institutional sign-in/provisioning policy or enabling live credentials. Do not start P3b service adoption until full applicable local P3a gates pass.

### 2026-10-26 23:23 Asia/Singapore — P3a frontend lifecycle implementation, exit gates underway

- Current/base HEAD main `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`; pre-existing dirty tree preserved, no Git writes. Owner local P2-P8 authority unchanged. Acceptance written first in `docs/production/local-20261026/p3a-web-session-acceptance.md`.
- Implemented institutional-only, provider-agnostic Firebase ID-token observation and current Gateway `/auth/me` membership with abort/generation/UID/role guards, timeouts, offline clearing, sign-out races/failure containment, cache clearing, StrictMode/unmount cleanup. Role candidates are server-verified, never client grants. No institutional sign-in/provisioning method chosen; no credentials submitted; generic institutional academic/scheduling APIs remain unavailable. No synthetic dashboard fallback. New `apps/web/src/auth/university-session*`, provider/panel and four test files; AuthPage/RouteGuard/app-mode text/scoped entrance styles integrate existing Soft Rouge components.
- Targeted frontend45/45 in4files12.65s; full `npm run test:web`709/709 in40files215.18s, exit0. Lint/typecheck0; ordinary build0 (existing >500kB warning); presentation build0; artifact tests4/4; security15/15; full configured Ruff0. Evidence logs prefixed `p3a-web-session-` under dated directory. New Python exclusive evidence sentinel test1/1. Full backend exit regression pending (previous provider333/333 remains historical).
- Actual official Auth Emulator -> SDK browser -> Gateway-owned current PostgreSQL provider -> synthetic membership lifecycle passed (`p3a-web-session-browser-retry.json`), all three roles, forbidden role, current grant withdrawal/revocation, actual DB permission outage/recovery, offline/reconnect, identity server stop, signout and deep-link unavailable. Browser errors0/unexpectedconsole0/externalrequests0. Five widths360/390/768/1024/1440,15screenshots. No real identities, no original DB connection.
- Independent security/UI review reproduced and fixed focused role-control removal during checking (stable aria-disabled controls) and HTTPS backslash origin ambiguity (reject before SDK/network). Security reviewer then identified fixture output overwrite race and unvalidated browser control/proxy config: both fixed with exclusive x writes plus sentinel test, marked temp root/demo/exact loopback high-port/nonce validator before mutations/network, portable negative validator checks. Reviewer confirmed closure, no remaining actionable finding. CI now includes new fixture Ruff target/security validator tests.
- Native200% actual Chrome tabs.setZoom/getZoom2 confirmed DPR1->2, viewport1424->712, CSSzoom1/visualscale1, keyboard role-denial focus and nooverflow. First run passed native checks then failed separate390px screenshot because origin-wide zoom remained applied; fixture now resets actual zoom before mobile checks. Corrected run `p3a-web-session-browser-zoom-reviewed.json` exit0, all owned services stopped. Visual inspection found Playwright's CSS-sized native screenshot physically cropped; final run now uses Chrome physical-pixel capture plus explicit panel bounds. Final visual acceptance pending that image; no screenshot defect concealed. Ordinary screenshot review and independent UI review found no actionable layout defect; manual screen-reader remains unverified.
- Failed first Vite/browser setup retained: wrong Vite cwd and port0 normalization caused30s navigation failure; fixed cwd/strict reserved random port without relaxing timeouts. All failed fixture clusters shut down. No solver run concurrent with this workload, no hard constraints/time limits changed.
- Gate remains P3a PARTIAL pending final native screenshot inspection, fresh backend exit regression, public presentation browser proof and preservation check. Local slices only, production NO-GO. Next: close these gates then dependency-ready P3b acceptance/repository rehearsal; never modify original SQLite.

### 2026-10-26 23:27 Asia/Singapore — bounded emulator/local P3a exit PASS

- Backend serial disposable run `p3a-web-session-backend.log`:334/334,80.46s,exit0; existing Starlette/httpx deprecation warning only, no solverUNKNOWN, no altered constraints/timeouts. No concurrent solver workload. Frontend709/40files,security15,artifact4,bothbuilds,lint/types/Ruff0 as preceding checkpoint; npm tree0 and pipcheck0, no dependency changes since exact Python68/0 and npm0 audits in prior provider/P2b evidence. These audits are not reclassified as freshly rerun scans.
- Final actual browser `p3a-web-session-browser-exit.json`/log exit0, Authstoppedtrue,PGstoppedtrue,deniedOutbound0. Runtime/console/externalerrors0; all3roles and forbiddenaccess/currentrevocation/outagerecovery/offline/reload/signout/deeplinkunavailable proven with actual demo Auth and current PG via source Gateway lifespan. Sixteen screenshots including actual native200%. Chrome physicalpixel screenshot independently inspected by root/UIreviewer; wrapped denial, controls inside viewport, keyboardfocus clear; panelbounds81..631 within712, nativezoom2/DPR2/CSSzoom1/visualscale1. Previous crop was evidence capture, corrected without weakening checks. Manualscreenreader remains unverified.
- Fresh presentation browser15/15 role x widths, deeprefresh, nooverflow/runtimeerrors/APIrequests; `p3a-web-session-browser.json` and presentation-browser.log. Dirty release is correctly rejected for clean-release metadata, not a productionrelease. Existing illustrative timetable remains labelled synthetic.
- `p3a-web-session-preservation.json`: all3originalSHA256 unchanged and15 recorded owned Auth/Gateway/control/PG ports freshly probedclosed. No original-data writes, realrecords, productionFirebase/cloud/Gitremote/deploy/messages. Workingtree inventory retained in dated directory, HEADunchanged.
- Independent review: security found4issues across frontend/fixture, reproduced/fixed and closed; UIreviewer confirmed ordinary/mobile and native200% images, no actionable issue. Final screenshot gate and portable fixture safeguards now PASS. No test skips/xfails, no permission/constraints relaxation.
- Gate: bounded emulator/local P3a PASS. Institutional sign-in/provisioning authority, real token/provider/TLS deployment, cloud/realdata/cutover and complete connected roleworkflows remain unverified/separately gated. No institutional acceptance follows. P3b fullrepository adaptation remains PLANNED; next thin slice is isolated PG academic-period metadata foundation with current admin/tenant checks and rollback/restart tests, no original migration or endpoint cutover. Full P2-P8 Goal ACTIVE/incomplete.

### 2026-10-26 23:36 Asia/Singapore — P3b isolated academic-period metadata slice PASS

- Base/current main HEAD unchanged39200a4f2ef3ec7557bc3c86127e674e260ca4fc, dirty work protected. Bounded local P3a exitPASS enabled this next authorized P3b slice. Acceptance written before edits: `p3b-period-metadata-acceptance.md`. No service route/default provider or original DB changed.
- New Alembic0004 `classsync_academic.period_metadata` with composite tenant/owner/member FK, tenant+owner+id PK covering lookup/FK prefix, nonblank/length/revision constraints, ENABLE/FORCE RLS and explicit SELECT/INSERTonly current activeAdmin/project/tenant/owner policies. New `classync_persistence.academic_periods` performs same-statement current membership+data operation; validempty differs from typeddenied. Never trusts client/cached rolegrants. Uses existing engine transactions and clears context transactionally. Metadata is not a complete create-period/snapshot replacement and does not seed invented academic data.
- Existing request title maximum160 preserved after independent review caught initial200 mismatch. Reviewer also caught an ownership-test confound (otherowner also lackedAdmin): final qualification seeds two activeAdmins, each with metadata; independent list/directSELECT sees ownonly, cross-ownerINSERT42501 despitebothactiveAdmins. Non-superuser tableowner noctxcount0, contextcount1, UPDATErowcount0. No remaining actionable security finding in bounded metadata slice after independentreview.
- Executed: portable new boundary13/13 (serverbinding/principal/title beforeDB), full persistence68/68 in2.08s; configured Ruff0 after fixing qualifier linewrap/unusedimport/loopbinding warnings; no skips/xfails. ActualPG18.6 final `p3b-period-metadata-owner-reviewed.json`/log exit0: create/list/reconnect persistence; typedstudent-teacher/missingUID/wrongtenant/wrongproject denial; actualROLLBACK; sixconstraintcases includingduplicate/title/revision/id/missingownerFK; currentrevocation/reactivation; realDBpermissionoutage/recovery; 0004down/up identityrowcountunchanged. Foundationalso re-proves existing identitymigration/RLS/13constraints onnewhead. All3metadatafixtureclustersstopped/portsprobedclosed.
- Package isolated wheelbuild0; all11Pythonfiles byteequalcurrentworkspace, newadapter/migrationincluded; SHA256166d292f49bf8e3619244abebedb176a969d6b5636db0aa805371375ea2718be, `p3b-period-wheel-contents.json`. No app dependency change, no productionrelease. CI Ruff includesnewqualifier; persistence tests discovered by existing pytest job. No frontendbehaviorchanged; prior freshP3a5width/native200/presentation15 evidence remains applicable, no newUIclaim.
- Gate: metadata slice PASS; fullP3b PARTIAL. OriginalSQLite remainslocalacademic/scheduling source; no sourcecutover, no originalmigration/recordread/write, no realinstitutional policy/provisioning. Metadata downgrade intentionally removes disposablemetadata, not a data-preservingrollback claim. Fullrepository adaptation, calendar/records/references/revisionparity, deterministicdisposableSQLite->PGmapping/checksums/restore and furtherprivilege/concurrency/API qualification remain next. ProductionNO-GO/fullGoalACTIVEincomplete.

### 2026-10-27 00:04 Asia/Singapore — P3b complete academic adapter and synthetic migration rehearsal slices PASS

- Previous goal turn classified PROGRESS (P3a exit and metadata slice). This continuation inspected root AGENTS and all autonomy files, actual main/HEAD39200a4f2ef3ec7557bc3c86127e674e260ca4fc and dirty tree. No nested AGENTS, reset/stash/commit/push/remote operation. Owner scoped P2-P8 local authority unchanged. Acceptance written before edits: `docs/production/local-20261026/p3b-academic-repository-acceptance.md`.
- Actual source: new `services/academic/app/postgres_repository.py` implements create/list/snapshot/record/calendar save with explicit verified principal/server tenant/project, current activeAdmin checks, RLS, period rowlock, record/calendar CAS, checked parentrevision bump, repeatable-read snapshots and generic DB/pool failure states. SQLite repository refactored to shared `record_rules.py` (same reference/eligibility/section/curriculum/provenance rules and initial catalog/constraints, one checksum/model decoder); no SQL text-translation shim or duplicate domain-rule implementation. Existing default routes/providers still SQLite/unconfigured. Academic requirements now explicitly declare the already-installed local persistence package; no third-party versions changed.
- New Alembic0005 records/reference/calendar tables: composite tenant/owner/period keys/FKs, primary/reference target indexes, unique labels and normalized faculty institutional-ID index, positive revisions, JSON object/payload identity and SHA256 checks, ENABLE/FORCE RLS. Period UPDATE policy supports record/calendar revision bumps; qualified runtime receives UPDATE(revision) only on metadata. The older metadata-only qualification now explicitly targets0004, whose no-update semantics it tests; it is not current-head evidence. New complete adapter qualification tests head0005. No original schema/cutover or startup migration.
- Regression exposed a real pre-existing gap: initial period calendar accepted caller-supplied published_version although calendar editing rejected it. New SQLite test RED (1failed/1passed, did not raise); shared create/edit guard makes both adapters reject before write; GREEN2/2. No published version is invented by academic input. Refactor initially omitted json import, caught/fixed by Ruff. Initial named-baseline347/34759.53s overlapped editing and is NOT accepted as pristine pre-change/final-source evidence; subsequent source-frozen full354/35459.58s and final358/35864.46s are authoritative. Existing Starlette/httpx deprecation only, no solverUNKNOWN/constraint/time changes, solver tests serial and not overlapped with PG runs.
- Actual PG first+reviewed+final exit commands: `.venv/Scripts/python.exe -m scripts.postgres_academic_repository_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output <new evidence>` exit0; `p3b-academic-repository-exit.json`/log is finalUTC source evidence. All7recordkinds, existing readiness4offerings, optional catalog/calendar, no-catalog constraints/revision, 59provisional rooms unknowncapacity, reconnect durability, twoactiveAdminowner isolation, separate activeStudent/Teacher role denial, wrongUID/tenant/project, stale record/calendar, identity mismatch, missingreference, duplicate label/faculty, badCdMprovenance. Checksum-consistent malformed storedrecord/calendar returns409 and is restored; direct checksum/payloadID/missingID checks23514 and referenceFK23503. Two actual lock waiters observed before release: exactly one committed submitted winner/one409, subject and parent revisions increment exactly once. Revocation/reactivation, actual SELECT privilege outage503/recovery and pooledcontext clearing proven. Explicit down4/up5 preserves identityrows but intentionally drops disposable academic children, NOT data-preserving migration rollback.
- Generated-only rehearsal new `scripts/postgres_academic_migration_qualification.py` takes no arbitrary sourcepath. It generates SQLite inside the new marked clusterroot, checks typed source payloads/references/labels, maps only explicit synthetic tenant/owner, preserves81record rawpayloads/checksums/revisions, timestamps and fullsnapshot semantics. Interrupted import after3records rolls back all4destinationtables; replay409 cannot overwrite; reconnect stable; generated SQLite bytes unchanged. First real run failed strict snapshot equality due same timestamp instants displayedUTC vsPG+08; source UTC decoder fixed (not comparison waived), two portable timezone regressions and20focused guards passed. Exact reviewed real run `p3b-academic-migration-reviewed.json` passes fullmapped equality and rawcanonical rows SHA2563002bbb15260a305050fa81fd2ae260ae81bd0d7c10eeca69333a1339b966ddd. SourcefixtureSHAced58b00c987f5309d4592f7ba1f14dd9ab621fad4744ec5930a3aca0f5b6dfc unchanged. Outside-path/wrong-filename portable guard2/2 verifies no source open. This is not an institutional import tool or original-data migration.
- Static/package/security: Ruff configured services/packages/newqualifiers exit0, diffcheck0, pipcheck0. CI Ruff explicitly includes new repository/migration qualification scripts; pytest discovers new guards. Final wheelbuild0; all12persistencePythonfiles byteequal currentworkspace (including0005 and UTCdecoder), SHA256a63cdcb3a92843e776e689ba069c38517eaa992a30ede90d59036f0bb9e0f349 (`p3b-academic-wheel-contents.json`). Pinned pip-audit2.10.1 exact68installedversions/0findings against updated manifests, no skips/advisory exclusions (`p3b-academic-python-audit`). No frontend source or third-party version change; previous P3a web709/security15/bothbuilds/artifact4/rendered5width/native200/presentation15 remain dated applicable evidence, not rerun claims. No new connected UI/journey claim; manualscreenreader unverified.
- Independent reviewer: no source auth leak; requested malformedstorage/DBconstraints/provenance/initialcalendar and exactwinner/revision evidence, all added and actualPGpassed. It independently corroborated timestamp mismatch and reviewed generated-source/atomic/replay/mapping boundaries. Final review closed, no remaining actionable issue in these bounded slices. Review alone is not proof; commands/results above provide actual evidence.
- Preservation: `p3b-academic-preservation.json` all3original SQLite SHA256 identical; all5owned PGclusters including failed rehearsal have stoppedtrue and freshlyclosed ports. No originalrecordreads beyond filehash, writes/imports, real identities/records/credentials, Firebase/IAM/cloud/spending, messages or Git/deployment changes. All owned process/toolhandles terminal at checkpoint.
- Gate: complete academic adapter + generatedmigration rehearsal slices PASS; fullP3b remains PARTIAL, productionNO-GO, fullGoalACTIVE/incomplete. Next dependency-ready local slice: qualify explicit Academic service identity/PG provider adoption (owned lifecycle, current membership, actual Auth/HTTP positives/negatives, missingconfiguration unavailable, no startup migration and no fallback/originalcutover), then academic backup/restore and scheduling/draft/publication repositories. Do not advance P4-P8 phase gates before fullP3b exit. Rubrics/institutional enrollment/provisioning/cloud/realdata/cutover remain external/separate authority.

### 2026-10-27 00:24 Asia/Singapore — P3b Academic owned provider/HTTP adoption PASS

- Previous goal turn PROGRESS (complete PG academic adapter and81-record synthetic migration rehearsal). Re-read root AGENTS/autonomyfiles/currenttraceability and actual mainHEAD39200a4f2ef3ec7557bc3c86127e674e260ca4fc/dirtydiff; protected all prior work, no nested AGENTS or Git mutations. Owner scoped local P2-P8 authorization unchanged. Before edits acceptance: `docs/production/local-20261027/academic-provider-acceptance.md`; relevant pristine baseline40/40 in17.26s.
- New source `services/academic/app/authorization.py` owns bounded onepool/currentmembership+writer adapters; mainlifespan installs/removes/disposes. New provider.py selectsPG only for explicitSecretStrACADEMIC_DATABASE_URL+ownedengine. Absent institutional productionconfig returns503 beforeSQLite. Existing isolated legacySQLite identityfixtures require exacttest+explicitadapterflag+absoluteOS-temp path; sandboxstaysdevelopment-only. Institutional routes use verifiedguardUID and servertenant/project, no frontend/claims authority. No startupDDL/migration/originalcutover or implicitstoragefallback. .env.example documents optionalURL/defaultverifyfull only; actual.env unchanged.
- Shared reviewed transport/target validation extracted from Gateway to `classync_persistence.configuration` with Gatewaywrapper preservingbehavior/testmonkeypatchtargets: exactPsycopg URL/explicitserver+db+user+port/project/tenant, noquery/PG*ambient/passfilefallback; defaultsystem-rootverifyfull/SCRAM, exacttest127/highnondefaultport/noPasswordSSPI only. Academicfivephysicalslots/nooverflow/3scheckout/connect+statement5s/lock1500ms. No new third-party dependencies or app installs; existing68-version exactaudit0 frompriorcheckpoint appliesunchangedgraph, not a newly rerunscan.
- RED2 newtests beforeimplementation (productiontrustedguard wouldopenSQLite; provider missing). Targeted42/42 in17.20s afterimplementation. Independentreview found typedMembershipAuthorizationError fromrepositorycouldescape500 afterinitialguard: generic403DENIED/503UNAVAILABLE handler added, portablebothcases pass and actualguard->DBrevocation tested. Portableprovider+Gateway40/40 in1.50s coverpoolcaps, normal/body/constructorfailurecleanup, conflictingstatepreservation, prohibitedSQLitefallbackmodes and missinglifespan. Fullsource-frozen serialbackend372/372 in87.89s, existingStarlette/httpxdeprecation only; nosolverUNKNOWN/settings/constraint changes. Rootsecurity15/15, Ruff0, pipcheck0, diffcheck0. CI includes newproviderqualifierRufftarget. No tests skipped/weakened.
- Actual command `node scripts/auth_emulator_qualification.cjs --tools-root <existing reviewed pinned toolroot> --postgres-bin "C:/Program Files/PostgreSQL/18/bin" --output <new evidence> --academic`: newstrictwhitelistedprofile usesactualownedofficialAuthserver+SDK+newPG+sourceAcademiclifespan, nevermembershiplookupinjection. `academic-provider-reviewed.json`/log finalexit0; realanonymousidentityalone403, missing/malformed401; committed create/list/snapshot/record/calendar, defaultconstraints/revisions, stale409; twoactiveAdminowner404, activeStudent/Teacher403, spoofedclientheaders/queryignored. DeterministicactualSQLrevocationafterrealSDK/currentmembershipguard producesprivate403, restore200unchangedsnapshot. ActualREVOKESELECTrecords503/regrant200; SHOW5s/1500ms, fiveactualheldpoolslotsforce503/release200. Wrongservertenant/project eachrestartsownedprovideranddenies403whileactualfixed-demoSDKidentity remainsactive; restoredserverconfigurationreturnsoriginalsnapshot200. Normal/exceptional/restartcleanup haszeropooled/serverruntimeconnections andownedstate removed; prohibitedSQLitefile nevercreated. HTTP evidence is FastAPI TestClient ASGI with realSDK/PG, NOT TCP/browser or production qualification.
- Reviewclosedafterrequesting explicitwrongservertenant/projectcases (clientspoof testsaloneinsufficient); addedandactualPGpassed. No remainingactionablefinding inboundedproviderslice; reviewer didnotrunservers/tests. RealTLS/providerconfig/institutionalprovisioning/privacy/realdata and connectedfrontendacademic/scheduling journeys remainunverified, not implied by ASGIproof. UI source/dataAPIgates unchanged; priorP3arendered/web709/build/artifactevidence staysdated, no newUI/browserclaim. Manualscreenreader remainsunverified.
- Wheelisolatedbuild0, all13persistencePythonfiles byteequalcurrentworkspace includingnewconfiguration.py, SHA256eb8008543dcb38d7bb44d2b5576fec03c88a481935c2ca72bec56fb861f08642 (`academic-provider-wheel-contents.json`). AllownedAuth/PGpairsstopped, fourportsfreshlyclosed andall3originalSQLiteSHA256unchanged (`academic-provider-preservation.json`). No originaldatareadsbeyondhash/write/import, realpeople/credentials/Firebase/cloud/IAM/spending/messages/commits/push/deploy. Alltoolhandles terminal.
- Gate: bounded Academic provider/HTTP adoption PASS; fullP3bPARTIAL/fullGoalACTIVEincomplete/productionNO-GO. Next dependency-ready local task: academic PGbackup/restore/catalog+data+ACL+RLS rehearsal, then scheduling/draft/publication adapters and fullphaseexit. Do notadvanceP4-P8 gates or originalcutover withoutrequiredproof/authority.

### 2026-10-27 05:12 local — P3b academic restore / PostgreSQL drafts, final regressions pending

- Local main/base/current HEAD remains `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`. Existing dirty tracked/untracked work is preserved; `scripts/test-web.cjs` was already untracked, so an empty Git diff for that file is not evidence of equality to HEAD. Owner's recorded P2–P8 local authority applies. Acceptance was written first in `local-20261027/academic-restore-acceptance.md`, `postgres-drafts-acceptance.md`, and later `frontend-bounded-worker-acceptance.md` before the runner edit.
- Academic restore implementation: new `scripts/postgres_academic_restore_qualification.py` and 58 portable safeguard cases. New marked generated-only cluster, exact migration0005 pin, guarded new database/archive/bindings; actual custom pg_dump + atomic pg_restore; all10 identity/academic tables and 14 catalog components compared, including raw payload/checksum/revisions/references/calendar, audit, roles/policies/ownership/ACL/default privileges. Reversible content/ACL/FORCE-RLS drift was detected. Restored two active Admin owners, separate Student/Teacher denials, wrong UID/tenant/project, reconnect, CAS/integrity/audit guards, revocation and actual permission outage/recovery passed. Source/archive remained unchanged. Actual final `academic-restore-qualification.json` exit0/stoppedtrue (cluster4da3723e...). Earlier failures retained: restricted Windows token before start; public schema already present; all-row reference probe hit uniqueness before FK. Fixed exact-one public-schema TOC omission and single-row FK probe; acceptance was not weakened. This is a same-cluster generated-database restore, not cross-host disaster recovery or original-data migration.
- Draft implementation: extracted shared `draft_rules.py` without changing CP-SAT or hard constraints; SQLite adapter inherits common decoder/summary/independent validation. New migration0006 provides owner/tenant/current active Admin/project FORCE RLS, composite run FK, payload SHA256/metadata checks, unique owner/run/key and immutable UPDATE/DELETE/TRUNCATE guards. New `postgres_draft_repository.py` stores independently validated server-held runs and immutable drafts with transaction-scoped owner advisory lock, strict-key replay, typed errors and 24h unsaved-run expiry. New boundary tests11; scheduling routes/provider/publication are not adopted by this slice.
- Actual draft runs `postgres-drafts-qualification.json` and final `postgres-drafts-reviewed.json` exit0/stoppedtrue. Final source proof: new physical backend PID after disposal + exact snapshot, two active owners and active non-Admin denial, wrong tenant/project, two observed advisory-lock waiters and exactly one creation, strict key/title/hash conflicts, missing/expired runs, UNKNOWN/infeasible/hash/incomplete rejection, checksum-consistent malformed snapshot denial, isolated checksum/FK/immutable DML constraints, fresh revocation, real outage recovery, pooled-context reset, upgrade/down/up. Destructive disposable downgrade does NOT preserve drafts and is not a production rollback claim. Legacy development SQLite still accepts an alternate key for an existing run; new PG rejects it with409 so no unbound accepted alias exists.
- Independent reviewer found the alternate-key defect and two evidence gaps (physical reconnect and isolated checksum probe); all were corrected and the reviewer confirmed closure. It also reviewed restore fixes and the bounded runner change with no further actionable finding. See `draft-restore-independent-review.md`; reviewer did not execute tests/servers. All original hashes unchanged and first five owned clusters/ports stopped (`draft-restore-preservation.json`); final sixth cluster separately reports stoppedtrue, fresh final preservation pending.
- Executed regression evidence: initial draft suites27/27; combined draft/restore portable65/65, then restore TOC safeguards58/58. Full backend initially440passed/1failed121.33s: existing multi-program case returnedUNKNOWN at its unchanged8s budget (first phase4.8s), while frontend work overlapped. No timetable was accepted, constraint/time settings were not relaxed; exact isolated case later passed1/1 in8.60s. Full source-frozen backend rerun remains REQUIRED after frontend work finishes.
- Frontend root command hit unchanged300s timeouts (logs retained); diagnostic proved continued test progress, not a startup deadlock. Node and DOM selections passed4/7/28 cases. Existing app config caps2 workers but wrapper forced1. Independent review found no isolation/shared-data safeguard reason against honoring2. Full diagnostic with2 passed709/40 in185.96s, unchanged300s/isolation/assertions. Removed only redundant one-worker override/comment in `scripts/test-web.cjs`; exact actual root command now live as tool session6115, followed by security checks. No claim that resource pressure is a proven root cause. Older unclassified Node processes preserved.
- Other executed gates: lint0, typecheck0, both builds0 (existing chunk-size warning), production artifacts4/4, security15/15, Ruff0, pipcheck0, Node syntax0, diffcheck0. Wheel build first failed sandbox network access; narrow isolated build retry succeeded, all14 Python sources byte-equal to workspace, SHAd8cdbb1bef1e1614ccf0bd9ef713fb853640d489e9e6cf64342b7359497b96ad (`draft-wheel-contents.json`). No application dependency change; previous exact68/0 audit remains dated evidence, not a fresh scan. No product UI source change/new browser acceptance or manual screen-reader claim.
- Status: implementation and targeted actual PG proofs verified; milestone acceptance pending exact final web/security and full serial backend gates plus final preservation. Full P3b PARTIAL; Goal ACTIVE/incomplete; production NO-GO. Next: finish live6115, run full backend serial without frontend/PG/solver overlap, inspect results and record closure; then only after applicable pass advance to Scheduling provider/adapters and remaining publication/restore/migration requirements. No original DB writes/import, real records, cloud/Firebase/credentials/messages, Git commit/push/deploy or cutover.

### 2026-10-27 05:19 local — bounded academic restore and PostgreSQL draft adapter PASS

- Base/current SHA unchanged (`39200a4f2ef3ec7557bc3c86127e674e260ca4fc`); existing dirty work protected. This closes the bounded slices described in the05:12 entry, not full P3b or the Goal.
- Final source-frozen serial backend: `.venv/Scripts/python.exe -m pytest services --basetemp <fresh-temp>/pytest -o cache_dir=<fresh-temp>/cache -q`, explicit fresh ACADEMIC_DATABASE_PATH/SCHEDULING_DATABASE_PATH; **441/441 passed87.54s**, existing Starlette/httpx deprecation only (`draft-restore-backend-serial.log`). No frontend/build/PG/other solver overlapped. Prior440/1UNKNOWN failure retained; isolated1/1 and full441/441 now pass without solver, constraint or time-budget changes.
- Final actual `npm run test:web` after removing only the wrapper's one-worker override: **709/709 in40 files,172.80s**, same thread pool/default isolation/assertions/300-second limit. `npm run test:security` **15/15** afterward,3.74s. The existing app configuration still bounds workers to2. Prior timeout diagnostics are retained; two-worker diagnostic709/40/185.96s and independent source review support the small throughput change, without asserting a proven external-resource cause.
- Actual reviewed PG draft run exit0, cluster1871812a... stopped; academic restore exit0, cluster4da3723e... stopped. Exact proof scopes/limitations are recorded in the preceding entry, acceptance/review docs, `postgres-drafts-reviewed.json` and `academic-restore-qualification.json`. No new UI source was changed; no new rendered/browser or manual screen-reader acceptance is claimed. Relevant prior P3a five-width/native200% evidence remains dated, not rerun.
- Final Ruff0 (`draft-restore-ruff-final.log`), diffcheck0 (line-ending warnings only), Node syntax0. Earlier fresh lint0/typecheck0, both builds0, artifacts4/4, pipcheck0 and wheel14 byte-equality remain applicable because their relevant source/dependency inputs did not change. Final wheel SHAd8cdbb1bef1e1614ccf0bd9ef713fb853640d489e9e6cf64342b7359497b96ad; dependency versions unchanged, exact68/0 audit not rerun. CI Ruff includes both new explicit qualification scripts; local checks are not a claimed remote CI run.
- Post-regression `draft-restore-exit-preservation.json` rechecks all3 original SQLite hashes and all6 owned clusters (including failed attempts); no postmaster PID, all assigned ports closed, original bytes unchanged. It binds the final backend log SHA256. No original writes/import/cutover, real identity/data/credentials, cloud/settings/spending/messages, Git commit/push/deploy or destructive user-file cleanup occurred. Older unclassified Node processes remain untouched.
- Documentation: persistence README now describes migration0006, strict PG replay versus legacy dev SQLite, bounded same-cluster academic restore, explicit qualification commands and pending Scheduling routing. TRACEABILITY/ROADMAP current pointers are updated. P3b remains PARTIAL; production NO-GO; Goal ACTIVE/incomplete.
- Next authorized task: write acceptance for source-owned Scheduling PG/identity provider and validated run/draft route adoption, preserving development SQLite and fail-closed unsupported publication boundaries. Actual emulator/current-PG HTTP and negative authority/owner/outage/pool/restart checks must prove this slice before advancing; remaining publication adapter, migration/restore and complete P3b exit still follow. No original-data permission is inferred.

### 2026-10-27 05:43 local — bounded Scheduling owned provider / PG draft HTTP PASS

- Same main/base/current SHA39200a4f2ef3ec7557bc3c86127e674e260ca4fc; dirty source preserved, no commit. Owner's P2–P8 local authority and preceding bounded441/web709/security15 gates apply. Acceptance was written first in `scheduling-provider-acceptance.md`; this is part of P3b, not an advance to P4 or complete Goal.
- Changed Scheduling source: new authorization.py owns one engine/current-PG membership/Firebase verifier, rejects conflicting state and cleans normal/body/constructor failures; provider.py selects explicit PG/verified owner/server tenant/project, with exact-test+flag+absolute-temp SQLite fixture exception only. main.py optional secretURL/transport/lifespan, bound generation/academic-generation/save/list/get, generic post-guard membership403/503 handler. Missing selected storage outside explicit sandbox scopes fails503 before solver slot. Successful solver result is not returned after failed persistence; slot always releases. No startup DDL or original cutover. Existing development-only sandbox preserved.
- publication_api.py guards all5 legacy factory access sites. Configured PG refuses publication/projection/history/restriction/stream before SQLite; unconfigured institutional production is also unavailable, with isolated test fixtures only. No second writable official source. Optional .env.example config and Scheduling local persistence dependency added; no third-party version change. Fixed `--scheduling` selector in guarded Auth harness accepts no arbitrary module/extra flags/prototype keys; CI Ruff includes the new qualifier.
- Test evidence: initial provider RED2 (unsafe prod SQLite fallback/missing provider), then portable47/47 in0.88s; extra unbound execute-scope4/4 in0.21s (51 total). Existing solver/draft/publication24/24 in41.97s. Full serial backend **492/492 in68.77s**, isolated fresh env paths/basetemp/cache, no overlapping solver/PG/frontend/build. No solver/constraint/time changes or skipped/weakened tests. Existing Starlette/httpx deprecation retained. Harness selector RED1→GREEN2; final root security **16/16 in6.23s**, Ruff0, pipcheck0, Node syntax0, diffcheck0 (line-ending warnings only).
- Actual command: `node scripts/auth_emulator_qualification.cjs --tools-root <previously reviewed pinned owned temp root> --postgres-bin <local PG18 bin> --output docs/production/local-20261027/scheduling-provider-qualification.json --scheduling`, narrow Windows-token escalation solely for owned new cluster. Exit0, Auth project demo-classsync-85afb7123638/root36cddb81..., PG root a95f696f...; Auth stopped, PG stopped, child exit0, outbound attempts0. Actual SDK5identities/current realPG membership; separate active Student/Teacher/no membership/missing/malformed denials; two active Admin owner isolation; actual tiny CP-SATgenerate→server-held save→strict replay/list/get, spoofed owner/tenant ignored, forged client/stored candidate denied, real infeasible not persisted; guard→DB revocation403/recovery, actual SELECT/INSERT denial503/no false candidate/no new run, positive recovery, five held pool slots503/recovery; all8 institutional publication paths503 and Student/Teacher projection503; wrong server tenant/project denied; actual owned postmaster restart/start time/new backend plus provider restart preserved both exact drafts and replay key; normal/exception cleanup zero runtime sessions/no SQLite. See JSON/log for exact HTTP statuses.
- Independent source and evidence review found no actionable issue; closure of defensive execute guard and fixed selector reviewed separately. `scheduling-provider-independent-review.md` records roles and limits; reviewer ran no tests/servers. Actual UNKNOWN not forced (portable control-flow and earlier actual PG adapter rejection remain the bounded negative evidence), Academic forwarding/TCP/browser not composed. Publication remains intentionally unavailable, not completed.
- Pinned pip-audit2.10.1 freshly audited **68 exact installed third-party versions/0 findings**, all5 service manifests checked including updated Scheduling; internal editable contracts/persistence provenance verified (`scheduling-provider-python-audit`). No resolver/fix/advisory exclusion; scanner's hashing recommendation retained. Previous same-turn frontend709/40 in172.80s, lint/typecheck0, both builds and artifact4/4 remain applicable: no frontend product/runner/build input changed in this slice. No fresh rendered/browser/manual assistive-technology claim. Persistence wheel's14 sources remain unchanged/byte-equal; no release claim.
- Fresh `scheduling-provider-preservation.json` verifies all3 original SQLite SHA256 unchanged and7 owned PG roots including prior failed attempts/no postmaster PID, all assigned PG and new Auth ports closed. It records exact source file SHA256 for the provider, routes, tests, manifest, harness, qualifier, example config and CI. No original writes/import/migration, real records/credentials/Firebase/cloud settings/spending/messages, commit/push/deploy/cutover or unclassified-process cleanup.
- Status: bounded local/emulator Scheduling provider PASS; full P3b PARTIAL, Goal ACTIVE/incomplete, production NO-GO. Next dependency-ready local work is generated-only Scheduling run/draft migration and backup/restore proof, followed by publication adapter/provider and complete P3b exit. Write acceptance before implementation; preserve originals and run actual solver-sensitive cases serially. Do not infer institutional authority or advance to P4 while P3b is partial.

### 2026-10-28 02:10 Asia/Singapore — bounded P3b generated Scheduling migration/restore PASS

- Current/base main HEAD unchanged `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`; uncommitted user work preserved. Owner local P2–P8 authorization unchanged. Actual implementation/drills ran 27 October; regression was observed terminal and preservation reverified 28 October after continuation. Acceptance preceded source changes: `docs/production/local-20261027/scheduling-migration-restore-acceptance.md`. This accepts these bounded P3b slices, not full P3b/P4 or the full Goal.
- New `scripts/postgres_scheduling_migration_qualification.py`: fixed-name generated-only read-only/immutable SQLite source under a new marked temp cluster; validates version/schema/integrity/FKs, canonical UTC, explicit synthetic Admin/tenant/project mapping, checksums and independently validated typed run/draft agreement before writes. One current-owner target-bound PG transaction/advisory lock inserts runs then drafts; no arbitrary source/DSN or automatic source migration. Raw payloads/checksums/IDs/times/key remain exact. Existing dev alternate-key behavior creates no alias to migrate.
- Actual command `.venv/Scripts/python.exe -m scripts.postgres_scheduling_migration_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output docs/production/local-20261027/scheduling-migration-qualification.json`, exit0. Two fresh serial owned PG18.6 clusters `227e63e9...`/`b5450e9a...` stopped. Three runs/one draft exact raw and typed equality, actual new backend PID, same-key replay/alternate-key409, run+draft interruption rollback, replay409, unexpired unsaved run save/expired410, current roles/tenant/project/current revocation denials, second active owner's snapshot preserved. Separate key-collision cluster proves inserted batch rollback and every existing target row unchanged. Generated source hashes unchanged. CP-SAT synthetic tiny candidates independently validated; no original source opened.
- New `scripts/postgres_scheduling_restore_qualification.py`: generated ready academic periods for two active Admin owners -> actual CP-SAT/independent validator -> private durable drafts plus expired run. Pin0006 after explicit known0005 academic fixture setup. Guarded archive/new-empty target only; all12 raw tables and14 canonical catalog categories equal, including ownership/columns/constraints/indexes/functions/triggers/FORCE RLS/ACL/default privileges. Only existing public-schema CREATE TOC entry omitted, all objects/ACLs retained. Content/ACL/FORCE-RLS tampering detected/reversed. Restored full academic/draft snapshots/new physical connection, two-owner isolation/roles/tenant/project, checksum/metadata/FK/CAS/audit/immutable DML/replay/expiry/revocation/permission outage/recovery/pool context proven. Exactly four expected membership/audit transitions allowed; all other raw rows and catalogs/source/archive/TOC unchanged.
- Actual restore command same module form with `postgres_scheduling_restore_qualification`, final output `scheduling-restore-reviewed.json`, exit0/stoppedtrue, cluster `0ddf9b61...`. Initial `scheduling-restore-qualification.log` retained: TRUNCATE solver_runs alone hit FK dependency0A000 before immutable42501 trigger. Corrected probe truncates both FK-connected tables in one statement, no CASCADE, still requires42501; independent reviewer confirmed isolation, fresh actual drill passed. Initial failed cluster `6bf24104...` stopped. No gate/test/constraint weakening.
- Portable tests: initial migration RED2 missing module -> guard2 PASS -> expanded63/63 in11.34s; restore RED2 ->52/52, root rerun52 in4.18s. No portable test starts a solver/server. Separate reviewer inspected source and final actual evidence, no remaining actionable issue; exact division/limitations in `scheduling-migration-restore-independent-review.md`. CI Ruff adds both new qualifier files.
- Full serial backend `.venv/Scripts/python.exe -m pytest --basetemp <fresh temp>/pytest -o cache_dir=<fresh temp>/cache` with both DB paths in new disposable temp directory: **607/607 PASS124.44s**, exit0. No overlapping PG/frontend/build/solver workload; existing Starlette/httpx deprecation only, no UNKNOWN failure or changed solver budget. Security16/16 in6.73s, configured Ruff0, pipcheck0. New scripts/tests/CI only; no dependency or UI change, so prior exact68/0 audit/frontend709/build/browser/wheel evidence is explicitly dated, not recast as fresh. No new rendered UI acceptance is implied.
- `scheduling-migration-restore-preservation.json`: all3 original database hashes match baseline, all11 recorded owned PG roots have no postmaster and assigned ports closed (one older never-started root has no port), current5 source hashes and backend log hash recorded. No original data writes/cutover/real records/cloud/Firebase production/remote Git/deploy/messages. Same-cluster synthetic restore does not prove cross-host recovery.
- Next authorized dependency-ready slice: publication PostgreSQL data-access boundary/schema and immutable version/head/restriction persistence, then provider adoption and full P3b exit. Keep publication unavailable in PG mode until its complete correctness/current-role/tenant/revision/atomicity tests pass; no second writable official source. P4–P8 remain pending predecessor gates; institutional authority and production remain NO-GO.

### 2026-10-28 02:24 Asia/Singapore — publication rules boundary and workload correction PASS

- Base/current HEAD unchanged39200a4f2ef3ec7557bc3c86127e674e260ca4fc, dirty work preserved. P3b local prerequisite under owner authority; acceptance written before source in `local-20261027/publication-rules-acceptance.md`. This is not full P3b or an advance to P4.
- `publication_rules.py` shares five prior domain methods and interval helper. `PublicationRepository` inherits them; SQLite queries/transactions stay in place. `occurrences.py` imports the same DraftError from draft_rules, removing its SQLite dependency. No provider/route/default database change. No duplicate validation implementation for a future PG adapter.
- Independent source review caught a pre-existing ordering bypass in teacher workload checks: after a smaller supplied cap, a later larger/missing cap could permit an excessive combined load. Added eight daily/ISO-week × forward/reverse × larger/missing cases; RED4failed/4passed in1.82s retained. Fixed per-teacher/bucket strictest supplied non-None cap; no institutional policy values selected, no relaxed constraints. Reviewer confirmed correction and privacy/extraction scope.
- Initial rule-boundary RED2missingmodule; final portable **43/43 PASS2.53s**, DB/solver sentinels, manually placed independently validated invented fixtures. Resource conflict negatives for room/faculty/section/student, half-open adjacency/stricter buffer, workload/bucket resets, effective revisions, historical corruption rejection, scoped rows/head ports, linked-record identity/denied access and private projection metadata removal. Separate author and independent read-only security reviewer used; review is not external certification.
- Existing publication/HTTP projection11/11 in44.47s before workload fix; final full serial disposable backend **650/650 PASS91.20s** after fix, exit0. Both DB paths/basetemp/cache under new temp root; no competing solver/PG/frontend/build. Existing Starlette/httpx warning only, no UNKNOWN or solver changes/skips. Security16/16 in16.75s, configured exitRuff0/diff0. Exact commands/logs in `publication-rules-*`; `publication-workload-red.log` preserves defect reproduction; `publication-rules-independent-review.md` records review/scope.
- Fresh `publication-rules-preservation.json`: all3 original hashes unchanged, all11 recorded owned PG roots have no postmaster;10 stopped with assigned ports closed and one never started, four source fingerprints and backendlogSHA. No dependencies/UI changed; older frontend709/build/artifact/browser/Python68-0/wheel checks are dated evidence, not rerun/new UI acceptance. No manual screen-reader claim, original-data migration, institutional policy/records, cloud/Firebase/Gitremote/deploy/messages.
- Next: PostgreSQL publication schema/data-access boundary and actual atomicity/current-authority qualification, then provider adoption/full P3b exit. Keep PG publication unavailable until its applicable gates pass; no second official source. Full Goal remains ACTIVE/incomplete, P3b PARTIAL, production NO-GO.

- Final independent evidence review corrected cluster wording: preservation proves10 stopped/closed-port owned clusters plus one never-started cluster, not11 running-then-stopped clusters. Underlying JSON states were already exact; no source/test failure or additional running process was found.

### 2026-10-28 02:40 Asia/Singapore — bounded publication-state foundation PASS

- Base/current main HEAD unchanged39200a4f2ef3ec7557bc3c86127e674e260ca4fc; dirty work preserved. Owner's P2–P8 local source/test/disposable-data authority applies. Acceptance written first in `local-20261027/publication-state-acceptance.md`. This accepts a schema foundation only, not full P3b/P4/P6/P7 or the Goal.
- New explicit Alembic0007 `published_versions`/`publication_heads`: positive revision/server identity sequence, exact command/request SHA/payload SHA and JSON envelope/calendar bindings, original key uniqueness, owned draft/academic-period composite FKs; immutable versions, retained heads, initial1/exact+1/stable head scope/owner, FORCE RLS/current activeAdmin/server tenant/project, own actor/version/head writes, no PUBLIC table/sequence/function privileges. Deferred constraint requires version/head same-owner commit together. No startup DDL, original cutover, new adapter/provider/API authority or Student/Teacher projection enabled.
- Independent source review found potential same-period owner takeover before qualification: private academic metadata can have same periodID under different activeAdmins. Fixed stable headowner/compositeFK, old/target owner checks and version-insert policy blocking other-owner succeeding/orphan versions. Actual two-active-Admin identical-period collision negatives now pass. No shared institutional-edit policy inferred. Reviewer also confirmed deferred trigger/RLS/no privileged execution and explicit orphan probe. Separate agent authored guarded actual qualifier and28 portable cases; root authored/reviewed migration and executed actual/regressions. Review is not external certification.
- Actual first run failed inherited fullbase downgrade: publication_create policy references heads. Fixed explicit named DROP POLICY before dropping these disposable tables, no CASCADE or runtime relaxation. Failed cluster974627f6... stopped/evidence retained in publication-state-qualification.log. Fresh `.venv/Scripts/python.exe -m scripts.postgres_publication_state_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output docs/production/local-20261027/publication-state-reviewed.json` exit0; cluster d975c304...PG18.6/stoppedtrue. Three actualoptimal tiny CP-SAT drafts independently validated, owned academic metadata; exact raw receipts/serversequence/new physicalPID;32constraint/immutable/state/ownedFK/JSON/key/hash negatives; sameperiodtwoAdmin rejection, separateAdmin positive, deferredorphan rejection23514, current active wrongroles/UID/tenant/project/revocation/readoutage/recovery/tableownerFORCERLS/contextclear. Uncommitted state invisible; inserted version/head failure rolls back together. Disposable downgrade/upgrade preserves all existing draft rows but deliberately removes publication data, not data-preserving live rollback.
- Portable initial RED2missingmodule -> root28/28 PASS3.17s, no solver/server. Full serial disposable backend **678/678 PASS82.90s**, exit0; fresh temp DB paths/basetemp/cache, no concurrent solver/PG/build/security workload. No UNKNOWN failure/constraint/time budget changes/skips. Existing Starlette/httpx deprecation remains. Security16/16 in4.16s, configured Ruff0/pipcheck0/diff0; CI includes new qualifier Ruff target.
- Fresh pinned pip-audit2.10.1 exact68versions/0findings with current five-manifest/internal-source provenance (`publication-state-python-audit`); dependency-hashing recommendation retained. Isolated final wheel SHA37c942912ba81a44a2caaf81aa7d68a52d3a5896754149984ef42383a93e650a;15 Python files byte-equal to current workspace including corrected0007 (`publication-state-wheel-contents.json`). Earlier successful wheel predates final schema and is explicitly superseded. No third-party dependency/version changes.
- `publication-state-preservation.json`: all3 original database SHA256 unchanged,12 owned clusters stopped/no postmaster/assigned ports closed plus1 older never-started cluster,8 source fingerprints/current backendlogSHA. No real records, original DB migration, production Firebase/cloud/remote Git/deploy/messages. No UI changed/new browser or manual accessibility claims; prior frontend/build/browser checks are dated only.
- Limitations: schema state proof does not prove current academic readiness/hash freshness, scoped approval, conflict-safe publication, concurrent transaction semantics, publication history migration/restore, outbox/realtime or production authority. Next dependency-ready local P3b task: PostgresPublicationRepository using shared rules, current academic/revision/owner transaction boundary, restrictions and failure/concurrency qualification; then guarded provider adoption and full P3b exit. Keep PG publication unavailable until its complete applicable gates pass. Goal ACTIVE/incomplete; P4–P8 await predecessor gates; production NO-GO.

### 2026-10-28 21:20 Asia/Singapore — usage-limit preservation and recovery priorities

- Existing Goal queried: `usageLimited`; retained unchanged, no second Goal or attempted budget/status override. This is a preservation/documentation checkpoint, not resumed implementation or a new acceptance PASS.
- Current HEAD remains `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`; extensive pre-existing tracked/untracked work preserved. Inspected Git status, aggregate diff and publication API/repository diff. Five latest changed files by filesystem modification time: `docs/autonomy/ClassSync_UIUX_Screenshot_Audit_2026-10-28.md`, `scripts/postgres_publication_repository_qualification.py`, `packages/persistence/classync_persistence/migrations/versions/0008_publication_transactions.py`, `services/persistence/tests/test_publication_repository_boundary.py`, `docs/production/local-20261027/publication-adapter-targeted.log`. Read audit, migration, guard tests, qualifier probe structure and retained test result. Modification time is an inspection aid, not authorship evidence.
- Current publication application repository/0008/restriction implementation is IMPLEMENTED-UNVERIFIED. Retained targeted log reports 212 passed / one Starlette warning / 27.49s; this was not rerun today. Prior full backend678 belongs to the earlier foundation checkpoint, not current adapter acceptance. No actual new repository PostgreSQL qualification or fresh browser verification occurred in this preservation turn.
- Independent reviewer returned source clearance for the guarded actual qualifier, including privileged migration rollback, forced audit failure and bounded pool checks. Remaining explicit acceptance gaps: direct unauthorized-context calls to the definer helper and an observed restriction-versus-publication writer race. Source clearance is not execution evidence.
- Resume first with the existing publication-adapter acceptance document and guarded disposable PostgreSQL repository qualifier; execute serially, retain failures, repair and test locking/current authorization/rollback/replay/concurrency/revision/outage cases. Cover the two reviewer gaps and resource/scale acceptance, then relevant full regression, migration reproducibility, packaging/security/preservation and independent evidence review before claiming adapter acceptance. Provider adoption, history migration/restore and complete P3b remain outstanding.
- Read the owner's audit at its actual filename above; added a high-priority bounded UI/UX recovery track to ROADMAP, ordered after the current backend gate. Connected timetable diagnosis and truthful presentation synchronization precede Student/Teacher/Admin workflow and navigation recovery. Screenshot-based findings are not represented as newly reproduced defects or fresh visual verification.
- Fresh SHA256 reads match original baselines: academic `4cd5f60de21bd365c914ac01e5be692b3bea1c7a56a7f17a76c6953ef8668738`; scheduling `1848377cc9a9eb656e12b5e58436e81198fef92f18dd71c1fea2f6f8b482e400`; backup `9ec149413d69c1165b74a75e366fa262417c1ecbf41e7029fdd0d86ac96f395d`. No original database changes, application edits, cluster starts, commits, pushes or deployment in this turn.
- Gate: P3b PARTIAL; current adapter acceptance pending; production NO-GO. Continue the existing Goal only when execution is available. No background continuation is claimed.

### 2026-10-28 — resumed publication repository qualification (interim)

- Existing Goal now reports ACTIVE; no new Goal. Prior preservation turn made documentation progress, not adapter acceptance. HEAD unchanged at `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`; dirty work preserved.
- Ran `.venv/Scripts/python.exe -m scripts.postgres_publication_repository_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output docs/production/local-20261027/publication-repository-qualification.json` serially on new marked cluster b17276c8ce9445528020c456739580e5. Exit1 late at stale-input negative: correct production `academic_input_changed`409 differed from qualifier's incorrect `academic_version_conflict` expectation. Failed log retained; no success JSON written. Corrected only that expected code after examining shared contract and independent reviewer confirmation; stale revision remains separately tested. No production rule or timeout weakened.
- Ruff on qualifier/repository exit0; portable qualifier guards22/22 passed3.49s, existing Starlette warning. Fresh actual rerun exit0: `publication-repository-reviewed.json` and log, PG18.6 cluster a34b9773da5144b1bd3a16b0d4af8f4d stopped. Verified actual optimal generated drafts, review/no-write, publish revisions/replay/history/projection/reconnect, current authority/owner negatives, two observed concurrent publication waiters with one winner and one409 loser, restrictions/audit rollback/recovery, permission/pool outages, membership/project/academic locks, stale revision/hash and corruption rejection. JSON explicitly excludes full resource/scale matrix, HTTP/provider/browser, approval/outbox and history migration/restore/full P3b acceptance.
- Historical foundation rerun pinned0007 exit0: `publication-state-pinned-recheck.json` and log; fresh PG18.6 cluster d72d1c51b08943e89d246665e5741610 stopped. Reproduces schema qualification without accidentally applying0008 through identity setup.
- CI Ruff list now includes the new publication repository qualifier. Independent agents are extending/reviewing direct helper authorization negatives and an observed restriction/publication writer race; those additions are not yet accepted. Full current backend/package/security gates pending; no UI screenshots or frontend tests rerun in this backend-only interval.
- Fresh originals all match recorded academic/scheduling/backup SHA256 baselines. All three newly used cluster postmaster.pid files absent; two successful evidence files explicitly report stopped. No original DB or Git/cloud operation.
- Gate remains PARTIAL, not complete adapter or P3b PASS. Next: finish missing actual negative/race probes, inspect resulting evidence, full serial regressions and remaining acceptance requirements. Owner's UI/UX recovery track remains next after backend acceptance.

### 2026-10-28 23:15 Asia/Singapore — publication transaction qualification and regression checkpoint

- Same main/HEAD `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`;134 status entries reflect cumulative protected work, not134 newly changed files. Existing Goal ACTIVE/incomplete. No original-data/Git/cloud actions.
- Qualifier now covers direct helper context/ACL/nonprivileged owner checks and both compatible publication/restriction writer orderings. Independent source review found no actionable defect; root portable guard tests39/39 PASS20.08s. Agent author hit a usage limit after saving changes; root inspected and verified them rather than assuming completion.
- Actual command `.venv/Scripts/python.exe -m scripts.postgres_publication_repository_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output docs/production/local-20261027/publication-repository-locks.json` exit0. Fresh PG18.6 cluster f6517ed1e3694b1788de346e972184ca stopped. Six unauthorized helper contexts return false and leave authority rows unlocked; valid Admin control succeeds. Both writer orderings observe one actual waiter and commit exact publication/restriction revisions4 then5, preserving immutable history and audit prefixes. Earlier concurrency/replay/revision/outage/rollback probes still pass. Independent evidence review agrees; these compatible writer cases do not prove conflicting-winner cases.
- Full serial `.venv/Scripts/python.exe -m pytest -q` exit0: **829 passed**,85.19s, one existing Starlette warning; isolated process database paths recorded in publication-adapter-backend-root.txt, complete log publication-adapter-backend.log. `npm run test:security` exit0 **16/16**. Ruff across services/packages and changed qualifiers, `pip check`, `git diff --check`: exit0. No solver constraints, timeouts or tests weakened.
- Packaging: initial no-build-isolation attempt failed because setuptools was unavailable; failure log retained. Isolated build from disposable copy exit0; **16 Python files byte-equal** to repository source, wheel SHA256 `2c6b980bd72f7ed5ff91292d677ee6306d2ff1edcee48bcfe75502cd5e9e182e`; publication-adapter-wheel-contents.json/log/root retained. No application dependency installation.
- Old disposable scanner failed importing pip_audit.**version**; NOT a successful scan. Fresh isolated scanner pinned2.10.1 installed successfully. Fresh audit exit0 **68 exact versions / zero findings**, retained hashing warning; evidence publication-adapter-python-audit-fresh directory/log. Application dependencies unchanged.
- Latest original hashes saved in publication-adapter-original-hashes.json match all three established baselines. The four clusters from this resumed interval were disposable; successful runs report stopped and earlier failed cluster's postmaster.pid was verified absent. Previous frontend709/build/browser evidence remains historical unchanged-input evidence; no fresh screenshots or UI claims.
- Review evidence: publication-adapter-independent-review.md. Clarification: JSON key mutation_denied_after_commit means access is denied after the authority mutation commits, not that mutation was denied.
- Gate: **P3b PARTIAL; complete publication adapter acceptance still open**. Next dependency-ready work: actual per-resource conflict matrix (room/faculty/section/student), conflicting restriction/publication outcomes and representative scale qualification. Then close adapter acceptance and continue guarded provider/history migration/restore/full P3b. Approval/outbox/institutional publication and production remain unqualified. UI/UX recovery retains high priority after backend gate; do not restart P1/P2 or bypass mode/authority guards.

### 2026-10-29 00:30 Asia/Singapore — publication resource, boundary and bounded scale evidence (interim)

- Existing Goal objective file read: current completion boundary is P3b local exit; stop after P3b, preserve UI/UX track for later milestone. HEAD remains `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`; cumulative user changes preserved.
- Independent reviewer found two shared-domain defects using focused RED cases: partial-week publications omitted retained classes elsewhere in the same ISO week from weekly workload caps; dated room moves did not recheck all eligible-room constraints. Added full affected-week plus one-day buffer halo to shared review expansion (preserving same-period occurrences only outside command effective dates) and reused `eligible_room` plus mandatory room availability on moved events. Regressions cover earlier/later same-week retained loads, Friday/year boundary controls, 30-minute Sunday/Monday buffer, moved room capacity/verification/type/equipment/program/building/availability and a valid room control. `publication-invariant-final.log`:67 passed, Ruff0. Pre-fix RED evidence retained (`publication-week-boundaries-red.log`, `publication-midnight-buffer-red.log`, room eligibility RED logs). No solver/database used for pure defect reproduction.
- Actual resource qualifier rerun after room fix: `publication-resource-final.json`, PG18.6 cluster e4bfc63fa35942b1bd3a16b0d4af8f4d stopped. Actual optimal saved drafts reject isolated room, teacher, section, student conflicts as exact422 while all six scheduling tables remain unchanged; disjoint-resource same-time publish succeeds. The earlier first run used identical source except later qualification hardening; final evidence is authoritative.
- Exploratory scale qualification: 100 offerings/3,000 enrollments consumed sustained CPU without reporting progress; stopped only its own process and verified its marked cluster had no running server using `pg_ctl status`. Its output is incomplete and not accepted. Reduced only the generated disposable fixture size, keeping all correctness assertions/solver settings:25 offerings,250 enrollments,13 Mondays,325 occurrences,225 projected,25 audited restrictions. `publication-scale-bounded.json` actual optimal CP-SAT + independent validation; fixture2.85s, solve/draft0.51s, review0.21s, publish0.31s, projection0.14s, replay0.04s, reconnect0.12s, restrictions0.05–0.12s each, review-after-restrictions0.22s. All operations under15s; PG18.6 cluster243bbca52df64593b8236515ee3e3660 stopped. This is bounded local capacity evidence only, not production scale.
- Scale evidence guard portable tests4 passed4.77s; Ruff clean. Worker remains at no UI/full regression until conflicting-writer probe source freezes.
- Remaining required race: actual conflicting publication/restriction outcomes under both writer orders, with a waiter, exact winner/loser, and no partial loser state. Current Goal remains P3b PARTIAL until that, updated final backend/static/security/package/current-source preservation checks and independent evidence review pass.

### 2026-10-29 — PostgreSQL publication conflict acceptance and regression checkpoint

- Resumed from the verified P3b checkpoint at HEAD `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`; cumulative dirty tracked and untracked work was preserved. Re-inspected the latest five previously recorded changed files, current aggregate diff, publication source/qualifiers, roadmap, quality gates, approvals and the owner screenshot audit. No reset, overwrite, commit, deployment, original DB write, real identity/data, cloud operation or destructive cleanup.
- Publication/restriction race acceptance: `.venv/Scripts/python.exe -m scripts.postgres_publication_conflict_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output docs/production/local-20261027/publication-conflict-qualification.json` exit 0. Actual generated academic inputs and CP-SAT produced two independently validated `optimal` drafts; fresh PostgreSQL 18.6 cluster `classsync-pg-f767c3b6b82b4230845b898699875c15` stopped. Publication-first observed a real post-review lock waiter, committed revision 2 and caused the restriction to return exact `409 restriction_publication_conflict`; restriction-first observed a real post-expansion lock waiter, committed restriction revision 1 and caused publication to return exact `422 room_restricted`. Before/after snapshots compared all six scheduling tables; loser keys/rows and partial mutations were absent. Evidence: JSON above; portable state-boundary tests are part of the current backend suite.
- Full serial current backend: `.venv/Scripts/python.exe -m pytest services --basetemp %TEMP%/classsync-final-20261029-pytest -o cache_dir=%TEMP%/classsync-final-20261029-cache -q`, with both application SQLite environment paths redirected to new disposable `%TEMP%` files: **901 passed in 81.52s**, one existing Starlette/httpx deprecation warning. The initial attempt used a cache directory that did not exist, exited 4 before collection, and ran no tests; created only the new temporary test/cache directories and reran successfully. No solver test overlap.
- Current checks: Ruff `services packages` plus the publication repository/resource/scale/conflict qualifiers passed; `pip check` reported no broken requirements; `npm run test:security` **16/16 passed**; `git diff --check` exited 0 (Git reported existing LF-to-CRLF working-copy advisories). No frontend, build or browser checks rerun because this checkpoint changed no product/frontend source. Existing frontend/build/browser screenshots remain historical, not fresh UX verification.
- Original DB SHA256 re-read: `var/academic.sqlite3` `4cd5f60de21bd365c914ac01e5be692b3bea1c7a56a7f17a76c6953ef8668738`; `var/scheduling.sqlite3` `1848377cc9a9eb656e12b5e58436e81198fef92f18dd71c1fea2f6f8b482e400`; `var/backups/scheduling-before-s2b-20261018074057.sqlite3` `9ec149413d69c1165b74a75e366fa262417c1ecbf41e7029fdd0d86ac96f395d`. All match recorded originals. Fresh actual-qualification evidence reports owned PG stopped.
- Publication application repository's bounded acceptance matrix is now covered by actual repository, direct helper authorization, compatible and conflicting writer ordering, rollback/failure/replay/revision, resource, and bounded-scale qualifications. This does **not** complete P3b: Scheduling's institutional HTTP/provider currently deliberately returns unavailable for PostgreSQL publication routes; publication history data migration/restore and provider/API composition remain open. Do not claim complete publication service or full P3b. Independent final source/evidence review is pending.
- UX recovery track remains high priority and is integrated in `ROADMAP.md` from the audit at `ClassSync_UIUX_Screenshot_Audit_2026-10-28.md`: connected timetable failure diagnosis; truthful presentation mode; Student home; Teacher requests; Administrator setup/scheduling; navigation/copy reduction. No UX source change or new screenshot is claimed in this backend checkpoint. Resume with scoped provider/history migration acceptance after reviewer feedback, then take the first dependency-ready UX slice only after its predecessor gate passes. Goal remains ACTIVE/incomplete; production remains NO-GO.

### 2026-10-29 00:53 Asia/Singapore — presentation connection status recovery (interim)

- After repository-level PG acceptance passed, implemented one isolated UI recovery item from the owner audit: `RoleScheduleWorkspace` now announces “reconnecting” only when a published timetable has loaded and its live connection is lost. Review and offline presentation samples cannot inherit a stale disconnected flag and imply live synchronization. `shouldAnnounceConnectionLoss` is a pure shared predicate with 5 direct positive/negative mode-state tests in `workspace-context.test.ts`.
- Targeted `npm run test --workspace=@classync/web -- src/lib/workspace-context.test.ts`: **5/5 passed**. Frontend `npm run lint --workspace=@classync/web` and `npm run typecheck --workspace=@classync/web` completed with no diagnostics. Full `npm run test:web`: **712 passed, 40 files**, 162.18s using the configured two-worker cap; evidence log `publication-and-presentation-final-web.log`. No test skipped or relaxed.
- Actual screenshot/browser review could not be performed: `cua.getState()` returned no browsers/apps and `Browsers: Local browser use is disabled in Work settings`. No before/after screenshot or manual keyboard/screen-reader/zoom claim is made. The component's rendered appearance and assistive-technology interaction remain unverified pending browser availability.
- Independent read-only PG source/evidence review found no concrete transaction/security/data-integrity defect. A second narrow review found no issue in the UI status predicate: the status is appropriate for a loaded published timetable, its `role=status` remains, and review/presentation exclusions are tested. No browser test was run. The PG review supports **repository adapter acceptance PASS only**; it explicitly confirmed P3b/provider remains PARTIAL because publication HTTP routes still fail closed under PG and continue to use SQLite repository factories, with history migration/restore unqualified.
- `npm run build` and `npm run build:presentation` both exited 0. Vite reported existing Firebase mixed static/dynamic import and >500 kB bundle warnings in ordinary build; presentation build reported the bundle-size warning. `npm run test:artifacts` **4/4 passed** with actual isolated ordinary, presentation and legacy-preview build/SPA/static/API checks. Logs: `publication-and-presentation-build.log`, `publication-and-presentation-presentation-build.log`; artifact result was emitted by the command.
- Current source changes for this UX slice are `apps/web/src/lib/workspace-context.ts`, `apps/web/src/lib/workspace-context.test.ts`, and `apps/web/src/pages/RoleScheduleWorkspace.tsx`. Existing Git work remains protected. Original SQLite hashes still match the established values in the preceding entry. No actual timetable-service recovery, Student/Teacher/Admin dashboard enhancement, fresh visual comparison, or full P3b exit is claimed. Continue from the dependency-ready provider/history P3b slice and take UX slices that do not falsely claim unavailable service behavior; Goal remains ACTIVE/incomplete and production NO-GO.

### 2026-10-29 — generated 0008 migration rollback/reapply qualification (interim)

- Added the rollback/reapply acceptance to `publication-adapter-acceptance.md` and the existing guarded PostgreSQL repository qualifier. `migration_rollback_rehearsal()` downgrades only the fresh generated cluster from 0008 to 0007, compares full ordered row values for solver runs, drafts, immutable published versions and heads, reapplies 0008, confirms new restriction/audit tables are empty, regrants only generated runtime privileges and checks history plus exact idempotent replay. Evidence explicitly distinguishes this schema rollback rehearsal from original SQLite migration/restore.
- Final command: `.venv/Scripts/python.exe -m scripts.postgres_publication_repository_qualification --bin "C:/Program Files/PostgreSQL/18/bin" --output docs/production/local-20261027/publication-repository-migration-rollback-full-pass.json` exit 0 on fresh PG18.6 cluster `classsync-pg-241705db317349b6aa92d9a90eda1117`, stopped. `upgrade_downgrade_upgrade=true`; all four protected-table SHA256 values, post-re-upgrade history/replay, and restriction revision-1 insert/revision-2 update with exact two-entry audit chain are in the JSON. Generated restriction/audit rows from the pre-rollback state were removed only by the deliberate 0008 rollback on this disposable fixture.
- Probe diagnostics retained: first attempt exposed an omitted SQL table alias; second exposed a session timezone mismatch in JSON row comparison; third exposed a stale pre-rollback expected-state variable later in the existing qualifier. Each was repaired with a focused correction; the final fresh run passed the entire qualifier. All three earlier cluster roots are disposable and their runner has stop-in-finally behavior; the first root was additionally confirmed `pg_ctl: no server running`. No data was cleaned up or deleted.
- Ruff and `py_compile` on the changed qualifier passed; portable publication repository boundary tests **39/39 passed** using fresh explicit basetemp/cache paths. One invocation using pytest's default Windows temp/cache paths yielded 22 passed,17 setup errors from `WinError 5` before test assertions; rerun with fresh explicit paths passed all39. The corrected migration probe then passed the full actual PG qualifier. Independent final review found no remaining issue in the migration rehearsal and confirmed its scoped claims, restored runtime DML/audit path, and stopped cluster. Existing 901-test backend, 712-test web, security16/16, build, artifact and original-hash results remain applicable because only the qualification script and acceptance/status documents changed after those suites; no service product/runtime code changed in this slice.
- P3b is still PARTIAL: this proves schema downgrade/re-upgrade preservation inside PG, not an old SQLite publication-history data migration, restore drill for that history, HTTP/provider adoption, or approval/outbox semantics. Source inspection found a concrete migration compatibility gap: legacy SQLite `published_versions` stores `request_hash` but no canonical `command` or `academic_revision`, while PG publication rows require a command whose digest matches `request_hash` plus the academic revision. Do not invent or rehash a legacy command as if it were original. Next bounded slice: generated-only source fixture and explicit compatibility design that preserves the old hash/key while preventing unsafe replay (or proves a valid recoverable source representation), with exact source immutability, owner mapping, transactional import rollback, backup/restore, and post-restart history/read checks. Use only generated/disposable source and target. Original SQLite hashes remain unchanged; no P4–P8 work within this Goal.

### 2026-10-29 01:39 Asia/Singapore — PostgreSQL publication HTTP composition (implemented, unverified)

- Existing Goal remains ACTIVE; completion boundary P3b only. HEAD `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`; cumulative worktree retained. Added institutional PG repository selection in `publication_api.py`; routed period/history/calendar/stream/availability/publish/restriction paths away from SQLite when PG is configured. Synthetic sandbox paths stay unavailable in PG mode. Repository now checks current role plus student/faculty record binding in the transaction, scopes period/occupancy reads, and rejects a role view if its visible snapshot trails a newer hidden publication.
- Added migration `0009_publication_record_projection.py`: RLS admits a published row only for an active current student enrollment or teacher assignment in that row; a publication head is visible only when its exact version is visible. Added provider binding, no-pool, cross-tenant, route-no-SQLite-fallback and migration policy boundary tests. Actual PG qualifier now targets 0009 and includes generated Student/Teacher/Admin projection, current period, occupied-room and unauthorized-role probes. This does not qualify legacy SQLite publication history migration/restore.
- Targeted command: `.venv/Scripts/python.exe -m pytest services/persistence/tests/test_publication_record_projection_boundary.py services/scheduling/tests/test_postgres_publication_provider.py services/scheduling/tests/test_provider_lifecycle.py services/scheduling/tests/test_identity_stream.py services/scheduling/tests/test_institutional_projection.py services/scheduling/tests/test_postgres_publication_boundary.py -q --basetemp <fresh-temp> -o cache_dir=<fresh-cache>`: **171 passed**, 3.97s; one existing Starlette/httpx deprecation warning. Ruff on all changed implementation/tests/qualifier: pass. `py_compile` on migration, qualifier and service files: pass. `git diff --check`: exit 0; only existing LF-to-CRLF advisories.
- Actual qualification command `.venv/Scripts/python.exe -m scripts.postgres_publication_repository_qualification --bin 'C:/Program Files/PostgreSQL/18/bin' --output docs/production/local-20261027/publication-provider-routes-qualification.json` did not reach application code. Windows `initdb` failed to create its restricted token (error 87; re-exec error 3), then `pg_ctl` failed identically. The runner recorded `not_running_at_cleanup`; independent `pg_ctl status` confirmed `no server running`. This latest attempt predates application of migration 0009 and is not qualification evidence. Do not enable privileged execution or mark the provider PASS on portable tests alone. Independent review of this changed slice is pending.
- Fresh SHA256 recheck matches the established originals: academic `4cd5f60de21bd365c914ac01e5be692b3bea1c7a56a7f17a76c6953ef8668738`, scheduling `1848377cc9a9eb656e12b5e58436e81198fef92f18dd71c1fea2f6f8b482e400`, backup `9ec149413d69c1165b74a75e366fa262417c1ecbf41e7029fdd0d86ac96f395d`. No original database, Git remote, cloud, production identity or deployment operation.
- Status: repository transaction matrix and schema rollback/reapply previously PASS on actual PG; provider composition and migration 0009 are IMPLEMENTED-UNVERIFIED. Full P3b remains PARTIAL. UI/UX audit and the verified presentation-language fix remain preserved; no screenshots/browser checks were available in this turn. Next: resolve local disposable PostgreSQL process startup within the enabled sandbox, execute the new actual qualifier, repair any discovered SQL/route defect, then one independent review and full P3b exit gates. If actual PG remains unavailable, continue portable/full serial regressions and leave exact qualification gate PARTIAL.

### 2026-10-29 01:45 Asia/Singapore — verified-role timetable projection correction

- Resumed the active P3b Goal at unchanged HEAD `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`; inspected the current aggregate diff and latest provider/API/test/documentation edits without altering unrelated work. The prior independent review found a concrete P1 regression: institutional `/periods`, `/calendar` and `/events` always projected as Student. Fixed all three to use the role selected by verified identity claims; the existing PostgreSQL repository still rechecks active current membership and linked record inside its transaction. Event streams use that same role for preflight and terminate on identity/membership changes at reconnect checks. Sandbox preview routes remain on their explicit sandbox-only role input.
- Added HTTP composition coverage across Student, Teacher and Administrator for periods/calendar/events, asserting the role passed to projection and event streaming. Focused regressions (`test_postgres_publication_provider.py`, `test_institutional_projection.py`, `test_identity_stream.py`, `test_publication_record_projection_boundary.py`): **17 passed**, one existing Starlette/httpx deprecation warning. Full scheduling+persistence regression `.venv/Scripts/python.exe -m pytest services/scheduling services/persistence -q`: **703 passed**, one existing warning, 56.61s. Ruff on changed API/tests passed after import formatting; `git diff --check` passed with only Git's existing LF-to-CRLF advisories.
- Fresh PostgreSQL 18.6 acceptance remains **NOT RUN / BLOCKED BEFORE SERVER STARTUP**: the attempted runner fails while Windows creates initdb/pg_ctl restricted process tokens (error 87 / re-exec error 3). No application SQL was exercised by that attempt. Transaction locks, authorization RLS, rollback, idempotency, conflicting publication, revisions and failure behavior have historical actual-PG evidence for the pre-0009 repository, but the current provider composition and migration 0009 are not actual-PG qualified. Do not claim the full PostgreSQL adapter or P3b acceptance complete. Do not repeat the same startup attempt absent a changed, safe local process path.
- Prior unchanged full backend/security/package/build evidence remains historical; this turn ran the current scheduling+persistence subset, not the root-wide backend suite or frontend checks. UI screenshot audit remains read and high-priority in ROADMAP. Browser surfaces remain unavailable; no screenshot/manual UX claim. Presentation-mode wording fix and UI recovery track are preserved, not newly verified here.
- Original academic/scheduling/backup SQLite hashes remain at the recorded baselines from the current session; no original DB writes, migration/cutover, commit, push, deploy or remote/cloud operation. No reset, stash, cleanup or destructive action. Independent route/security re-review is pending. Current provider composition and migration 0009 stay IMPLEMENTED-UNVERIFIED; P3b PARTIAL; production NO-GO. Next authorized P3b work is actual PG qualification when the restricted-token startup issue can be resolved safely, then remaining history migration/restore and exit evidence; do not advance to P4–P8 within the existing Goal.
- Independent follow-up reviewer confirmed the prior P1 is resolved and found no further actionable issue in verified-role routing, membership/record revalidation or stream closure. Reviewer explicitly noted mock route tests do not prove actual PostgreSQL RLS/reconnect behavior; real PG startup remains the outstanding gate. Existing Goal remains ACTIVE; no second Goal was created.
- Follow-up environment check found the installed PostgreSQL Windows service already listening on `127.0.0.1:5432` (`pg_isready`), but a read-only `psql --no-password` connection as the current Windows account failed with `fe_sendauth: no password supplied`. It is not the owned disposable cluster; I did not inspect existing databases or use credentials. This leaves no safe actual-PG runner available in the present sandbox. Corrected stale persistence README and current roadmap checkpoint to say the HTTP/provider and 0009 are implemented but unverified, not unavailable/not yet adopted. `git diff --check` and Ruff were rechecked; no source behavior changed in this follow-up.

### 2026-10-29 01:53 Asia/Singapore — legacy publication archive mapping contract

- Current goal, acceptance spec, STATUS checkpoint, migration source and legacy SQLite/PostgreSQL publication schemas were rechecked. Bounded slice: add `packages/persistence/classync_persistence/legacy_publication_archive.py` and `services/persistence/tests/test_legacy_publication_archive.py`. The mapper requires explicit source tenant/actor to target tenant/owner mapping, validates immutable payload checksum/scope/time/hash shape and uniqueness, preserves the original opaque request hash and payload bytes, and labels results `replayable=False`, `current=False`; it does not fabricate a canonical command or academic revision. No SQL connection or source database path is accepted.
- Tests define happy and negative cases before behavior: exact hash/payload retention and non-current classification; missing owner mapping; duplicate mapped idempotency; invalid hashes/checksum/revision/sequence/timezone; mismatched payload scope. `.venv/Scripts/python.exe -m pytest services/persistence/tests/test_legacy_publication_archive.py -q`: **8 passed**. Ruff and py_compile pass. Traceability row added as IMPLEMENTED-UNVERIFIED converter only.
- No PG archive table/import transaction/backup/restore is claimed. The active local PostgreSQL Windows service is listening on 5432, but the read-only no-password probe was rejected and it is not an owned disposable cluster; no databases or credentials were inspected. The guarded fresh-cluster runner's restricted-token startup blocker remains unchanged. Do not use the service or claim P3b acceptance. Next: define and implement archive-only PG persistence and generated SQLite fixture/transaction/restore probes, then qualify on an owned disposable PostgreSQL cluster when startup is available; provider 0009 actual SQL and P3b final gates also remain open.
- Original SQLite files were not accessed or modified in this slice; cumulative dirty tree preserved; no Git/cloud/production action. Goal remains ACTIVE and P3b PARTIAL.

### 2026-10-29 — publication archive downgrade race review

- Resumed from the existing dirty worktree and HEAD `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`; inspected the latest five modified source paths by filesystem timestamp plus the current Git status/diff inventory. Existing user changes were preserved. The requested `UIUX_SCREENSHOT_AUDIT_2026-10-28.md` filename is absent; read `ClassSync_UIUX_Screenshot_Audit_2026-10-28.md`. The recovery track is already in ROADMAP, and the 26 Oct P2–P8 local authorization remains recorded in APPROVALS.
- Independent review identified a downgrade race in migration `0010_legacy_publication_archive`: an importer might commit after the empty-table check but before `DROP TABLE`. Added an `ACCESS EXCLUSIVE` table lock before checking for retained rows and a regression assertion that the lock precedes the check. This serializes archive inserts against the guard/drop. Changed in this slice: `packages/persistence/classync_persistence/migrations/versions/0010_legacy_publication_archive.py`, `services/persistence/tests/test_legacy_publication_archive.py`, and this status record. Broader user diffs remain untouched.
- Portable acceptance cases: exact archive retry is a no-op; conflicting keys roll back; inactive/non-admin authorization is denied; downgrade source orders the lock before retained-evidence check. Focused tests: `.venv/Scripts/python.exe -m pytest services/persistence/tests/test_legacy_publication_archive.py -q` — **11 passed**. Persistence regression: `.venv/Scripts/python.exe -m pytest services/persistence -q --basetemp $env:TEMP/classsync-final-persistence --override-ini cache_dir=$env:TEMP/classsync-final-pytest-cache` — **373 passed**, one existing Starlette/httpx deprecation warning. Ruff on migration/test/qualification script passed; `git diff --check` passed with existing line-ending advisories.
- Actual-PG qualification attempted with `.venv/Scripts/python.exe -m scripts.postgres_publication_repository_qualification --bin 'C:/Program Files/PostgreSQL/18/bin' --output docs/production/local-20261029/publication-repository-qualification.json`. It stopped before application tests: `pg_ctl: could not create restricted token: error code 87` / `could not start server: error code 3`. No qualification evidence was produced. The separate PostgreSQL Windows service was not accessed. Therefore the lock race fix is not demonstrated under actual concurrent PostgreSQL transactions; authorization, rollback, idempotency, competing publication, revision conflict and failure gates at current migration 0010 remain unproven. Do not claim the adapter complete.
- Reviewer confirmed the ACCESS EXCLUSIVE ordering closes the writer/drop race but noted only source-ordering tests exist; actual PostgreSQL concurrency remains unverified. Reviewer also found importer provenance is caller-attested: `rows` and `source_fingerprint` are supplied independently, so their relationship is not cryptographically bound by the importer. The generated probe binds its own disposable fixture; broader source provenance remains an open limitation. No further authorization or active-schedule mutation issue was found in the inspected archive code.
- No original SQLite database or records were opened or modified; no existing PostgreSQL database/service was queried; no commit, external change, deployment or destructive operation occurred. No UI source was changed in this slice and no fresh browser screenshot is claimed. UI recovery stays queued per roadmap until this backend acceptance gate can run safely. Next task: obtain an unprivileged owned disposable PostgreSQL runner, then run the complete publication-repository qualification including archive transaction concurrency; if unavailable, continue only independent authorized local work without marking P3b passed.
- Follow-up runner diagnosis: `docker`/`podman` are absent and WSL has no installed distribution. A generated-only probe launched PostgreSQL 18.6 `postgres.exe` directly (bypassing `pg_ctl`'s restricted-token startup path), confirmed the server became ready on a random loopback port, then `psql` failed SSPI with `could not acquire SSPI credentials: No credentials are available in the security package (8009030e)`. `pg_ctl stop -m fast` successfully stopped that exact marked temporary cluster. This proves the current sandbox lacks both the required process-token operation and client SSPI credentials; no trust/password fallback was used. No tracked source changed in this follow-up; generated cluster remains stopped under the temp directory. Actual publication acceptance remains unrun.
- Revalidated that exact generated cluster using its marker and `pg_ctl status`: **no server running**, no `postmaster.pid`. Attempted current persistence-wheel packaging from a clean temporary source copy to avoid touching existing build artifacts; `pip wheel --no-deps --no-build-isolation` stopped during metadata preparation because this venv has no installed `setuptools` backend (`Cannot import 'setuptools.build_meta'`). No dependency was installed because package index/network use is unavailable in the restricted environment. Existing `packages/persistence/build` contains only old migrations through `0005`, so it is not evidence for `0010`. Package acceptance remains open alongside actual PostgreSQL acceptance.

### 2026-10-29 — isolated persistence wheel recovery

- Created isolated venv `%TEMP%\classsync-wheel-venv-c927ee52cab442869873a143afaf8447`; after sandbox package-index access failed, installed the declared `setuptools>=75` build backend there (84.2.1). The repository `.venv`, dependency files and lockfiles were not changed.
- Copied `packages/persistence` to a clean temporary source tree (excluding stale `build`, egg-info and bytecode), then ran `pip wheel --no-deps --no-build-isolation`. Result: **PASS**, `classync_persistence-0.1.0-py3-none-any.whl`, SHA256 `8a71bc5305eecc0eb95066ca7b606b948b061c05e5792c63facd00c4528bfddd`. Inspected the wheel: all 19 Python files compile; migration `0010_legacy_publication_archive.py` is included; wheel metadata declares SQLAlchemy, Alembic and Psycopg dependencies. The earlier missing-setuptools finding is resolved for isolated packaging.
- PostgreSQL still cannot authenticate in this Codex sandbox. The same qualification is ready for the owner's interactive Windows PowerShell session, where the verified Windows SSPI identity is available. Safe command (uses the existing `.venv`, a new evidence filename, and the guarded harness's fresh marked temp cluster):
  ```powershell
  Set-Location 'C:\Projects\ClassSync'
  & '.\.venv\Scripts\python.exe' -m scripts.postgres_publication_repository_qualification --bin 'C:\Program Files\PostgreSQL\18\bin' --output 'docs\production\local-20261029\publication-repository-qualification-interactive.json'
  ```
  The output's parent exists and that output file is absent. The harness uses a random nondefault loopback port, SSPI-only generated mapping, no password/trust, writes only under its new `%TEMP%\classsync-pg-*` root, and stops only its own server. Command not run here because this process lacks SSPI credentials.
- Current HEAD remains `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`; no project source, original database, or tracked dependency file changed in this slice. P3b remains PARTIAL pending actual interactive PostgreSQL qualification, archive backup/restore evidence and final phase-exit checks.

### 2026-10-29 — fix confirmed Alembic version capacity failure

- Owner's interactive qualification reached PostgreSQL migrations and failed SQLSTATE `22001` while stamping `0009_publication_record_projection` into `VARCHAR(32)`. Actual graph has ten linear revisions; lengths are 13,24,21,29,21,22,22,29,34,31 respectively. No additional planned revision IDs are defined in the graph. `env.py` uses transactional DDL and `schema.migrate` requires a caller-owned PostgreSQL transaction. The disposable harness creates `alembic_version` under the same non-superuser/non-BYPASSRLS migration owner that upgrades 0009.
- Added `ALTER TABLE public.alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)` as the first operation in 0009, before policy DDL and Alembic's subsequent stamp. Downgrade deliberately retains capacity. No revision IDs, stamps, Alembic configuration options or earlier qualified revisions changed. README records the enforced <=128 identifier/parent rule and <=32 pre-0009 rule.
- Red/green portable regression: first-operation test failed on original 0009, then passed with the fix. `.venv/Scripts/python.exe -m pytest services/persistence/tests/test_migration_revision_capacity.py services/persistence/tests/test_publication_record_projection_boundary.py services/persistence/tests/test_identity_boundary.py -q`: **11 passed**. Targeted Ruff, qualifier py_compile/help, and diff whitespace checks pass. These are portable proofs only.
- Added `scripts/postgres_revision_capacity_qualification.py` for real generated-cluster SQLSTATE22001 reproduction at 0008 in a savepoint; capacity+stamp transactional rollback; incremental 0008→0009→0010; downgrade to0008/re-upgrade retaining128; downgrade tobase then clean version-table creation/base→head. Its only explicit table drop is the empty generated Alembic table after a base downgrade on the fresh marked disposable cluster. **Actual PG probes NOT RUN in this sandbox**, which lacks SSPI credentials; owner must run the focused qualifier then the publication qualifier. Full P3b remains PARTIAL. Original databases and unrelated user diffs preserved; no Git/cloud/deployment operation or UI change.
- One focused independent reviewer found no concrete blocking source defect in the widening, transaction/ownership compatibility, downgrade capacity or qualification coverage. Reviewer explicitly withheld actual PostgreSQL acceptance pending interactive execution.

### 2026-10-29 — correct 0010 canonical namespace and qualify chain

- Owner's interactive capacity/migration qualifier is **FAILED**, exit1, at0010 with `InvalidSchemaName` / SQLSTATE3F000; the subsequent publication qualifier was **NOT RUN**. That failure remains historical evidence. Root cause: 0010 and archive importer SQL incorrectly used `classync_scheduling`/`classync_identity`. Canonical schemas are `classsync_identity` (created0001), `classsync_academic` (0004) and `classsync_scheduling` (0006). Linear graph0001→0010 already declares dependencies correctly; no new schema, revision rename, manual stamp or earlier qualified revision rewrite is needed. 0009 still widens version capacity before its 34-character stamp.
- Corrected all archive SQL namespace references in migration0010 and `legacy_publication_archive.py`, including FK targets, policies, trigger functions, regclass, reads/inserts and downgrade. Reused0008's current-authority locking helper instead of direct SELECT FOR SHARE, and removed unnecessary FOR UPDATE on immutable archive rows: both would otherwise require forbidden runtime UPDATE grants. Runtime retains only SELECT/INSERT plus explicit helper EXECUTE; no broader grants added. One focused independent review found the archive calendar CHECK could pass NULL; fixed with COALESCE and matching importer dict validation, adding missing/null/scalar/list negative tests. No additional reviewer loop.
- New `test_migration_namespace_contract.py` failed twice against the old migration/importer, then passes against the correction; it checks namespace creation ordering in the complete graph, upgrade/downgrade references, and absence of DROP SCHEMA CASCADE. Updated existing archive mock/contract tests to canonical SQL and helper/no-row-lock behavior. Targeted command: `.venv/Scripts/python.exe -m pytest services/persistence/tests/test_migration_namespace_contract.py services/persistence/tests/test_legacy_publication_archive.py services/persistence/tests/test_migration_revision_capacity.py services/persistence/tests/test_publication_record_projection_boundary.py -q`: **23 passed**. Targeted Ruff and py_compile pass. No unrelated full suite or frontend gate was run.
- Extended `scripts/postgres_revision_capacity_qualification.py` (still guarded fresh marked SSPI cluster only): reproduces missing-schema3F000 and capacity22001 inside savepoints; cleanbase→head and0008→0009→0010; capacity128; injected0010 transaction failure; schema/table/sequence/function ownership, PUBLIC ACL denial, fixed SECURITY DEFINER search_path, archive ENABLE/FORCE RLS; current Admin insert/replay; wrong tenant/UID/project/non-admin/missing-identity denial; runtime CREATE/UPDATE denial; cross-schema FK/checksum/calendar constraints and immutable mutation/truncate denial; empty downgrade/re-upgrade and nonempty downgrade rejection preserving archive and revision. **Actual PostgreSQL checks remain NOT RUN here**, because Codex lacks SSPI credentials. The owner must run the new evidence filenames below; portable results are not SQL acceptance.
- Built the corrected persistence wheel from a clean temporary source copy using the isolated setuptools venv: **PASS**, SHA256 `20cc99ae5983a84f25da19809cadb36defbb65507213af304abc7e2bd443f11b`; all19 Python files, including all ten migrations, compile and byte-match current source. README documents namespace/ownership and downgrade limits. Existing scheduling restore manifests cover identity/academic/drafts, not the new publication/archive tables: full archive backup/restore remains an explicit P3b gap, not a passing legacy drill.
- Changed files: migration0010, archive importer, its tests, new namespace tests, revision-capacity qualifier, persistence README, STATUS. HEAD unchanged `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`; unrelated dirty worktree preserved. No original databases opened/written; no installed PostgreSQL service, production config, Git/cloud/deployment operation. UI/UX recovery remains preserved in ROADMAP. P3b **PARTIAL**, pending actual chain/publication, restore and exit gates. Fresh interactive outputs: `docs/production/local-20261029/migration-chain-0010-schema-fixed.json`, then `publication-repository-0010-schema-fixed.json` (both absent when checked).

### 2026-10-29 — confirmed publication RLS recursion, forward correction

- Read both owner stability/RLS directives. Inspected saved `migration-chain-0010-schema-fixed.json`: actual PG18.6, all migration/archive acceptance flags true and `stopped:true/server_state:stopped`. This supersedes pending migration0010 status. Publication's named output file is absent (the harness writes that output only on success); owner supplied the failed INSERT RETURNING stack root: `InvalidObjectDefinition`, infinite recursion on published_versions, SQLSTATE42P17. Publication acceptance remains **FAILED** for that attempt.
- Exact cycle: 0007 `published_versions.publication_create` WITH CHECK reads publication_heads; 0009 `publication_heads.publication_read` USING reads published_versions. INSERT RETURNING expands both write/read policy paths and recurses. Version SELECT's own membership/record predicate is not removed. Existing deployment authority is local/disposable only; no rollout is recorded. Added forward `0011_publication_policy_cycle` after already-qualified0010 instead of rewriting those revisions. It changes only `publication_create` to current active Administrator+tenant/project+owner checks without a head subquery. Existing unique revision keys, owner FK, immutable-owner/single-step head trigger and deferred version→head check continue enforcing atomic sequencing. No RLS, RETURNING, grants, hard constraints or role projections removed; no helper/service added. Downgrade restores the exact known-recursive prior predicate and is explicitly unsuitable for publication service at0010.
- Added `test_publication_policy_cycle.py`; its initial corrective-migration test failed before implementation. Updated both disposable qualifiers' head to0011. The publication qualifier now downgrades only0011 on its empty generated publication tables, records actual pg_policy/pg_get_expr, owner and FORCE RLS catalog, reproduces old42P17 under the non-superuser runtime using EXPLAIN INSERT DEFAULT VALUES RETURNING, upgrades0010→0011, asserts only the intended policy changed and that INSERT RETURNING planning succeeds. Existing subsequent real repository publish/head/history/calendar/Student/Teacher/authority/concurrency/rollback/replay probes remain mandatory. Added direct populated-version/head SELECT denials for seven missing/wrong tenant/UID/project/role/record contexts. These new actual SQL probes are **IMPLEMENTED-UNVERIFIED**, not performed in this sandbox with missing SSPI credentials.
- Targeted tests: `.venv/Scripts/python.exe -m pytest services/persistence/tests/test_publication_policy_cycle.py services/persistence/tests/test_publication_record_projection_boundary.py services/persistence/tests/test_publication_state_boundary.py services/persistence/tests/test_publication_repository_boundary.py services/persistence/tests/test_migration_namespace_contract.py services/persistence/tests/test_migration_revision_capacity.py -q` — **76 passed**, one existing Starlette/httpx warning. Targeted Ruff passes. One focused independent reviewer found no blocking source defect; explicitly withheld actual PG acceptance. No full/frontend regression repeated.
- Corrected wheel built in isolated temporary source/venv: **PASS**, all20 Python files including0011 byte-match current source and compile; SHA256 `d11c3bed5692a3a9917139966b5b794d0ee33427ee65ae7ff521d7fdf28d1c77`. Fresh SHA256 checks match all three recorded originals (academic, scheduling, backup) in `p1-database-preservation.json`; no original DB mutation or installed cluster access. HEAD remains `39200a4f2ef3ec7557bc3c86127e674e260ca4fc` and unrelated dirty work preserved.
- Files: new0011 migration/new policy-cycle tests, both qualification scripts, persistence README, ROADMAP, STATUS. Next: owner runs fresh `migration-chain-0011-rls-fixed.json`, then `publication-repository-0011-rls-fixed.json`. P3b **PARTIAL** pending actual current policy/publication acceptance, publication/archive restore and remaining phase-exit checks. UI/UX recovery preserved; no next phase, commit/push/deploy/cloud action.

### 2026-10-29 — Student publication qualification fixture linkage

- Saved `migration-chain-0011-rls-fixed.json` confirms migration-chain **PASS** and owned cluster stopped. Owner's subsequent publication qualification remains **FAILED**, now at Student calendar `projection_forbidden` after the RLS-cycle correction. Its requested output JSON is absent because the harness only writes that output on success; failure root is supplied by the owner, not inferred as a service outage.
- Confirmed cause: `complete()` saves academic constraints without enrollments; `academic_readiness` copies `rules.enrollments` into the generated input (`academic_input.py:244`), so the published draft contains no student-a enrollment. Verified uid-student→active tenant-a/student-a membership succeeds; 0009 RECORD_SCOPE then hides the version and its corresponding head. `calendar` correctly rejects `not visible or visible[-1].revision != current` (`postgres_publication_repository.py:204`). The qualifier's mock_section did not authorize that missing relationship. No product guard, RLS policy, record lookup or migration was changed.
- In `scripts/postgres_publication_repository_qualification.py`, added generated enrollment via the existing academic repository before solver/hash/draft creation: student-a→section-a offerings, student-other→section-b offerings. Added same-disposable-cluster identities for the other/unassigned Student. Removed mock_section. Also corrected the confirmed Teacher fixture mismatch: membership faculty-a differed from generated teacher-a/teacher-b; generated identity is now explicitly linked to an actual assignment's faculty ID using an audited, revisioned fixture membership update. These remain wholly synthetic fixtures, not institutional mappings.
- Actual qualifier now requires nonempty enrollment in the saved draft, checks Student offerings remain within that enrollment, disjoint Student section views, unassigned denial, revoked membership denial with audited restoration, and exact assigned Teacher filtering. Existing wrong-context, admin, head/version, stale-revision/conflict/concurrency/rollback/replay checks remain mandatory. New portable `test_publication_projection_fixture.py` reproduces the old empty-enrollment input, verifies persisted enrollment/revision/hash change across reload, and confirms the guard rejects hidden-current/older-visible snapshots. Command `.venv/Scripts/python.exe -m pytest services/persistence/tests/test_publication_projection_fixture.py services/persistence/tests/test_publication_repository_boundary.py services/scheduling/tests/test_institutional_projection.py -q`: **47 passed**, one existing Starlette/httpx warning. Targeted Ruff and py_compile pass. No unrelated frontend/full regression.
- Fresh SHA256 comparison matches all three originals in `p1-database-preservation.json`; no original data was opened through SQLite or modified. Current source change scope is the qualifier/new portable test and STATUS. Real PostgreSQL Student/Teacher acceptance is **NOT RUN here** (sandbox SSPI unavailable), so this is an implemented fixture correction, not a closed actual-PG acceptance claim. Next single command: `.venv/Scripts/python.exe -m scripts.postgres_publication_repository_qualification --bin 'C:/Program Files/PostgreSQL/18/bin' --output docs/production/local-20261029/publication-repository-student-enrollment-fixed.json` in interactive PowerShell; output verified absent. P3b **PARTIAL** pending that actual publication gate, publication/archive restore and final exit checks. UI/UX backlog and unrelated work preserved; no commit/push/deploy/cloud or original-database operation.
- One focused security reviewer found no blocking fixture/source defect and confirmed the unchanged RLS/guard correctly denied the original unenrolled Student. Accepted its optional assertion clarification: identify allowed offerings by student_id rather than enrollment list position. Actual PG acceptance remains pending.

### 2026-10-29 — narrow SQLite fallback mock to PostgreSQL publication operations

- Confirmed harness defect: the sole sqlite3.connect patch in the publication qualifier enclosed nearly all of `exercise`, including `legacy_archive_probe`'s legitimate generated-source setup. Relevant imported qualification helpers have no sqlite3.connect patch. The owner attempt `publication-repository-student-enrollment-fixed.json` remains **FAILED**; its output JSON is absent because only successful qualification writes it. The actual owned cluster's `qualification.json` at `%TEMP%/classsync-pg-dc04125547914ad58f1bd6bbeda1ddde` records `exercise_error: SQLite fallback prohibited`, `server_state: stopped`. Validated that exact marker, then `pg_ctl status`: exit3/no server running, no postmaster.pid. No other cluster/process was touched.
- In `scripts/postgres_publication_repository_qualification.py`, restricted the existing patch context to the initial PostgreSQL `repo.publish(commit=False/True)` operations and their no-write/atomic assertions. All other phases, including generated archive setup/import, now execute after the context restores sqlite3.connect. Outer try/finally engine cleanup, archive marked-root/fixed-new-file validation, ownership, immutability and production repository selection remain unchanged. No bypass/original-connect alias was introduced.
- Added `services/persistence/tests/test_publication_sqlite_mock_scope.py`. It executes the actual qualifier patch AST block with controlled operations: fallback explicitly raises; successful/application-failing/fallback-failing contexts all restore the original function; generated marked-root SQLite source creation/read succeeds afterward. It asserts archive/fixture phases are outside that patch and rejects an external/unmarked archive root before SQLite can open. Focused source self-review confirmed the remaining body was only dedented and existing finally cleanup retained; no separate reviewer loop for this harness-only scope correction.
- Command `.venv/Scripts/python.exe -m pytest services/persistence/tests/test_publication_sqlite_mock_scope.py services/persistence/tests/test_publication_projection_fixture.py services/persistence/tests/test_publication_repository_boundary.py services/scheduling/tests/test_institutional_projection.py -q`: **51 passed**, one existing Starlette/httpx warning. Targeted Ruff, py_compile and diff whitespace checks pass. Fresh hashes match all three originals in `p1-database-preservation.json`. No original SQLite DB connection/write, production change, Git/cloud operation or unrelated suite. Changed files: qualifier, new mock-scope tests, STATUS.
- Actual full PostgreSQL acceptance remains **PENDING** (sandbox lacks SSPI), not PASS. Next single interactive command: `.venv/Scripts/python.exe -m scripts.postgres_publication_repository_qualification --bin 'C:/Program Files/PostgreSQL/18/bin' --output docs/production/local-20261029/publication-repository-sqlite-scope-fixed.json` (output absent). P3b remains **PARTIAL** pending publication/archive/restore and final exit gates; Student/Teacher/RLS controls and UI/UX recovery roadmap preserved.

### 2026-10-29 — publication repository actual acceptance PASS

- Read actual `docs/production/local-20261029/publication-repository-sqlite-scope-fixed.json`: migration0011, PostgreSQL18.6, both actual solver statuses optimal; runtime publication/replay/history/projection/reconnect, current-role/tenant/project/record denial, direct read denial, observed competing publication and restriction lock orders, exception/audit rollback, stale academic/hash/head checks, authority locks, bounded pool/permission failure recovery, immutable corruption rejection, migration rollback/reapply and archive preservation/idempotency checks all complete successfully. `stopped:true`, `server_state:stopped`, no exercise_error. Publication repository acceptance at current unchanged application source is **PASS**. Passing evidence explicitly excludes provider/HTTP/browser composition and full publication/archive restore; those are not inferred as passed. P3b remains PARTIAL. Do not rerun this full qualifier without an invalidating source change.

### 2026-10-29 — actual publication/archive restore and provider HTTP PASS

- Added `scripts/postgres_publication_restore_qualification.py` using existing marked-cluster tools, academic/draft/publication fixtures, catalog queries, new restore database guard, dump/TOC hashing and transactional pg_restore. It generates new inputs/two published versions/head/restriction audit/archive; it does not repeat the full publication qualification. Actual command `python -m scripts.postgres_publication_restore_qualification --bin 'C:/Program Files/PostgreSQL/18/bin' --output docs/production/local-20261029/publication-archive-restore.json` **PASS**, owned cluster stopped. All17 tables' complete ordered data, sequence state and17 catalog categories match after restore, including opaque request hash/payload and explicit owner mapping. Restored exact replay/history/draft/three-role calendars, negative contexts, archive changed-retry rollback, no mutation grants, immutability and reconnect pass; source/restored state and dump/TOC hashes remain unchanged. Archive stays outside active timetable and non-replayable. Same-cluster restore only; institutional provenance/cross-host recovery unclaimed. Seven portable manifest/target/output guard tests pass.
- Added `scripts/postgres_publication_provider_qualification.py` and fixed `--publication` mode to the existing owned Auth runner allowlist (plus its allowlist test). Actual command `node scripts/auth_emulator_qualification.cjs --tools-root <existing reviewed pinned temp root> --postgres-bin 'C:/Program Files/PostgreSQL/18/bin' --output docs/production/local-20261029/publication-provider-http.json --publication` **PASS**. Real emulator SDK token verification/current-PG membership/owned pool/ASGI HTTP review/publish/replay/admin history and all three role periods/calendars; unassigned/unbound/wrong-role/revoked denials; no SQLite fallback and lifecycle cleanup. JSON reports authStopped:true, deniedOutbound:0 and PG stopped:true/server_state:stopped. No real Firebase/cloud credentials/configuration. Portable affected provider/restore tests64 pass; runner allowlist tests2 pass. New TCP/browser UI journeys are not claimed.
- Final serial `.venv/Scripts/python.exe -m pytest -q --basetemp <fresh-temp> -o cache_dir=<fresh-cache>`: **947 passed**, one existing Starlette/httpx deprecation,72.89s (`p3b-backend-exit.log`). Ruff services/packages/new scripts pass; pip check passes; npm security16 pass. Exact Python pip-audit2.10.1 scans68 versions/zero findings (`p3b-python-audit/`); npm audit zero findings (`p3b-npm-audit.json`). Both internal wheels build in clean temporary copies with isolated setuptools: contracts11 Python files/persistence20 files compile and match current source, all11 migrations included; wheel SHA256 contracts `fd75b209794100b4663541fa958d4916e7bd022be274080bbbc9dec5b85a3f90`, persistence `fc9438585257330b4a2d4730811c5454456457bf91b85ab8340782595b432781`.
- Fresh original academic/scheduling/backup hashes match `p1-database-preservation.json`; all113 marked PostgreSQL temp roots checked, no running owned server. One independent focused P3b exit review found no blocking source/evidence defect in this bounded scope; retained limits: same-cluster restore, ASGI HTTP, generated/caller-attested legacy provenance and no production/cutover authority. Reviewer requested final frontend/build results and stale documentation reconciliation before declaring P3b exit.
- Final frontend lint/typecheck passed. First `npm run test:web` attempt **FAILED** with spawnSync ETIMEDOUT and no test results (`p3b-web-test-web.log`); unchanged command now retried outside the restricted token using the same timeout/worker settings (`p3b-web-test-web-retry.log`). No test weakening or solver changes. Builds/artifacts await that result. P3b still **PARTIAL** pending this last exit gate; full publication PASS not invalidated. Documentation-only runtime module docstring cleanup does not alter executable code; stale provider/archive acceptance wording superseded.

### 2026-10-29 — bounded local P3b exit PASS; stop at milestone

The final unchanged web retry **PASS**,712 tests/40 files in143.23s. Final `npm run build`, `npm run build:presentation` and `npm run test:artifacts` **PASS** (all4 artifact checks; production metadata, direct SPA refresh and static/API errors). Lint/typecheck pass. First failed web timeout remains in its original log. No timeout, worker, assertion, solver or production dependency changes. Vite's >500kB chunk/mixed Firebase-import warnings and the existing Starlette/httpx deprecation remain disclosed nonblocking observations.

| Approved P3b requirement                                                                                                   | Final status | Authoritative evidence                                                                                                                                                                                                                       |
| -------------------------------------------------------------------------------------------------------------------------- | ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Actual PostgreSQL publication; current identity/tenant/role/record scope; immutable revision/head state                    | PASS         | `publication-repository-sqlite-scope-fixed.json`, migration0011; actual SDK/current-PG `publication-provider-http.json`                                                                                                                      |
| Restriction/publication serialization; rollback; conflicting writes; exact replay; freshness; restart/reconnect and errors | PASS         | Actual observed lock orders and precise failures in publication JSON; previously qualified draft/provider restart retained; restored reconnect/replay verified                                                                               |
| Generated migration and legacy compatibility; hashes; ownership; rollback                                                  | PASS         | Prior generated academic/draft migration evidence retained; actual0011 chain/publication rollback; archive opaque hash/payload/owner mapping, no canonical preimage fabricated, non-current/non-replayable                                   |
| Complete publication/archive backup and restore                                                                            | PASS         | `publication-archive-restore.json`:17 nonempty/related tables,17 catalog categories/sequence equality, role calendars/history/replay, RLS/grants/immutability and unchanged source/dump                                                      |
| Current provider/API composition and role calendars                                                                        | PASS         | `publication-provider-http.json`: actual Auth Emulator SDK/current membership/owned PG pool/ASGI HTTP; admin publish/replay/history, three-role calendars/periods, unassigned/unbound/wrong-role/revoked denial, no SQLite fallback, cleanup |
| Final regressions/static/security/package consistency                                                                      | PASS         | backend947, frontend712/40, security16, artifacts4; lint/types/builds/Ruff/pip-check; Python68 exact/0 findings, npm0; both byte-matched wheels/all11 migrations, graph single head0011                                                      |
| Original databases and owned process preservation                                                                          | PASS         | All3 SHA256 baselines match. All113 marked PG roots checked,0 running; one stale PID marker independently returned pg_ctl exit3/no server. No files deleted. All owned Auth/PG service cleanup recorded                                      |
| Independent review and truthful limitations                                                                                | PASS         | One focused independent exit reviewer: no blocking defect. Same-cluster restore, ASGI HTTP, generated/caller-attested source provenance; no cross-host DR/new browser acceptance/production cutover claimed                                  |

Current-source hashes (65 files), qualification SHA256s, exact gate counts, original hashes and process check are in `docs/production/local-20261029/p3b-exit-evidence.json`; command logs are adjacent. Runtime behavior did not change during this closure; new source is disposable restore/provider qualification and guard tests, plus the fixed emulator runner mode. Documentation/traceability supersede stale pending checkpoints. Full publication qualifier was not rerun. Original data, unrelated user diffs and HEAD `39200a4f2ef3ec7557bc3c86127e674e260ca4fc` preserved; no commit/push/deploy/cloud/real Firebase change.

**P3b PASS for the approved bounded local scope.** Production release and original-data cutover remain unauthorized/NO-GO. Institutional authority, real people/data, production IAM/TLS/infrastructure, cross-host disaster recovery and the P4–P8 features remain outside this completed Goal (not claimed implemented). The UI/UX recovery audit/roadmap remains intact for the next separately bounded task. Stop automatic development here.

### 2026-10-30 02:32 Asia/Singapore — P4a/P4b PARTIAL; bounded stop

- Owner authorized connected recovery + Student experience, preserving P3b and excluding P4c/P4d. Read current instructions/autonomy/audit/source before changes; acceptance written first in `P4_ACCEPTANCE.md`. Base/current HEAD remains `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`; prior dirty work preserved.
- IMPLEMENTED: configured Firebase email/password entry and verified Student continuation; current-membership guarded Student routes; narrow same-origin token/Student-role GET periods/calendar client with token+read timeout, cancellation and no sample fallback; actual-data Student Home, agenda/week/version/changed flags/rooms; honest empty/denied/unavailable states; shared nav hides planned destinations and connected nav exposes working Home/Schedule/Rooms. Original institutional write clients remain closed and all server authorization unchanged. Corrected dashboard requests to current Monday through +62days, preserving the63-inclusive-day server limit.
- Files: `pages/StudentHome.tsx`, `pages/student-home.css`, `lib/student-timetable-api.ts`, `lib/use-schedule-workspace.ts`, `routes/RouteGuard.tsx`, `components/layout/AppShell.tsx`, `pages/AuthPage.tsx`, `auth/UniversitySessionPanel.tsx`, `pages/OperationsPreviewPage.tsx`, connected error copy in `RoleScheduleWorkspace.tsx`, mode description; focused tests; owned Student browser/PG qualification scripts and fixed Auth runner allowlist/tests. No services/packages implementation changed in this phase. See `P4_EVIDENCE.md` for file-level behavior, source limitations and complete commands/failures.
- VERIFIED positives: actual owned demo Auth SDK sign-in/current-PG membership → TCP Gateway/Scheduling periods200/calendar200 → published Student Home/version/classes, all360/390/768/1024/1440 screenshots/no overflow, Enter/details/Escape/focus restoration, room navigation/unknown availability. These are generated authorized fixtures, not institutional records. Connected and presentation desktop/mobile images inspected. Presentation production-artifact browser separately passes all five widths, zero API requests/runtime/console errors, keyboard/details/rooms/deep refresh.
- Automated checks: final relevant frontend **50/9 files PASS** (`p4-relevant-final.log`); subsequent empty-copy **7 PASS**; isolated Admin/verified-role **7/2 PASS**. Lint/typecheck PASS. Fresh-temp backend projections/publication/Gateway authorization **125 PASS**, one existing Starlette/httpx warning (`p4-backend-regressions-fresh.log`). Auth runner allowlist **2 PASS**, targeted Ruff and diff whitespace PASS. Institutional/presentation builds PASS; all4 artifact checks PASS. Existing chunk-size/mixed Firebase warnings retained; dependencies unchanged, no new audit claimed.
- NOT PASSED: full web run timed out at unchanged300s and recorded an Admin readiness timing failure; isolated unchanged Admin test passes. Early focused restricted runs also timed out without results; intended planned-nav assertion changes and a missing jsdom matchMedia fixture were corrected, without weakened gates. First backend run77 passed/48 setup errors was caused by inaccessible existing pytest temp root; new owned basetemp/cache resolved all125. Original failure logs retained.
- BLOCKING final live evidence: owned initdb repeatedly exceeded its unchanged45s guard. Owner explicitly approved exactly one serial retry after independent checks; that attempt (`p4-student-browser-06-approved-serial.log`) reached actual successful published Home and screenshots, then real calendar503/periods503 and failed return Home after schedule refresh. It stopped before live offline/loading/injected denial/revoked/unassigned/logout/native200 assertions. Success JSON absent. Root cause of503 remains unconfirmed; provider/fixture connection/resource lifecycle is a next diagnostic hypothesis, not a proven frontend or backend defect. No further connected retry performed. No complete browser/console/200%-zoom or live-negative acceptance claimed.
- One independent focused reviewer found five issues: stale class fallback, token-refresh timeout, sample dialog label, sample controls, full-week coverage. All corrected; tests cover stale details, bounded token/read path, month boundary and no-data-on-denial. No repeated review loop. Pink-card secondary text uses the existing darker text-on-tint token after a measured contrast issue; no global palette replacement. Empty copy avoids claiming no publication exists outside the caller's visible scope.
- Preservation: all3 original SQLite hashes match `p4-original-preservation.json`; all61 P3b backend/package hashes match `p4-p3b-source-preservation.json`. All5 P4 marked PG roots freshly return pg_ctl3/no server; all5 owned Auth servers stopped/outbound denied0 (`p4-owned-*-status.json`). Temporary baseline launcher stopped using its verified owned PID tree after its stdin pipe closed. No original DB access through SQLite, migration/cutover, user-file reset/stash, deletion, commit/push/deploy/cloud/real Firebase/real people/messages occurred.
- **P4a/P4b PARTIAL, not accepted. Stop here.** Next: separately approved bounded diagnosis/repair of real503 recovery, then complete connected negative/session/native200 journeys and a successful full frontend exit gate. Manual screen reader remains unverified. Teacher/Admin UI backlog is PLANNED only in `P4_EVIDENCE.md`; P4c/P4d not started. P3b bounded local PASS remains intact; production/cutover still unauthorized.

### 2026-10-30 03:35 Asia/Singapore — P4a/P4b stability exit PASS; stop

- Current owner task explicitly reopened bounded stability recovery after the consumed prior retry. Read AGENTS/autonomy/current evidence before edits; recorded renewal/acceptance, retained attempt numbers and all failures. Base/current HEAD `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`; prior dirty work retained; P4c/P4d excluded.
- Confirmed PostgreSQL admission exhaustion in retained attempt06 server log at02:24:55/57, before shutdown02:25:29. Setup-only owner/runtime pools remained open alongside real service pools. Dispose setup engines before TCP handoff and owner after fixture controls: observed idle1/1→0/0. No service pool/cluster limit/timeout/privilege/RLS or services/packages implementation change. Old per-request origin/query/payload was not logged, so individual historical503 attribution remains explicitly unavailable.
- Added test-only correlated service timeline and genuine Scheduling stop/restart outage. Attempt07 had no healthy503 but exposed held-route teardown error; release + unrouteAll(wait) corrects it without swallowed exceptions. Attempt08 full connected PASS. Required fresh audit then found Vite6.4.4 GHSA-8g5g-mxqh-grgj; patched root/workspace to6.4.5 with override, stronger installed-version/denied-file regression. Dirty lockfile backed up; comparison shows only Vite version changes, no added/removed paths. Final attempt09 on6.4.5 **PASS**, Auth/PG stopped, outbound0. No indefinite unchanged retry loop or advisory exception.
- VERIFIED actual SDK/current-PG Student login and wrong-role denial; published Home/full timetable; actual class-room ID/date detail and refresh; back/forward; session restoration; logout/no revival; unbound/revoked/unassigned denial/empty and restoration; real endpoint outage503/unavailable/no stale classes + recovery. Final healthy Gateway62×200/Scheduling49×200 and expected403s, **zero healthy503s**; only three deliberate Gateway503s in outage phase. Providers present, no premature cleanup. Current per-service timeline includes time/method/path/query/request IDs/pool state.
- Student-only polish: UUID disclosure, concise period option + complete wrapping selected title, compact Next Class spacing, readable event names/time/room/instructor, quieter empty days and concise truthful copy. Independent review found missing PG room links; fixed ClassSessionDetails Student institutional branch, scoped room-detail filtering/unknown state and date-aware/keyed route reset. No Teacher/Admin redesign or invented records.
- Final gates: complete frontend **731/43 PASS**,132.36s after patch; backend **125 PASS**,2.87s; security **17 PASS**; lint/types/Ruff/pip-check PASS; institutional/presentation builds PASS; artifacts **4 PASS**. npm audit0; exact Python68versions/0 findings. Existing Starlette/httpx, chunk/mixed-import and audit hashing warnings retained. No worker, timeout, constraint, skip or xfail weakening. Earlier failures remain in original logs.
- Actual connected Home at360/390/768/1024/1440/no overflow; mobile final-action clearance above bottom nav; keyboard details/Escape/focus restoration; native Chrome200 via tabs.setZoom2/DPR2/no overflow. Final desktop/mobile/native screenshots inspected. Final presentation artifact Home **and timetable** all five widths, zero API/runtime/console errors, keyboard/room/deep refresh PASS. Manual screen reader, physical notch/cross-browser and production acceptance not claimed.
- Preservation: fresh `p4-stability-preservation.json` matches all3 original DB hashes/all61 P3b backend/package hashes. All3 recovery PG roots pg_ctl3/stopped; owned Auth stopped/outbound0. No original migration/cutover/real import, cloud/Firebase settings, messaging, commits/pushes/deployments or deletion. Final09 screenshots use unique run names; earlier reused screenshot paths are identified as mutable historical paths in the report.
- **P4a/P4b PASS for approved bounded local scope. Stop here; P4c/P4d not started.** Full traceability, commands/logs, proof/forensic limits, review resolution and deferred Teacher/Admin backlog: `P4_STABILITY_EVIDENCE.md`; final machine evidence `../production/local-20261029/p4-stability-exit-evidence.json`. Next work requires a separate task; no automatic phase advancement or production authority follows.

## 30 October 2026 — Student refinement exit: PASS, bounded local

Owner's attached-mockup Student refinement is complete at the P4a/P4b boundary. Base/current HEAD `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`; existing uncommitted work preserved, no commit/push/deploy/cloud/prod Firebase/original DB changes. Exact UTC timestamp/source/screenshot hashes: `docs/production/local-20261029/student-refinement-exit-evidence.json`.

Implemented focused Home/Student Schedule, source-backed read-only term, human-readable presentation mapping, consistent Home/Schedule/Rooms/Alerts, useful room search/details with retained legacy directory, source-separated updates, richer domain-validated synthetic fixture (3 subjects/9 weekly sessions/3-class Friday; separate room-change scenario), date/history, pending-data and midnight-duration fixes. P3b core backend/package source hashes61 and original SQLite hashes3 remain identical. Prior503 setup-pool handoff correction retained.

Fresh evidence: full web739/45 PASS(167.06s); additional final Home/change UI10 PASS; backend126 PASS plus calendar/fixture6 PASS(one initial fixture case repeated); lint/types/Ruff/whitespace/builds PASS; security17/artifacts4 PASS; npm0 and Python68 exact versions/0 advisories. Final artifact Home/Schedule all360/390/768/1024/1440 rendered and inspected; no overflow/API/console/runtime errors; actual native200 plus keyboard focus/bottom-nav clearance; class/room/day/week/Today/month/refresh/back and secondary role route smoke. Final real Auth/current disposable PG/TCP journey:73×200,7 expected403,3 deliberate outage503, **zero healthy503**, denial/revocation/unassigned/offline/recovery/logout PASS; both owned Auth/PG stopped. One independent focused review produced four fixes, all verified. Intermediate failures and corrected harness setup retained honestly.

Details, research, command logs, screenshots, limitations and Teacher/Admin backlog: [STUDENT_REFINEMENT_EVIDENCE.md](STUDENT_REFINEMENT_EVIDENCE.md). Manual screen-reader/physical-device and production acceptance remain unverified; push delivery and physical room availability are not simulated. Static read-only local preview remains available. **STOP: Student milestone accepted; do not start P4c/P4d.**

## 30 October 2026 — Campus Companion visual refinement PARTIAL; approval required

Owner authorized Student visual polish. Implemented Student-scoped shell/header/spacing, compact Schedule options with Preview tools disclosure, reduced repeated sample/room/announcement copy, and captured 18 baseline / 24 after presentation screenshots. Focused Home/Schedule/AppShell 26 tests and Schedule options 5 tests passed; lint and typecheck passed. Current 64 preservation hashes match. Initial after-browser capture had no overflow, console errors or API requests across requested widths, but a subsequent term-selector width fix has not been rebuilt or recaptured.

Full frontend regression: 739 passed, 1 failed (`student-visual-20261030/web-final.log`): institutional role-boundary test expects `Student · University`, which the visual change removed from the sidebar. A focused retry failed the same test (`institutional-fix.log`, 3 passed / 1 failed). The attempted restoration did not apply because the JSX had been formatted across multiple lines; current `AppShell.tsx` still omits the suffix for Student. This is a known local presentation regression, not evidence of an authorization failure. Per AGENTS.md persistent-test-failure gate, stop and request explicit owner approval before further correction/retest. No limits or assertions were weakened.

Remaining: correct the label with a matching edit; rerun focused and full relevant tests; rebuild/reinspect final screenshots including the term width; complete connected/security/artifact/native200 and Teacher/Admin regression checks; finish PageHeader and remaining room/alert/announcement visual polish; conduct the single focused review; update acceptance and preservation. No PASS or production acceptance claimed. Original3 SQLite hashes and 61 P3b source hashes matched at the last check; no commits, deployment or production changes.

## 30 October 2026 — Selected Claude implementation PARTIAL; new test gate

Owner explicitly approved prior sidebar recovery. Correct institutional/demo account suffixes applied; exact former failing test1 PASS. Proceeded with actual code: new Student-scoped claude-student.css/main import, AppShell labels, reusable StudentPageHeader, Home/room/alert visuals, Schedule view controls and aligned month/date navigation. Phase captures:2 shell,2 Home,4 Schedule/options,8 Rooms/Alerts at390/1440, no recorded console errors/API requests. Focused30 tests PASS. No bundled runtime/fonts imported.

New month alignment/year-navigation test failed twice (5 existing Schedule cases PASS each attempt); failures occur while querying the month navigation around asynchronous loading. Added waits after navigation did not cover the initial view transition. Stop at the new persistent-failure gate; request a bounded correction/retest authorization. Final fidelity/full regression/connected/native200/build/artifact gates remain open. Do not claim design acceptance. Current3 original DB +61 P3b source hashes match. Details: CLAUDE_STUDENT_IMPLEMENTATION.md; logs/capture indexes: ../production/claude-student-20261030/. All prior dirty work preserved; no commits/cloud/production changes. P4c/P4d not started.

## 30 October 2026 — Vercel TypeScript build correction PASS locally

Owner's narrow confirmed TS2769 fix applied at StudentSchedule.test.tsx:130: removed unsupported `exact: true` from Testing Library getByRole options, retained role/name matcher and all assertions. Installed ByRoleOptions inspected; AST scan of frontend role queries found no other invalid exact property. Only application/test source change is this one line; UI/auth/publication/SQL logic and dependencies unchanged. Base/current HEAD8f7004c1765338fd88fd24663c6b0c94d593986d; no commit/push/deployment.

Fresh gates: affected StudentSchedule6 PASS; full frontend741/45 PASS207.14s via existing workspace `npm run test --workspace=@classync/web -- --pool=threads --reporter=verbose` (root has no test script); root typecheck/build/security/presentation build all exit0; security17 PASS; npm audit0. Actual apps/web/dist/release.json mode `read-only-presentation`, appMode `presentation`, current HEAD and uncommittedChanges=true. Both builds retained TypeScript validation. Existing chunk-size warnings are nonblocking. All3 original SQLite and61 P3b backend/package hashes match before/after. No new backend/browser/production acceptance is claimed.

Evidence: ../production/vercel-typescript-20261030/exit-evidence.json and command logs. The minimal fix is locally ready for owner commit/push. Vercel deployment success requires the next remote build and remains UNVERIFIED. Earlier broader Student design/fidelity acceptance remains separate; no automatic UI scope continuation.

## 30 October 2026 — Student Rooms milestone PASS locally

Approved Rooms-only implementation accepted at base/current SHA8100dba82ed1064a1e26bfb171efed1135d745ea. Added StudentRooms.tsx/student-rooms.css, strict stable-ID student-rooms.ts, Rooms tests; routed primary Student Rooms to unified My/All/Labs experience; ClassSessionDetails retains period; exact Schedule-link regression updated. Search-first layout, deduplicated assigned rooms/classes, preview-only59-space catalog, honest unsupported Labs/connected-directory states, compact source notice and useful context-preserving details. Teacher/Admin implementation and all backend files unchanged.

Fresh final evidence: frontend752/46 PASS179.01s, affected backend125, security17, artifacts4, audit0; typecheck/lint/rootbuild/presentationbuild exit0. Real connected Auth Emulator/disposable PG journey PASS with68 healthy200,7 expected403,3 intentional503,zero unexplained503,zero browser errors. Final presentation browser five widths360/390/768/1024/1440 and actual native200 keyboard/overflow checks PASS; screenshots/reference inspected. Single focused independent review:2 findings resolved. Original3 SQLite +61 P3b hashes unchanged. Earlier whole-run timeout and stale exact-link expectation are retained in STUDENT_ROOMS_EVIDENCE.md and resolved by serial qualification; guards/assertions preserved. No commit/push/deployment. Release remains explicit read-only presentation. Evidence: STUDENT_ROOMS_EVIDENCE.md and ../production/student-rooms-20261030/exit-evidence.json.

Remaining: verified lab/physical occupancy data and tenant-authorized connected full directory are unavailable; manual screen-reader/physical-device/production acceptance unverified. No automatic P4c/P4d or further redesign. Await separate owner release authority for GitHub/Vercel changes.

## 31 October 2026 — bounded CI repair PARTIAL; security BLOCKED; qualification gate

Base/current SHAaea9494db46153672a31a2161070e5e4ff713966 matches failed GitHub run41184643255; all3 remote job logs inspected. Implemented two-file repair: deterministic Date-only clock and explicit Oct/Nov + Dec/Jan calendar tests in StructuredCalendarPage.test.tsx; quality.yml uses python -m pytest. Reproduced reported Web failure once; focused6 PASS. Python console17 collection errors reproduced; module invocation collects947. Fresh npm ci and npm ls --all PASS in source snapshot; npm audit low remains12 moderate due minimatch<11.0.1. Latest stable ESLint10.14/TypeScript-ESLint8.72.1 still require10.x, so no supported upstream fix; no lockfile changes/force/overrides/exceptions.

Full clean frontend run reached unchanged300s guard:750 passing case records, no final suite result. Clean Python install hit180s setup limit twice (one cached continuation), so stop at conservative persistent-qualification gate; no third attempt or weakened guards. Full backend execution and remaining final gates NOT RUN. Evidence and exact attempts: CI_REPAIR_EVIDENCE.md; ../production/ci-repair-20261031/.70 before/after hashes match (3 original DB,61 backend/package,6 Rooms/routing files). Student Rooms/security source intact; no commit/push/deploy. Owner approval required for bounded serial continuation using existing validated runtimes; dependency advisory separately BLOCKED pending compatible upstream release or explicit policy decision. No remote CI PASS claimed.

## 31 October 2026 18:05 SGT — institutional schedule priority corrected; isolated review complete

Owner explicitly authorizes this independent review-only task; CI retry/security blockers remain unchanged. Base/current HEAD aea9494db46153672a31a2161070e5e4ff713966; existing workflow/calendar/CI documentation changes preserved. Acceptance written before implementation in docs/academic/review-20261031/ACCEPTANCE.md; authorization recorded in APPROVALS.md.

VERIFIED: green is owner-confirmed current revised BSIT 3A operational evidence; pink superseded, 3B currency unconfirmed; NB 107 preserved separately with unknown effective date. All three original attachment bytes copied and SHA-256 checked. Twelve raw-code/raw-room sessions file-staged as JSON/CSV; tentative Tue ITOPSYS has null room; no conflicting pink assignments merged. Observed 1620 weekly minutes including180 tentative (1440 without);9 codes each180 observed, not verified curriculum contact requirements. No section overlaps; no candidate-room overlaps within this section. PRC versus PRRC spelling, COMLAB candidate mappings and all exact Registrar codes remain explicitly unverified.

Existing AcademicSnapshot contracts and scheduling Window/intersects/academic_readiness reused without architecture/application changes. Academic snapshot validates; readiness correctly BLOCKED with missing faculty, eligible resources, minutes and operating hours. Full scheduling/student/faculty/cross-section validation and actual PostgreSQL persistence NOT RUN: file-only review has no authorized tenant/principal/term or fabricated Assignments. No institutional identities created. Applicable Registrar version absent; missing-information list and ten-requirement traceability in review README. Self-review compared all twelve rows to green merged boundaries, inspected CSV/readiness, ensured catalog candidates exist and NB/PRRC identities differ. No independent external review claimed.

Fresh final commands: .venv/Scripts/python.exe docs/academic/review-20261031/prepare_review.py exit0 (count/interval/section/minutes/overlap/source hash/contract/blocked readiness/preservation assertions); .venv/Scripts/ruff.exe check docs/academic/review-20261031/prepare_review.py exit0. Initial script formatting findings corrected before final checks. git diff --check exit0 (existing CRLF notices only). Original3 SQLite SHA-256 before/after match each other and P1 baselines; hashes in review validation.json. No original DB connection/write, PG connection/import, cloud, account, publication, Git commit or deployment. No unrelated frontend/backend full regression claimed for review artifacts.

Files: review-20261031 README/acceptance/script,3 preserved sources, source-register.json,current-bsit3a.json/CSV,academic-review-snapshot.json,academic-readiness.json,validation.json; curriculum-source-register.md; APPROVALS/ROADMAP/STATUS. Local staging/transcription COMPLETE; institutional reconciliation and scheduling promotion BLOCKED pending listed Registrar/term/room/faculty/eligibility evidence. STOP at review; next is owner review/missing information, not publication or deployment.

## 31 October 2026 — bounded CI qualification: WEB PASS / PYTHON PARTIAL / security BLOCKED

Explicit owner approval reopened prior gate for one serial full execution each using existing runtimes/guards. Preflight: no stale workers or running review agents; existing preview services preserved. Frontend754/46 PASS219.68s (231.28s wall), unchanged300s guard, no retry. Fresh lint/typecheck/security17/rootbuild/artifacts4/presentationbuild PASS serially; release remains read-only-presentation. Full Python947 executed:934 passed/13 failed in120.08s. Runner mistake: workspace --basetemp violates existing OS-temp-only test provider guard, producing intended503s. No backend relaxation/source change or second full run; correctly configured plain python-mpytest remains pending under one-run cap. Python pip check/Ruff PASS; reused pinned audit tool finds4 pyasn1.6.4 advisories, fixes.6.5, no policy exception/update applied. minimatch compatibility/exposure assessed once: latest supported parents still require affected3.x/10.x; dev-only installed graph, absent production dependency/source/bundle signatures, audit BLOCKED12 moderate. All70 preservation hashes match; unrelated academic-review work retained. CI source still only workflow module invocation and deterministic calendar tests. No commit/push/deployment/remote pass. Latest CI_REPAIR_EVIDENCE.md appendix and approved-qualification-summary.json contain counts/timings/causes. Stop; need authority for further Python run/dependency remediation; do not call this green CI.

## 3 November 2026 — cohort-aware curriculum / synthetic BSIT pilot PASS locally

Base/current HEAD `aea9494db46153672a31a2161070e5e4ff713966` (all work remains uncommitted). Owner-approved bounded pilot implemented after reading `docs/academic/README_START_HERE.md` and `CODEX_IMPLEMENTATION_DIRECTIVE.txt`; acceptance and authorization are in `COHORT_PILOT_ACCEPTANCE.md` and `APPROVALS.md`. Final source changes cover catalog contracts, cohort bindings, PostgreSQL migration/repository, academic API/gateway, Admin workflows, scheduling readiness/publication guards, synthetic pilot, and targeted tests. Requirements and limitations are traced in `COHORT_PILOT_EVIDENCE.md`.

VERIFIED: 39 curriculum source versions / 8 programs / 2,062 source rows retained as unreviewed; 27 hypothetical BSIT first-term offerings and 81 tagged synthetic candidates; no automatic migration from 2024 cohort curriculum; exact codes preserved. Green BSIT3A current sessions remain separate review-only files (12 sessions, 1,620 observed weekly minutes including tentative Tuesday ITOPSYS; no approved-contact-minute claim). Pink is superseded; BSIT3B currency unconfirmed; NB107 remains independent from PRRC107 with unknown effective date. Code and room reconciliation gaps remain explicit.

Fresh gates: `.venv/Scripts/python.exe -m pytest services/academic services/scheduling services/persistence -q` → **790 passed**, one framework deprecation warning, 87.06s. Earlier simultaneous CPU load caused one existing 8s solver test to return UNKNOWN; isolated retry passed, then the serial full suite passed unchanged. `.venv/Scripts/ruff.exe check services packages scripts` passed. `npm run typecheck`, `npm run lint`, `npm run build` passed; build retains existing chunk-size/Firebase split warnings. Focused frontend15 passed; full frontend759 passed / 48 skipped; security17 passed. Updated `node scripts/cohort_pilot_browser.cjs` passed synthetic API-render review, widths360/390/768/1024/1440, native200, keyboard, exact source-code selection, empty contact minutes/readiness blocker, no page/console errors/external calls. It is not connected backend acceptance. Disposable PostgreSQL18.6 qualification passed using `python -m scripts.postgres_cohort_pilot_qualification`; fresh evidence `../production/cohort-pilot-20261031/postgres-pilot-final-20261103.json` covers migrations, atomic seed, feasible54-session OR-Tools solve + independent validation, draft/revision/idempotency, synthetic-only publication, Student/Teacher scoping, role/tenant denials, cohort binding persistence/immutability, clear-metadata denial, rollback, RLS and stopped cluster. `git diff --check` passed (line-ending notices only).

Original SQLite hashes were freshly compared with `docs/production/p1-database-preservation.json` and match exactly: academic `4cd5f60de21bd365c914ac01e5be692b3bea1c7a56a7f17a76c6953ef8668738`; scheduling `1848377cc9a9eb656e12b5e58436e81198fef92f18dd71c1fea2f6f8b482e400`; backup `9ec149413d69c1165b74a75e366fa262417c1ecbf41e7029fdd0d86ac96f395d`. No original DB writes, live imports, accounts, cloud, real timetable publication, commits, pushes or deployment. Prior minimatch/pyasn1 audit blockers remain open. **Milestone PASS locally; stop at bounded first academic pilot.** Next institutional work is blocked pending Registrar-approved version/code mappings and minutes, effective term/calendar, confirmed rooms/room schedules, Tuesday ITOPSYS decision, actual sections/enrollments/faculty/eligibility, and cross-institute room/faculty locks. No real-data acceptance is claimed.

## 3 November 2026 15:52 SGT — real academic-data readiness PASS, real scheduling BLOCKED

Owner-authorized bounded milestone completed at base/current HEAD `aea9494db46153672a31a2161070e5e4ff713966`; no commit/push. Preserved all earlier dirty work and pilot data. Acceptance cases: `REAL_ACADEMIC_READINESS_ACCEPTANCE.md`; full traceability/evidence: `REAL_ACADEMIC_READINESS_EVIDENCE.md`.

Delivered a review-only BSIT Years 1–4 readiness report, input checklist, cohort-version and code candidate reconciliations, and a current Admin data-entry flow using existing contracts/screens. Source inventory is structurally reconciled: 39 versions, 8 programs, 2,062 extracted course rows, 20 distinct PDF hashes, 5 BSIT version candidates, 27 first-semester requirement rows, 36 unresolved code-change candidates, and 12 green BSIT3A sessions. No Registrar approval, actual term offering, or curriculum equivalency is inferred. Green remains owner-confirmed; Tuesday ITOPSYS remains tentative/null-room; pink is superseded; 3B currency remains unconfirmed; NB 107 remains distinct from PRRC 107 with unknown effective date.

Readiness now blocks institutional generation on missing approved calendar, exact cohort/version and section identity, verified aggregate population/source, reviewed exact source/course and approved contact-minute references, actual term offerings, faculty eligibility/availability/workload references, room availability/blocks and institutional room provenance, operating-window approval, complete scope, and same-period ICS/IBE/ITE scope review. Admin edits invalidate related review flags. Fixed assignments use structured saved offering/faculty/room selections. Complete synthetic-only simulation remains isolated to synthetic faculty and rooms, cannot mix with provisioned room/faculty scope, and cannot publish to the institutional dataset.

Fresh verification: `.venv/Scripts/python.exe -m pytest services/academic services/scheduling -q` **393 passed**, 1 existing Starlette/httpx warning, 69.96s; focused `AcademicManagementPage.test.tsx` **11 passed**; web typecheck/lint/build passed; Ruff focused files passed; review builder reported `PASS_REVIEW_ONLY`; `git diff --check` passed with line-ending notices. Build emits existing Firebase dynamic-import and bundle-size warnings. Final disposable PostgreSQL 18.6 evidence: `../production/real-academic-readiness-20261103/postgres-synthetic-final.json` — 27 hypothetical offerings, 81 synthetic candidates, 54 feasible independently validated sessions, draft/revision/role/tenant/RLS/rollback checks, and attempted institutional publication denied with state unchanged. Cluster stopped. Original academic/scheduling/backup SQLite hashes match the P1 baseline; values are in the evidence file. An initial sandboxed `pg_ctl` attempt failed before server startup with restricted-token error; no existing DB was contacted. The successful retry used a new marked temporary cluster. An intermediate readiness assertion exposed the synthetic-only scenario distinction; corrected and retested, no test or solver gate relaxed.

Real-data pilot entry is **BLOCKED** pending Registrar-certified source/version/cohort assignment and code equivalencies/minutes; the official effective calendar; real sections, populations and current offerings; authentic faculty/eligibility/availability/workload; verified physical room identities, restrictions/blocks and NB107 effective date; full ICS/IBE/ITE shared-resource commitments; and named supervised-pilot authority/rollback/publication-stop plan. No student roster, real faculty, room or schedule imported; no account, cloud/deployment or publication action. Stop here; Teacher/Admin visual redesign remains out of scope. Existing CI/dependency security blockers remain separate and unchanged.

### Final verification correction — 3 November 2026

The paragraph above records the initial bounded checks; final evidence supersedes its test count and PostgreSQL artifact path. Added migration `0013_synthetic_review_period_mode`: ordinary periods default to institutional data; only a separately persisted synthetic-review period can contain synthetic faculty and rooms, and it is excluded from the institutional period list. PostgreSQL qualification separately verifies the migration revision/column after downgrade and reapply. Final disposable PostgreSQL 18.6 run **PASS**: 54 independently validated sessions, institutional synthetic-write denials, synthetic period isolation, role/tenant/RLS/rollback and denied publication; cluster stopped. Final backend suite **395 passed** (81.67s; one existing Starlette/httpx deprecation warning); focused Admin UI **11 passed**; web typecheck, lint and build passed (existing Firebase dynamic-import and bundle-size warnings); Ruff and source review builder `PASS_REVIEW_ONLY`; original SQLite hashes match. Evidence: `REAL_ACADEMIC_READINESS_EVIDENCE.md` and `../production/real-academic-readiness-20261103/postgres-synthetic-mode-final.json`. No production action. Stop at this milestone.

## 6 November 2026 — Auth and SaaS onboarding

**Verified locally and ready for review** in the isolated `feature/auth-onboarding-saas` worktree. Base and current commit are `96cbd34a9ea2a040e00061357f7b362485743d4e`. The feature changes are uncommitted. The release worktree is clean at the same commit.

The institutional entrance uses Soft Rouge and role-specific guidance. Student signup, recovery, email verification, profile review and claim submission reuse Firebase and the existing Gateway. Academic binding appears in the authorized Student profile after approval. The optional scanner still requires verified enrollment for published matching. Teacher activation uses a university-provisioned Firebase account and an approved invitation. Current PostgreSQL membership continues to gate protected requests and enforce revocation. Administrator provisioning stays restricted. Account mutations bind to the Firebase UID that opened the form. The separate read-only presentation exposes sample navigation without credential forms.

- `npm run typecheck` and `npm run lint` passed. `npm run test:web` passed 807 tests across 59 files in 215.61s under the existing 300s guard.
- `npm run test:security` passed 19 checks. The targeted Gateway onboarding, registration, request authorization and authorization lifecycle suites passed 128 tests with one existing Starlette/httpx warning.
- `npm run test:artifacts` passed all four checks, including institutional and presentation builds. A browser opened the built presentation and followed its sample link with no credential inputs or live requests.
- Owned Firebase Auth Emulator and disposable PostgreSQL 18.6 passed the onboarding and scanner browser modes. Covered Student verification, profile review, pending status, Admin approval, session restoration and recovery. Teacher verified a provisioned account and accepted an approved invitation. Provider cases covered invalid, replayed, expired and revoked invitations, membership revocation and cross-role, cross-user and cross-tenant denial. Scanner evidence covers synthetic PDF and photo OCR, review corrections, pending and wrong-term results, authorized published matching and temporary scan deletion.
- Chromium checked 360, 390, 768, 1024 and 1440px widths, keyboard selection, logout focus and native 200% zoom. The initial cold onboarding attempt timed out on navigation. The serial retry passed with the existing guards. Both owned providers stopped. Local evidence is under the parent workspace's ignored `var/auth-saas-evidence` directory.
- All three original SQLite SHA-256 digests match the release checkpoint. Test documents and accounts were synthetic. Manual screen-reader testing and hosted staging remain pending. The release checkpoint's recorded npm advisory, remote Actions and Linux container/OCR qualifications remain open.

## 6 November 2026 — Live local SaaS entrance correction

**Verified** in feature/auth-onboarding-saas at base/current 96cbd34a9ea2a040e00061357f7b362485743d4e. Chromium reproduced the demo-first root on the user's port 5190. Plain Vite selected sandbox before checking Firebase. The plain frontend now selects the institutional entrance, while the explicit sandbox launcher and the public presentation keep their own modes. Auth configuration on a development server requires an explicit institutional selection. The default 5190 launch renders all four account entry routes with truthful unavailable status when the provider is absent.

The owned connected preview uses the existing connected qualification fixture and local Gateway, Academic, Scheduling, Firebase Auth Emulator and disposable PostgreSQL. With CLASSSYNC_ONBOARDING_PREVIEW=true and the --connected-browser launcher, it serves http://127.0.0.1:5191/ for ten minutes and prints a graceful stop command and synthetic account details. The developer-only synthetic notice distinguishes this from university service. The interactive launch produces a preview receipt, while the automated onboarding journey keeps its existing 180-second guard.

- Actual Chromium browser checks passed on 5190 and 5191 for /, /auth/login, /auth/signup and /auth/teacher-invite. Connected acceptance covered signup, verification, profile and claim review, Admin approval, refresh, recovery, denied Admin escalation, Teacher activation and logout. Separate smoke on the full preview blocked the Gateway membership request, observed unavailable status and restored authorized Admin access after retry.
- Captured real 1440px and 390px screenshots from the connected preview. The automated run also checked five widths and native 200% zoom. A Chromium run against the built public presentation showed sample navigation, absent credential forms and absent signup/invitation routes.
- Typecheck, lint, Ruff, Node syntax and diff checks passed. The focused mode, route and onboarding set passed 474 tests across seven files. All four production artifact checks passed. Logs and automated onboarding evidence are under the parent workspace's ignored var/auth-saas-evidence directory.
- All three original SQLite hashes match. Release and feature refs still point to the reviewed checkpoint. Feature edits are local and uncommitted.

## 7 November 2026 — Universal SaaS authentication and entrance

**Verified locally** in feature/auth-onboarding-saas, based on 96cbd34a9ea2a040e00061357f7b362485743d4e. The shared entrance uses the original ClassSync artwork, self-hosted Inter, navy #142B45, red #A8273A and cool background #F7F9FC. A code-native, clearly illustrative timetable sits beside the form on desktop and below it on mobile. Sign-in, recovery, signup with password confirmation, verification, Student claim and Teacher invitation use the existing identity and record workflows. The public build uses the same visual shell for its separate sample entry.

Firebase proves identity and the Gateway looks up current PostgreSQL membership. The signed-out experience offers a single sign-in form. A verified single membership routes automatically to its workspace. Multiple memberships expose only the server-confirmed choices on the account screen. Each choice triggers a fresh authorized lookup. Failed role selection clears the remembered choice for retry. Internal return targets must be registered paths owned by the verified role. Teacher invitation URLs return through universal sign-in and verified email before the existing private code is accepted. Admin approval and provisioning stay behind current server authorization.

### Verification

- Port 5190 served the SaaS UI with a clear unavailable state and no credential fields or live requests. Chromium inspected all seven requested entry routes. The full synthetic preview on 5191 linked to the built read-only presentation on 5192. The sample application exposed no credential forms or signup or invitation routes.
- Owned Auth Emulator and disposable PostgreSQL onboarding run passed signup, verification, claim and approval, invalid sign-in, recovery request, refresh, expired-session handling, protected-role denials, safe-return fallback and Teacher invitation activation. The disposable scanner run passed approved Student access to published classes, correction, pending and wrong-term denial.
- A separate Chromium smoke on the marked disposable preview verified actual PostgreSQL Student and Teacher grants, switching, omission of Admin, and recovery to the remaining Student grant when the selected Teacher grant was removed. The legacy standalone web-session runner stopped before Chromium on its stale six-table identity RLS inventory. The two newer onboarding tables both have ENABLE and FORCE in the existing migration. The legacy guard and schema were preserved.
- Tested widths 360, 390, 768, 1024 and 1440, native Chrome 200% zoom, first-viewport sign-in, keyboard focus and password toggle, associated field errors and reduced motion. Measured navy on white at 14.37:1, red on white at 6.96:1, muted text on the page background at 6.82:1, input boundary on white at 3.17:1 and focus blue on white at 6.85:1. Accessibility semantics were inspected in Chromium. Manual screen-reader and physical-device checks remain pending.
- Typecheck, lint, Ruff, browser script syntax and diff checks passed. The 12-file focused web run passed 516 tests with one test-string encoding failure. All four sample entrance tests passed on the targeted retest after correcting the string. Gateway regression passed 126 tests, security passed 19 checks, and artifacts passed all four checks.
- All three original SQLite SHA-256 digests match. Release branch remains clean at the reviewed checkpoint. Changes are local and uncommitted. Cloud staging configuration and hosted-provider acceptance are pending. Evidence is under the parent workspace's ignored var/auth-saas-evidence directory.

### Files changed in this refinement

- Entrance and navigation — apps/web/src/pages/AuthPage.tsx, apps/web/src/pages/InstitutionalEntrance.tsx, apps/web/src/pages/institutional-entrance.css, apps/web/src/routes/app-routes.tsx, apps/web/src/components/layout/AppShell.tsx.
- Account and membership UI — apps/web/src/auth/AccountAdministrationPanel.tsx, apps/web/src/auth/AccountOnboardingPanel.tsx, apps/web/src/auth/UniversitySessionPanel.tsx, apps/web/src/auth/access.ts, apps/web/src/auth/account-actions.ts, apps/web/src/auth/university-session.ts, apps/web/src/auth/university-session-driver.ts.
- Verified workspace metadata — packages/api-contracts/classync_contracts/request_authorization.py, services/gateway/app/main.py.
- Tests — apps/web/src/pages/AuthPage.test.tsx, apps/web/src/pages/InstitutionalEntrance.test.tsx, apps/web/src/auth/UniversitySessionPanel.test.tsx, apps/web/src/auth/university-session.test.ts, apps/web/src/auth/university-session-driver.test.ts, services/gateway/tests/test_request_authorization.py.
- Browser qualification selectors and journeys — scripts/onboarding_browser.cjs, scripts/registration_browser.cjs, scripts/connected_browser.cjs, scripts/mvp_features_browser.cjs, scripts/student_experience_browser.cjs, scripts/web_session_browser.cjs.
- Scope and evidence — docs/autonomy/APPROVALS.md and docs/autonomy/STATUS.md.

## Persistent connected local development and entrance refinement

Implemented npm run dev:connected in the existing emulator launcher. The dedicated development path performs prerequisite checks and bootstrap only, without launching browser acceptance or the API qualification assertions. It creates a marked disposable Windows-SSPI PostgreSQL database, starts the owned Firebase Auth Emulator and all three required APIs, verifies readiness, and starts Vite on the configured free loopback port. Manual development has no timer. Intentional shutdown writes the owned stop marker and closes providers. Generated session credentials stay in the private temporary directory and are blocked by Vite with HTTP403. Session-specific Firebase keys prevent old emulator identities being restored after a new disposable launch.

The screenshot's unavailable state came from the frontend-only 5190 server. Its feature worktree lacked provider configuration; the parent worktree's classsync-f444c web registration was separate, and the former 5191 evaluation preview expired. Developer logs now identify missing setup and Gateway probe failures. The credential form stays withheld until local provider readiness. The new persistent command supplies its own isolated synthetic configuration.

The entrance now combines the larger original logo with the sign-in surface, uses a compact coherent sample agenda and room update, removes the old external header/footer, and replaces the large yellow unavailable panel with a restrained status. Mobile keeps authentication first. Screenshots at 1440 and 390 were reviewed after correcting text encoding. Browser tests covered 360, 390, 768, 1024 and 1440, native Chrome200, keyboard focus and reduced motion.

### Current qualification and approval boundary

- Persistent browser acceptance passed Student signup, email verification, pending refresh, Admin approval, Teacher invitation activation, Admin denial and Student timetable access. The later final browser sequence also completed optional synthetic PDF extraction, invalid invitation, Teacher revocation denial and actual password reset before its outage check timed out during concurrent regression. The outage/recovery, withheld-password and native200 keyboard checks passed in the isolated serial retest.
- Focused web tests passed31 across3 files. Typecheck and lint passed before the final startup-guidance-only Vite plugin addition. Security checks passed20. Ruff and browser script syntax checks passed for the launcher edits.
- Full frontend regression remains BLOCKED at the AGENTS approval boundary. The initial concurrent run and the one serial retry both hit the unchanged300-second guard. Logs contain190 and778 completed test lines respectively; neither produced a passing suite summary. No guard, worker cap or assertion was relaxed. Further performance diagnosis and qualification require the pending explicit owner approval.
- The chained fresh Gateway regression and production artifact checks did not run after the full frontend guard failed. Historical results remain separate. Manual screen-reader and physical-device tests remain open.
- The initial intentional stop closed the owned Auth and PostgreSQL servers, with receipt fields confirming both. One restart ended with Windows console interruption code0xC000013A before database startup. Signal handling was corrected to write the owned stop marker and restore handlers. The subsequent command started successfully and remains active for manual use on5191.
- Independent source review identified inherited cloud-provider settings and child-exit cleanup risks. The synthetic Gateway now explicitly disables cloud features and clears Gemini/storage settings, and its health/forwarding map uses owned endpoints only. The environment scrub removes COURSE/GEMINI settings. The supervisor signals stop in child-exit cleanup too. Independent read-only review confirmed both corrections.
- All3 original SQLite hashes match; the release worktree is clean at96cbd34a9ea2a040e00061357f7b362485743d4e. Current edits remain uncommitted.
- Read-only console discovery timed out and the Firebase CLI project-list probe was unavailable. Existing root web configuration identifies classsync-f444c. Its provider/domain state and staging designation are unverified, and no Vercel project link is configured in this worktree. The one pending hosted question asks for the approved staging project and authenticated connection; hosted settings were untouched.

Startup and shutdown instructions, exact mode distinctions and the environment-name inventory are in docs/infrastructure/local-connected-development.md. Current run receipts and test logs are in the parent workspace's ignored var/auth-saas-evidence directory. Local functionality is usable; full milestone acceptance remains PARTIAL pending the required regression-diagnosis approval.

## 7 November 2026 — Approved regression diagnosis and local connected qualification

Current/base SHA96cbd34a9ea2a040e00061357f7b362485743d4e on feature/auth-onboarding-saas; all feature work is uncommitted. The owner reopened bounded frontend performance diagnosis and confirmed read-only inspection of Firebase classsync-f444c and Vercel class-sync-bhiv. Hosted mutation authority was not granted.

The repeated frontend guard failure was import/environment overhead under host resource pressure, without recorded assertion failures. A four-file probe passed37 tests in31.06s, with19.86s aggregate imports and16.64s DOM environment work. Vitest's documented client dependency optimizer reduced the same probe's imports to7.74s. Three inspected DOM-free suites now use Node, passing10 tests in3.48s. The two-worker cap, per-file isolation, assertions and300s wrapper remain unchanged. Full npm run test:web passed812 tests across59 files in190.83s. No further full frontend run was needed after Python-only fixture corrections.

Fresh gates: npm run typecheck PASS; npm run lint PASS; python -m pytest services/gateway/tests -q PASS241 (one existing Starlette/httpx deprecation warning); npm run test:security PASS20; npm run test:artifacts PASS4 in151.66s, including ordinary/presentation/legacy production artifacts and unsafe-mode rejection. Ruff and launcher/browser JavaScript syntax checks passed. The fresh public npm audit confirms7 moderate findings, no low/high/critical: GHSA-g3hv-75wg-m249 through minimatch and its TypeScript-ESLint parents. No production minimatch entry exists in the lockfile. The release security gate remains blocked; no audit threshold or dependency version was changed here. Ignored evidence: var/auth-saas-evidence/final-npm-audit.json in the parent workspace.

The persistent connected application remains live at http://127.0.0.1:5191/ with Gateway http://127.0.0.1:52328. Fresh health/login requests returned200; unauthenticated identity and academic requests returned401; Vite denied the private session account file with403. Existing persistent-browser receipts prove signup, email verification, pending refresh, Admin claim approval, Teacher activation, Admin denial and published Student timetable; the separate outage/Retry/native200 keyboard receipt passed. These browser results are separate from the failed legacy harness described below. Screenshots were manually reviewed at1440/390; earlier responsive checks covered360/390/768/1024/1440 and reduced motion. Manual screen-reader and physical-device qualification remain open.

The stale legacy session harness expected six identity tables despite migration0014 adding account_claims/faculty_invitations. The corrected guard follows the requested Alembic graph, checks exact table names and ENABLE/FORCE RLS, and tests no-context/cross-tenant access on all expected tables. Eight focused tests cover old/current revisions and missing/replaced/unprotected tables. A fresh unused synthetic Student record isolates the person-binding negative case from the newer unique-account constraint while retaining its exact expected SQLSTATE. This foundation passed in disposable PostgreSQL before the browser control failure below.

Legacy full session qualification remains BLOCKED at the AGENTS persistent-failure approval boundary. The first attempt could not create the Windows restricted token inside the sandbox. Outside that sandbox, the stale person-binding fixture failed on unique-account protection; the corrected attempt passed the foundation and reached Chromium, then its nonce-protected fixture control returned400 instead of200. Static inspection shows that register/administrator fixture actions reuse person-a/student-a/faculty-a already linked by the foundation fixture. No successful browser-result receipt was emitted. Proposed next correction: distinct authorized disposable records per test account, preserving HTTP200 expectations, uniqueness, RLS and all current guards, followed by one session qualification. A consolidated approval question is pending; no further correction/retry is authorized by elapsed time. The failed run's owned Auth and PostgreSQL stopped; the persistent manual environment is separate and remains running.

Hosted inspection remains unverified. In-app browser has no signed-in console tabs; Windows browser control refused access because it could not determine the current URL. No Firebase user records or hosted settings were read/changed. Existing project IDs do not establish staging isolation. Unless authenticated read-only review proves classsync-f444c isolated, recommend a separately approved staging Firebase project. Preserve class-sync-bhiv's public presentation. Requirements and environment names are in docs/infrastructure/local-connected-development.md. Linux/container/OCR and remote Actions remain outside current verified evidence.

Independent review of earlier security-sensitive launcher changes passed. The requested follow-up review of the performance-only diff was unavailable because the review agent exhausted its usage allowance; direct diff review was completed and this is not represented as an independent review pass.

All three original SQLite digests still match their baselines after the failed disposable runs. Release ref96cbd34a9ea2a040e00061357f7b362485743d4e and main aea9494db46153672a31a2161070e5e4ff713966 remain unchanged; the release worktree is clean. No commits, push, deployment or live configuration changes occurred. Source-only credential/private-file pattern scan found no matches; generated accounts, receipts, logs and databases remain outside the source inventory. Local app is usable; overall qualification is PARTIAL pending the legacy harness approval, release security resolution and separate hosted/platform qualification.

Exact current changed/untracked source, test, configuration and evidence inventory:

- apps/web/.env.example
- apps/web/src/auth/AccountAdministrationPanel.tsx
- apps/web/src/auth/AccountOnboardingPanel.test.tsx
- apps/web/src/auth/AccountOnboardingPanel.tsx
- apps/web/src/auth/UniversitySessionPanel.test.tsx
- apps/web/src/auth/UniversitySessionPanel.tsx
- apps/web/src/auth/access.ts
- apps/web/src/auth/account-actions.test.ts
- apps/web/src/auth/account-actions.ts
- apps/web/src/auth/university-session-driver.test.ts
- apps/web/src/auth/university-session-driver.ts
- apps/web/src/auth/university-session.test.ts
- apps/web/src/auth/university-session.ts
- apps/web/src/components/layout/AppShell.tsx
- apps/web/src/config/app-mode.test.ts
- apps/web/src/config/app-mode.ts
- apps/web/src/config/runtime-config.ts
- apps/web/src/lib/firebase.ts
- apps/web/src/lib/sample-calendar-api.test.ts
- apps/web/src/lib/student-presentation.test.ts
- apps/web/src/pages/AccountProfilePage.tsx
- apps/web/src/pages/AuthPage.test.tsx
- apps/web/src/pages/AuthPage.tsx
- apps/web/src/routes/app-routes.tsx
- apps/web/vite.config.ts
- apps/web/vitest.config.ts
- docs/autonomy/APPROVALS.md
- docs/autonomy/STATUS.md
- package.json
- packages/api-contracts/classync_contracts/request_authorization.py
- scripts/auth_emulator_qualification.cjs
- scripts/connected_browser.cjs
- scripts/dev.py
- scripts/mvp_features_browser.cjs
- scripts/onboarding_browser.cjs
- scripts/postgres_identity_qualification.py
- scripts/postgres_onboarding_qualification.py
- scripts/registration_browser.cjs
- scripts/registration_connected_qualification.py
- scripts/student_experience_browser.cjs
- scripts/tests/auth-emulator-qualification.test.cjs
- scripts/web_session_browser.cjs
- services/gateway/app/main.py
- services/gateway/tests/test_request_authorization.py
- apps/web/src/pages/InstitutionalEntrance.test.tsx
- apps/web/src/pages/InstitutionalEntrance.tsx
- apps/web/src/pages/institutional-entrance.css
- docs/infrastructure/local-connected-development.md
- services/persistence/tests/test_identity_qualification_inventory.py

## 7 November 2026 21:59 SGT — Approved legacy account fixture correction

Owner approved the bounded fixture correction and one session journey. Base/current SHA96cbd34a9ea2a040e00061357f7b362485743d4e on feature/auth-onboarding-saas remains uncommitted. Acceptance and scope are appended to APPROVALS.md.

Changed scripts/postgres_web_session_qualification.py only for test-account creation: allocate UUID-namespaced synthetic person/Student/faculty records per emulator account, create only a person binding for Administrator, and insert the membership with explicit columns inside the existing single transaction. Current uniqueness, RLS, nonce/loopback control protection, required HTTP200 and browser assertions are unchanged. Direct diff review confirmed parameterized record values, fresh namespaces, atomic rollback and no production route changes. The earlier independent reviewer remains unavailable due its usage allowance.

Ruff, AST syntax and git diff --check PASS. Exactly one approved actual session run executed with the existing pinned Auth tools, current Python/Node, owned loopback emulator and a new disposable SSPI PostgreSQL cluster outside the Windows restricted-token sandbox. Command: node scripts/auth_emulator_qualification.cjs --tools-root <existing pinned tools> --postgres-bin <installed PostgreSQL bin> --output <new ignored evidence> --browser. Evidence/log: parent workspace var/auth-saas-evidence/approved-session-fixture.log; temporary root classsync-auth-run-69f7bb45865b4762abd82c90ab1b3062.

The previous fixture-control400 is resolved. The run passed the identity foundation and the sequential browser assertions for verified Student/Teacher workspace choices, forbidden Administrator role request403, role reduction, database outage/recovery, browser offline/recovery, revocation/reactivation, refresh, logout, separate single-Administrator routing, five viewport widths, keyboard focus, native Chrome200% zoom and Auth outage/signout. It then FAILED the unchanged final unexpected-console assertion: eight503 resource errors with timetable-period requests present in the diagnostic receipt. No browser-result.json or successful whole-run receipt was emitted. No runtime JavaScript errors were recorded. This is a PARTIAL result, not a passing session qualification.

Static setup inspection confirms this legacy harness starts Gateway and identity adapters only; newly exercised dashboard redirects also request timetable data. Its timetable backend is not connected to a qualified provider in this fixture. Proposed next bounded action: reuse the existing real Academic/Scheduling test-service setup against this same marked disposable database and owned emulator, retain honest empty timetable responses and all console/error assertions, and run the journey once. No ignored503s, fake HTTP200s or reduced assertions are proposed. Further correction/qualification stops at the existing persistent-failure gate pending explicit approval.

Owned Auth cleanup receipt: authStopped=true, childExit=1, deniedOutbound=0. Owned PostgreSQL receipt: stopped=true. The separate persistent manual application remains healthy: login5191 returned200 and Gateway52328 health returned200. All3 original SQLite hashes still match the recorded baselines. Release/main refs remain unchanged. No Git staging/commit/push, cloud settings, original database writes or deployment occurred.

This turn changes scripts/postgres_web_session_qualification.py, docs/autonomy/APPROVALS.md and docs/autonomy/STATUS.md. The earlier source inventory gains the qualification script; all pre-existing feature edits remain preserved. Previous passing frontend812/Gateway241/security20/artifacts4 results remain separate evidence; those full suites were not repeated for this fixture-only edit. Hosted provider isolation,7 moderate npm findings, Linux/OCR/remote Actions and manual screen-reader acceptance remain open.

## 7 November 2026 22:13 SGT — Approved real service setup; exact grant blocker

Owner approved connecting the legacy session harness to real Academic/Scheduling providers followed by one run. Current/base SHA96cbd34a9ea2a040e00061357f7b362485743d4e remains on feature/auth-onboarding-saas, uncommitted. scripts/postgres_web_session_qualification.py now reuses registration_connected_qualification.server for owned loopback Academic and Scheduling apps, configures both with the same marked disposable PostgreSQL runtime and owned Auth verifier, grants SELECT-only academic/scheduling access, disables SQLite fallback and cloud integrations, scopes Gateway forwarding to those owned services, and verifies all3 health endpoints plus unauthenticated identity401. Pool sizes2 are within existing caps. Gateway stops before its dependencies through the existing ExitStack. No browser assertion or service/test timeout changed.

Ruff, AST syntax and git diff --check PASS. Exactly one authorized actual run executed: parent ignored var/auth-saas-evidence/approved-connected-session.log; Auth root classsync-auth-run-e11ca0f406494ebcb4bedc376c0d00cf; PostgreSQL root classsync-pg-8fd4efffd8194b979bbf28db0261e757. All service preflights and sequential identity/role/revocation/recovery/refresh/logout/native200 assertions completed. The final unchanged unexpected-console assertion FAILED with eight503 messages, no runtime JavaScript errors. No browser-result.json or successful whole-run receipt was produced.

Correction to the prior provisional diagnosis: pending timetable requests in browser-failure.json did not establish the source of those eight errors. Full PostgreSQL server.log now shows exactly eight permission-denied errors for classsync_identity.account_claims during browser execution, on SELECT state WHERE tenant_id/uid. Other permission/constraint errors belong to the deliberate foundation and outage negative checks. I missed this Gateway onboarding-status read when specifying the fixture grants. The real downstream service setup is implemented, but it did not resolve this distinct onboarding privilege gap. Do not treat role-journey progress as a passing whole run.

The precise proposed correction is SELECT permission on classsync_identity.account_claims for this generated disposable runtime only; retain ENABLE/FORCE RLS and omit INSERT/UPDATE/DELETE grants. Add a runtime privilege preflight so missing required reads fail before Chromium, and retain the zero-unexpected-console assertion. A single further qualification requires renewed explicit approval under the persistent-failure boundary. No correction/retry after this failed approved run has occurred.

Cleanup verified authStopped=true, childExit=1, deniedOutbound=0; PostgreSQL stopped=true. The separate persistent manual environment still returns200 at login5191 and Gateway52328 health. All3 original SQLite SHA256 values match the prior baselines. Existing release/main refs and pre-existing work remain preserved. No staging, commit, push, cloud setting or deployment changes. Source files changed this turn: scripts/postgres_web_session_qualification.py, docs/autonomy/APPROVALS.md, docs/autonomy/STATUS.md. Earlier passing full suites remain separate evidence and were not repeated. Overall local qualification remains PARTIAL with this exact blocker recorded; hosted/Linux/security release limitations remain unchanged.

## 7 November 2026 22:19 SGT — Final session qualification PASS

Owner approved the exact account_claims read grant, privilege preflight and one session qualification. Current/base SHA96cbd34a9ea2a040e00061357f7b362485743d4e on feature/auth-onboarding-saas remains uncommitted. This closes the previously recorded local legacy-session approval/failure boundary; it does not grant Git/cloud/release authority.

Implemented in scripts/postgres_web_session_qualification.py: grant only SELECT on classsync_identity.account_claims to the generated disposable runtime. Before Chromium, assert that runtime SELECT=true and INSERT/UPDATE/DELETE=false, and assert both relrowsecurity/relforcerowsecurity=true. Successful qualification evidence now records onboarding_read_only_privileges=true only after these checks and the full browser journey pass. Browser assertions, response expectations, worker/service limits and security guards remain unchanged. Direct review verified the internally generated role identifier, parameterized privilege lookup, no application authorization changes and no original-data target. Independent reviewer remains unavailable due its previously recorded usage allowance.

Ruff, AST syntax and git diff --check PASS. Exactly one approved actual run PASS, exit0: node scripts/auth_emulator_qualification.cjs --tools-root <existing pinned official tools> --postgres-bin <installed PostgreSQL bin> --output <new ignored evidence> --browser, from the feature worktree with current package PYTHONPATH and existing Playwright module. Evidence: parent ignored var/auth-saas-evidence/approved-onboarding-read-session.json and .log. Owned root: classsync-auth-run-5ab45597f8dd47daa64a045d04aa9bf7; PostgreSQL root: classsync-pg-38ed465c9ece48e994d4bde42f937943. A successful browser-result.json and whole-run receipt were emitted. This is a new passing run, not reinterpretation of the earlier failed receipts.

Receipt confirms actualFirebaseEmulatorAndCurrentPostgres=true; threeRolesAndDeniedAccess=true; revocationAndOutageRecovery=true; sdkRefreshAndSignOut=true; keyboardFocusPreserved=true; widths360/390/768/1024/1440; nativeZoom2 with real Chrome zoom, keyboard=true, noOverflow=true; runtimeErrors=[] and unexpectedConsole=[]. The unchanged zero-unexpected-console assertion now passes. The role journey includes backend-denied Administrator escalation, current membership reduction/revocation, browser offline/recovery, intentional database/Auth outages, refresh, logout and separately authorized Administrator routing. Read-only privilege preflight passed while FORCE RLS remained enabled. Real Academic/Scheduling/Gateway health checks passed against the same disposable database; SQLite fallback was prohibited. Manual screen-reader and physical-device tests remain unverified.

Cleanup receipt confirms authStopped=true, deniedOutbound=0 and postgres.stopped=true. Existing service context managers completed and verified stopped threads. The separate persistent manual app remains running: http://127.0.0.1:5191/auth/login returned200; http://127.0.0.1:52328/health returned200. Startup remains npm run dev:connected from this worktree; no evaluation timer.

All3 original SQLite hashes match: academic4cd5f60de21bd365c914ac01e5be692b3bea1c7a56a7f17a76c6953ef8668738; schedulingedd232195a1fcf79389bf633ce3fbdc8120705923c5d1441810069a878c1d88d; backup9ec149413d69c1165b74a75e366fa262417c1ecbf41e7029fdd0d86ac96f395d. Release/main refs remain96cbd34a9ea2a040e00061357f7b362485743d4e/aea9494db46153672a31a2161070e5e4ff713966; release worktree is clean. Nothing staged, committed, pushed or deployed.

This turn changes scripts/postgres_web_session_qualification.py, docs/autonomy/APPROVALS.md and docs/autonomy/STATUS.md; all other feature work is preserved. Prior frontend812/Gateway241/security20/artifacts4 gates remain separately recorded; no redundant full suites were run for the fixture-only grant correction. Local connected auth/session qualification is PASS and ready for owner review. Overall release remains PARTIAL/production NO-GO:7 moderate npm findings, authenticated hosted-project isolation/configuration review, approved connected staging acceptance, Linux container/OCR and remote Actions evidence are still open. No further local session retries or approval request are needed for this now-passing journey.

## 10 November 2026 03:15 SGT — Production directive: local Firestore access/onboarding slice

Current/base SHA `96cbd34a9ea2a040e00061357f7b362485743d4e` on `feature/auth-onboarding-saas`. Baseline inventory confirmed the feature worktree descends directly from the clean release checkpoint; the independently dirty main worktree at `aea9494db46153672a31a2161070e5e4ff713966` was not merged or overwritten. Final inventory: main 82 modified tracked / 365 individual untracked, feature 50 modified tracked / 12 untracked, release clean, zero staged in all three. The source/config digest is `5b599b9671f68543275f23f1593fc416175c464ad0ba46260febadd101da84ef`; HEAD plus dirty source is the tested local candidate, not a deployable commit. Receipt with exact source hashes and lockfile digest: ignored parent `var/auth-saas-evidence/production-directive-baseline-preservation.json`.

Firestore Native is required for operational access and onboarding. PostgreSQL remains canonical for academic data, enrollment, generation and publication. Record owners, stable keys, admission/revocation rules, migration/rollback and next actions are in `docs/production/firestore-authority.md`. Updated README, architecture, staging, traceability, Firebase setup and approval ledgers distinguish current SQL runtime, target authority, and qualified local scope.

Implemented transactional Firestore membership reservations and revision-bound revocation receipts, Student claim and Admin decision, Teacher one-use invitations and replacement/revocation, and a bounded shadow importer with persistent checkpoint and read-only parity. Existing Gateway onboarding routes and direct Scheduling were exercised under a test-trust, fail-closed projection bridge. It denies writes to Scheduling and rejects shadow access. The real SQL publication fixture is created before runtime data-write privileges are removed. No production configuration enables the bridge. New files: `services/gateway/app/firestore_access.py`, `firestore_student_onboarding.py`, `firestore_faculty_onboarding.py`; `scripts/firestore_shadow_import.py`, `postgres_firestore_access_qualification.py`; `infrastructure/firebase/firestore.indexes.json`. Existing Auth and onboarding qualification runners gained a fixed `--firestore-slice` entry; no live launcher behavior changed.

Fresh actual role run `production-firestore-role-5.json` PASS with owned Firebase Auth and Native Firestore emulators, real Gateway/Scheduling APIs and new disposable PostgreSQL. Verified email through emulator OOB, exact Student approval replay, unchanged published eight-occurrence Student view, scoped Teacher view, all three workspace roles, no SQL-only or shadow admission, mismatch/outage503, recovery after restoring a matching projection, revoked old token403 despite active SQL, active Teacher denied during Firestore outage, direct Rules403 for unauthenticated/authenticated reads and authenticated write. Invite negatives: wrong email, expired, replaced, revoked, revoked issuer and replay. Concurrent acceptance produced200/403. Shadow dry run wrote nothing, duplicate/orphan rejected, interrupted/concurrent replay and exact membership/reservation parity passed for two records. A new client read the approved grant. Hosted restart, actual outage recovery, and privileged SQL in-flight revocation remain unverified. Auth/PostgreSQL cleanup receipts true, owned Firestore stopped and was unavailable, denied outbound0.

The earlier Teacher run exposed a token/schema mismatch. Independent source review also found issuer revocation, shadow reservation parity and an assumed concurrent ordering issue. Corrected all four, reviewer rechecked the exact fixes, and the new role run passed. Earlier receipts are retained as history, not substituted for the current result. Reproduction command with scoped prerequisites is in the authority contract.

Fresh checks on Windows Python3.12.14/Node22.23.1: Ruff and diff check PASS; focused pytest142 PASS, including synthetic cross-institute locks and publication, authorization, OCR/parser/limit and container-contract tests; Windows synthetic OCR four input types PASS with private fixture purge and cloud_calls0; typecheck/lint PASS; security20 PASS; production-artifact4 PASS including read-only presentation and ordinary SPA/API boundaries. The whole frontend/backend suites and new Firestore browser journey were not run in this phase. Earlier full-suite and session receipts remain separate historical evidence. Docker runtime was not available; Linux OCR boundary tests do not prove native image execution. No remote Actions run was triggered.

Fresh npm audit on unchanged lockfile:7 moderate entries, all associated with GHSA-g3hv-75wg-m249 via @typescript-eslint/typescript-estree8.71.1 → minimatch10.2.6. The production-only dependency tree has no minimatch; release audit policy still blocks. Upstream8.72.1 still requests ^10.2.2 and the advisory patch is11.0.1. No supported in-range remediation established; no override, suppression or policy change. Next: supported parser upgrade with locked regression, or explicit authorized policy disposition.

All3 original SQLite hashes matched before and after. Main/release refs and public presentation deployment are unchanged. No staged files, commit, push, real accounts/data or hosted changes. The existing SQL-backed preview and Gateway health returned200 during this run at5191/52328. No new hosted URL, project approval, deployment digest or production claim.

Decisions: isolated local Firestore role/shadow slice PASS; full local production candidate PARTIAL, next implement the fenced projection writer and integrate all protected operations/OCR without dual authority; hosted staging BLOCKED pending a qualified candidate and separate approved project, budget, region and operators; institutional launch NO-GO pending security, CI/Linux, hosted/provider restore and real account delivery, institution-approved ICS/IBE/ITE inputs/privacy and explicit release authorization. No provisioning approval is sought for this incomplete candidate.

## 10 November 2026 04:18 SGT — Connected hosting configuration review

Base/current `96cbd34a9ea2a040e00061357f7b362485743d4e`, `feature/auth-onboarding-saas`. This is a dirty local candidate. Added a review-only hosting renderer (`scripts/hosting_plan.py`) and a connected Vite build guard with separate Vercel configuration, updated scoped environment examples, Firebase ADC, Cloud Run IAM transport with the end-user Firebase header preserved, managed SQL CA input, and fail-closed hosted container startup. Changed the Gateway, Academic and Scheduling integration points without changing the solver or publication transaction. No change to the tracked presentation `vercel.json`. Usage, safety checks, IAM review, cost inputs and acceptance order: `docs/infrastructure/hosting-automation.md`.

Local evidence: synthetic CLI render produced six ignored review files and a names-only environment inventory. Backend focused suite 226 PASS; after independent review and fixes to ADC app isolation and provider digest selection, focused hosting/token suite 28 PASS. Frontend focused 26 PASS; typecheck, lint, Ruff and diff check PASS. Security 20 PASS; artifact checks 5 PASS (including connected and separate presentation builds). No guard or advisory threshold was changed. The lockfile is unchanged from the current seven-moderate audit receipt, GHSA-g3hv-75wg-m249. Linux Docker/OCR remains unverified: no local Docker or approved runner. The GitHub connector found no PR-triggered run for the base SHA; this is not remote CI evidence for the dirty candidate.

Read-only discovery: Firebase CLI is available without an authenticated CLI account; gcloud and Vercel CLI are unavailable. The owner confirmed signing in to both browser consoles; the connected browser could not verify access to that signed-in session. Provider settings, project isolation, Firebase domain/provider status and Vercel protection are unverified. No mutations, billing, deployment, staging URL or approved target. The next provider access step is supported CLI OAuth/read-only access, distinct from the browser console session. The current setup cannot support a concrete hosted-change approval until the exact projects, costs and owners are verified.

The existing synthetic local frontend `http://127.0.0.1:5191/auth/login` and Gateway `http://127.0.0.1:52328/health` returned 200. Main and release refs match the previous receipt, the release worktree is clean, and all three original SQLite hashes match the previous receipt. Nothing staged, committed or pushed. Local hosting bundle PASS in synthetic review; staging remains BLOCKED on verified access and targets, Firestore publication/revocation fencing, durable reviewed OCR, supply-chain disposition, Linux/CI and actual provider qualification. No hosted-ready or release claim.

04:22 SGT qualification follow-up: the fresh `--firestore-slice` run exited 1 before starting the role journey. PostgreSQL `initdb` timed out under the existing 45-second guard in a newly marked disposable cluster. Its initial cleanup encountered an in-flight single-user bootstrap, but the bootstrap PID subsequently exited and `pg_ctl status` reported no server running for that exact cluster. The Auth receipt reports `authStopped=true`, `deniedOutbound=0`. All three original SQLite hashes were rechecked and still match. The previous 10 November Firestore role PASS remains separate evidence; there is no fresh PASS from this attempt. No timeout or test guard changed. The Python CI lint command now includes the hosting renderer; no remote workflow was triggered.

## 10 November 2026 — Private registration review and deployment target selection

Base/current `96cbd34a9ea2a040e00061357f7b362485743d4e`, `feature/auth-onboarding-saas`. Owner selected `classsync-f444c` for deployment review. The signed-in Firebase General settings showed Environment type Production under `pnm.edu.ph` and an existing ClassSync Web registration. This does not establish isolation or authorize hosted mutation. See `docs/infrastructure/hosting-automation.md` for the remaining target checks.

Implemented `services/gateway/app/firestore_registration.py` and composed the optional repository in the existing scanner routes for local qualification. Firestore stores reviewed academic fields at a project/tenant/UID/scan-scoped key through the original expiry. No raw file, extraction evidence, student number, or timetable is stored. Erasure replaces the fields transactionally with an expiry marker, preventing delayed recreation. Added scanner UI resume copy, a TTL configuration proposal, and route/UI regressions. Independent review found a stale membership response race. The Gateway now revalidates the exact UID, tenant, student binding and revision before returning an institutional match. Normal service startup keeps the existing in-memory scanner pending hosted composition and retention review.

Focused Python scanner/Linux OCR contract/request authorization suite 111 PASS (`python -m pytest services/gateway/tests/test_registration.py services/gateway/tests/test_linux_ocr.py services/gateway/tests/test_request_authorization.py -q`). Focused scanner UI 9 PASS (`npm run test:web -- src/pages/RegistrationScannerPage.test.tsx`). Typecheck, lint, Ruff, JSON parse and diff check PASS. The owned Firestore emulator with synthetic identity exercised actual PDF upload and review, fresh Gateway and SDK client readback, redaction, foreign account/tenant and direct-client denials, erase while another instance held an in-flight review, expiry 404 and outage 503. Final redacted receipt `var/registration-review-qualification-14a6c5321d0c45d39c7ffa6aae9df554/result.json`; the owned emulator stopped. Logical expiration was verified; physical managed TTL and hosted rules/IAM were not exercised.

Original SQLite hashes match the earlier receipt. No staged files, hosted changes or Git ref changes. Local durable review PASS in isolated composition. Next gate is a publication/revocation fence spanning Firestore admission and the existing PostgreSQL commit, followed by release-candidate Linux/CI and provider acceptance. The previous whole-role bootstrap timeout and outstanding npm audit findings remain open.

## 16 November 2026 02:52 SGT — Administrator dashboard command-center slice (PARTIAL)

Base/current SHA `7165fa130e413f8dc8893b85d30ecbe530ef8173` on `feature/auth-onboarding-saas`. Before work, the feature worktree was verified as the target and was already substantially dirty. All pre-existing edits, `main`, branch refs and worktree registrations were preserved. Owner approved only the local UI slice recorded in `APPROVALS.md`; no merge, commit, push, deployment, external-service change, database write or production-data operation occurred.

Implemented the connected `/admin/dashboard` command-center hierarchy: inline period selector, truthful mode badge, period-scoped section/offering/resource/draft links, unified readiness/status card with typed issue-code setup destinations, distinct publication and draft panels, stable loading/error/retry states, refresh action, bounded issue disclosure, responsive CSS, focus styling, reduced-motion-aware CSS transitions, and thinner sidebar scrollbar. The Administrator topbar now opens a grouped selection-only route menu derived from existing available role routes, with arrow/Home/End, Escape, Tab, pointer-close and route-close behavior. Student and Teacher typed local route search remains unchanged. Reused the readiness destination resolver from Academic Generation rather than maintaining a second regex map. Dashboard copy does not claim that schedulable spaces are available/suitable and does not reuse the stale 59-room count. CSS was used instead of adding Motion or changing the lockfile.

Changed for this slice: `apps/web/src/pages/AdminSchedulingHome.tsx`, `apps/web/src/pages/AdminSchedulingHome.test.tsx`, `apps/web/src/components/layout/AppShell.tsx`, `apps/web/src/components/layout/AppShell.test.tsx`, `apps/web/src/pages/AcademicGenerationPage.tsx`, new `apps/web/src/lib/readiness-navigation.ts` and test, `apps/web/src/operational-ui.css`, `apps/web/src/styles/layout/shell.css`, `README.md`, and dashboard plan/approval/roadmap/traceability documents. No backend, contracts, migrations, user records, or database files were modified.

Fresh verification on the final focused source: **49 tests passed across 5 files** (Admin dashboard, AppShell, readiness routing, Academic Management, preview dashboard); `npm run typecheck --workspace=@classync/web` PASS; `npm run lint --workspace=@classync/web` PASS; `npm run build --workspace=@classync/web` PASS. Build retains the existing Firebase mixed static/dynamic import warning and emits a 730.05 kB minified JavaScript chunk (>500 kB warning). A full `npm run test:web` run reported three failures in `src/pages/PresentationRoutes.test.tsx`: PRRC and New Building card assertions each expected 3 but received 4, and the Court `View Court rooms` link assertion was not found. The failures concern the already-dirty updated room/building catalog and are outside this dashboard slice; no unrelated test or inventory files were changed. Full-suite PASS is not claimed.

Visual/browser acceptance is UNVERIFIED: the expected local web/API listener ports were not active and `npm ls playwright --workspace=@classync/web` returned no local Playwright package. No live API, responsive viewport/zoom, manual keyboard browser, or assistive-technology run was claimed. Continue by reconciling the three inventory presentation failures in their own approved scope, then perform real 360/390/768/1024/1440 rendering and native 200%/keyboard review when the local app is available. Production and institutional acceptance remain separate.

## 16 November 2026 04:03 SGT — Administrator secondary screens density and topbar repair (PARTIAL)

Base/current SHA remains `7165fa130e413f8dc8893b85d30ecbe530ef8173` on `feature/auth-onboarding-saas`. The worktree was already dirty before this task; existing source, untracked files, database files, branch refs, and the separate `main` worktree were preserved. Owner-approved scope is recorded in `APPROVALS.md`. No backend/API contract, solver, migration, provider, database data, commit, push, branch operation, or deployment changed.

Implemented the active Administrator command-menu popover in `operational-ui.css` with a 64px locked topbar, right-anchored bounded overlay, two-column grouped route links, horizontal icon/label alignment, and active application CSS load path. `styles.css` now uses the thinner, non-reserved sidebar scrollbar. `AcademicPeriodSetup.tsx` presents seven counted setup selectors and only one active category, preserving calendar disclosure and existing inline record editing. `AcademicManagementPage.tsx` uses record-status selection instead of text search. Schedule Generation and Conflict Center use tighter toolbars/layouts; the conflict checklist reflects checks present in `services/scheduling/app/validation.py` only. The active `/admin/requests` route uses `PreviewRequestsView`, so its preview feed now has counted status filters and compact request rows; notifications likewise remain preview-only, with selection filters and compact update cards. The separate API-backed `ClassroomRequestsPage` has corresponding filtering but is not the currently mounted `/admin/requests` implementation. No new operational request or delivery capability is claimed.

The room presentation regression was aligned to the already-current November 2026 source inventory of 53 spaces across PRRC, New Building, Campus Grounds and Montalban Sports Complex; stale tests expected the former three-group catalog. Updated README, workspace audit, roadmap and traceability describe the implementation and limitations.

Fresh verification on the final code: `npm test` **836 passed / 0 failed across 62 files**; `npm run typecheck` PASS; `npm run lint` PASS; `npm run build` PASS; `git diff --check` PASS with only Git line-ending conversion warnings. Production build still reports the existing Firebase mixed dynamic/static import warning and a **734.29 kB** minified chunk over Vite's 500 kB advisory threshold.

Rendered viewport acceptance is **UNVERIFIED**. Starting Vite failed because port 5173 is already occupied by PID 16276; process command-line inspection was denied, so that existing process was not stopped or treated as the feature worktree. A frontend-only dev server was started on 5174 and stopped after `/dev/role-preview` redirected to sign-in with “University sign-in is unavailable”; no Admin preview was reachable. No target-screen screenshot or pixel-width assertion is claimed. Keyboard behavior was covered by the existing AppShell tests; real-browser responsive, 100% zoom, reduced-motion visual, manual keyboard/focus, and assistive-technology checks remain open. `docs/hci/admin-workspace-audit.md` contains the current screen-specific notes.

## 16 November 2026 13:31 SGT — Command menu, production chunks and live preview qualification (PASS local)

Base/current HEAD remains `7165fa130e413f8dc8893b85d30ecbe530ef8173` on `feature/auth-onboarding-saas`; all previous dirty work and the separate `main` worktree were preserved. This is a follow-up to the prior entry: the existing Vite service on `127.0.0.1:5173` is now reachable and was used without stopping or replacing it. Administrator preview was entered through the app's `/dev/role-preview` flow; this is local presentation data, not connected institutional/provider acceptance.

Updated `apps/web/src/operational-ui.css` so each command-menu category lays out destination links in one column, with a wider bounded two-column category popover, scrollable body/bottom padding, neutral inactive links, burgundy active route, muted icons and a theme-colored focus ring. Added manual `react-vendor`, `firebase-vendor` and `ui-vendor` chunks in `apps/web/vite.config.ts`; `apps/web/src/auth/account-actions.ts` and `university-session-driver.ts` now import the shared Firebase app module consistently instead of mixing static and dynamic imports. Corrected the request-filter test in `apps/web/src/pages/PresentationRoutes.test.tsx` to distinguish the filter button from the request status badge. Updated GitHub README and approval/roadmap/traceability notes. No server/API behavior, records, migration, provider, deployment or branch changed.

Fresh verification: `npm run lint` PASS; `npm run typecheck` PASS; focused PresentationRoutes test **13/13 PASS**; full `npm run test` **837/837 PASS across 62 files**; `npm run build` PASS with **no Firebase mixed-import or chunk-size warning**. Minified JavaScript chunks: `react-vendor` 318.51 kB, `firebase-vendor` 243.27 kB, `ui-vendor` 47.38 kB, app entry 321.16 kB. `git diff --check` PASS with only pre-existing/standard LF-to-CRLF working-tree notices.

Real Chrome/Playwright preview measurements: menu checked at 1366×768, 1440×900 and 1024×768. In each, `.topbar` measured 64px; all 23 destination labels had `scrollWidth <= clientWidth`; active route color was `rgb(135, 46, 73)` and every inactive link `rgb(32, 36, 44)`; focus ring matched Soft Rouge; bottom destination was fully visible after scrolling. The five routes `/admin/academic`, `/admin/ai-scheduling`, `/admin/conflicts`, `/admin/requests` and `/admin/notifications` rendered at 1366×768 and 390×844 with document/body width equal to viewport and no browser `pageerror`. The desktop page picker is hidden on mobile by the existing shell in favor of its navigation drawer. No screenshot file, 200% zoom, device screen-reader or connected service behavior is claimed; those remain open.

## P4d Administrator lifecycle implementation — PARTIAL, 18 November 2026 (SGT)

- **Branch/preservation:** `feature/auth-onboarding-saas`, HEAD `7165fa130e413f8dc8893b85d30ecbe530ef8173`. The candidate worktree was already dirty; its existing edits and untracked files were preserved. The separate `main` worktree was not inspected or changed in this phase. The existing service on port 5173 was left untouched. No live data, original DB, hosted provider, cloud setting, migration/cutover, commit, push, merge, or deployment was touched.
- **Scope:** P4d acceptance cases were written first in `P4D_ADMIN_ACCEPTANCE.md`; scope recorded in `APPROVALS.md`. Current room source remains the 53-row November catalog; this phase did not infer availability, capacity, equipment, or institutional readiness from that provisional catalog.
- **Implementation:** added migration `packages/persistence/classync_persistence/migrations/versions/0017_administrator_activity_audit.py`, creating an append-only, FORCE-RLS, tenant-scoped activity table. PostgreSQL triggers record period creation, academic record create/update, calendar saves, immutable draft saves, and publications with hashed entity references and no copied row payload. Added a bounded Administrator-only `GET /api/v1/timetables/audit/{period}` in `services/scheduling/app/publication_api.py`, tenant-scoped query in `postgres_publication_repository.py`, Gateway Administrator enforcement in `services/gateway/app/main.py`, and institutional activity / clearly labeled synthetic preview in `apps/web/src/pages/PublicationAuditPage.tsx`. Added audit endpoint/provider and Gateway authorization tests, plus `--activity-only` disposable PG qualification in `scripts/postgres_academic_repository_qualification.py`. Updated the synthetic qualification fixture's provisional-room provenance note and stale 59-room test expectation to the current 53-room catalog. Updated `scripts/connected_browser.cjs` to include audit and publication destinations.
- **Disposable PostgreSQL evidence:** command: `.venv/Scripts/python.exe -m scripts.postgres_academic_repository_qualification --bin 'C:/Program Files/PostgreSQL/18/bin' --output var/p4d-evidence/activity-only-20261117.json --activity-only`. PG 18.6 isolated temporary cluster; evidence reports `stopped: true`, `activity_count: 78`, `redacted_admin_activity_triggers: true`, `same_tenant_admin_activity_read: true`, `cross_tenant_activity_rls: true`, `activity_append_only: true`, `payload_values_copied: false`, `fixture_mode: synthetic`, `production_acceptance: false`. A broader academic PostgreSQL qualification attempt passed the activity checks then stopped later at its fixture expectation `Persisted academic snapshot no longer satisfies existing readiness contract`; this P4d run did not change readiness semantics or weaken assertions. No claim is made that the full period-to-publication PostgreSQL chain passed.
- **Backend regression:** command run with `PYTHONPATH=packages/api-contracts;packages/persistence;.`: `.venv/Scripts/python.exe -m pytest -q`; result **1092 passed, 0 failed, 1 warning** in 141.66s. Warning: installed Starlette deprecates using `httpx` with `starlette.testclient`. Full output: `var/p4d-evidence/pytest-20261117-retry.log`.
- **Python static:** `.venv/Scripts/python.exe -m ruff check services packages scripts` → `All checks passed!`.
- **Frontend:** in `apps/web`, `npm run lint` PASS, `npm run typecheck` PASS, `npm run test` **838 passed across 63 files**, `npm run build` PASS (1777 modules). Build output has no Firebase mixed-import warning and no >500kB chunk warning; minified JS chunks are 321.61 kB app entry, 318.51 kB React vendor, 243.27 kB Firebase vendor, 47.38 kB UI vendor, 12.65 kB role workspace. Logs: `var/p4d-evidence/web-lint-20261117.log`, `web-typecheck-20261117.log`, `web-test-20261117.log`, `web-build-20261117.log`. `node --check scripts/connected_browser.cjs` PASS. These are unit/static/build checks, not rendered connected acceptance.
- **Dependency security gate:** a fresh pinned `pip-audit 2.10.1` scan of installed third-party versions found **1 known vulnerability**: CVE-2026-126360 / GHSA-mf5v-w3w3-f6cg in installed `opentelemetry-api 1.45.1`, fixed in 1.45.2 (ReDoS for attacker-controlled trace-context strings in applicable carriers). Added `opentelemetry-api==1.45.2` to `services/security-constraints.txt`. The compatible update was not installed into the application environment and a zero-finding re-scan was not completed: the approval request for the local package installation was rejected because the approval service hit its usage limit. Per instruction, no retry/bypass was attempted. The repository's strict wrapper `scripts/security/python_audit.py` also did not complete because it classified Windows editable package source provenance as unverified; the raw scan result is `var/p4d-evidence/pip-audit-20261117/pip-audit-direct.json`. `npm audit` was not run. Do not describe the security gate as passing.
- **Connected/auth/browser gates:** `node scripts/auth_emulator_qualification.cjs --development` exits with `Missing pinned Auth Emulator tools. See docs/infrastructure/local-connected-development.md.` No owned Emulator + PostgreSQL + Chrome journey could start. The 5173 service was not probed or interrupted. No native 200% browser zoom, keyboard-only flow, focus/announcement test, screen-reader run, or connected create-period → readiness → generate → save draft → validate → publish → calendar/dashboard journey was performed. Mark these UNVERIFIED; current UI/API wiring and unit tests are not substitutes for that evidence.
- **Current phase decision:** P4d **PARTIAL**. The PostgreSQL audit slice and local automated suites passed, but open gates include resolving and re-scanning the Python advisory, qualifying the full PostgreSQL academic fixture, supplying the pinned isolated Auth Emulator tools, running the real connected browser journey, and completing native 200% and keyboard/focus acceptance. No production-readiness claim.

## 18 November 2026 — P4d qualification continuation (PARTIAL)

Branch remains `feature/auth-onboarding-saas`, HEAD `7165fa130e413f8dc8893b85d30ecbe530ef817`. Existing dirty changes and untracked files were preserved. The live `localhost:5173` service was not changed; a read-only probe found it unavailable (`ERR_CONNECTION_REFUSED`). No original database, hosted service, provider setting, branch/ref, or remote system was modified.

Fresh evidence after the readiness-fixture characterization:

- `.venv/Scripts/python.exe -m pytest -q` with `PYTHONPATH=packages/api-contracts;packages/persistence;.`: **1093 passed, 0 failed, 1 Starlette deprecation warning**, 135.71s. Log: `var/p4d-evidence/pytest-20261118-post-fixture.log`.
- `.venv/Scripts/python.exe -m ruff check services packages scripts`: **All checks passed!**
- `.venv/Scripts/python.exe -m pip check`: **No broken requirements found.** This is not a vulnerability scan.
- In `apps/web`, `npm run lint` PASS, `npm run typecheck` PASS, `npm run test` **838 passed across 63 files**, and `npm run build` PASS. Logs: `var/p4d-evidence/web-lint-20261118.log`, `web-typecheck-20261118.log`, `web-test-20261118.log`, and `web-build-20261118.log`. The build reports no Firebase mixed-import or >500 kB chunk warning.
- The corrected full academic PostgreSQL qualification did **not** reach the assertion: non-elevated Windows `pg_ctl` failed at disposable-cluster startup with `could not create restricted token: error code 87`. The disposable PostgreSQL activity-only qualification remains separately PASS with 78 synthetic events; it is not evidence for the full academic/draft/publication journey.
- The feature `.venv` is a junction to `C:\Projects\ClassSync\.venv`, shared with the main worktree. No Python package was installed or upgraded in this shared environment. Existing advisory evidence remains one finding: `CVE-2026-126360` / `GHSA-mf5v-w3w3-f6cg`, installed `opentelemetry-api 1.45.1`, fixed version constrained at `1.45.2`. A clean re-scan is not available; `pip check` does not resolve this gate. The strict scanner provenance limitation and raw scan are recorded above.
- `node scripts/auth_emulator_qualification.cjs --development` remains blocked because pinned isolated Auth Emulator tools are missing. No network installation was attempted.
- A separate presentation-only Vite preview on `127.0.0.1:5193` was used and then stopped. Playwright evidence is `var/p4d-evidence/admin-preview-qa-20261118.json`, script `var/p4d-evidence/admin-preview-qa-20261118.cjs`, screenshots under `var/p4d-evidence/admin-preview-screenshots-20261118/`. At 1366×768 and 390×844, the shell measured 64px topbar, no document/body horizontal overflow, and no page errors. Keyboard checks for route menu/mobile drawer passed (focus entry, arrow navigation, Escape and focus restoration, Tab/Shift+Tab, visible theme focus ring). However, dashboard, academic, generation, conflicts, and audit routes each exposed only one main control in this preview; only calendar had a substantial control count. Treat those routes as **shell/preview-gate measurements only**, not actual screen-level responsive acceptance. The attempted native 200% probe was blocked by Chrome (`ERR_BLOCKED_BY_CLIENT` loading the temporary extension); `native200` is empty. No connected API flow, actual workspace browser acceptance, or manual screen-reader check is claimed.
- Independent read-only review of the activity audit implementation found no critical authorization/RLS defect in the inspected slice. Open production concerns remain: guessable unkeyed entity-reference hashes; migration downgrade dropping audit history; nondeterministic ordering for timestamp ties; no pagination beyond 500 events; and stable Firebase actor UIDs displayed to tenant Administrators. These require a documented policy/fix before production adoption.

Current decision: **P4d PARTIAL / not closed**. Remaining gates are a clean current `pip-audit` with zero findings or approved disposition, corrected full disposable PostgreSQL academic qualification, pinned Auth Emulator setup and connected Administrator lifecycle E2E, real workspace responsive/keyboard acceptance, native 200% zoom, and audit privacy/retention decisions. Next safe action: arrange an isolated Python environment and viable Windows PostgreSQL execution context, then rerun the disposable qualification; keep all original databases and port 5173 out of scope.

## 18 November 2026 — PostgreSQL qualification script corrections (PARTIAL)

The user's latest normal-PowerShell setup is now visible in the feature worktree: branch remains
`feature/auth-onboarding-saas`; `.venv` is a Python **3.12.10** directory, while
`.venv-main-junction` preserves the separate link to `C:\Projects\ClassSync\.venv`. A temp tool
root was found at `C:\Users\lenovo\AppData\Local\Temp\classsync-auth-tools-354b2a1670cc40b4894547335932b187`
with `firebase-tools 15.34.1`, `@opentelemetry/core 2.8.0`, and `uuid 11.1.1`. No port 5173 process,
original database, live data, hosted service, or branch was changed.

Corrected the five reported qualification defects without changing RLS, uniqueness, validation,
scheduler constraints, or migration owner checks:

1. `postgres_academic_period_qualification.py` provisions a generated `NOLOGIN NOSUPERUSER
   NOBYPASSRLS` migrator role and verifies its effective role flags before upgrading through 0008.
2. `postgres_academic_repository_qualification.py` checks exact room IDs/count against
   `services.academic.app.repository.catalog_data()` and requires all provisional capacities to
   remain `None`; stale 59-room expectations are removed from this assertion.
3. Publication qualification setup migrates schema before academic repository writes so
   `period_metadata.data_mode` exists. Provider migration scope resolves the current Alembic head
   through `ScriptDirectory` rather than a stale 0006/0011 constant. Publication qualification still
   tests that an unprivileged owner is rejected at 0008 and that the failed migration rolls back.
4. Synthetic provider identities receive distinct student/faculty records. Student bindings are
   checked before insertion; publication fixtures use the distinct `student-restore` record and the
   corresponding projection regression expectation was synchronized.
5. Scheduling provider migration scope now compares against the repository's resolved current head.

Fresh checks on this corrected source:

- `pytest -q services/persistence/tests/test_publication_projection_fixture.py scripts/tests/test_postgres_qualification_regressions.py`
  → **11 passed, 0 failed, 1 Starlette/httpx deprecation warning**. The seven dedicated qualification
  regression cases cover migrator enforcement, canonical provisional IDs/no capacity, duplicate
  synthetic bindings, and current migration-head selection; the remaining four exercise the affected
  publication projection fixture and guards.
- Full serial `pytest -q` before the final expectation sync → **1090 passed, 3 failed, 1 warning**.
  One failure was the now-updated stale assertion expecting `student-a` after the fixture correctly
  moved to `student-restore`; the targeted rerun above passes. Two solver-dependent failures remain:
  `test_new_run_creates_separate_draft_and_old_snapshot_is_unchanged` rejected an incomplete result,
  and `test_complete_multi_program_batch_and_independent_minutes_check` returned `unknown` at its
  existing 8-second limit. No limit or hard constraint was changed; both are existing scheduling
  blockers and prevent a full-suite pass claim.
- `ruff check scripts services packages` → **All checks passed**.
- `npm run test` in `apps/web` → **838 passed across 63 files**.
- `.venv/Scripts/python.exe -m pip check` → **No broken requirements found**.
- `.venv/Scripts/python.exe -m pip_audit --strict` could not complete: Windows sandbox networking
  denied the connection to `pypi.org` (`WinError 10013`). User reports that `scripts/security/python_audit.py`
  and `pip check` passed in normal PowerShell, but that external audit output has not yet been provided
  as a receipt and is not represented as independently verified here.

The five PostgreSQL/Auth Emulator qualifications have **not** been run in this turn. The user asked
to rerun them in normal PowerShell after these fixes; their report says only the audit qualification
already passed. The script fixes are locally unit-checked but remain **IMPLEMENTED-UNVERIFIED** until
the disposable runs produce receipts. P4d remains **PARTIAL**; connected administrator E2E and browser
acceptance remain open.

## 18 November 2026 — external environment handoff verification (BLOCKED)

The follow-up prompt said the blockers had been resolved outside the sandbox. A fresh read-only check of this feature worktree does not show that setup:

- `C:\Projects\ClassSync\var\feature-auth-onboarding-saas\.venv` is still a **Junction** targeting `C:\Projects\ClassSync\.venv`; it is not an isolated feature environment. The target environment reports Python 3.12.14.
- `py -0p` reports `No installed Pythons found!`; system `python` resolves to Python 3.14. A new environment created with that interpreter would not satisfy the repository's documented Python 3.12 qualification requirement.
- `.venv/Scripts/python.exe -m pip check` → `No broken requirements found.` This does not establish an advisory-free environment.
- `.venv/Scripts/python.exe -m pip_audit --version` → `No module named pip_audit`.
- `node scripts/auth_emulator_qualification.cjs --development` → exit 1, `Missing pinned Auth Emulator tools. See docs/infrastructure/local-connected-development.md.` A scan of the system temp root did not find a `classync-auth-tools-*` installation.
- The repository requires pinned `firebase-tools 15.34.1`, `@opentelemetry/core 2.8.0`, and `uuid 11.1.1`; the supplied `npx firebase-tools@latest` command does not satisfy that pinned-tool gate by itself. Do not infer emulator qualification from a global CLI version.

Therefore the outside-shell commands in the handoff have not yet produced evidence visible to this worktree/session. I did not install packages, replace/remove the `.venv` junction, run a PostgreSQL qualification expected to fail under the same restricted process, start an unqualified backend/frontend, or touch port 5173. No connected E2E attempt was made. P4d remains **PARTIAL**. Required next prerequisite: provide an isolated Python 3.12 environment and the repository-pinned Auth Emulator tool root; then run the disposable PostgreSQL qualifications in a normal shell and make their receipts available in this worktree before connected browser testing.

## 18 November 2026 — local MVP continuation and merge preparation (PARTIAL)

- **Branch/preservation:** Work was performed on `feature/auth-onboarding-saas` at base HEAD
  `7165fa130e413f8dc8893b85d30ecbe530ef8173`. The worktree contained extensive pre-existing dirty
  application, docs, migration, test, script, and local artifact changes before this slice. No reset,
  stash, cleanup, stage, commit, branch switch, merge, push, or deployment was performed. The
  existing service on port 5173 was left alone.
- **Student identity correction:** `onboarding_repository.py` now requires the authenticated Firebase
  email to match the exact lowercase `^[a-z]+(?:\.[a-z]+)*@student\.pnm\.edu\.ph$` format and the
  stored Registrar email byte-for-byte after the format check. A new uppercase-email regression was
  observed failing first, then passed after the minimal correction. Active enrollment and exact
  student ID/email matching remain mandatory; old rows default to `unverified`. The exact generic
  Registrar message remains centralized in `onboarding.py`. No Registrar data was imported and no
  migration was executed against a database.
- **Fresh local verification:**
  - `apps/web`: focused Auth/onboarding tests **18 passed**; full `npm run test` **843 passed across
    63 files**; `npm run lint` exit 0; `npm run typecheck` exit 0; `npm run build` exit 0. Build output:
    React vendor 318.51 kB, Firebase vendor 243.27 kB, UI vendor 47.38 kB, app entry 322.15 kB; no
    oversized-chunk or mixed Firebase import warning.
  - Python: `.venv/Scripts/python.exe -m pytest -q` **1115 passed**, one Starlette/httpx deprecation
    warning. Focused onboarding and qualification-regression tests **24 passed**, same warning.
  - Ruff: `ruff check --no-cache scripts services packages` **All checks passed** using the preserved
    shared Ruff executable via `.venv-main-junction`; the isolated Python 3.12.10 feature `.venv`
    itself does not contain Ruff. `--no-cache` was used to avoid environment/cache writes.
- **Deferred by owner direction:** Do not wait for manual PowerShell receipts, disposable `pg_ctl`
  runs, or isolated `pip-audit` checks to continue local feature development. Those environment-
  specific checks are deferred to CI/pre-release. This does not convert PostgreSQL migration/RLS,
  dependency security, Auth Emulator, connected browser journey, institutional roster, native 200%,
  or keyboard accessibility gates into PASS. The identical Registrar response is covered by
  contract-level tests; response-time equivalence has not been measured and is not claimed. P4d
  remains **PARTIAL** and production readiness is not established.
- **Merge preparation:** `feature/auth-onboarding-saas` is three commits ahead of `main` per
  `git log main..feature/auth-onboarding-saas --oneline`. The root directory is a separate checkpoint
  worktree, not checked out to `main`; main worktree safety/status could not be confirmed in this
  sandbox because Git reports its parent directory as dubious ownership. No global Git safe-directory
  exception was added. Numerous pre-existing untracked files (including `.venv-main-junction/`) mean
  a blanket `git add -A` would be unsafe. Stage reviewed paths in logical commits only after reviewing
  this worktree's complete diff and confirming a clean merge target.
- **Files changed in this slice:** `services/gateway/app/onboarding_repository.py`,
  `services/gateway/tests/test_onboarding.py`,
  `packages/persistence/classync_persistence/migrations/versions/0018_student_roster_verification.py`,
  `README.md`, `docs/autonomy/TRACEABILITY.md`, and this ledger. Other dirty files listed by Git are
  retained from earlier work and were not rewritten as part of this slice.

## 18 November 2026 — Render preview/qualification configuration (NOT DEPLOYED)

- Added `CORS_ALLOWED_ORIGINS` as a validated environment alias while preserving the existing
  `CORS_ORIGINS` name. Its red-first regression and final focused checks pass.
- Extended the existing `Dockerfile` with a default all-service build while retaining explicit
  `SERVICE=gateway|academic|scheduling` CI/Cloud Run images. Added `scripts/render_entrypoint.py`
  to launch Academic, Scheduling, and the current Notification health stub on loopback, then the
  Gateway on `$PORT`; added signal handling, readiness checks, no access logs, and fail-the-container
  behavior if one child exits. The existing service entrypoint remains in use for single-service
  builds. CI now builds the all-service image in addition to the three existing isolated images.
- Added root `render.yaml` with `main` selected, automatic deploys disabled, exact Vercel CORS origin,
  fail-closed security flags, verified-TLS DSN prompts, and no database creation/migration. Added
  `.dockerignore`/`.gitignore` exclusions for the environment junction and local P4d JSON evidence.
  YAML parser validation passes; ignore probes confirm `.venv-main-junction/`,
  `docs/production/p4d-local/`, and `var/p4d-evidence/` stay untracked/ignored.
- Targeted render/CORS/config suite: **41 passed**, one Starlette/httpx deprecation warning. Full
  Python: **1115 passed**, same warning. Web: **843 passed/63 files**, lint and typecheck pass;
  production build pass with chunks 318.51/243.27/47.38/322.15 kB and no earlier chunk/import warning.
  Ruff and `git diff --check` pass. `render.yaml` parses and has the required main/off policy.
- Local Docker is unavailable (`docker` command not found), so container build and supervisor runtime
  are not locally verified; the new all-service image build is assigned to CI. No Render resources,
  Neon resources, environment secrets, Firebase settings, hosted domain/CORS settings, or Vercel
  configuration were created or changed. No deployment was made.
- **Production limitation:** this blueprint uses Render's Free plan only for preview/qualification.
  Its documented idle shutdown, cold-start, ephemeral filesystem, compute limits, and explicit
  non-production guidance mean it does not meet ClassSync production reliability. The Notification
  service also remains a health stub. Keep production blocked unless an approved hosting path passes
  recovery, privacy, latency, and full workflow gates.
- **Merge/push authorization:** the 18 November owner instruction now explicitly authorizes selective
  staging, local commit(s), merge of `feature/auth-onboarding-saas` into `main`, and pushes of both
  refs to `origin`. Earlier approval text prohibiting those Git actions is superseded for this exact
  request. Hosted deployment, cloud provisioning/settings, spending, live-data import, and original
  database migration remain unauthorized.

## 20 November 2026 — Auth cold-start and request hardening

- **Target/state:** inspected and modified only `feature/auth-onboarding-saas`, starting at
  `9ae2676296df0077712a6750415aaafee5632b79`; port 5173 was not touched. Main worktree was
  independently inspected: branch `main`, clean at `097f7e8e8020a2ad8657db1ab65c03612bbaa77d`.
- **Changes:** Render's `scripts/render_entrypoint.py` now starts Academic, Scheduling, and
  Notification before polling their health endpoints concurrently; a partial startup failure stops
  children already started. Gateway exposes `/api/v1/health` for non-blocking auth-screen warm-up.
  Auth HTTP calls use a 45-second timeout and retry one transient 502/503/504 response. External
  Firebase Identity Toolkit, Turnstile, notification, email-provider, and service-health HTTP
  clients use 15-second timeouts (the existing long-lived solver proxy/SSE timeouts are unchanged).
- **Authentication/security:** Google popup invocation is synchronous in the click handler and uses
  an existing Turnstile token; only after Firebase resolves does the client send its ID token and
  challenge to Gateway. Popup-blocked browsers fall back to Firebase redirect with a short-lived,
  one-use session challenge. Password setup and reset send `SecretStr`-backed passwords to Gateway;
  server validation enforces 12+ characters with upper/lowercase, digit, and special character.
  Gateway auth request DTOs protect password, OTP, Turnstile, reset, and invitation secrets; auth
  responses are no-store, response headers include the security baseline and request ID, and a
  bounded five-per-minute per-IP/per-endpoint auth limiter returns `429`/`Retry-After`. CORS accepts strict JSON
  arrays or comma-separated exact origins from either supported environment variable. Error logs
  use reason codes without identity or secret values. This limiter is per process, so production
  still requires the configured edge limiter for distributed enforcement.
- **Tests:** full serial Python suite: `.venv/Scripts/python.exe -m pytest` — **1,147 passed**,
  one Starlette/httpx TestClient deprecation warning, 106.76 seconds. Full web suite:
  `npm run test:web` — **855 passed across 65 files**, 194.59 seconds. `npm run lint`,
  `npm run typecheck`, `npm run build`, and `.venv/Scripts/ruff.exe check` all passed. Build emitted
  no Vite import/chunk warning; final largest JavaScript chunk was 337.04 kB. Focused auth/backend
  qualification also passed: **74 Python tests** and **27 web tests** before the complete suites.
  After the final per-endpoint rate-limit and failed-Google-sign-in cleanup changes, the directly
  affected tests were rerun: **41 Python tests** and **27 web tests** passed; frontend lint,
  typecheck, Ruff, and `git diff --check` were rerun cleanly.
- **Evidence/limits:** no live Render startup, remote Firebase Auth, Turnstile, Resend/Brevo delivery,
  Google popup/redirect in a real browser, device viewport/zoom, or keyboard/screen-reader journey was
  exercised. `npm run test:web` is a React/Vitest suite, not connected E2E evidence. Reset notification
  still runs in in-process FastAPI background tasks; process termination can lose delivery, so a
  durable outbox remains a production reliability task. Production readiness remains unverified.
- **Files changed:** `README.md`, `apps/web/src/auth/AccountOnboardingPanel.test.tsx`,
  `apps/web/src/auth/AccountOnboardingPanel.tsx`, `apps/web/src/auth/account-actions.test.ts`,
  `apps/web/src/auth/account-actions.ts`, `apps/web/src/pages/InstitutionalEntrance.test.tsx`,
  `apps/web/src/pages/InstitutionalEntrance.tsx`, `apps/web/src/styles/pages/auth.css`,
  `scripts/render_entrypoint.py`, `services/gateway/app/coursework_cloud.py`,
  `services/gateway/app/main.py`, `services/gateway/app/onboarding.py`,
  `services/gateway/app/turnstile.py`, Gateway tests for CORS, headers, rate limiting, security
  contracts and concurrent startup, `services/notification/app/main.py`, its email tests, and this
  ledger. No database, provider, cloud setting, credential, original data, or dev server was changed.
- **Git delivery:** implementation commit `817cf225032120104d7f10e40bd821a9a414e55a` was created
  on `feature/auth-onboarding-saas`; merge commit `df539fc7fa4feeb1b39fc1912f5f4e73d2d9a08a` was
  created on `main`. `git push origin feature/auth-onboarding-saas main` succeeded and reported
  `9ae2676..817cf22` for the feature branch and `097f7e8..df539fc` for `main`. Both worktrees were
  clean immediately after the merge. A subsequent `git ls-remote` read-back could not connect to
  GitHub, so no separate remote-ref read-back was obtained.

## 20 November 2026 — Gateway Identity PostgreSQL TLS root

- **Target/state:** root worktree branch `main`, base SHA
  `8c0c3fdba62913df73f29f6f3548b2dc4ad0c388`. Only the existing Gateway identity connection path
  was changed; no other database transport, schema, migration, database data, credential, or running
  development server was changed.
- **Implementation:** `services/gateway/app/authorization.py` continues to use the existing shared
  `postgres_engine` and its `pool_pre_ping=True`; the identity-only configuration now passes
  `sslmode=verify-full`, `sslrootcert=certifi.where()`, `require_auth=scram-sha-256`, and
  `gssencmode=disable`. Academic and Scheduling connection behavior is unchanged. PostgreSQL URL
  query parameters remain rejected, preventing a URL from conflicting with or weakening these
  transport settings. `certifi==2026.10.19` is an explicit Gateway dependency. The existing Docker
  build installs Gateway requirements, so no Dockerfile change is needed. Gateway environment
  examples and README document the URL and CA behavior.
- **Verification:** `services/gateway/tests/test_authorization_lifecycle.py` and
  `services/persistence/tests/test_database_boundary.py` — **46 passed**; identity engine
  construction is verified without opening a connection, the configured URL driver and pool
  pre-ping are checked, and explicit TLS connect args are asserted. Final full serial Python suite
  `.venv/Scripts/python.exe -m pytest` — **1,152 passed**, one existing Starlette/httpx deprecation
  warning, 97.98 seconds. Ruff on the touched Python files passed; `.venv/Scripts/python.exe -m pip
  check` reported no broken requirements; Gateway auth imports and Certifi CA bundle resolution
  succeeded; `git diff --check` passed.
- **Provider boundary:** the local `IDENTITY_DATABASE_URL` is not configured, so a real Neon
  `SELECT 1` and a live membership query could not be run. The existing request boundary continues
  to mask database failures as `membership_unavailable` without exposing URLs or credentials.
  After deployment, TLS success still depends on a valid Neon endpoint/credential and the configured
  database role having required schema/table grants. FORCE RLS tenant context, correct tenant ID,
  and an active membership row must also be valid; absent or revoked membership is an authorization
  denial, while connection/permission failures can remain unavailable errors.
- **Files changed:** `.env.example`, `.env.gateway.example`, `README.md`,
  `packages/persistence/README.md`, `services/gateway/app/authorization.py`,
  `services/gateway/requirements.txt`, `services/gateway/tests/test_authorization_lifecycle.py`,
  `services/persistence/tests/test_database_boundary.py`, and this ledger. Changes remain local and
  uncommitted; Render settings and deployment were not changed.

## 21 November 2026 — open email onboarding and COR activation implementation

- **Scope/base:** root worktree `main`, base `de130d0da91025e93ed5971d16e2be23550d08d7`. Local implementation only; no commit, merge, push, provider change, hosted database operation, or live student data import.
- **Implemented:** normalized domain-neutral email parsing in `packages/api-contracts/classync_contracts/email_address.py`, Gateway/notification/provisioning paths accept valid normalized addresses without requiring `@student.pnm.edu.ph`, and migration `0021_student_email_and_cor_source` relaxes the old roster constraint while recording verification provenance. Default `STUDENT_VERIFICATION_MODE=cor_or_roster` supports verified email plus confirmed server-stored COR activation; `strict_roster` remains configurable. Activation checks duplicate student-number ownership and runs record/membership creation in the existing tenant-scoped transaction. Branded Firebase Admin verification/reset action emails route through Notification. Frontend adds branded `/auth/action`, persistent resend cooldown helpers, student number formatting, a compact COR review, and an Admin dashboard setup journey. README updated to describe the new state and limits.
- **Python evidence:** `.venv\\Scripts\\python.exe -m pytest` collected 1157 and ended **1156 passed, 1 failed, 1 Starlette/httpx deprecation warning** in 223.11s. The remaining failure is `services/scheduling/tests/test_drafts.py::test_new_run_creates_separate_draft_and_old_snapshot_is_unchanged`: the existing unchanged 8-second CP-SAT run returns `unknown`, 0/12 offerings scheduled, and the draft repository correctly rejects it. An isolated rerun reproduced `unknown` in 10.65s; solver result metadata reports 4.6–4.9 seconds wall time. Constraints, limit, validation and assertions were not weakened. Focused relevant Python suite after formatting/migration edits: **101 passed, 1 warning**. `.venv\\Scripts\\ruff.exe check`: **All checks passed**.
- **Web evidence:** first `npm run test:web` hit its fixed 300-second wrapper timeout after streaming many passing assertions; it is not counted as a suite pass. Direct `npm test` after correcting stale fixtures/expectations completed: **859 passed across 67 files** in 383.05s. Focused scanner/auth validation after corrections: **12 passed**. `npm run lint`, `npm run typecheck`, and `npm run build` passed. Build transformed 2186 modules and produced no oversized-chunk or mixed Firebase import warnings; largest chunk was 345.81 kB.
- **Final post-copy reruns:** affected Gateway/registration/Notification/email-contract tests — **75 passed, 1 warning**; affected auth/COR Web tests — **39 passed across 5 files**. Final `npm run lint`, `npm run typecheck`, and `npm run build` passed again on the copy-cleanup tree; largest emitted chunk was 345.82 kB. `pip check` reported no broken requirements.
- **Static/review evidence:** final `git diff --check` passed after fixture/microcopy cleanup and Python formatting. Repository search found no domain-locked email validator or user-facing institutional-domain restriction. Remaining institutional addresses are valid examples/test fixtures; the migration downgrade keeps a bracket-escaped legacy pattern solely to refuse unsafe rollback when personal-address data exists.
- **Open limits:** Full Python suite is not green because of the solver `unknown`; the full PostgreSQL migration was not applied to a disposable or live database; no live Firebase Auth, Brevo/Resend, Turnstile, Registrar roster/COR, Cloudflare, Render, or connected browser verification occurred. Email cooldown/rate limiting uses process-local state and must be replaced or backed by shared storage before multi-instance production. Migration rollback intentionally refuses to discard personal-address/self-verified records. No production readiness claim is made.
- **Changed areas:** README; shared email contract/tests; migration 0021; Gateway auth/onboarding/COR repository and tests; notification action email endpoint/template/tests; live-account provisioning and tests; frontend login/onboarding/account actions/cooldowns/student-number helpers/COR review/admin account review/dashboard guided setup/action route and tests/CSS; this evidence ledger. Generated `package-lock.json` reordering from local npm installation was excluded because no dependency version changed.
- **Next:** resolve the existing deterministic solver `unknown` without relaxing constraints/time limit; qualify migration 0021 and activation/RLS against disposable PostgreSQL; replace process-local cooldown/rate-limit state with shared durable coordination; then run the full Python and browser-connected acceptance gates again.

## 21 November 2026 — delivery receipt

- **Commit:** `410ce68` (`feat(auth): support email-neutral student onboarding`) on `main`; 44 files, 1,384 insertions and 259 deletions. The staged diff passed `git diff --cached --check` before commit.
- **Merge state:** the existing `feature/auth-onboarding-saas` ref (`59193cf`) is already an ancestor of `main` (`de130d0` before this commit), so this change was committed directly on the already-checked-out target branch; no merge commit was needed. The feature worktree's existing `.env.example` modification was preserved.
- **Push:** `git push origin main` succeeded: `de130d0..410ce68 main -> main`.
- **Quality state at delivery:** Web full suite 859/859; lint, typecheck, production build, Ruff, `pip check`, diff check passed. Full Python suite remains 1156 passed/1 failed because the existing 8-second CP-SAT draft regression returns `unknown`; this is not represented as a pass. Migration 0021/PostgreSQL RLS, live auth/email/Turnstile providers, and connected browser flows remain unverified as documented above.

## 21 November 2026 — auth form edge-case follow-up

- **Base/state:** root worktree on `main`, base SHA `8eae95e` (delivery-ledger commit for `410ce68`). Only six auth UI/helper/test files were changed; no database, API, provider, deployment, credential, or Git-history changes.
- **Fixes:** login and recovery `Retry-After` now write only to their own cooldown action; signup persists its verification cooldown without assigning an unused local timer; login never writes cooldowns keyed by a student number. Cooldown keys normalize email identities, and the recovery UI recomputes remaining seconds from the absolute session-storage expiry on each tick. Login validation and Firebase/Gateway submission now use the same normalized email; student-number submissions use trimmed identifiers. Login ID formatting is restricted to numeric student-number shapes and removes an inserted student-number separator when the user continues into an email. Invalid forms remain submittable so field errors can be shown; Turnstile absence yields an accessible alert instead of silent blocking. The login/signup placeholder is now `student@example.com`.
- **Regression coverage:** component/helper tests exercise numeric-prefix and pasted email cases, retry handling for login/signup/recovery, cooldown identity normalization, delayed/background countdown accuracy, mixed-case/padded login submission, inline validation and Turnstile recovery.
- **Verification:** focused auth/helper command — **21 passed across 3 files**; full `npm test` — **864 passed across 67 files**; `npm run lint`, `npm run typecheck`, `npm run build`, and `git diff --check` passed. Production build transformed 2186 modules; largest JavaScript chunk 345.88 kB with no chunk-size or Firebase mixed-import warning.
- **Limits:** no real Firebase/Turnstile provider attempt, browser automation, or connected end-to-end auth journey was run. No commit or push was made.
- **Next:** browser-check the sign-in/signup/recovery paths at narrow and desktop widths, including real Turnstile failure/expiry and background-tab timer behavior when the provider test environment is available.

## 21 November 2026 — auth identifier and recovery timer edge cases

- **Scope/base:** root worktree on `main`, base SHA `8eae95e`. Follow-up to the existing local auth changes; no commit, push, provider call, database operation, or other worktree change.
- **Fixes:** split recovery cooldown initialization from its active timer. The active 500 ms interval recalculates against the persisted expiry and remains scheduled even when two adjacent ticks produce the same rounded second. Login identifier formatting now receives the previous value, preserves pasted or typed intentional hyphens (including `23-juan@example.com` and `20-01425@example.com`), and removes only an auto-inserted separator when the user extends a numeric student-number prefix into a nonnumeric identifier. Login validation now consistently uses the normalized identifier.
- **Regression evidence:** added helper and component coverage for pasted/typed hyphenated emails, the `230` → `23-0` → `23-0j` transition, and a cooldown interval tick that retains the same displayed second before continuing to expiry. Focused tests first failed on the prior behavior, then passed after the fix: **24 passed across 2 files**.
- **Quality checks:** `npm run lint` passed; `npm run typecheck` passed; full `npm test` passed with **868 tests across 67 files**; `git diff --check` passed (Git emitted only its Windows line-ending notices).
- **Data/worktree:** no database or external service was accessed. Existing uncommitted work was preserved. Changes remain uncommitted as requested.
- **Remaining limits:** real browser timing under background-tab throttling and provider-connected auth behavior were not run in this follow-up.

## 22 November 2026 — COR activation and onboarding edge-case follow-up

- **Scope/base:** root worktree on `main`, base SHA `8eae95e`. No commit, push, database/provider operation, or deployment. Existing local auth identifier/timer changes were preserved.
- **Backend fixes:** derive `password_configured` from the Firebase-verified `sign_in_provider` claim and pass it into COR activation; keep existing membership response shape consistent with new activation responses and preserve the stored verification provenance; propagate the actual student-code resend `Retry-After`; require verified email before activation. A committed activation now remains a successful confirmation if the subsequent schedule lookup returns a downstream `401`, `403`, `409`, `422`, or `503`; the response reports schedule lookup as unavailable without exposing downstream details.
- **Frontend fixes:** onboarding resend timers recompute from persisted expiry on a 500 ms interval and resync when account email changes; verification cooldown writes only occur on verification-email resend; completed/current onboarding steps are labeled correctly; use a provider-neutral email placeholder; student ID, OTP, missing Turnstile, and password setup validation can be submitted to show actionable feedback. Manual COR entry no longer presents a forbidden activation action; scan edits clear stale matches, unlisted OCR programs stay visible, and invalid review submission gives feedback. Admin membership revocation now requires an inline per-row confirmation and reports the revoked student ID after refresh.
- **Regression evidence:** backend Gateway/contracts/Notification suite — **348 passed**, one existing Starlette/httpx deprecation warning. Web full suite — **879 passed across 68 files**. Registration route suite — **30 passed** after adding downstream-error-after-activation cases for `401`, `409`, and `422`. Web lint, typecheck, and production build passed; build transformed 2,186 modules and emitted no oversized-chunk warning. Ruff passed for all touched Python files.
- **Independent review:** reviewer confirmed verified-token provider provenance, tenant-scoped uniqueness handling, and Retry-After calculation. It found that post-commit schedule errors `401`/`409`/`422` could still make a successful activation look failed; added regression tests and changed schedule lookup failure to a non-blocking unavailable result.
- **Data/worktree:** no database or external service was accessed. No files were staged or committed. `git diff --check` is the final pending verification after the last Python formatting edit.
- **Limits:** no live Firebase/Registrar/COR provider journey or browser-connected verification was run. PostgreSQL migration/RLS behavior and live scheduling projection remain unverified. The existing solver `unknown` and other open gates remain unchanged.

## 22 November 2026 05:02 SGT — repository artifacts and public asset cleanup

- **Scope/base:** root worktree, branch `main`, HEAD `48b6524`; preexisting local edits in the identity contract/token verification and earlier status ledger were preserved. No commit, push, or index staging. Git refused `git rm` because `.git/index.lock` could not be created, so requested tracked artifacts are represented as ordinary working-tree deletions.
- **Cleanup:** deleted the stale `packages/persistence/build/` copy (13 files, 31,982 bytes, containing only migrations through `0005`), `apps/web/public/branding/classsync_logo_provisional_assets.zip` (774,298 bytes), and unused `apps/web/public/classsync-logo.png` (849,728 bytes). Removed assets total **1,656,008 bytes (1.58 MiB)**. Updated `.gitignore` and `.dockerignore` to explicitly exclude nested Python `build/`, `*.egg-info/`, `__pycache__/`, `.pytest_cache/`, and frontend `dist/`. Updated `docs/branding.md`; no source/doc reference to the provisional ZIP existed.
- **Bundle audit:** source JSON `apps/web/src/data/presentation-timetable.v1.json` is 99,833 bytes and is already loaded with `import()` inside `presentationData()`. Its 361 distinct long string values do not appear in any emitted JavaScript chunk in the institutional production build. No source-loader change was needed. `curriculum-review.json` is 1,761,761 bytes; `packages/api-contracts/classync_contracts/curriculum.py::_catalog()` already loads it on demand with `@lru_cache(maxsize=1)`. Academic service loads it on catalog/course lookup; importing the shared contract, academic record rules, or the pilot helper does not read the JSON at module import time. Gateway proxies the academic endpoints and does not load the catalog.
- **Bundle baseline vs final:** `npm run build` before and after cleanup produced identical JavaScript chunks: app entry 347.62 kB (gzip 89.74 kB), React vendor 318.51 kB (gzip 101.36 kB), Firebase vendor 243.92 kB (gzip 50.05 kB), Motion vendor 125.02 kB (gzip 40.87 kB), UI vendor 48.16 kB (gzip 13.02 kB), and schedule workspace 12.68 kB (gzip 4.18 kB). No chunk-size warning. Vite output no longer contains either deleted public asset; total emitted public payload falls by 1,624,026 bytes (1.55 MiB). JS bundle savings are zero because neither deleted public file was imported by application code.
- **Remaining image reference map:** `classsync-horizontal-light.png` (146,238 bytes) and `classsync-full-light.png` (176,839 bytes) are rendered by `src/components/brand/ClassSyncLogo.tsx`; the full variant is selected at 1280px and falls back to horizontal, with component tests. `classsync-ribbon-mark.png` (337,210 bytes) serves the symbol variant and is component-tested. `classsync-icon-32.png` (1,546 bytes) is the HTML favicon and is checked by hosted/build artifact tests; `classsync-icon-48.png` (2,728 bytes) and `classsync-icon-192.png` (20,176 bytes) are linked by `index.html`; `classsync-icon-192.png` and `classsync-icon-512.png` (95,204 bytes) are also the manifest/touch icons. The three used non-icon PNGs above 100 KB remain for manual optimization review; no Pillow, cwebp, ImageMagick, oxipng, optipng, or pngquant tool was available, and no unverified image conversion was attempted.
- **STATUS history:** archive/rotation was not performed. `AGENTS.md` requires “Append concrete evidence to `docs/autonomy/STATUS.md`”; this entry is appended and prior history remains intact.
- **Verification:** `npm run lint`, `npm run typecheck`, `npm test` (**879 passed / 68 files**), `npm run build` (before and after; identical chunks), full `.venv/Scripts/python.exe -m pytest` (**1,170 passed**, one existing Starlette/httpx deprecation warning), `.venv/Scripts/ruff.exe check` (pass), `git check-ignore --no-index` (all five required artifact examples ignored), deleted files absent from Vite output, and `git diff --check` (pass; only Windows line-ending notices).
- **Next/manual items:** optimize the three active non-icon PNGs with fidelity-preserving source tooling when available. Deletions remain unstaged because the repository index is not writable in this session; no source bundle/code change was needed.

## 22 November 2026 06:06 SGT — Phase 2 backend security and data integrity fixes

- **Scope/base:** root worktree on `main`, base HEAD `48b6524`. Existing edits in this status ledger and in `packages/api-contracts/classync_contracts/identity.py` and `token_verification.py` were preserved. No commit, push, database connection, or external service call.
- **Gateway error envelopes:** scheduling and academic service proxies share `service_proxy`; proxied error codes are pattern-checked and messages pass through `safe_public_error_message`. Unknown response shapes and unsafe diagnostics receive a generic public message. Added regression cases for safe messages, SQL/schema diagnostics, malformed error objects, and non-object payloads.
- **Rate limits and COR conflicts:** in-process email cooldown and login bucket maps now purge expired entries before capacity checks and fail closed for new keys instead of evicting active entries. Added tests for retained active cooldowns/lockouts and expired-entry cleanup. COR student insertion now uses untargeted `ON CONFLICT DO NOTHING`; a conflicting registered email becomes the existing clean 409 response.
- **Persistence and history:** added migration `0022_classroom_request_indexes` after `0021_student_email_and_cor_source`, creating owner-timeline and tenant-timeline indexes for the existing `classsync_scheduling.classroom_requests` table. Downgrade drops both indexes. Publication history now uses newest-first SQL `LIMIT`/`OFFSET`, with API limits 1–100 and offset max 10,000. Metadata-only pages avoid reading snapshot payload columns; the publication review panel opts into details and requests one row. The preview history UI has 50-row pagination.
- **Security documentation:** `docs/security.md` now states in-process rate limits protect one Gateway instance and need edge/shared limiting when scaling replicas.
- **Verification:** focused Gateway tests **48 passed**; migration revision/provider/publication tests **16 passed**; focused web publication tests **3 passed**. Final full `.venv/Scripts/python.exe -m pytest -q`: **1,180 passed**, one existing Starlette/httpx deprecation warning. `.venv/Scripts/ruff.exe check`: passed. Web `npm run lint`, `npm run typecheck`, `npm test` (**880 tests, 68 files**) and `npm run build` passed; build transformed 2,186 modules, largest JS chunk 347.81 kB, no chunk-size warning. Final `git diff --check` passed.
- **Limitations:** no disposable PostgreSQL migration execution or live Gateway/replica rate-limit exercise was performed. Existing in-process limiters remain per-process by design. No existing work was staged or committed.

## 23 November 2026 03:14 SGT — Phase 3 CSS and design-system cleanup

Worktree: `C:\Projects\ClassSync`, branch `main`, base/current HEAD
`a9ef3c2d330cb73a2005093c83be382eec06747c`. Existing unrelated worktree edits were preserved;
none were present at start of this slice. No application behavior, backend, data, dependencies,
Tailwind directives, PostCSS, or Preflight configuration was changed. No commit or push occurred.

Deleted 21 verified orphan stylesheets under `apps/web/src/styles/` and removed the old
`styles/pages/auth.css` after moving its rules after `pages/institutional-entrance.css` rules in
the latter canonical sheet. The email-action and institutional entrance imports now load that
single sheet. Removed exact duplicate declarations only: four entrance-sheet declarations
(`.connected-entrance__frame { display:grid }`, duplicate `.connected-entrance__access`
`grid-row`/`grid-column` placement), three academic/operational declarations (jump overflow,
records-row alignment, actions alignment), three `.topbar` declarations already supplied by
later `operational-ui.css`, and exact auth declarations shadowed by the canonical later auth
rules. Retained differing layout values, all `!important` operational declarations, reduced-motion
rules, and the 1024px responsive token overrides. `theme.css` remains the active token authority;
`styles/tokens.css` was orphaned and deleted.

Removed 22 CSS files total (the 21 orphans plus the replaced auth sheet). CSS source inventory
went from 288,785 B to 206,605 B, net reduction 82,180 B. Existing CSS build artifact before:
172,857 B. Final `apps/web/dist/assets/index-CFCch1U6.css`: 172,033 B, reduction 824 B (gzip
30.74 kB). Build transformed 2,185 modules and passed.

Verification on the final tree: `npm run lint` PASS; `npm run typecheck` PASS; focused
`npx vitest run src/pages/PublicationPanel.request.test.tsx` PASS (1 test); `npm run build` PASS;
`git diff --check` PASS. The final full `npm test` attempt was not green: 65 files passed, one
publication-panel test failed, and two Vitest fork workers timed out starting. The failing test
passed in isolation. An initial whole-suite attempt before the later cascade corrections passed
880 tests across 68 files; it is not represented as final-tree evidence.

No runtime imports or tests reference deleted orphan files. The HCI plan now points to active
stylesheets; remaining `STATUS.md` references to former auth/shell stylesheets are historical
change receipts and were preserved. No screenshot/pixel-diff comparison was run; visual
preservation was checked by retaining rule order/media scopes and removing only exact cascade
duplicates. Current full test suite should be rerun in a less-contended environment.

### Phase 4A — Route-level code splitting and development-route gating — PASS locally, 23 November 2026

Worktree: `C:\Projects\ClassSync`, branch `main`, base/current HEAD
`02ce81e064a0eb5e4d23f85c9e620db5c3d8bcca`. The worktree was clean before this slice; no prior
uncommitted work was present. No commit or push occurred.

Captured a fresh baseline build before editing. The entry JS was **347,813 B (89.83 kB gzip)**;
the React, Firebase, motion and UI vendor chunks were respectively 318,505 B, 243,924 B, 125,017 B
and 48,161 B. `RouteGuard` now lazy-loads connected and preview leaves behind status-announcing
Suspense surfaces, while session/role checks, `AppShell`, route guard, and login remain eager.
The student schedule and preview-only operations/building panels now load on demand. Onboarding
and account-administration panels load only when their authenticated screens render. Institutional
route construction omits `/dev/design-system` and `/dev/role-preview`; sandbox and presentation
route construction keeps them. The Vite vendor chunk rules were unchanged and did not pull lazy
page modules back into the entry.

Final build: entry **96,488 B (25.83 kB gzip)**, a reduction of **251,325 B / 72.2%** versus the
baseline entry. Route chunks include AcademicManagementPage 60,312 B, ProductScreenPage 29,909 B,
SchedulingDraftPages 16,402 B, RegistrationScannerPage 13,943 B, OperationsPreviewPage 13,075 B,
AcademicGenerationPage 11,167 B, StudentHome 9,530 B, ClassroomRequestsPage 8,300 B,
StudentSchedule 7,970 B, and AccountOnboardingPanel 10,360 B. The four vendor chunks remain
preloaded by Vite; their sizes are unchanged. No oversized-chunk warning was emitted.

Timing-only test updates wait for lazy route content before checking the same route, role,
navigation, and data assertions. A first full run exposed 43 synchronous-query failures after the
lazy boundaries; the affected route suites were updated, then passed focused verification. The
final full web suite passed **883 tests across 69 files**. `npm run lint`, `npm run typecheck`,
`npm run build`, and `git diff --check` also passed. No authorization assertions were weakened.

Changed application files: `apps/web/src/routes/RouteGuard.tsx`, `app-routes.tsx`,
`pages/StructuredCalendarPage.tsx`, `pages/ProductScreenPage.tsx`,
`pages/InstitutionalEntrance.tsx`, `config/app-mode.ts`. Added
`apps/web/src/config/development-routes.test.ts`; updated connected, institutional, preview,
room-navigation and route-reliability tests. `dist/` contains the ignored local build output.
No browser screenshot or production-mode deployed navigation test was run. Next: visually verify
lazy loading fallbacks on direct deep links and confirm production CDN caching/waterfall behavior.

## 24 November 2026 15:10 SGT — Phase 0 production routing and CI repair

Worktree: `C:\Projects\ClassSync`, branch `main`, base/current HEAD
`2313efd3c11aa03c614bdf966ca3c5cf688ad784`. The pre-existing uncommitted dependency-security
changes in `apps/web/package.json`, `package-lock.json`, and this status file were preserved; no
commit, push, deployment, hosted setting, database, or live service was changed.

Acceptance cases for this bounded Phase 0 work:

- The Linux container qualification retains read-only root filesystems, dropped capabilities,
  no-new-privileges, and health/denial/outage-recovery assertions; failures print container state
  and bounded logs before cleanup.
- Institutional browser API requests stay at same-origin `/api/v1`, are reverse-proxied to the
  configured Render Gateway, and the client same-origin guard remains enabled.
- Render's Firebase project ID matches the production frontend project supplied by the owner;
  the Render blueprint declares Resend credentials instead of unused Brevo credentials.

Implemented: raised the three long-running Linux qualification containers' hard memory limit from
1 GiB to 2 GiB; added an EXIT failure diagnostic that prints `docker ps -a`, each named container's
status/OOMKilled/exit code, and at most 40 log lines before cleanup. The 1 GiB cap is the leading
explanation for exit 137: the Gateway's qualification exec starts a second Python process within
the running container's memory cgroup. The raw failed-run log/cgroup event is unavailable and
Docker is not installed here, so the specific killed process remains **unverified**. The current
checked-in workflow starts three long-running service containers; the supplied Run #52 excerpt
mentions four container IDs, which may reflect a different workflow revision.

Added a fixed external rewrite for `/api/v1/:path*` to
`https://classsync-o3u3.onrender.com/api/v1/:path*` ahead of SPA rewrites. Vercel's external
rewrite keeps the browser URL unchanged and proxies requests to the external origin ([Vercel
rewrite documentation](https://vercel.com/docs/routing/rewrites)). Existing API clients continue
to send Firebase bearer tokens, omit cookies, and enforce same-origin URLs; no auth/CORS/CSRF
guard was removed. Updated `render.yaml`'s `FIREBASE_PROJECT_ID` to `classsync-8af14` per the
owner's current-production observation and changed the blueprint email provider to Resend with
`RESEND_API_KEY` and `RESEND_FROM_EMAIL` as unsynced secrets. Historical docs and explicit
non-disclosure test assertions for `classsync-f444c` remain as historical evidence/tests.

Fresh verification:

- System `python -m pytest` could not start (`pytest` is not installed in system Python); the
  repository runtime `.venv\Scripts\python.exe -m pytest` passed **1,194 tests** with one
  existing Starlette/httpx deprecation warning.
- `.venv\Scripts\ruff.exe check scripts services packages` — PASS.
- `.venv\Scripts\python.exe scripts/export_scheduling_contracts.py --check` — PASS.
- In `apps/web`, `npm run lint` and `npm run typecheck` — PASS; `npm run build` — PASS.
- In `apps/web`, `npm test` — **882 passed, 1 failed** across 69 files. The failure is the
  existing `RoomNavigation.test.tsx` focus assertion after pagination: expected the “Rooms &
  spaces” heading, received `main#main-content`. It is outside this Phase 0 scope and was not
  changed.
- In `apps/web`, `npm audit --audit-level=low` — BLOCKED because the npm registry audit endpoint
  returned a network error. Existing dependency-security changes were not modified.
- `vercel.json` parsed as JSON; `render.yaml` parsed successfully with `js-yaml`.
- `git diff --check` — PASS on the final worktree; Docker qualification was not runnable because the
  Docker CLI is unavailable. No deployed same-origin request, live login, or hosted variable was
  verified or changed.

Changed for this Phase 0 slice: `.github/workflows/quality.yml`, `vercel.json`, `render.yaml`, and
this appended evidence. Pre-existing dependency-security files remain dirty and preserved.
Next: verify/update the exact Vercel/Render environment values listed in the task before an
authorized deployment, then inspect the next Linux qualification run's failure diagnostics.

## 23 November 2026 19:46 UTC — Dependency security job follow-up

Worktree: `C:\Projects\ClassSync`, branch `main`, base HEAD
`2313efd3c11aa03c614bdf966ca3c5cf688ad784`. Worktree was clean before this task. No commit,
push, database, provider, cloud setting, or running service was changed.

Updated the Web workspace `typescript-eslint` dependency from `^8.24.0` to `^8.74.0` and
refreshed the root lockfile. The previous locked `8.71.1` tree resolved
`@typescript-eslint/typescript-estree` to vulnerable `minimatch@10.2.6`; the new compatible
8.x tree resolves patched `minimatch@11.0.9`. No forced major update was used.

Evidence: `npm ci --ignore-scripts` — PASS, 416 packages added, 419 audited, zero vulnerabilities;
`npm audit --audit-level=low` — PASS, zero vulnerabilities;
`npm ls --all` — PASS;
`apps/web`: `npm run lint` — PASS; `npm run typecheck` — PASS; `npm test` — PASS, 883 tests in
69 files; `npm run build` — PASS. The build emitted no fatal errors. `git diff --check` passed.

Linux container job remains unresolved. Public GitHub run 52 (`45128001383`, HEAD above) confirms
the `linux-containers` job's combined qualification step ended with exit code 137. GitHub's public
check annotation contains only that generic code; downloading the job log returned HTTP 403
(`Must have admin rights to Repository`). Docker is not installed in this environment, so the
container sequence could not be reproduced. In the checked-in workflow, after the three service
containers start, the first command is `docker exec ...gateway python -m
scripts.linux_runtime_probe --health`; this ordering makes it the first candidate if the failure
occurred immediately after startup, but the exact SIGKILLed command and root cause are unverified.
No speculative memory-limit change was made. Next: obtain the failed step's raw log from a repository
administrator, then reproduce/fix the exact command without weakening the health, denial, or recovery
assertions.

Files changed in this follow-up: `apps/web/package.json`, `package-lock.json`, and this status entry.

## 24 November 2026 16:04 SGT — Phase 0 Gateway container startup correction

Worktree: `C:\Projects\ClassSync`, branch `main`, HEAD
`2313efd3c11aa03c614bdf966ca3c5cf688ad784`. Preserved all prior uncommitted edits; no
database connection, provisioning, hosted setting, commit, or push occurred.

Restored the three qualification containers to `--memory 1g` after the supplied diagnostics
ruled out OOM, and passed `CLASSSYNC_WEB_URL=https://class-sync-bhiv.vercel.app` into them so
Gateway production-origin validation uses HTTPS. Kept the failure-only Docker diagnostic trap.

Traced `membership_unavailable`: the shared membership contract emits it when a membership
repository raises or returns a non-`MembershipSnapshot`; the unconfigured repository also raises
it. Gateway, Academic, and Scheduling map that condition to 503. A missing/inactive/wrong-tenant
membership maps to 403 `membership_denied` instead. Academic independently checks current
membership when `/api/v1/academic/periods` is proxied, using `ACADEMIC_DATABASE_URL`; Gateway
`/api/v1/auth/me` uses `IDENTITY_DATABASE_URL`. Exact `/api/v1/me` is not a registered Gateway
route in this checkout. No production identity/database state was inspected.

Verification: `js-yaml` parsed `.github/workflows/quality.yml` and assertions confirmed the HTTPS
origin, restored 1 GiB limit, and retained trap; `.venv\Scripts\python.exe scripts/provision_live_accounts.py --help`
printed the existing provisioning CLI options without
connecting to providers; `git diff --check` passed. No Docker execution or live API request was
performed.

## 24 November 2026 16:06 SGT — Phase 0 qualification environment follow-up

Worktree: `C:\Projects\ClassSync`, branch `main`, HEAD
`2313efd3c11aa03c614bdf966ca3c5cf688ad784`. Restored the `linux-containers` service memory cap
to 1 GiB and set `CLASSSYNC_WEB_URL=https://class-sync-bhiv.vercel.app` in its container loop;
failure diagnostics and all hardening remain. `js-yaml` syntax/settings check and `git diff --check`
passed. Read-only source trace confirms Academic independently uses
`ACADEMIC_DATABASE_URL` for the current membership lookup. No database, hosted configuration,
identity, or live provisioning was accessed or changed; no commit or push.

## 24 November 2026 17:03 SGT — Phase 0 membership TLS and web CI stability

Worktree: `C:\Projects\ClassSync`, branch `main`, base/current HEAD
`0391e2fb4ae064069816e7a6e13c025ad5f83516` (changes remain uncommitted). Academic and Scheduling
membership engines now use the Gateway-proven Certifi CA bundle for `verify-full`, with the
dependency declared in both isolated service requirements. Shared membership lookup failures
log exception type and bounded, sanitized detail in the rendered log message; focused coverage
checks URL, credential, token redaction. Added Academic/Scheduling TLS configuration tests.

The presentation reset test now waits for its conditional reset control; calendar fetches ignore
all stale aborted requests. Room pagination focus runs after the page state commits, and the
navigation test waits for route and pagination focus changes. Both affected frontend test files
passed 3 consecutive runs (33 tests per run).

Verification: `.venv\Scripts\python.exe -m pytest` — 1197 passed, 1 existing Starlette/httpx
deprecation warning; `.venv\Scripts\ruff.exe check scripts services packages` — passed;
`.venv\Scripts\python.exe scripts/export_scheduling_contracts.py --check` — passed;
`npm run test:web` — 69 files / 883 tests passed; in `apps/web`, `npm run lint`,
`npm run typecheck`, `npm test` (69 files / 883 tests), and `npm run build` — passed;
`git diff --check` — passed (Git emitted line-ending normalization notices only). No live Render
database, hosted configuration, or membership record was accessed or changed. No commit or push.
Next: deploy through the separately authorized release process and verify production membership
lookups; do not advance into Phase 1/2 here.

## 25 November 2026 07:23 SGT — Phase 1 admin UX and loading states; Phase 2 source gate

Worktree: `C:\Projects\ClassSync`, branch `main`, base/current HEAD
`01d01229430b2284739454468f0fd734182d15f1` (no commit or push). Implemented admin setup overview
with six linked, ordered steps and saved-record readiness/counts; clarified period and record forms,
including reviewable campus scheduling defaults; added search/year/section/status filtering and
20-row pagination where supported. Resource counts reflect actual verification flags. Added
lightweight ClassSync page, skeleton and inline-button loading states, reduced-motion CSS, and
wired them across route, academic, admin, teacher, student and account workflows. A focused
academic validator change lets an admin edit provisional room type while keeping it explicitly
unverified; regression coverage ensures the edit does not claim verification.

Phase 2 institutional data seeding and bulk verification are BLOCKED on authoritative input:
repository review found no approved complete BSIT curriculum, numeric room capacities/equipment,
faculty qualifications/availability, or student roster source. Existing campus inventory includes
53 spaces, of which source metadata marks 41 schedulable and 12 excluded; no room was falsely
verified or assigned inferred capacity/type. No seed script or seed tests were added, and no Neon
or other live data was read or written. Truthful synthetic/presentation labels remain in local
presentation paths so the product does not imply generated data are official. No student PII was
created. Responsive/browser/screen-reader manual review remains open.

Files: `docs/autonomy/STATUS.md`; `apps/web/src/academic-management.css`; `apps/web/src/auth/TurnstileWidget.tsx`;
`apps/web/src/components/loading/ClassSyncLoading.tsx`; `apps/web/src/components/loading/loading.css`;
`apps/web/src/components/loading/ClassSyncLoading.test.tsx`; `apps/web/src/components/scheduling/PresentationConflictSummary.tsx`;
`apps/web/src/components/ui/Button.tsx`; `apps/web/src/pages/AcademicCalendarEditor.tsx`;
`apps/web/src/pages/AcademicGenerationPage.tsx`; `apps/web/src/pages/AcademicManagementPage.test.tsx`;
`apps/web/src/pages/AcademicManagementPage.tsx`; `apps/web/src/pages/AcademicPeriodSetup.tsx`;
`apps/web/src/pages/AcademicRecordEditor.tsx`; `apps/web/src/pages/AccountProfilePage.tsx`;
`apps/web/src/pages/AdminSchedulingHome.tsx`; `apps/web/src/pages/AnnouncementsPage.tsx`;
`apps/web/src/pages/ClassroomRequestsPage.tsx`; `apps/web/src/pages/ConflictCenterPage.tsx`;
`apps/web/src/pages/ConnectedRoomsPage.tsx`; `apps/web/src/pages/ConnectedUpdatesPage.tsx`;
`apps/web/src/pages/CurriculumSelection.tsx`; `apps/web/src/pages/EmailActionPage.tsx`;
`apps/web/src/pages/InstitutionalEntrance.tsx`; `apps/web/src/pages/ProductScreenPage.tsx`;
`apps/web/src/pages/PublicationAuditPage.tsx`; `apps/web/src/pages/PublicationPanel.tsx`;
`apps/web/src/pages/R1Presentation.test.tsx`; `apps/web/src/pages/RoleScheduleWorkspace.tsx`;
`apps/web/src/pages/ScheduledRooms.tsx`; `apps/web/src/pages/SchedulingDraftPages.tsx`;
`apps/web/src/pages/StructuredCalendarPage.tsx`; `apps/web/src/pages/StudentHome.tsx`;
`apps/web/src/pages/StudentRooms.tsx`; `apps/web/src/pages/StudentSchedule.tsx`;
`apps/web/src/pages/TimetableValidation.tsx`; `apps/web/src/routes/RouteGuard.tsx`;
`apps/web/src/routes/app-routes.tsx`; `services/academic/app/record_rules.py`;
`services/academic/tests/test_record_rules.py`.

Verification: `.venv\\Scripts\\python.exe -m pytest` — 1,198 passed (one existing Starlette/httpx
deprecation warning); `.venv\\Scripts\\ruff.exe check scripts services packages` — passed;
`.venv\\Scripts\\python.exe scripts/export_scheduling_contracts.py --check` — passed;
`npm run lint` — passed; `npm run typecheck` — passed; `npm test` — 70 files / 889 tests passed;
`npm run build` — passed, main JS entry 97.61 kB raw / 26.18 kB gzip; `git diff --check` — passed
(Git reported only LF-to-CRLF normalization notices). No hosted settings, live database or external
service was changed. Seed acceptance and end-to-end institutional verification remain pending
official source data and a separately authorized live-data operation.

### 25 November 2026 09:44 SGT — owner-authorized defense dataset implementation

Worktree: `C:\Projects\ClassSync`, branch `main`, base/current HEAD
`6dbb2c1d454023e52eb3f2393a020f656ed73b39`. The approval records a narrow defense-data exception:
AY 2026–2027 first semester (2026-08-01 through 2026-12-31), 41 catalog schedulable spaces and
12 catalog-excluded spaces. No commit/push, deployment, live database connection, migration, or
`--apply` occurred.

Added `scripts/seed_campus_data.py` with an explicit defense environment gate, exact tenant
confirmation for `--apply`, stable IDs, TLS `verify-full`, atomic repository writes, seed rerun
preservation, and a dry-run path. It provisions 32 editable BSIT curriculum records, 8 sections,
12 faculty, 54 offerings, 96 unverified roster identities, owner-authorized defaults, and only the
41 catalog-approved schedulable rooms. The 12 excluded rooms are not written. Added migrations
0023/0024 for display names and academic record deletion audit, and an Admin UI bulk action whose
candidate list and ready counts both use the canonical 41-ID allowlist. Individual academic
records retain normal edit/delete actions. Added a paginated institutional roster view; student
identity rows are currently displayed read-only because the existing service has no authorized
student-profile edit/delete route. Student CRUD remains open and must not be represented as complete.

The owner authorized synthetic defense records, but those records remain unverified against
Registrar/Facilities source. The roster identities are unverified and do not create Firebase
accounts, memberships, consent, or email delivery. Migration execution and RLS behavior against an
isolated PostgreSQL instance remain IMPLEMENTED-UNVERIFIED; no live Neon query/write was made.

Changed files: `AGENTS.md`, `docs/autonomy/APPROVALS.md`, `apps/web/src/lib/academic-api.ts`,
`apps/web/src/pages/AcademicManagementPage.tsx`, `apps/web/src/pages/AcademicManagementPage.test.tsx`,
`apps/web/src/pages/AcademicRecordEditor.tsx`, `apps/web/src/pages/ProductScreenPage.tsx`,
`apps/web/src/pages/AcademicStudentRosterPage.tsx`,
`apps/web/src/pages/AcademicStudentRosterPage.test.tsx`, Academic and Scheduling contract models,
generated scheduling JSON/TypeScript contracts, Academic service repositories/routes/tests,
`services/scheduling/app/academic_input.py`, migrations `0023_person_display_name.py` and
`0024_academic_record_deletion_audit.py`, `scripts/seed_campus_data.py`,
`scripts/tests/test_seed_campus_data.py`, and `scripts/tests/test_postgres_qualification_regressions.py`.

Verification: `.venv\\Scripts\\python.exe -m pytest` — 1,201 passed, one existing Starlette/httpx
deprecation warning; seed/migration regression subset — 12 passed; Ruff — passed; contract export
`--check` — passed; frontend lint/typecheck — passed; final `npm test` — 891 passed across 71 files.
Final `npm run build` passed; main entry `index-H1SfvGhn.js` is 97.62 kB raw / 26.19 kB gzip.
`git diff --check` passed with line-ending normalization notices only. The initial frontend run
under concurrent heavy load had 4 route/navigation timeouts; the isolated full rerun and final
full rerun both passed. Independent review findings on unknown room IDs, post-action count
consistency, and seed overwrite preservation were addressed; review did not access a database.
