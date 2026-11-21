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

from classync_contracts.email_address import normalize_email
from classync_contracts.identity import VerifiedPrincipal
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import identity_context
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .onboarding import STUDENT_VERIFICATION_ERROR

STUDENT_ID_PATTERN = re.compile(r"^[0-9]{2}-[0-9]{5}$")


def student_record_matches(row, student_id, email):
    candidate = normalize_email(email)
    valid_email = candidate is not None
    candidate = candidate or ""
    valid_student_id = isinstance(student_id, str) and bool(
        STUDENT_ID_PATTERN.fullmatch(student_id)
    )
    registered = normalize_email(row["registered_email"] if row is not None else None) or ""
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

    def activate_from_cor(self, principal, review, *, allow_self_verification: bool):
        """Link a verified account from its own server-stored, confirmed COR review."""
        student_id = review.student_identifier
        email = normalize_email(principal.email)
        if (not email or not STUDENT_ID_PATTERN.fullmatch(student_id)
                or not review.program.strip() or review.year_level is None
                or not review.courses):
            raise HTTPException(
                422, "Complete the student number and course details from your form"
            )
        with self.session(principal) as db:
            membership = db.execute(text("""
                SELECT student_id,roles,state FROM classsync_identity.memberships
                WHERE tenant_id=:tenant AND uid=:uid FOR UPDATE
            """), self.params(principal)).mappings().first()
            if membership:
                if (membership["student_id"] == student_id
                        and "student" in membership["roles"]
                        and membership["state"] == "active"):
                    return {"status": "active", "verification_source": "existing_membership"}
                raise HTTPException(
                    409, "This account already has a different university membership"
                )

            row = db.execute(text("""
                SELECT id,person_id,registered_email,enrollment_status,verification_source
                FROM classsync_identity.students
                WHERE tenant_id=:tenant AND id=:student FOR UPDATE
            """), self.params(principal, student=student_id)).mappings().first()
            if row is not None:
                if not student_record_matches(row, student_id, email):
                    raise HTTPException(
                        409,
                        "This student number is already linked to another account. "
                        "Contact your administrator for help.",
                    )
                person_id = row["person_id"]
                source = "registrar_roster"
            else:
                if not allow_self_verification:
                    raise HTTPException(
                        403,
                        "Your student record is not on the Registrar roster. "
                        "Contact the Registrar.",
                    )
                person_id = str(uuid4())
                db.execute(text("""
                    INSERT INTO classsync_identity.people(tenant_id,id)
                    VALUES(:tenant,:person) ON CONFLICT DO NOTHING
                """), self.params(principal, person=person_id))
                inserted = db.execute(text("""
                    INSERT INTO classsync_identity.students
                        (tenant_id,id,person_id,registered_email,enrollment_status,
                         password_configured,verification_source)
                    VALUES(:tenant,:student,:person,:email,'active',false,'cor_self_verified')
                    ON CONFLICT (tenant_id,id) DO NOTHING
                """), self.params(principal, student=student_id, person=person_id, email=email))
                if inserted.rowcount != 1:
                    raise HTTPException(409,
                        "This student number is already linked to another account. "
                        "Contact your administrator for help.")
                source = "cor_self_verified"

            inserted = db.execute(text("""
                INSERT INTO classsync_identity.memberships
                    (tenant_id,uid,person_id,student_id,roles,state,revision)
                VALUES(:tenant,:uid,:person,:student,ARRAY['student']::text[],'active',1)
                ON CONFLICT DO NOTHING
            """), self.params(principal, person=person_id, student=student_id))
            if inserted.rowcount != 1:
                raise HTTPException(409,
                    "This student number is already linked to another account. "
                    "Contact your administrator for help.")
        return {"status": "active", "verification_source": source,
                "student_id": student_id, "email": email}

    def issue_student_challenge(self, principal, student_id, challenge_id, digest):
        lookup_id = student_id if isinstance(student_id, str) and STUDENT_ID_PATTERN.fullmatch(
            student_id
        ) else None
        with self.session(principal) as db:
            row = db.execute(text("""
                SELECT id,person_id,registered_email,enrollment_status
                FROM classsync_identity.students
                WHERE tenant_id=:tenant AND id=:student FOR SHARE
            """), self.params(principal, student=lookup_id)).mappings().first()
            if not student_record_matches(row, student_id, principal.email):
                raise HTTPException(403, STUDENT_VERIFICATION_ERROR,
                                    headers={"Cache-Control": "no-store"})
            current = db.execute(text("""
                SELECT resend_after FROM classsync_identity.email_verification_challenges
                WHERE tenant_id=:tenant AND uid=:uid AND consumed_at IS NULL
                ORDER BY created_at DESC LIMIT 1 FOR UPDATE
            """), self.params(principal)).mappings().first()
            if current and db.scalar(text("SELECT :resend_after > transaction_timestamp()"),
                                     {"resend_after": current["resend_after"]}):
                raise HTTPException(429, "Wait before requesting another verification code",
                                    headers={"Retry-After": "30", "Cache-Control": "no-store"})
            db.execute(text("""
                UPDATE classsync_identity.email_verification_challenges
                SET consumed_at=transaction_timestamp()
                WHERE tenant_id=:tenant AND uid=:uid AND consumed_at IS NULL
            """), self.params(principal))
            db.execute(text("""
                INSERT INTO classsync_identity.email_verification_challenges
                    (tenant_id,uid,challenge_id,student_id,otp_hmac,expires_at,resend_after)
                VALUES (:tenant,:uid,:challenge,:student,:digest,
                    transaction_timestamp()+interval '5 minutes',
                    transaction_timestamp()+interval '30 seconds')
            """), self.params(principal, challenge=challenge_id, student=student_id,
                              digest=digest))
        local, domain = principal.email.split("@", 1)
        return f"{local[:1]}{'*' * min(max(len(local)-1, 4), 8)}@{domain}"

    def cancel_student_challenge(self, principal, challenge_id):
        with self.session(principal) as db:
            db.execute(text("""
                UPDATE classsync_identity.email_verification_challenges
                SET consumed_at=transaction_timestamp()
                WHERE tenant_id=:tenant AND uid=:uid AND challenge_id=:challenge
                    AND consumed_at IS NULL
            """), self.params(principal, challenge=challenge_id))

    def verify_student_challenge(self, principal, student_id, challenge_id, code, secret):
        invalid_code = False
        result = None
        with self.session(principal) as db:
            row = db.execute(text("""
                SELECT c.otp_hmac,c.failed_attempts,c.expires_at,c.consumed_at,
                       s.id,s.person_id,s.registered_email,s.enrollment_status
                FROM classsync_identity.email_verification_challenges c
                JOIN classsync_identity.students s
                  ON s.tenant_id=c.tenant_id AND s.id=c.student_id
                WHERE c.tenant_id=:tenant AND c.uid=:uid AND c.challenge_id=:challenge
                  AND c.student_id=:student
                FOR UPDATE OF c,s
            """), self.params(principal, challenge=challenge_id, student=student_id)) \
                .mappings().first()
            if (row is None or row["consumed_at"] is not None or row["failed_attempts"] >= 5
                    or db.scalar(text("SELECT :expires_at <= transaction_timestamp()"),
                                 {"expires_at": row["expires_at"] if row else "epoch"})
                    or not student_record_matches(row, student_id, principal.email)):
                raise HTTPException(403, "Verification code could not be confirmed",
                                    headers={"Cache-Control": "no-store"})
            expected = hmac.new(
                secret, f"{principal.uid}\0{challenge_id}\0{code}".encode(), "sha256"
            ).digest()
            if not hmac.compare_digest(expected, bytes(row["otp_hmac"])):
                db.execute(text("""
                    UPDATE classsync_identity.email_verification_challenges
                    SET failed_attempts=failed_attempts+1,
                        consumed_at=CASE WHEN failed_attempts+1>=5
                            THEN transaction_timestamp() ELSE consumed_at END
                    WHERE tenant_id=:tenant AND uid=:uid AND challenge_id=:challenge
                """), self.params(principal, challenge=challenge_id))
                invalid_code = True
            else:
                db.execute(text("""
                    UPDATE classsync_identity.email_verification_challenges
                    SET consumed_at=transaction_timestamp(), verified_at=transaction_timestamp()
                    WHERE tenant_id=:tenant AND uid=:uid AND challenge_id=:challenge
                """), self.params(principal, challenge=challenge_id))
                existing = db.execute(text("""
                    SELECT student_id,roles,state FROM classsync_identity.memberships
                    WHERE tenant_id=:tenant AND uid=:uid FOR UPDATE
                """), self.params(principal)).mappings().first()
                if existing:
                    if (existing["student_id"] == student_id and "student" in existing["roles"]
                            and existing["state"] == "active"):
                        result = {"status": "verified"}
                    else:
                        raise HTTPException(403, STUDENT_VERIFICATION_ERROR,
                                            headers={"Cache-Control": "no-store"})
                else:
                    result = {"status": "verified"}
        if invalid_code:
            raise HTTPException(403, "Verification code could not be confirmed",
                                headers={"Cache-Control": "no-store"})
        return result

    def complete_student_onboarding(self, principal, student_id, challenge_id):
        normalized_email = normalize_email(principal.email)
        with self.session(principal) as db:
            row = db.execute(text("""
                SELECT c.verified_at,s.id,s.person_id,s.registered_email,s.enrollment_status
                FROM classsync_identity.email_verification_challenges c
                JOIN classsync_identity.students s
                  ON s.tenant_id=c.tenant_id AND s.id=c.student_id
                WHERE c.tenant_id=:tenant AND c.uid=:uid AND c.challenge_id=:challenge
                  AND c.student_id=:student
                  AND c.verified_at > transaction_timestamp()-interval '10 minutes'
                FOR UPDATE OF c,s
            """), self.params(principal, challenge=challenge_id, student=student_id)) \
                .mappings().first()
            if not student_record_matches(row, student_id, principal.email):
                raise HTTPException(403, STUDENT_VERIFICATION_ERROR,
                                    headers={"Cache-Control": "no-store"})
            existing = db.execute(text("""
                SELECT student_id,roles,state FROM classsync_identity.memberships
                WHERE tenant_id=:tenant AND uid=:uid FOR UPDATE
            """), self.params(principal)).mappings().first()
            if existing and not (
                existing["student_id"] == student_id
                and "student" in existing["roles"]
                and existing["state"] == "active"
            ):
                raise HTTPException(403, STUDENT_VERIFICATION_ERROR,
                                    headers={"Cache-Control": "no-store"})
            db.execute(text("""
                UPDATE classsync_identity.students SET password_configured=true
                WHERE tenant_id=:tenant AND id=:student AND enrollment_status='active'
                    AND registered_email=:email
            """), self.params(principal, student=student_id, email=normalized_email))
            if existing is None:
                inserted = db.execute(text("""
                    INSERT INTO classsync_identity.memberships
                        (tenant_id,uid,person_id,student_id,roles,state,revision)
                    VALUES (:tenant,:uid,:person,:student,ARRAY['student']::text[],'active',1)
                    ON CONFLICT DO NOTHING
                """), self.params(principal, person=row["person_id"], student=student_id))
                if inserted.rowcount != 1:
                    raise HTTPException(403, STUDENT_VERIFICATION_ERROR,
                                        headers={"Cache-Control": "no-store"})
        return {"status": "active", "password_configured": True}

    def student_login_email(self, student_id):
        """Resolve an eligible roster email internally; never return it to the client."""
        with transaction(self.engine) as db:
            db.execute(text("SELECT set_config('classsync.tenant_id',:tenant,true)"),
                       {"tenant": self.tenant})
            row = db.execute(text("""
                SELECT registered_email FROM classsync_identity.students
                WHERE tenant_id=:tenant AND id=:student AND enrollment_status='active'
                    AND password_configured=true
            """), {"tenant": self.tenant, "student": student_id}).mappings().first()
            return row["registered_email"] if row else None

    def student_login_membership_matches(self, uid, student_id):
        if not isinstance(uid, str) or not uid or len(uid) > 128:
            return False
        with transaction(self.engine) as db:
            identity_context(db, tenant_id=self.tenant, uid=uid)
            return db.scalar(text("""
                SELECT EXISTS (
                    SELECT 1 FROM classsync_identity.memberships m
                    JOIN classsync_identity.students s
                      ON s.tenant_id=m.tenant_id AND s.id=m.student_id
                    JOIN classsync_identity.tenants t ON t.id=m.tenant_id
                    WHERE m.tenant_id=:tenant AND m.uid=:uid AND m.student_id=:student
                        AND m.state='active' AND 'student'=ANY(m.roles)
                        AND s.enrollment_status='active' AND s.password_configured=true
                        AND t.firebase_project_id=:project
                )
            """), {"tenant": self.tenant, "uid": uid, "student": student_id,
                  "project": self.project}) is True

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

    def self_verified_students(self, principal):
        with self.session(principal, admin=True) as db:
            return [dict(row) for row in db.execute(text("""
                SELECT m.uid,s.id AS student_id,s.registered_email,s.verification_source,
                       m.revision AS membership_revision
                FROM classsync_identity.students s
                JOIN classsync_identity.memberships m
                  ON m.tenant_id=s.tenant_id AND m.student_id=s.id
                WHERE s.tenant_id=:tenant AND s.verification_source='cor_self_verified'
                  AND m.state='active' AND 'student'=ANY(m.roles)
                ORDER BY s.id LIMIT 1000
            """), self.params(principal)).mappings()]

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
