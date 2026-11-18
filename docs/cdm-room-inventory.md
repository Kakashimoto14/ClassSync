# CdM room inventory — superseded source snapshot

**Do not use the former 2026-10 inventory as the current room catalog.** It described a
59-space list that was superseded by the owner's November 2026 room inventory. The
current row-by-row source classification, stable ID mapping, category counts, unresolved
37/16 versus 41/12 discrepancy, and verification limits are documented in
[`docs/audit/ROOM_INVENTORY_UPDATE.md`](audit/ROOM_INVENTORY_UPDATE.md).

The feature-branch implementation now contains 53 spaces from the November rows: 41
source-designated schedulable and 12 excluded. The source provides no numeric seat
capacities, complete equipment inventory, or time-specific availability. Facilities
verification remains required before production scheduling. “Schedulable” represents a
source designation only; the backend separately requires verified operational status
and room type.

Older 59-space references in dated qualification receipts describe the test fixture used
at the time and are retained as historical evidence. They are not evidence for the
current catalog.
