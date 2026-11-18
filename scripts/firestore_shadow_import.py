"""Bounded, synthetic snapshot rehearsal. No SQL or live access writes."""

from collections import Counter
from dataclasses import dataclass

from classync_contracts.identity import MembershipSnapshot
from google.cloud import firestore

from services.gateway.app.firestore_access import AccessConflict, FirestoreAccess, access_key


@dataclass(frozen=True)
class ShadowPlan:
    project: str
    tenant: str
    members: tuple[MembershipSnapshot, ...]
    checksum: str

    def receipt(self):
        return {
            "memberships": len(self.members),
            "roles": dict(sorted(Counter(r.value for m in self.members for r in m.roles).items())),
            "states": dict(sorted(Counter(m.state.value for m in self.members).items())),
            "snapshot_checksum": self.checksum,
        }


def _require_shadow(target):
    if (
        not target.shadow or not target.project.startswith("demo-classsync-")
        or not target.client._emulator_host
        or not target.client._emulator_host.startswith("127.0.0.1:")
    ):
        raise ValueError("An isolated demo shadow emulator is required")


def plan_snapshot(target: FirestoreAccess, rows, *, approved_binding):
    """Validate a bounded immutable input without writing any Firestore documents."""
    _require_shadow(target)
    members, subjects, reserved = [], set(), set()
    for member in rows:
        if len(members) >= 1000:
            raise ValueError("Disposable snapshot exceeds the rehearsal bound")
        if not isinstance(member, MembershipSnapshot):
            raise ValueError("Invalid snapshot membership")
        target._validated(member)
        target._member(member.uid)
        keys = {ref.id for ref in target._reservations(member)}
        if member.uid in subjects or keys & reserved:
            raise AccessConflict("Duplicate subject or record in snapshot")
        if not approved_binding(member):
            raise AccessConflict("Snapshot has an unverified or orphaned binding")
        members.append(member)
        subjects.add(member.uid)
        reserved.update(keys)
    members.sort(key=lambda member: member.uid)
    checksum = access_key(target.project, target.tenant, [target._encode(m) for m in members])
    return ShadowPlan(target.project, target.tenant, tuple(members), checksum)


def _scope(target, plan):
    _require_shadow(target)
    if (target.project, target.tenant) != (plan.project, plan.tenant) or access_key(
        plan.project, plan.tenant, [target._encode(m) for m in plan.members]
    ) != plan.checksum:
        raise AccessConflict("Snapshot checksum or scope mismatch")


def resume_batch(target, plan, *, batch_size):
    """Replay exact records, then persist a monotonic checkpoint after the batch."""
    _scope(target, plan)
    if type(batch_size) is not int or not 1 <= batch_size <= 100:
        raise ValueError("Shadow batch size must be 1 through 100")
    ref = target.root.collection("shadowImports").document(plan.checksum)

    def offset(snapshot):
        if not snapshot.exists:
            return 0
        data = snapshot.to_dict()
        value = data.get("offset")
        if (
            data.get("checksum") != plan.checksum or data.get("count") != len(plan.members)
            or type(value) is not int or not 0 <= value <= len(plan.members)
        ):
            raise AccessConflict("Invalid shadow checkpoint")
        return value

    start = offset(ref.get(retry=None, timeout=5))
    end = min(start + batch_size, len(plan.members))
    for member in plan.members[start:end]:
        target.seed_snapshot(member)

    @firestore.transactional
    def commit(tx):
        current = offset(ref.get(transaction=tx, retry=None, timeout=5))
        if current >= end:
            return current
        tx.set(ref, {"checksum": plan.checksum, "count": len(plan.members), "offset": end})
        return end

    return commit(target.client.transaction(max_attempts=3))


def compare_snapshot(target, plan):
    """Read-only check including extra records; returns counts/checksum, not identifiers."""
    _scope(target, plan)
    collection = target.root.collection("memberships")
    actual = collection.limit(len(plan.members) + 1).get(retry=None, timeout=5)
    expected = {target._member(m.uid).id: m for m in plan.members}
    if len(actual) != len(expected) or any(
        item.id not in expected or target._decode(item, expected[item.id].uid) != expected[item.id]
        for item in actual
    ):
        raise AccessConflict("Shadow membership parity failed")
    reservations = {ref.id: target._member(m.uid).id for m in plan.members
                    for ref in target._reservations(m)}
    actual_reservations = target.root.collection("reservations").limit(
        len(reservations) + 1
    ).get(retry=None, timeout=5)
    if len(actual_reservations) != len(reservations) or any(
        item.id not in reservations or item.to_dict() != {"member": reservations[item.id]}
        for item in actual_reservations
    ):
        raise AccessConflict("Shadow reservation parity failed")
    return plan.receipt()
