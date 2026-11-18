"""Account linking on the existing identity database; every write is transactional.

Runtime SQL permissions must be granted separately in an approved environment.
No startup migrations, credentials, cloud calls, roster creation or fallback store.
"""

import hashlib
import hmac
import re
import secrets
from contextlib import contextmanager
from uuid import uuid4

from classync_contracts.identity import VerifiedPrincipal
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import identity_context
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .onboarding import STUDENT_VERIFICATION_ERROR

STUDENT_ID_PATTERN = re.compile(r"^[0-9]{2}-[0-9]{5}$")
STUDENT_EMAIL_PATTERN = re.compile(r"^[a-z]+(?:\.[a-z]+)*@student\.pnm\.edu\.ph$")


def student_record_matches(row, student_id, email):
    candidate = email if isinstance(email, str) else ""
    valid_email = bool(STUDENT_EMAIL_PATTERN.fullmatch(candidate))
    valid_student_id = isinstance(student_id, str) and bool(
        STUDENT_ID_PATTERN.fullmatch(student_id)
    )
    registered = row["registered_email"] if row is not None else ""
    email_matches = hmac.compare_digest(candidate.encode("utf-8"), registered.encode("utf-8"))
    return bool(
        valid_student_id
        and valid_email
        and row is not None
        and row["id"] == student_id
        and row["enrollment_status"] == "active"
        and email_matches
    )


