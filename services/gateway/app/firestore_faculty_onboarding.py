"""Teacher invitations on the isolated Firestore onboarding adapter."""

import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from classync_contracts.identity import MembershipState
from classync_contracts.models import UserRole
from fastapi import HTTPException
from google.cloud import firestore

from .firestore_access import access_key
from .firestore_student_onboarding import FirestoreStudentOnboarding, account_boundary


class FirestoreOnboarding(FirestoreStudentOnboarding):
    def __init__(self, access, bridge, resolve_binding, *, list_faculty, resolve_faculty):
        super().__init__(access, bridge, resolve_binding)
        self.list_faculty, self.resolve_faculty = list_faculty, resolve_faculty
        self.invitations = access.root.collection("facultyInvitations")
        self.invite_heads = access.root.collection("facultyInviteHeads")

    def _head(self, faculty_id):
        return self.invite_heads.document(access_key(faculty_id))

    def _check_actor(self, tx, admin):
        actor = self.access._member(admin.uid).get(transaction=tx, retry=None, timeout=5)
        if self.access._decode(actor, admin.uid) != admin:
            raise HTTPException(403, "Current Administrator membership required")

    def faculty_records(self, principal):
        with account_boundary():
            self._administrator(principal)
            return [{"id": record} for record in self.list_faculty()]

    def invite(self, principal, faculty_id, email, hours):
        with account_boundary():
            admin = self._administrator(principal)
            if faculty_id not in self.list_faculty():
                raise HTTPException(409, "Approved faculty record is unavailable")
            invitation_id = uuid4()
            # Fixed-width UUID prefix preserves the existing URL-safe API contract.
            token = invitation_id.hex + secrets.token_urlsafe(32)
            ref = self.invitations.document(str(invitation_id))
            head = self._head(faculty_id)
            expires = datetime.now(UTC) + timedelta(hours=hours)
            invitation = {
                "faculty_id": faculty_id, "email_key": access_key(email.casefold()),
                "token_hash": access_key(token), "issuer_uid": principal.uid,
                "expires_at": expires, "state": "pending",
            }

            @firestore.transactional
            def write(tx):
                self._check_actor(tx, admin)
                # Read the head so a concurrent resend is ordered against acceptance.
                head.get(transaction=tx, retry=None, timeout=5)
                tx.create(ref, invitation)
                tx.set(head, {"invitation_id": ref.id})

            write(self.access.client.transaction(max_attempts=3))
            return {"id": ref.id, "token": token, "expires_in_hours": hours}

    @staticmethod
    def _read_pending(snapshot, principal, token):
        value = snapshot.to_dict() if snapshot.exists else None
        if (
            not value or value.get("state") != "pending"
            or value.get("email_key") != access_key((principal.email or "").casefold())
            or not isinstance(value.get("token_hash"), str)
            or re.fullmatch(r"[a-f0-9]{64}", value["token_hash"]) is None
            or not hmac.compare_digest(value["token_hash"], access_key(token))
            or not isinstance(value.get("expires_at"), datetime)
            or value["expires_at"].tzinfo is None
            or value["expires_at"] <= datetime.now(UTC)
            or not isinstance(value.get("faculty_id"), str)
            or not isinstance(value.get("issuer_uid"), str)
        ):
            raise HTTPException(403, "Invitation is unavailable")
        return value

    def accept(self, principal, token):
        with account_boundary():
            match = re.fullmatch(r"([a-f0-9]{32})[A-Za-z0-9_-]{43}", token)
            if match is None or not principal.email_verified:
                raise HTTPException(403, "Invitation is unavailable")
            ref = self.invitations.document(str(UUID(hex=match[1])))
            before = self._read_pending(ref.get(retry=None, timeout=5), principal, token)
            faculty = before["faculty_id"]
            issuer = self.bridge.lookup_current(tenant_id=self.access.tenant,
                                                uid=before["issuer_uid"])
            if (
                issuer is None or issuer.state != MembershipState.ACTIVE
                or UserRole.ADMINISTRATOR not in issuer.roles
            ):
                raise HTTPException(403, "Invitation is unavailable")
            grant = self.resolve_faculty(principal.uid, faculty)
            if (
                grant is None or grant.uid != principal.uid or grant.faculty_id != faculty
                or grant.roles != {UserRole.TEACHER} or grant.state != MembershipState.ACTIVE
            ):
                raise HTTPException(403, "Invitation is unavailable")
            self.access._validated(grant)
            member = self.access._member(principal.uid)
            reservations = self.access._reservations(grant)

            @firestore.transactional
            def write(tx):
                self._check_actor(tx, issuer)
                current = self._read_pending(ref.get(transaction=tx, retry=None, timeout=5),
                                             principal, token)
                head = self._head(faculty).get(transaction=tx, retry=None, timeout=5)
                if current != before or not head.exists or head.to_dict() != {
                    "invitation_id": ref.id,
                }:
                    raise HTTPException(403, "Invitation is unavailable")
                if member.get(transaction=tx, retry=None, timeout=5).exists or any(
                    item.get(transaction=tx, retry=None, timeout=5).exists
                    for item in reservations
                ):
                    raise HTTPException(409, "Account or academic record is already linked")
                self.access._create(tx, member, grant, reservations)
                tx.update(ref, {"state": "used", "used_by": access_key(principal.uid),
                                "used_at": firestore.SERVER_TIMESTAMP})
                return {"status": "active"}

            return write(self.access.client.transaction(max_attempts=3))

    def revoke_invite(self, principal, invitation_id):
        with account_boundary():
            admin = self._administrator(principal)
            ref = self.invitations.document(invitation_id)

            @firestore.transactional
            def write(tx):
                self._check_actor(tx, admin)
                current = ref.get(transaction=tx, retry=None, timeout=5)
                state = current.to_dict().get("state") if current.exists else None
                if state not in {"pending", "revoked"}:
                    raise HTTPException(409, "Invitation is unavailable")
                if state == "pending":
                    tx.update(ref, {"state": "revoked", "revoked_by": access_key(principal.uid),
                                    "revoked_at": firestore.SERVER_TIMESTAMP})
                return {"status": "revoked"}

            return write(self.access.client.transaction(max_attempts=3))
