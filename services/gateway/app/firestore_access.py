"""Firestore access records and a local-only SQL projection intersection.

Mutation methods are trusted operator/import primitives, not HTTP endpoints.
There is no production composition or SQL-authority cutover in this slice.
"""

import hashlib
import json

from classync_contracts.identity import MembershipSnapshot, MembershipState
from classync_contracts.models import UserRole
from classync_contracts.token_verification import AdapterTrust
from google.cloud import firestore


class AccessConflict(ValueError):
    """Stale revision, conflicting reservation, or changed operation replay."""


def access_key(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=True, sort_keys=True)
                          .encode("ascii")).hexdigest()


class FirestoreAccess:
    """Use an explicitly supplied, project-bound Native Firestore client."""

    def __init__(self, client, *, project, tenant, shadow=False):
        if client.project != project or not project or not tenant:
            raise ValueError("Explicit Firestore project and tenant required")
        self.client, self.project, self.tenant = client, project, tenant
        self.shadow = shadow
        collection = "accessShadowTenants" if shadow else "accessTenants"
        self.root = client.collection(collection).document(access_key(project, tenant))

    def _member(self, uid):
        if not isinstance(uid, str) or not uid.strip() or len(uid) > 128:
            raise ValueError("Invalid membership subject")
        return self.root.collection("memberships").document(access_key(uid))

    def _decode(self, snapshot, uid):
        if not snapshot.exists:
            return None
        data = snapshot.to_dict()
        if data.keys() != {"schema_version", "firebase_project", "membership"} or (
            type(data["schema_version"]) is not int or data["schema_version"] != 1
            or data["firebase_project"] != self.project
        ):
            raise ValueError("Invalid access document")
        member = MembershipSnapshot.model_validate(data["membership"])
        if member.uid != uid:
            raise ValueError("Invalid access subject")
        return self._validated(member)

    def _validated(self, member):
        if (
            member.tenant_id != self.tenant
            or not member.person_id or not member.roles
            or (UserRole.STUDENT in member.roles and not member.student_id)
            or (UserRole.TEACHER in member.roles and not member.faculty_id)
            or any(len(x) > 128 for x in (
                member.person_id, member.student_id or "", member.faculty_id or "",
            ))
        ):
            raise ValueError("Invalid access binding")
        return member

    def _encode(self, member):
        value = member.model_dump(mode="json")
        value["roles"] = sorted(value["roles"])
        return {"schema_version": 1, "firebase_project": self.project, "membership": value}

    def _reservations(self, member):
        return [
            self.root.collection("reservations").document(access_key(kind, record))
            for kind, record in (("student", member.student_id), ("faculty", member.faculty_id))
            if record
        ]

    def _create(self, tx, ref, member, reservations):
        tx.create(ref, self._encode(member))
        for reservation in reservations:
            tx.create(reservation, {"member": ref.id})

    def lookup_current(self, *, tenant_id, uid):
        if tenant_id != self.tenant:
            return None
        return self._decode(self._member(uid).get(retry=None, timeout=5), uid)

    def seed_snapshot(self, member: MembershipSnapshot):
        """Import a trusted initial snapshot once; never replace an existing grant."""
        ref = self._member(member.uid)
        self._validated(member)
        reservations = self._reservations(member)

        @firestore.transactional
        def write(tx):
            existing = self._decode(ref.get(transaction=tx, retry=None, timeout=5), member.uid)
            reserved = [item.get(transaction=tx, retry=None, timeout=5) for item in reservations]
            if existing is not None:
                if existing == member and all(
                    item.exists and item.to_dict() == {"member": ref.id} for item in reserved
                ):
                    return
                raise AccessConflict("Membership already exists with different state")
            if any(item.exists for item in reserved):
                raise AccessConflict("Academic record already reserved")
            self._create(tx, ref, member, reservations)

        write(self.client.transaction(max_attempts=3))

    def revoke(self, *, uid, expected_revision, operation_id, actor_uid):
        """Advance the revision and audit the operation atomically."""
        if type(expected_revision) is not int or expected_revision < 1 or any(
            not isinstance(value, str) or not value.strip() or len(value) > 128
            for value in (operation_id, actor_uid)
        ):
            raise ValueError("Invalid revocation operation")
        ref = self._member(uid)
        receipt = self.root.collection("revocations").document(access_key(operation_id))
        event = {"member": ref.id, "actor": access_key(actor_uid),
                 "previous_revision": expected_revision, "revision": expected_revision + 1}

        @firestore.transactional
        def write(tx):
            previous = receipt.get(transaction=tx, retry=None, timeout=5)
            if previous.exists:
                if previous.to_dict() != event:
                    raise AccessConflict("Revocation operation already used")
                return event["revision"]
            member = self._decode(ref.get(transaction=tx, retry=None, timeout=5), uid)
            if (
                member is None or member.state != MembershipState.ACTIVE
                or member.revision != expected_revision
            ):
                raise AccessConflict("Current active revision required")
            tx.set(ref, self._encode(member.model_copy(update={
                "state": MembershipState.REVOKED, "revision": event["revision"],
            })))
            tx.create(receipt, event)
            return event["revision"]

        return write(self.client.transaction(max_attempts=3))


class QualificationMembershipBridge:
    """Firestore gates every read; the SQL projection can only further restrict it."""

    trust = AdapterTrust.TEST

    def __init__(self, access, projection):
        if access.shadow:
            raise ValueError("Shadow records cannot authorize a request")
        self.access, self.projection = access, projection

    def lookup_current(self, *, tenant_id, uid):
        grant = self.access.lookup_current(tenant_id=tenant_id, uid=uid)
        if grant is None or grant.state != MembershipState.ACTIVE:
            return grant
        if self.projection.lookup_current(tenant_id=tenant_id, uid=uid) != grant:
            raise ValueError("Access projection unavailable or inconsistent")
        return grant
