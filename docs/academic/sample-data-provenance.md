# Sample data provenance

No verified full CdM curriculum was found in the inspected authoritative courses
catalog. See curriculum-source-register.md for every generated subject and the
source limitations. The synthetic catalogue contains 132 subjects, 132 explicitly
sample faculty records with per-subject eligibility and explicit teaching windows,
nine CdM catalog program identities, four independent synthetic solver rooms, and
59 unchanged provisional CdM inventory entries. The default scenario offers just
two subjects to mock BSIT 3A. The catalogue is intentionally not a complete degree
curriculum. The configurable year/letter generator supports years 1–4 and A–D for
all eight degree programs. TCP uses separately configured certificate cohort labels.

Idempotent imports use a deterministic UUID derived from a versioned configuration.
They create a separate period atomically. Repeating a configuration returns its current
saved records, retaining any edits. Existing S2B records and immutable drafts are not
replaced. Imports are explicit actions, never startup side effects. Synthetic resources
have their own IDs and do not fill unknown capacity/equipment/floors of provisional
inventory. No fabricated faculty identities are represented as CdM employees.

Calendar dates, 180 weekly minutes, two 90-minute sessions, weekdays 08:00–17:00,
and synthetic-room operational status are test assumptions. Midterm and final dates
may be configured within a semester without changing those weekly requirements.
Owner-listed subject codes are recorded as untranscribed references, not persisted
as verified schedule entries; no missing image times or room names were guessed.

Scale measurements use increasingly configured section counts, not all hypothetical
sections by default. They include full/partial coverage, unknown statuses and memory
where measured; they do not establish institution-wide readiness. Raw benchmark
results are c1-benchmark.json in the task visualization directory.

Measured local OR-Tools runs (single worker, wall time includes generation; peak RSS is
whole-process Windows peak working set, not incremental solver-only memory):

| Sections | Offerings | Sessions | Room demand/supply minutes | Seconds | Result | Coverage | Hard conflicts | Peak MiB |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2 | 4 | 360/10,800 | 1.943 | Optimal | 2/2 | 0 | 103.4 |
| 4 | 8 | 16 | 1,440/10,800 | 3.283 | Feasible | 8/8 | 0 | 137.3 |
| 8 | 16 | 32 | 2,880/10,800 | 3.547 | Feasible | 16/16 | 0 | 150.4 |
| 16 | 32 | 64 | 5,760/10,800 | 3.779 | Feasible | 32/32 | 0 | 175.4 |
| 32 | 64 | 0 | 11,520/10,800 | 2.098 | Unknown | 0/64 | Not validated | 103.1 |

Unknown is not an infeasibility proof. A separate deliberately infeasible existing
engine scenario returned Infeasible with zero assignments. Large scenarios and native
solver timeouts are machine/load dependent; these results do not establish a safe
whole-campus scope. Start with the configured small scenario and inspect coverage.
