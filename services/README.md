# Service boundaries

Each directory is a separately deployable FastAPI process. The gateway owns public API concerns: versioning, Firebase token verification, standard errors, request IDs, CORS, and service routing. The domain services never use frontend claims as authorization.

`academic` will own academic reference data and teacher availability. `scheduling` will own schedule validation, conflict intelligence, and optimization. `notification` will own delivery providers and notification workflows. No business endpoint is implemented in this foundation phase.
