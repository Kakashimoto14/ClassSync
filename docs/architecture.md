# Architecture

```text
React web / future React Native
              |
              v
       API Gateway (/api/v1)
       /        |         \\
Academic   Scheduling   Notification
       \\        |         /
              Firebase
```

The gateway owns public HTTP conventions, Firebase token verification, request correlation, CORS, rate-limit policy enforcement, and routing. It is the authentication boundary; frontend route guards are UX only.

The Academic service will own teachers, students, subjects, programs, sections, classrooms, academic periods, and availability. The Scheduling service will own schedule validity, conflicts, room recommendations, and optimization. The Notification service will own delivery orchestration and provider integrations. Each service can be deployed and tested independently; their public contracts live in `packages/api-contracts`.

Scheduling constraints are not implemented. The service boundary deliberately gives its future engine authoritative access to teacher, section, room, capacity, and operating-hour validation rather than placing those rules in React.
