# Firebase foundation

Firebase Authentication is the identity provider. The gateway verifies Firebase ID tokens using the Admin SDK, then services will enforce server-side authorization for every domain action. Firestore is intentionally deny-by-default until the collection model and access patterns are designed.

Create a Firebase project, add a Web app, and copy only public Web configuration values into `apps/web/.env`. Supply backend credentials through the deployment secret store as `FIREBASE_SERVICE_ACCOUNT_JSON`, or the individual Admin fields in the root `.env`. Do not place service-account files in this repository.

Firebase Cloud Messaging and Storage are reserved integrations; neither has an active workflow in this phase.
