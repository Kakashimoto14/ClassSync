# Bounded P1 execution contract — 2026-10-21

Baseline: main, `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`, clean before edits. Owner authorizes local P1 only. No P2, migrations, authentication implementation, solver changes, Firebase settings, dependency upgrades, commits or deployment.

## Before-edit specification

Checkpoint 1 adds `src/config/app-mode.ts`, runtime configuration and exhaustive mode tests; integrates Vite configuration. Checkpoint 2 changes preview/presentation/sandbox compatibility exports, RouteGuard and the four academic/scheduling/calendar/publication API clients. Checkpoint 3 changes build-presentation, release generation, preview artifact server, artifact tests, package scripts and Quality CI. Checkpoint 4 adds boundary tests, regression evidence and architecture/security documentation corrections. UI changes are limited to truthful unavailable descriptions; branding and navigation architecture remain intact.

Configuration precedence: process environment overrides Vite-loaded env files; Vite mode-specific files override generic files. Validate canonical `VITE_CLASSSYNC_MODE` and exact legacy booleans before resolution. Explicit presentation build target rejects contradictory configuration. No browser storage/query parameter participates. Build command rejects sandbox regardless of Vite mode or NODE_ENV. Production NODE_ENV also rejects sandbox serving.

| Canonical | Legacy flags | Serve development | Any distributable build |
|---|---|---|---|
| absent | absent/false | sandbox | institutional |
| absent | either true, other absent/true | sandbox | presentation |
| absent | true and explicit false | sandbox | reject |
| presentation | absent/true only | presentation | presentation |
| sandbox | any valid boolean | sandbox | reject |
| institutional | absent/false only | institutional | institutional |
| invalid | any | reject | reject |

Development default preserves the current connected local workflow. Institutional mode grants no preview identity or live access until production authentication exists. Presentation forces the existing versioned bundled sample; APIs fail before fetch, never substitute samples after live failure. Capabilities describe frontend availability only; server token checks and explicit development sandbox gates remain authoritative.

Acceptance: resolver matrix and malformed configuration tests; P0 8-hour persistence/expiry and role switching; API no-fetch in presentation/institutional; all role routes and refresh; assets retain precedence; missing API/assets return non-HTML 404; metadata commit/appMode/capabilityVersion plus legacy presentation mode; all builds reject sandbox including development NODE_ENV; lint, typecheck, web/Python tests, Ruff, ordinary/presentation builds; actual 390/1440 rendered checks, keyboard/focus and native zoom where tooling permits. Skips/failures are not passes.

Rollback: review and reverse only P1's file diff, preserving other work. No database rollback is required because P1 never opens the originals for writing. Tests use temporary database paths. Initial SHA256:

| File | SHA256 |
|---|---|
| var/academic.sqlite3 | 4cd5f60de21bd365c914ac01e5be692b3bea1c7a56a7f17a76c6953ef8668738 |
| var/scheduling.sqlite3 | 1848377cc9a9eb656e12b5e58436e81198fef92f18dd71c1fea2f6f8b482e400 |
| var/backups/scheduling-before-s2b-20261018074057.sqlite3 | 9ec149413d69c1165b74a75e366fa262417c1ecbf41e7029fdd0d86ac96f395d |
