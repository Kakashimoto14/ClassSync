# Calendar information architecture

C1 unifies the live Student/Teacher Calendar, Schedule and dashboard paths around
structured occurrences from generated academic data. The previous fixture components
remain isolated regression/reference views and are no longer the personal schedule
source in the routed application. This intentionally changes legacy fixture assertions.

Academic Management contains academic years/semesters, Programs, Sections, Subjects,
Faculty and Subject Offerings. Generation has its own Scheduling destination beside
Saved Drafts and review. Room inventory remains separate under Campus Resources.
Stable routes and role guards are retained; internal API names are unchanged.
Student and Teacher calendar URLs remain supported aliases under My Schedule, removing
the duplicate sidebar destination. Their dashboards put Next Class (including its
actual date) before calendar controls. Period/identity controls are progressively
disclosed on the dashboard; the selected-day agenda excludes that same next class.

A mobile week strip selects a date immediately. Month expansion is optional; expanded
month and week strip do not duplicate each other. Desktop supports a real-time-positioned
weekly grid and a month/agenda view. Today uses Asia/Manila; date-only arithmetic uses
UTC to avoid the browser's local timezone shifting a selected date. Occurrence instants
carry +08:00 offsets. End times are half-open. Teachers select their own mock identity
in synthetic review, and students select their mock section. These selections do not
authorize institutional access. Semester phases are date ranges within a semester and
never duplicate teaching hours.

The sample review source is explicitly unpublished. No legacy assignments are silently
substituted if the service is unavailable. Source details are discoverable rather than
repeated above each class. Subject, time, room, section and instructor are present in
chronological agenda rows; synthetic room details explicitly keep suitability unknown.

C1 browser gate used the real Gateway→Academic→Scheduling→OR-Tools→SQLite workflow
with isolated QA databases (not existing working records). Imported BSIT 3A, checked
readiness, generated 2 offerings/4 sessions, saved the draft, and browsed Student and
Teacher calendars at 390px and 1440px. Native logo/role shell remains intact. Evidence
is in the task visualization directory as c1-*.png and c1-gate.json. Local automated
checks cover import idempotency, all-program/year/semester synthetic catalog coverage,
certificate cohorts, immutable draft persistence, phase dates and holiday cancellation.

C2 changes the default record source to authoritative published occurrences. Generated
review is an explicit, separately labeled mode available only in local development.
Published version changes update Calendar, Schedule and Next Class through the same
component. Disconnection keeps the last confirmed version visible; online/resume and
ordered server events refetch. The first-time mock identity is explicit and remembered
per role within the browser session, independent of P0 preview-role authorization.
Week rendering includes adjacent-month dates, uses elapsed duration for block height,
and has a labeled hour axis. Mobile uses the compact strip/agenda and desktop may choose
Month or Week; controls without a useful mobile/dashboard action are hidden.
