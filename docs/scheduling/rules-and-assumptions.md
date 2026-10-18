# S1 institutional inputs, defaults, and synthetic assumptions

## Owner-supplied information

The S1 request supplies the nine-program catalog and institute groupings: BSIT,
BSCPE, BSEd-SCI, BEEd-GEN, BEEd-ECED, BTLEd-ICT, TCP, BSBA-HRM, and BSE.
`packages/api-contracts/classync_contracts/catalogs/programs.json` stores stable
IDs, display acronyms, spelling aliases, and configurable section naming policies.
This records the owner's supplied catalog; it is not independent registrar
verification or a curriculum mapping.

Degree sections use structured program ID, year level, and section letters with
stable IDs independent of labels. No universal program length or section count is
assumed. TCP uses a custom label policy pending an approved institutional format.

The owner also supplies the 59-space provisional CdM inventory and explicit floor
assignments. See [inventory provenance](../cdm-room-inventory.md). PRRC 304–306 do
not exist in this dataset. PRRC 302's VGA label remains unconfirmed. Laboratory
aliases do not verify equipment or capacity. Court and Function Hall are not
automatically eligible classrooms. Legacy fictional campus records remain separate.

## Proposed configurable scheduling defaults

These are implementation/scenario defaults, **not verified university policy**:

- 180 instructional minutes per offering per week, using one 180-minute session or
  two 90-minute sessions on distinct days. Each offering explicitly permits its
  patterns. Overrides must supply patterns summing to the exact required minutes.
- Local weekly time: Monday=0 through Sunday=6, integer minutes on a 30-minute
  grid. Intervals are half-open. Default transition buffer is zero; a supplied
  buffer applies to shared room, instructor, section, and student resources,
  including across midnight and the recurring Sunday/Monday boundary.
- One explicitly eligible instructor per offering, consistent across its sessions.
  Team teaching and alternating-week calendars are outside the current contract.
- Required type, equipment, and capacity constraints require corresponding verified
  metadata. Unknown condition or missing operating availability never establishes
  that a resource is usable. Administrator-supplied eligibility is explicit.
- Default objective weights: idle gaps 2, section daily balance 1, preferences 3,
  building mixing 2, prior-placement disruption 5, room daily load balance 1.
  Units differ; these are integer heuristic preferences, not calibrated university
  utility scores. Hard requirements always take precedence.

## Synthetic presentation scenario

`services/scheduling/scenarios/synthetic-week.json` is an **input fixture**, not a
prewritten timetable. The backend constructs an equivalent input on request.

It contains three catalog program labels, four invented sections, twelve example
offerings, four example instructors, four synthetic resources, and an explicitly
synthetic cross-section enrollment. Each section has one forced 180-minute
offering, one forced two-day 90-minute offering, and one offering allowing both.
Required instruction totals 2,160 minutes. Example resource capacity, equipment,
and operating condition are assertions inside this synthetic scenario only.

The example week is Monday–Friday, 08:00–12:00 and 13:00–17:00. One instructor has
a Tuesday afternoon restriction. The impossible variant limits the week to a
single Monday 08:00–11:00 window; each section still requires 540 minutes. These
times and requirements are not asserted as CdM rules.

## Still needed for institutional use

S2B accepts persisted Administrator-entered records. A verified checkbox records
the Administrator's assertion; it does not independently establish an official
institutional fact. Resource verification requires a provenance note, and unknown
CdM capacities/equipment/conditions remain unknown. Faculty workload limits are
optional supplied constraints, never invented defaults. Period scope declarations
and readiness checks do not certify curriculum completeness. The exercised browser
scenario uses explicitly labeled QA subjects, faculty and resources; its facts are
not CdM inventory metadata. See [S2B evidence](../hci/s2b-academic-inputs.md).

Approved period/calendar and timezone; complete intended offerings and curricula;
subject contact-hour/session rules; valid sections and enrollments; faculty
assignments/eligibility and availability; verified resource type, capacity,
equipment, condition and operating hours; program/building restrictions; transition
rules; and existing assignments to lock or preserve. Coverage is always measured
against the supplied batch. An administrator's scope declaration does not verify
that the input actually contains the entire university.
