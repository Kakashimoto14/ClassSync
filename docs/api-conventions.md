# API conventions

Public APIs use `/api/v1`. Collections use plural nouns, resources use stable identifiers, and standard HTTP semantics apply. Successful resource endpoints will return `{ "data": ... }`. Rejected requests return:

```json
{"error":{"code":"machine_readable_code","message":"Safe user-facing message","requestId":"uuid"}}
```

The gateway accepts `X-Request-ID` or generates one and returns it in the response. Any future authenticated route requires `Authorization: Bearer <Firebase ID token>`. Roles are exactly `administrator`, `teacher`, and `student`; there is no Department Head role.

Validation is layered: Zod/RHF for browser feedback and Pydantic at the API boundary. Server-side authorization and business validation remain authoritative.
