# Firebase identity and operational access

Firebase Authentication supplies verified identities. The [authority contract](../../docs/production/firestore-authority.md) requires Firestore Native mode for operational access and onboarding. Keep `firestore.rules` deny-by-default: clients use the Gateway, and server SDK access relies on IAM and API checks. The first slice uses point reads and transactional reservation/receipt documents; `firestore.indexes.json` exempts those unqueried fields from indexing. Hosted index and IAM qualification remain open.

Provision separate staging and production projects only after approval. Copy only public Web configuration to the client, and prefer dedicated managed runtime identities and ADC for backend access. Keep credentials outside this repository.

Firebase Cloud Messaging and Storage are reserved integrations; neither has an active workflow in this phase.
