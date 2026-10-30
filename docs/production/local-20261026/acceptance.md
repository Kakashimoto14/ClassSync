# P1 acceptance before implementation — 26 October 2026

Base/current HEAD: main, 39200a4f2ef3ec7557bc3c86127e674e260ca4fc. Existing dirty work is preserved.

First newly identified unmet P1 verification case: the hosted HTTP gate accepts a 200 HTML login/error page on a role deep link, including redirects, as successful SPA refresh. Its route set also omits existing schedule/calendar routes covered by local artifact tests. This can falsely certify release routing independently of the known dependency blocker.

Acceptance before source edits:
- Positive: matching clean release metadata, identical application shell at all supported role/entry routes, real JS/CSS references and correct static/API boundaries pass the HTTP fixture.
- Negative: a role route returning a different HTML shell must fail, even with status 200 and correct content type.
- Negative: a role route redirecting to the homepage/login must fail, even if its final body matches the homepage.
- Negative: schedule/calendar routes omitted by the previous verifier must be probed and fail when broken.
- Existing missing SHA, wrong SHA, missing bundle, dirty metadata and happy-path assertions remain intact.

This is an HTTP verification slice, not browser or live release certification. No production request, original database mutation or UI change is required. P1 remains gated by the fresh strict dependency audit; P2 cannot start while that gate fails.

## Dependency remediation acceptance (before manifest changes)

The fresh registry audit reports unused zod (high) and Vitest/mocker (moderate); historical braces-only reports are superseded for this installed graph. Repository source search finds zod only in the web manifest. Remove that unused direct dependency and qualify the non-major Vitest 4.1.12 patch. Require actual installed version checks, no zod in the lock graph, full strict audit with zero findings, complete peer graph, unchanged functional assertions, web/static/build/artifact/browser regressions. No advisory exception or major Zod migration is proposed. If runtime/lock installation fails, mark the remediation incomplete rather than representing manifest edits as a fix.

## Reproducible root web command (before script edit)

Nested npm runs stalled with no suite results. Direct Node execution of the entire unchanged suite with one thread worker passed 664/664 across 36 files in 230.66s. Make the documented root command invoke Vitest directly with the explicit web root and the proven thread/worker configuration. Acceptance: `npm run test:web` itself must report all 664 tests and 36 files passed; no filtering, retry acceptance, assertion removal or timeout change. Preserve the workspace's existing test command. If this still stalls, leave the gate unresolved and retain both successful direct and unsuccessful command evidence.

The direct CLI root variant also failed to report suite results within five minutes and was interrupted. Use a small Node harness reproducing the successful direct child invocation exactly: web working directory, verbose reporter, one thread, captured output. Bound the overall process to five minutes (failure on timeout; individual test timeouts unchanged). Preserve stdout/stderr and propagate nonzero or signaled exits; no retries. This is a tooling workaround, not a proven diagnosis of the underlying Windows/npm/reporting stall.
