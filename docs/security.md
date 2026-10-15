# Security approach

Firebase ID tokens are verified by the gateway with the Firebase Admin SDK. A bearer token is mandatory unless the explicit local-only `ALLOW_UNAUTHENTICATED_DEVELOPMENT=true` switch is set. That switch must remain false in every non-development deployment.

Firestore starts deny-by-default. Future security rules will be drafted only after collection ownership and access patterns are approved. Backend services will use least-privilege credentials from a secret manager, never source-controlled credentials.

The gateway supplies safe error envelopes and request IDs. It is also the planned enforcement point for rate limiting (per IP on public/auth-sensitive paths, per identity on authenticated paths); exact quotas require usage data and are intentionally not guessed. Audit logging will be server-side for privileged changes, publishing, conflict overrides, and request decisions.
