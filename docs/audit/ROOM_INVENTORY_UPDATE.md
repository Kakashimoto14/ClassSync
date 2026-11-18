# CdM room inventory update

## Source and reconciliation

Source: `cdm-room-inventory.docx`, supplied as the updated November 2026 on-site inventory. Its title and source statement identify it as the Product Owner's authoritative inspection. The extracted tables enumerate 53 spaces. The document summary says 37 schedulable and 16 non-schedulable, but the row markings and category breakdown yield 41 schedulable and 12 non-schedulable. This plan follows the individual rows as directed by the owner and preserves the discrepancy for source correction.

The DOCX's row text was extracted. Visual rendering was not available because LibreOffice is not installed. The document does not provide numeric seat capacities, a complete equipment inventory, or time-specific live occupancy. The term “schedulable” is an activity eligibility flag, not an availability claim.

## Canonical row mapping

Stable IDs follow the existing catalog convention: `cdm-prrc-NNN`, `cdm-new-NNN`, plus `cdm-new-function-hall`, `cdm-court`, and `cdm-oval`.

The complete row-to-ID mapping is: PRRC floors 1–3: `cdm-prrc-101` through `cdm-prrc-108`, `cdm-prrc-201` through `cdm-prrc-209`, and `cdm-prrc-301` through `cdm-prrc-310`; New Building floors 1–3: `cdm-new-101` through `cdm-new-107`, `cdm-new-201` through `cdm-new-208`, and `cdm-new-301` through `cdm-new-308`; New Building Function Hall: `cdm-new-function-hall`; campus Court: `cdm-court`; Municipal Ground Oval: `cdm-oval`. Each numeric interval here is inclusive. The building prefix is part of the ID, so identically numbered PRRC and New Building rooms remain distinct.

| Area                 | Room IDs                                         | Purpose and schedulability                                                                                                                                                                          |
| -------------------- | ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PRRC Floor 1         | 101, 102, 103, 104, 105, 106, 107, 108           | 101 simulation lab: excluded. 102 and 104 food hub: excluded. 103, 105, 106, 107 lecture: schedulable. 108 ITE Science Lab: schedulable only for BSEd Science.                                      |
| PRRC Floor 2         | 201, 202, 203, 204, 205, 206, 207, 208, 209      | 201–203 and 206–209 lecture: schedulable. 204 Engineering Professional Laboratory and 205 Educational Technology Center: excluded from general CP-SAT scheduling.                                   |
| PRRC Floor 3         | 301, 302, 303, 304, 305, 306, 307, 308, 309, 310 | 301 AVR, 303 Property/Supply Office, 305 storage, 306 ICTO: excluded. 302 COMLAB 1, 304 COMLAB 2, 307 COMLAB 3, 308 COMLAB 4: schedulable for computer-lab offerings. 309–310 lecture: schedulable. |
| New Building Floor 1 | 101–107                                          | Lecture rooms: schedulable.                                                                                                                                                                         |
| New Building Floor 2 | 201–208                                          | 201–203 and 205–208 lecture: schedulable. 204 ITE Faculty Room: excluded.                                                                                                                           |
| New Building Floor 3 | 301–308                                          | 301–303 and 305–307 lecture: schedulable. 304 joint ICS/IBE Faculty Room and 308 Faculty Lounge: excluded.                                                                                          |
| New Building Floor 4 | Function Hall                                    | Multipurpose hall: schedulable only for approved special bookings/activity type.                                                                                                                    |
| Campus grounds       | Court                                            | Covered athletic court: schedulable only for PAHFIT, sports, or assemblies.                                                                                                                         |
| Municipal ground     | Oval                                             | Montalban Sports Complex Oval, off-campus: schedulable only for PAHFIT, athletics, or ROTC. Preserve the off-campus location attribute.                                                             |

## Row-derived counts

| Group          | Physical spaces | Schedulable | Excluded |
| -------------- | --------------: | ----------: | -------: |
| PRRC           |              27 |          18 |        9 |
| New Building   |              24 |          21 |        3 |
| Court and Oval |               2 |           2 |        0 |
| **Total**      |          **53** |      **41** |   **12** |

Schedulable categories: 33 lecture classrooms (13 PRRC, 20 New Building), 4 computer labs, 1 restricted-use science lab, and 3 special activity spaces (Function Hall, Court, Oval). These are room counts, not seat capacities.

## Implementation and remaining gates

Implemented on `feature/auth-onboarding-saas`: `packages/api-contracts/classync_contracts/catalogs/cdm-spaces.json` and `apps/web/src/data/cdm-room-inventory.ts` contain 53 stable IDs, remove obsolete IDs, correct COMLAB aliases (1 at PRRC 302, 2 at 304, 3 at 307, 4 at 308), add `cdm-oval`, and preserve the Court/Function Hall/Oval activity designations. Scheduling and academic contracts carry `ActivityType`; readiness rejects activity-restricted rooms until type and operational condition are verified. No capacities or equipment were added.

Focused local evidence on 15 November: frontend inventory/room discovery/Admin selection tests, 66 passed across five files; backend catalog/readiness/API tests, 14 passed; TypeScript, ESLint, and Ruff passed. Admin offering choices filter to active, source-designated schedulable spaces matching activity and program; readiness independently requires operational and verified room type. Remaining gates: review all 53 row-to-ID mappings against the original DOCX, resolve its 37/16 summary, obtain Facilities verification, run full regression, and qualify scheduling on approved inputs. Every excluded resource remains non-schedulable; source designation does not establish room availability.
