# Stage 2 Package A — core experience

## Delivered

- A1: `ClassSyncLogo` centralizes login, demo, sidebar, and mobile-header branding.
  Official ribbon exports remain unavailable; see [branding.md](branding.md).
  The fallback is plain product-name text, not a recreated official wordmark.
- A2: typed preview occurrences, explicit Student assignment IDs, Teacher ownership,
  requests, updates, and conflict references share one dataset. Pure selectors drive
  the dashboards and their counts. Shared schedule entries, agendas, next-class
  summaries, and an attention queue reuse existing UI primitives.
- A3: separate role compositions prioritize the next class, teaching assignments,
  or administrative intervention. Login validates locally, focuses invalid fields,
  supports password visibility, and never simulates authentication.
- Fixed shared input padding: Tailwind preflight's element selector outranked the
  zero-specificity `:where(...)` control rule. The control rule now has element
  specificity while preserving wrapper overrides. No negative-margin workaround.

## Data boundary

`src/data/schedule-preview.ts` is a development fixture, not enrollment data or an
authorization mechanism. The fixed reference is **2026-10-12 at 09:45** in an
unspecified local calendar frame. Every dashboard displays that context.

Occurrences use normalized local date-time strings with minute precision. This
internal fixture contract is not a parser for untrusted backend timestamps. No
institutional timezone, live countdown, recurrence policy, or real assignment is
inferred. Selectors accept an explicit reference for deterministic tests; finished,
empty, unpublished, unavailable, overlapping, and overnight scenarios are covered.
Missing records are not converted into zero counts.

Student scope uses explicit assignment IDs across multiple sections. Teacher scope
uses Teacher IDs. Published records drive personal agendas; administrators can see
drafts. Attention records are supplied examples, not output from a conflict engine.
The fixture does not feed the existing ICS serializer: authoritative dates/timezones
and assignments must be established before enabling export from this layer.

The existing schedule, request, notification, room, and management destination pages
retain their earlier representative data and functionality. Migrating those screens
to a coherent authoritative adapter belongs to Package B/C; dashboard links do not
imply that their sample records have been persisted there.

## Verification

- `npm run lint`, `npm run typecheck`, `npm run test:web` (52 tests), and
  `npm run build` passed.
- Browser screenshots and DOM measurements checked login and all three dashboards
  at 360, 390, 768, 1024, and 1440px. No horizontal document overflow was observed.
- Administrator shell checked at 1024 × 480: sidebar width and header offset both
  256px; navigation has its own scroll area above the reserved account region.
- Mobile menu opened using Enter; Escape closed it and restored trigger focus.
  Automated shell tests cover drawer closure after navigation, active destinations,
  role-owned links, and Student's four mobile destinations.
- Inter was loaded in the browser. Login control padding was rechecked after the
  preflight fix. Branding legibility checks cover the text fallback only.
- This is focused regression coverage, not a full WCAG conformance audit. Browser
  zoom, screen-reader announcements, and production backend behavior are unverified.

## Deferred

Official isolated logo exports and derived favicon/application icons; Package B
schedule/room workflows; Package C supporting workflows; backend authentication,
authoritative assignments, conflict validation, publishing, AI, and OCR.

No packages, route changes, backend changes, or commits are part of Package A.
