"""Student claim transitions for the isolated Firestore authority qualification."""

from contextlib import contextmanager

from classync_contracts.identity import MembershipState
from classync_contracts.models import UserRole
from fastapi import HTTPException
from google.api_core.exceptions import GoogleAPICallError
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from sqlalchemy.exc import SQLAlchemyError

from .firestore_access import access_key


@contextmanager
def account_boundary():
    try:
        yield
    except (GoogleAPICallError, SQLAlchemyError, ValueError) as error:
        raise HTTPException(503, "Account service unavailable; no change confirmed") from error


class FirestoreStudentOnboarding:
    """Uses current verified principals from the existing account router.

    The binding resolver is supplied by the trusted fixture; release use requires
    a fenced canonical roster resolver and a qualified SQL projection writer.
    """

    def __init__(self, access, bridge, resolve_binding):
        self.access, self.bridge, self.resolve_binding = access, bridge, resolve_binding
        self.claims_collection = access.root.collection("studentClaims")

    def _claim(self, uid):
        self.access._member(uid)  # Validate the same bounded subject key.
        return self.claims_collection.document(access_key(uid))

    @staticmethod
    def _claim_data(snapshot, uid=None):
        if not snapshot.exists:
            return None
        data = snapshot.to_dict()
        state, subject, record = data.get("state"), data.get("uid"), data.get("student_id")
        if (
            state not in ("pending", "approved", "rejected")
            or not isinstance(subject, str) or not 0 < len(subject) <= 128
            or snapshot.id != access_key(subject) or (uid is not None and subject != uid)
            or not isinstance(record, str) or not 0 < len(record) <= 128
        ):
            raise ValueError("Invalid student claim")
        fields = {"state", "uid", "student_id"}
        if state != "pending":
            decision = data.get("decision")
            if (
                not isinstance(decision, dict) or decision.get("state") != state
                or set(decision) != {"state", "actor", "reference_hash"}
            ):
                raise ValueError("Invalid student claim decision")
            fields.add("decision")
        if data.keys() != fields:
            raise ValueError("Unexpected student claim fields")
        return data

    def _administrator(self, principal):
        member = self.bridge.lookup_current(tenant_id=self.access.tenant, uid=principal.uid)
        if (
            member is None or member.state != MembershipState.ACTIVE
            or UserRole.ADMINISTRATOR not in member.roles
        ):
            raise HTTPException(403, "Current Administrator membership required")
        return member

    def status(self, principal):
        with account_boundary():
            ref = self.access._member(principal.uid)
            claim = self._claim(principal.uid)

            @firestore.transactional
            def read(tx):
                member = self.access._decode(ref.get(transaction=tx, retry=None, timeout=5),
                                             principal.uid)
                snapshot = self._claim_data(claim.get(transaction=tx, retry=None, timeout=5),
                                            principal.uid)
                state = snapshot["state"] if snapshot else None
                return {"email_verified": principal.email_verified, "claim_state": state,
                        "membership_state": member.state.value if member else None,
                        "status": "verify-email" if not principal.email_verified
                        else member.state.value if member else state or "unlinked"}

            return read(self.access.client.transaction(max_attempts=3, read_only=True))

    def submit_claim(self, principal, student_id):
        with account_boundary():
            ref, member = self._claim(principal.uid), self.access._member(principal.uid)
            pending = {"uid": principal.uid, "student_id": student_id, "state": "pending"}

            @firestore.transactional
            def write(tx):
                current = ref.get(transaction=tx, retry=None, timeout=5)
                if member.get(transaction=tx, retry=None, timeout=5).exists:
                    raise HTTPException(409, "This account already has a university membership")
                if current.exists:
                    if self._claim_data(current, principal.uid) != pending:
                        raise HTTPException(409, "A claim already exists for this account")
                else:
                    tx.create(ref, pending)
                return {"status": "pending"}

            return write(self.access.client.transaction(max_attempts=3))

    def claims(self, principal):
        with account_boundary():
            self._administrator(principal)
            query = self.claims_collection.where(filter=FieldFilter("state", "==", "pending"))
            return [self._claim_data(row) for row in query.limit(100).get(retry=None, timeout=5)]

    def decide(self, principal, uid, *, approve, reference):
        with account_boundary():
            admin = self._administrator(principal)
            claim_ref = self._claim(uid)
            before = self._claim_data(claim_ref.get(retry=None, timeout=5), uid)
            if before is None:
                raise HTTPException(409, "Claim is unavailable or already decided")
            decision = {"state": "approved" if approve else "rejected",
                        "actor": access_key(principal.uid), "reference_hash": access_key(reference)}
            grant = (
                self.resolve_binding(uid, before["student_id"])
                if approve and before["state"] == "pending" else None
            )
            if approve and before["state"] == "pending" and (
                grant is None or grant.uid != uid or grant.student_id != before["student_id"]
                or grant.roles != {UserRole.STUDENT} or grant.state != MembershipState.ACTIVE
            ):
                raise HTTPException(409, "Approved academic identity record is unavailable")

            @firestore.transactional
            def write(tx):
                actor = self.access._member(principal.uid).get(
                    transaction=tx, retry=None, timeout=5
                )
                if self.access._decode(actor, principal.uid) != admin:
                    raise HTTPException(403, "Current Administrator membership required")
                current = self._claim_data(claim_ref.get(transaction=tx, retry=None, timeout=5),
                                           uid)
                if (
                    current and current["state"] != "pending"
                    and current.get("decision") == decision
                ):
                    return {"status": decision["state"]}
                if current != before or current["state"] != "pending":
                    raise HTTPException(409, "Claim is unavailable or already decided")
                if grant is not None:
                    self.access._validated(grant)
                    ref = self.access._member(uid)
                    reservations = self.access._reservations(grant)
                    if ref.get(transaction=tx, retry=None, timeout=5).exists or any(
                        item.get(transaction=tx, retry=None, timeout=5).exists
                        for item in reservations
                    ):
                        raise HTTPException(409, "Account or academic record is already linked")
                    self.access._create(tx, ref, grant, reservations)
                tx.update(claim_ref, {"state": decision["state"], "decision": decision})
                return {"status": decision["state"]}

            return write(self.access.client.transaction(max_attempts=3))
