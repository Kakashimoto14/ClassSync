# Publication repository review — 28 October 2026

Status: interim; actual supplementary checks and full adapter exit still pending.

Independent reviewer p2a_security_review inspected the adapter qualification additions without executing them. The stale-input expectation correction matches shared production behavior: stale revision -> academic_version_conflict409; current revision with stale draft hash -> academic_input_changed409. Both cases retain unchanged-state assertions.

The reviewer found no actionable source issue in direct helper context/ACL/owner checks or both observed writer orderings. Hooks delegate to real validation and only coordinate timing; they do not replace validation outcomes. These cases prove serialization when both writes are compatible, not mutual exclusion of conflicting writes. The full resource/scale matrix remains open.

Root inspected migration0008's non-superuser/non-BYPASSRLS guard, fixed-path no-argument authority helper, RLS and immutable restriction audit, qualifier fixture guards, exact transaction-state assertions and advanced revision propagation. Root portable guards:39 passed, Ruff clean. Actual original qualifier passed on PG18.6 in publication-repository-reviewed.json. Supplementary actual execution must be judged from its own terminal result and evidence.

No approval workflow, provider/browser composition, institutional authority, outbox, history migration/restore, full P3b or production acceptance follows from this review.

Supplementary actual evidence reviewed independently: publication-repository-locks.json closes helper and compatible-writer ordering gaps on real PostgreSQL; six denied helper contexts and both observed lock orders pass. Reviewer wording clarification: the historical evidence key `mutation_denied_after_commit` means access is denied after the authority mutation commits; it does not mean that the authority mutation was denied. No actual execution by reviewer. Resource/scale and other explicitly excluded scopes remain open.
