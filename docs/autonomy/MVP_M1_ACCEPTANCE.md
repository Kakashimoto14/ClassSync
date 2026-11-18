# M1 account lifecycle acceptance — 4 November 2026

- Firebase email/password signup, verification/resend/refresh, login, recovery,
  restored session and logout; errors remain actionable and do not grant roles.
- Pending authenticated users can read only their own onboarding status and submit
  one student record claim. Unverified email cannot activate institutional access.
- Administrator reviews claims against an existing institutional identity record,
  records an external verification reference, and approves or rejects atomically.
- Administrator issues an email-bound, faculty-bound, expiring invitation; only
  its verified email identity can accept once. No public Teacher/Admin grant.
- Current Administrator authority is checked within writes; duplicate UID/record,
  cross-tenant, escalation, revoked, expired and replayed operations fail closed.
- Revocation increments current membership revision and immediately blocks role APIs.
- Use disposable PostgreSQL and synthetic/emulator identities only; verify RLS,
  rollback/audit and the actual browser account journey before declaring M1 PASS.
- Preserve original databases and pre-existing dirty work. Cloud verification and
  manual screen reader evidence remain explicitly separate.
