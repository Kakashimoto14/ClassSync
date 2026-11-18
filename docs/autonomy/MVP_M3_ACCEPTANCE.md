# M3 connected schedule acceptance

- Match current verified role to route; no preview data on institutional routes.
- Teacher dashboard and weekly calendar use current faculty-assignment projection;
  no identity selector or mock assignments. Student views retain verified enrollment.
- Administrator uses existing academic inputs/cohort/calendar/readiness/generation,
  drafts/review/publication/history. Readiness failures block publication server-side.
- Same-origin bounded authenticated clients; token/session changes cancel results,
  unavailable/forbidden responses clear institutional data without sample fallback.
- Real Auth Emulator/disposable PostgreSQL browser: authorized Administrator reviews
  and publishes validated academic draft; Student and Teacher see matching current
  version/session/room/faculty data. Revocation denies further reads; cross-role and
  tenant/draft access remain denied. Preserve solver/publication constraints and guards.
- Appropriate regression/static/build/security and responsive role-journey checks;
  report exact evidence and outstanding external qualification separately.
- Teacher submits an own-current-class room request; Administrator approval remains
  pending implementation until independently validated publication. Replay is safe,
  changed replay/foreign assignments/Student access are denied. Rejection is final.
- Restore an earlier validated calendar as a new immutable version, with current-head
  compare-and-swap and readiness checks intact; reject unchanged current duplicates.
- SQL independently denies cross-tenant, foreign-faculty and revoked access, submitted
  evidence mutation and completed-request reopening. Check request and publication
  forms at native 200% zoom with actual controls, and preserve original database hashes.
