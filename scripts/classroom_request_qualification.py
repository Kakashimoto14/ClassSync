"""Disposable-only SQL isolation/integrity checks after the actual browser request journey."""

import json
from uuid import uuid4

from classync_contracts.identity import VerifiedPrincipal
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import identity_context
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from scripts.postgres_driver_qualification import require


def qualify(owner, runtime, *, project, request_id):
    require(project.startswith("demo-classsync-"), "Disposable demo project required")
    actor = "request-rls-" + uuid4().hex
    with transaction(owner) as db:
        row = dict(
            db.execute(
                text(
                    "SELECT * FROM classsync_scheduling.classroom_requests "
                    "WHERE tenant_id='tenant-a' AND id=:id"
                ),
                {"id": request_id},
            )
            .mappings()
            .one()
        )
        require(row["status"] == "fulfilled", "Completed browser request required")
        identity_context(db, tenant_id="tenant-a", uid=actor)
        audit_actor(db, VerifiedPrincipal(uid="synthetic-request-control-provisioner"))
        for tenant in ("tenant-a", "tenant-b"):
            identity_context(db, tenant_id=tenant, uid=actor)
            db.execute(
                text("INSERT INTO classsync_identity.people VALUES(:tenant,:person)"),
                {"tenant": tenant, "person": actor},
            )
            if tenant == "tenant-a":
                db.execute(
                    text("INSERT INTO classsync_identity.faculty VALUES(:tenant,:id,:id)"),
                    {"tenant": tenant, "id": actor},
                )
            db.execute(
                text(
                    "INSERT INTO classsync_identity.memberships "
                    "(tenant_id,uid,person_id,faculty_id,roles,state,revision) VALUES "
                    "(:tenant,:uid,:uid,:faculty,CAST(:roles AS text[]),'active',1)"
                ),
                {
                    "tenant": tenant,
                    "uid": actor,
                    "faculty": actor if tenant == "tenant-a" else None,
                    "roles": ["teacher", "administrator"]
                    if tenant == "tenant-a"
                    else ["administrator"],
                },
            )

    def context(db, uid=actor, tenant="tenant-a", role="teacher"):
        identity_context(db, tenant_id=tenant, uid=uid)
        db.execute(
            text(
                "SELECT set_config('classsync.project_id',:project,true), "
                "set_config('classsync.role',:role,true), "
                "set_config('classsync.record_id',:record,true)"
            ),
            {"project": project, "role": role, "record": actor},
        )

    for tenant, role, expected in (
        ("tenant-a", "teacher", 0),
        ("tenant-b", "administrator", 0),
        ("tenant-a", "administrator", 1),
    ):
        with transaction(runtime) as db:
            context(db, tenant=tenant, role=role)
            count = db.scalar(
                text("SELECT count(*) FROM classsync_scheduling.classroom_requests WHERE id=:id"),
                {"id": request_id},
            )
            require(count == expected, "Request role/tenant ownership isolation failed")
    with transaction(runtime) as db:
        context(db, uid=row["owner_uid"])
        require(
            db.scalar(
                text("SELECT count(*) FROM classsync_scheduling.classroom_requests WHERE id=:id"),
                {"id": request_id},
            )
            == 0,
            "Revoked requester retained SQL access",
        )
    for operation, sqlstate in (
        ("foreign-faculty", "42501"),
        ("rewrite-evidence", "23514"),
        ("reopen-completed", "23514"),
    ):
        try:
            with transaction(runtime) as db:
                context(db, role="teacher" if operation == "foreign-faculty" else "administrator")
                if operation == "foreign-faculty":
                    db.execute(
                        text(
                            "INSERT INTO classsync_scheduling.classroom_requests "
                            "(tenant_id,id,owner_uid,faculty_id,period_id,publication_id,occurrence_id,"
                            "proposed_room_id,reason,context,idempotency_key,input_hash) VALUES "
                            "('tenant-a',:id,:actor,:faculty,:period,:publication,:occurrence,:room,"
                            ":reason,CAST(:context AS jsonb),:key,:hash)"
                        ),
                        {
                            "id": str(uuid4()),
                            "actor": actor,
                            "faculty": row["faculty_id"],
                            "period": row["period_id"],
                            "publication": row["publication_id"],
                            "occurrence": row["occurrence_id"],
                            "room": row["proposed_room_id"],
                            "reason": "Invented unauthorized faculty test",
                            "context": json.dumps({}),
                            "key": str(uuid4()),
                            "hash": "0" * 64,
                        },
                    )
                else:
                    db.execute(
                        text(
                            "UPDATE classsync_scheduling.classroom_requests SET "
                            "revision=revision+1,"
                            + (
                                "fulfilled_by=:actor,reason='altered evidence' "
                                if operation == "rewrite-evidence"
                                else "status='approved',decided_by=:actor,"
                                "fulfilled_by=NULL,fulfilled_version=NULL "
                            )
                            + "WHERE tenant_id='tenant-a' AND id=:id"
                        ),
                        {"id": request_id, "actor": actor},
                    )
        except DBAPIError as error:
            require(
                getattr(error.orig, "sqlstate", None) == sqlstate,
                "Request integrity denial had an unexpected cause",
            )
            primary = getattr(getattr(error.orig, "diag", None), "message_primary", "")
            expected = {
                "foreign-faculty": "row-level security",
                "rewrite-evidence": "Request identity and submitted evidence are immutable",
                "reopen-completed": "Invalid classroom request transition",
            }[operation]
            require(expected in primary, "The intended request invariant was not exercised")
        else:
            raise RuntimeError("Request SQL isolation/integrity was bypassed")
    from scripts.mvp_features_qualification import qualify as qualify_features

    features = qualify_features(runtime, actor=actor, project=project, period=row["period_id"])
    return {
        "multi_role_teacher_scope_denied": True,
        "cross_tenant_denied": True,
        "current_admin_read": True,
        "revoked_read_denied": True,
        "foreign_faculty_insert_denied": True,
        "evidence_immutable": True,
        "completed_transition_immutable": True,
        "mvp_features": features,
    }
