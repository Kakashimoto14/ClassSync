# P2a first contract slice — acceptance before implementation

Entry: P1 local engineering passed with exact root frontend command 664/664, backend serial105/105, artifact4/4, browser15/15, independent review and clean dependency scans. Owner's 26 October scoped authorization permits this local P2a work. Original databases and current production/service authorization remain unchanged.

This slice introduces immutable internal verified-principal and membership-snapshot contracts, a current-membership lookup port, and a fail-closed authorization helper. It does not implement token cryptography, provisioning, production adapters, routes, PostgreSQL or policy for assigning roles. UID and academic person ID remain distinct. A verified UID never supplies membership by itself. These internal contracts must never be parsed from client-provided role/membership claims as authority.

Acceptance cases:
- Happy: server-obtained current active membership with matching tenant+UID and required Student/Teacher/Administrator grant returns an immutable scoped context.
- Negative: missing membership, inactive/revoked membership, unknown/missing role, tenant/UID mismatch, lookup failure and malformed identifiers deny or produce typed unavailable errors.
- Negative: returned snapshots cannot silently transfer a grant to another tenant/UID; membership is queried afresh on every authorization call, so revocation takes effect on the next call.
- Negative: role lists and principal/snapshot/context fields are immutable; extra client role/tenant fields on principals rejected. Stable UID differs from academic person identifiers.
- No endpoint integration: verify current service imports remain unchanged and no synthetic adapter is added to runtime packages. Tests use disposable in-memory doubles only.

This is a PARTIAL P2a phase even if these cases pass. Missing/bad/expired/revoked/wrong issuer/audience token verification, production exclusion of test/emulator identity providers, service dependency integration and later real PostgreSQL/current-membership acceptance remain separate slices. Do not advance to P2b on this contract-only result.
