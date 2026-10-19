# Firebase readiness — UX-06

Verified 19 October 2026. No cloud resource, security rule, credential, index or data
was created or changed. SDK was already installed and was not reinstalled.

## Findings

| Milestone | Evidence / status |
| --- | --- |
| Web registration | Local six-key configuration identifies `classsync-f444c`. Firebase's web-config API returned 200 and matched the configured project and app ID. The display label “ClassSync Web” still needs authenticated console verification; the public endpoint does not prove a display name |
| Local configuration | `apps/web/.env.local` supplies all six expected `VITE_FIREBASE_*` keys. Values were not printed. Root `.env` and process-level Admin credential variables are absent |
| SDK initialization | Actual local browser import reports `initialized`, default app `[DEFAULT]`, project `classsync-f444c` |
| Duplicate initialization | Client reuses the existing default app only when its project/app match; incomplete and mismatched configurations remain distinct non-ready states |
| Vercel configuration | Current public main bundle does not embed the expected local project/app ID. Authenticated Vercel settings are inaccessible; successful Firebase initialization for the intended project is **not verified** there |
| Firestore database | **BLOCKED**: database metadata GET returns 401 UNAUTHENTICATED (OAuth required). Database ID/region/provisioning cannot be certified from this response |
| Firestore anonymous probe | Valid collection-list probe returns 403 PERMISSION_DENIED. This confirms denial for that probe, not a complete rules audit or proof that every collection is private |
| Rules, collections, indexes | **BLOCKED**: no authenticated console/Admin access. No records enumerated, no test document written, no indexes changed |
| Authentication | Frontend SDK configuration is separate from sign-in. Backend Firebase Admin credentials and institutional identity/claims are not configured in this workspace. Provider/domain/claim setup is unverified. University sign-in remains unavailable |
| Realtime scheduling | Existing authoritative local publication/SSE remains. Firestore is not connected to scheduling; no claim of Firestore synchronization is made |

The initial incomplete `/documents` root probe returned 404 and is not evidence of
database absence; only the valid collection probe above is used to assess anonymous
access. A web API key is not an OAuth administration credential.

## What was changed

`firebase-config.ts` validates key presence, reuses a matching default registration
and exposes readiness without logging keys. `firebase.ts` keeps the existing app
export for its consumers. Focused tests cover absent/incomplete configuration,
module reload reuse, and project/app mismatch. No second Firebase application is
created as a workaround.

Recognized build-time keys: `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`,
`VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_STORAGE_BUCKET`,
`VITE_FIREBASE_MESSAGING_SENDER_ID`, `VITE_FIREBASE_APP_ID`.
Server Admin credentials must never be placed in `VITE_*` variables.

## Owner verification / approval steps

1. Open Firebase console for the confirmed project; General → Apps → ClassSync Web.
   Confirm project and app IDs against the existing local registration without
   creating another app. Check Authentication providers and authorized domains.
2. Inspect Firestore Database. Record existing database ID, location and mode. If
   absent, obtain owner approval for provisioning, location and billing **before**
   creation. Do not use unrestricted test mode.
3. Review deployed rules and indexes with an authenticated principal; enumerate
   collections without copying institutional data into a public sample. Test denied
   anonymous administrative reads/writes in an emulator and approved test scope.
4. After approval, add the six web configuration values to the intended Vercel
   environment. Rebuild is required for Vite configuration changes. This only
   configures Firebase; it does not deploy the scheduling API.
5. Production sign-in needs verified identities, tenant/enrollment/faculty mappings
   and controlled Administrator claims. Prefer workload identity for deployed Admin
   services rather than distributing private service-account keys.

For any future Firestore signal projection, keep authoritative publication in the
transactional backend. Clients must not create publication notifications. An
approved server-side outbox can project version IDs after commit; client rules must
permit only the intended authenticated reads and deny client administrative writes.
This design is proposed, not implemented or provisioned.

References: [Firestore setup](https://firebase.google.com/docs/firestore/quickstart),
[security rules](https://firebase.google.com/docs/firestore/security/get-started),
[IAM and rules](https://firebase.google.com/docs/firestore/security/iam).
