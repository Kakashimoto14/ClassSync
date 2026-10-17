# CDM room inventory — provisional

Source: room list supplied by the product owner in this ClassSync task. There is no
official CDM inventory file. These are **user-supplied, provisional records**, not
verified university resource or availability data.

## Supplied list

| Building / area | Spaces                    | Supplied labels / notes           |
| --------------- | ------------------------- | --------------------------------- |
| PRRC            | 101–110                   | 108 = ITE Lab                     |
| PRRC            | 201–210                   | No additional metadata supplied   |
| PRRC            | 301                       | COMLAB1                           |
| PRRC            | 302                       | VGA Room — explicitly unconfirmed |
| PRRC            | 303                       | COMLAB2                           |
| PRRC            | 307                       | COMLAB3                           |
| PRRC            | 308                       | COMLAB4                           |
| PRRC            | 309–310                   | No additional metadata supplied   |
| New Building    | 101–110, 201–210, 301–310 | No additional metadata supplied   |
| New Building    | Function Hall             | On the 4th floor                  |
| Court           | Court                     | Beside New Building               |

The supplied list contains **59 spaces**: PRRC 27, New Building 31 (including the
Function Hall), and Court 1. PRRC 304, 305, and 306 were not supplied and are not
created. New Building 405 is not part of this provisional list.

## Verification boundaries

- Capacities, equipment/facilities, resource type, operational condition, scheduled
  occupancy, availability, suitability, and institutional restrictions are unverified.
- Numbering is not treated as verified floor information. Only the Function Hall's
  4th-floor location was explicitly supplied. Other floor fields stay unknown.
- ITE Lab and COMLAB1–4 are supplied aliases. They do not establish equipment,
  computer counts, usable capacity, or a verified resource-type classification.
- VGA Room retains an explicit unconfirmed-label flag.
- Court is a building/area filter group for the supplied location label;
  no separate physical building is asserted.
- No class assignment or reservation is created for these spaces. Missing assignment
  records do not establish that a space is free.

## Frontend integration

- `apps/web/src/data/cdm-room-inventory.ts` contains typed provisional records.
- `SchedulePreviewData.inventory` holds them independently of the existing demo
  `resources` and `occurrences`; `roomCatalog` adapts both using stable IDs.
- IDs: `cdm-prrc-<number>`, `cdm-new-<number>`, `cdm-new-function-hall`, `cdm-court`.
- The room directory defaults to **CDM · Provisional**, with name/number/alias search,
  building/area filtering, and 12 results per page. The existing demo scenario stays
  accessible through the Inventory selector; its status claims stay demo-scoped.
- Selecting a space opens its own role-owned read-only detail route. Unknown resource
  fields are labeled Unverified, and provisional condition never becomes Resource active.
- Existing Science/Engineering/Computing fixtures and Room 405 remain explicitly demo
  records. Room 405 is not silently renamed or merged into the Function Hall.

When an official source arrives, reconcile IDs and aliases before adding verified
metadata. Do not infer capacities, equipment, availability, or floors from names.