class OnboardingRepository:
    def __init__(self, engine, *, tenant, project):
        self.engine, self.tenant, self.project = engine, tenant, project

    @contextmanager
    def session(self, principal, *, admin=False):
        try:
            with transaction(self.engine) as db:
                identity_context(db, tenant_id=self.tenant, uid=principal.uid)
                db.execute(text("SELECT set_config('classsync.onboarding_admin','false',true)"))
                if not db.scalar(
                    text(
                        "SELECT 1 FROM classsync_identity.tenants "
                        "WHERE id=:tenant AND firebase_project_id=:project"
                    ),
                    {"tenant": self.tenant, "project": self.project},
                ):
                    raise HTTPException(403, "University access could not be verified")
                if admin:
                    # Lock current authority until commit; concurrent revocation waits.
                    row = (
                        db.execute(
                            text(
                                "SELECT roles,state FROM classsync_identity.memberships "
                                "WHERE tenant_id=:tenant AND uid=:uid FOR SHARE"
                            ),
                            {"tenant": self.tenant, "uid": principal.uid},
                        )
                        .mappings()
                        .first()
                    )
                    if not row or row["state"] != "active" or "administrator" not in row["roles"]:
                        raise HTTPException(403, "Current Administrator membership required")
                    db.execute(text("SELECT set_config('classsync.onboarding_admin','true',true)"))
                audit_actor(db, principal)
                yield db
        except IntegrityError as error:
            raise HTTPException(
                409, "Account or academic record is already linked or unavailable"
            ) from error
        except SQLAlchemyError as error:
            raise HTTPException(503, "Account service unavailable; no change confirmed") from error

    def params(self, principal, **extra):
        return {"tenant": self.tenant, "uid": principal.uid, **extra}

    def status(self, principal):
        with self.session(principal) as db:
            state = db.scalar(
                text(
                    "SELECT state FROM classsync_identity.account_claims "
                    "WHERE tenant_id=:tenant AND uid=:uid"
                ),
                self.params(principal),
            )
            membership = db.scalar(
                text(
                    "SELECT state FROM classsync_identity.memberships "
                    "WHERE tenant_id=:tenant AND uid=:uid"
                ),
                self.params(principal),
            )
            return {
                "email_verified": principal.email_verified,
                "claim_state": state,
                "membership_state": membership,
                "status": "verify-email"
                if not principal.email_verified
                else "active"
                if membership == "active"
                else "revoked"
                if membership == "revoked"
                else state or "unlinked",
            }

    def submit_claim(self, principal, student_id):
        with self.session(principal) as db:
            if db.scalar(
                text(
                    "SELECT 1 FROM classsync_identity.memberships "
                    "WHERE tenant_id=:tenant AND uid=:uid"
                ),
                self.params(principal),
            ):
                raise HTTPException(409, "This account already has a university membership")
            # Never reveal whether a submitted student identifier exists.
            db.execute(
                text(
                    "INSERT INTO classsync_identity.account_claims(tenant_id,uid,student_id) "
                    "VALUES(:tenant,:uid,:student)"
                ),
                self.params(principal, student=student_id),
            )
        return {"status": "pending"}

    def verify_student(self, principal, student_id):
        """Bind only an active roster record whose registered email matches verified Firebase email.

        Every failed roster match uses the same response. The lookup is tenant-scoped,
        row-locked, and the membership insert is in the same transaction.
        """
        lookup_id = student_id if isinstance(student_id, str) and STUDENT_ID_PATTERN.fullmatch(
            student_id
        ) else None

        with self.session(principal) as db:
            row = (
                db.execute(
                    text(
                        "SELECT id,person_id,registered_email,enrollment_status "
                        "FROM classsync_identity.students "
                        "WHERE tenant_id=:tenant AND id=:student FOR SHARE"
                    ),
                    self.params(principal, student=lookup_id),
                )
                .mappings()
                .first()
            )
            # The pure comparator runs a constant-time email comparison even when
            # the queried student row is absent.
            if not student_record_matches(row, student_id, principal.email):
                raise HTTPException(403, STUDENT_VERIFICATION_ERROR,
                                    headers={"Cache-Control": "no-store"})

            existing = (
                db.execute(
                    text(
                        "SELECT student_id,roles,state FROM classsync_identity.memberships "
                        "WHERE tenant_id=:tenant AND uid=:uid FOR UPDATE"
                    ),
                    self.params(principal),
                )
                .mappings()
                .first()
            )
            if existing is not None:
                if (
                    existing["student_id"] == student_id
                    and "student" in existing["roles"]
                    and existing["state"] == "active"
                ):
                    return {"status": "verified"}
                raise HTTPException(403, STUDENT_VERIFICATION_ERROR,
                                    headers={"Cache-Control": "no-store"})

            inserted = db.execute(
                text(
                    "INSERT INTO classsync_identity.memberships "
                    "(tenant_id,uid,person_id,student_id,roles,state,revision) "
                    "VALUES(:tenant,:uid,:person,:student,ARRAY['student']::text[],'active',1) "
                    "ON CONFLICT DO NOTHING"
                ),
                self.params(principal, person=row["person_id"], student=student_id),
            )
            if inserted.rowcount != 1:
                raise HTTPException(403, STUDENT_VERIFICATION_ERROR,
                                    headers={"Cache-Control": "no-store"})
        return {"status": "verified"}

    def claims(self, principal):
        with self.session(principal, admin=True) as db:
            return [
                dict(row)
                for row in db.execute(
                    text(
                        "SELECT uid,student_id,state FROM classsync_identity.account_claims "
                        "WHERE tenant_id=:tenant AND state='pending' ORDER BY created_at LIMIT 100"
                    ),
                    self.params(principal),
                ).mappings()
            ]

    def faculty_records(self, principal):
        with self.session(principal, admin=True) as db:
            return [
                dict(row)
                for row in db.execute(
                    text(
                        "SELECT id FROM classsync_identity.faculty WHERE tenant_id=:tenant "
                        "ORDER BY id LIMIT 1000"
                    ),
                    self.params(principal),
                ).mappings()
            ]

    def link(self, db, principal, *, uid, record, kind):
        table, column, role = (
            ("students", "student_id", "student")
            if kind == "student"
            else ("faculty", "faculty_id", "teacher")
        )
        person = db.scalar(
            text(
                f"SELECT person_id FROM classsync_identity.{table} "
                "WHERE tenant_id=:tenant AND id=:record"
            ),
            self.params(principal, record=record),
        )
        if person is None:
            raise HTTPException(409, "Approved academic identity record is unavailable")
        identity_context(db, tenant_id=self.tenant, uid=uid)
        db.execute(
            text(
                f"INSERT INTO classsync_identity.memberships "
                f"(tenant_id,uid,person_id,{column},roles,state,revision) "
                "VALUES(:tenant,:uid,:person, :record, ARRAY[:role]::text[], 'active', 1)"
            ),
            self.params(VerifiedPrincipal(uid=uid), person=person, record=record, role=role),
        )

    def decide(self, principal, uid, *, approve, reference):
        with self.session(principal, admin=True) as db:
            claim = (
                db.execute(
                    text(
                        "SELECT student_id,state FROM classsync_identity.account_claims "
                        "WHERE tenant_id=:tenant AND uid=:subject FOR UPDATE"
                    ),
                    self.params(principal, subject=uid),
                )
                .mappings()
                .first()
            )
            if not claim or claim["state"] != "pending":
                raise HTTPException(409, "Claim is unavailable or already decided")
            if approve:
                self.link(db, principal, uid=uid, record=claim["student_id"], kind="student")
            db.execute(
                text(
                    "UPDATE classsync_identity.account_claims SET state=:state, "
                    "verification_reference=:reference,decided_by=:actor "
                    "WHERE tenant_id=:tenant AND uid=:subject"
                ),
                self.params(
                    principal,
                    subject=uid,
                    actor=principal.uid,
                    state="approved" if approve else "rejected",
                    reference=reference,
                ),
            )
        return {"status": "approved" if approve else "rejected"}

    def invite(self, principal, faculty_id, email, hours):
        token, invitation_id = secrets.token_urlsafe(32), str(uuid4())
        with self.session(principal, admin=True) as db:
            db.execute(
                text(
                    "INSERT INTO classsync_identity.faculty_invitations "
                    "(tenant_id,id,faculty_id,email,token_hash,issued_by,expires_at) "
                    "VALUES(:tenant,CAST(:id AS uuid),:faculty,:email,:hash,:uid, "
                    "transaction_timestamp() + :hours * interval '1 hour')"
                ),
                self.params(
                    principal,
                    id=invitation_id,
                    faculty=faculty_id,
                    email=email.casefold(),
                    hash=hashlib.sha256(token.encode()).hexdigest(),
                    hours=hours,
                ),
            )
        # Raw token appears once, only in this authenticated Admin response.
        return {"id": invitation_id, "token": token, "expires_in_hours": hours}

    def accept(self, principal, token):
        with self.session(principal) as db:
            # Invitation lookup needs tenant-scoped visibility after identity is verified;
            # all ownership/expiry checks below run before any institutional write.
            db.execute(text("SELECT set_config('classsync.onboarding_admin','true',true)"))
            invitation = (
                db.execute(
                    text(
                        "SELECT id,faculty_id,email,issued_by FROM "
                        "classsync_identity.faculty_invitations WHERE tenant_id=:tenant "
                        "AND token_hash=:hash AND NOT revoked AND used_by IS NULL "
                        "AND expires_at > transaction_timestamp() FOR UPDATE"
                    ),
                    self.params(principal, hash=hashlib.sha256(token.encode()).hexdigest()),
                )
                .mappings()
                .first()
            )
            if (
                not invitation
                or not principal.email
                or invitation["email"] != principal.email.casefold()
            ):
                raise HTTPException(
                    403, "Invitation is invalid, expired or unavailable for this account"
                )
            # A revoked issuer cannot activate new faculty access.
            identity_context(db, tenant_id=self.tenant, uid=invitation["issued_by"])
            if not db.scalar(
                text(
                    "SELECT 1 FROM classsync_identity.memberships "
                    "WHERE tenant_id=:tenant AND uid=:issuer AND state='active' "
                    "AND 'administrator'=ANY(roles) FOR SHARE"
                ),
                self.params(principal, issuer=invitation["issued_by"]),
            ):
                raise HTTPException(403, "Invitation is no longer available")
            self.link(
                db, principal, uid=principal.uid, record=invitation["faculty_id"], kind="teacher"
            )
            db.execute(
                text(
                    "UPDATE classsync_identity.faculty_invitations SET used_by=:uid "
                    "WHERE tenant_id=:tenant AND id=:id"
                ),
                self.params(principal, id=invitation["id"]),
            )
        return {"status": "active"}

    def revoke_invite(self, principal, invitation_id):
        with self.session(principal, admin=True) as db:
            result = db.execute(
                text(
                    "UPDATE classsync_identity.faculty_invitations SET revoked=true "
                    "WHERE tenant_id=:tenant AND id=CAST(:id AS uuid) AND used_by IS NULL"
                ),
                self.params(principal, id=invitation_id),
            )
            if not result.rowcount:
                raise HTTPException(409, "Invitation is unavailable or already accepted")
        return {"status": "revoked"}

    def revoke_membership(self, principal, uid, revision):
        with self.session(principal, admin=True) as db:
            if uid == principal.uid:
                raise HTTPException(409, "Use another trusted Administrator to revoke this account")
            identity_context(db, tenant_id=self.tenant, uid=uid)
            result = db.execute(
                text(
                    "UPDATE classsync_identity.memberships "
                    "SET state='revoked',revision=revision+1 WHERE tenant_id=:tenant "
                    "AND uid=:subject AND revision=:revision"
                ),
                self.params(principal, subject=uid, revision=revision),
            )
            if not result.rowcount:
                raise HTTPException(409, "Membership changed; refresh before retrying")
        return {"status": "revoked"}
