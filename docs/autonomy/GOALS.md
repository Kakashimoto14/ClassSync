# ClassSync — autonomous engineering objective

## Long-term objective
A secure, well-designed, PostgreSQL-backed, Firebase-authenticated, independently validated university scheduling system with dependable academic input, durable drafts, conflict-safe edits/approval/publication, correct three-role experiences and comprehensive capstone evidence.

## Operating principle
Within currently authorized local phases, Codex should choose the smallest dependency-ready task, implement, self-review, test, fix, record evidence, and then continue without requesting routine 'next task' prompts. It may use independent review agents if supported. A self-review is not external certification; CI, real browser checks, manual usability and security review are separate sources of evidence.

## Local completion target
- Requirements-to-feature-to-test traceability, categorized VERIFIED / PARTIAL / BLOCKED / PLANNED.
- Every approved local milestone completed under the gates in `QUALITY_GATES.md` and constraints in `APPROVALS.md`.
- No unexamined regressions, silently degraded security, false solver success, unconsented changes to originals, or invented campus metadata.
- Durable status/report enough for a new Codex session to reproduce the claims.

## Production completion target (separate gated outcome)
- Institutional data/authority/privacy, cloud budget/configuration, identity provisioning, test/restore/release evidence and supervised pilot sign-offs satisfied. Local coding alone can never certify production readiness.

## Iteration and stop policy
- Continue to next task only when prior applicable gate is PASS; otherwise fix, isolate, or report a blocker.
- When no authorized task is ready, STOP and report the narrowest needed decision/approval instead of widening scope.
- At any session/budget limit, write checkpoint evidence and a precise resumable next action. Do not claim asynchronous work continues unless a Goal/Automation is active and supported.
