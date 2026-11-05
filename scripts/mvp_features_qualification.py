"""Additional SQL controls in the already-owned disposable request qualification."""

from classync_contracts.identity import VerifiedPrincipal
from classync_persistence.database import transaction
from classync_persistence.memberships import identity_context
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from scripts.postgres_driver_qualification import require
from services.gateway.app.announcements import Announcements, NoticeEdit, NoticeInput
from services.scheduling.app.draft_rules import DraftError
from services.scheduling.app.postgres_publication_repository import PostgresPublicationRepository


def qualify(runtime, *, actor, project, period):
    claims = {"tenant_id": "tenant-a", "uid": actor, "role": "administrator"}
    repo = Announcements(runtime, tenant="tenant-a", project=project)
    notice = repo.create(
        claims,
        NoticeInput(
            title="Synthetic SQL audience control",
            body="Invented local content",
            audience=["teacher"],
        ),
    )
    teacher = {**claims, "role": "teacher"}
    require(
        any(item["id"] == notice["id"] for item in repo.list(teacher)["announcements"]),
        "Current Teacher audience was not readable",
    )
    body = NoticeEdit(
        title=notice["title"], body=notice["body"], audience=["administrator"], expected_revision=1
    )
    repo.change(claims, notice["id"], 1, body)
    require(
        not any(item["id"] == notice["id"] for item in repo.list(teacher)["announcements"]),
        "Selected Teacher role inherited Administrator audience access",
    )
    for tenant, role in (("tenant-a", "teacher"), ("tenant-b", "administrator")):
        with transaction(runtime) as db:
            identity_context(db, tenant_id=tenant, uid=actor)
            db.execute(
                text(
                    "SELECT set_config('classsync.role',:role,true), "
                    "set_config('classsync.project_id',:project,true)"
                ),
                {"role": role, "project": project},
            )
            result = db.execute(
                text("""UPDATE classsync_academic.announcements
                SET title='Untrusted overwrite',revision=revision+1,updated_by=:uid
                WHERE tenant_id='tenant-a' AND id=:id"""),
                {"uid": actor, "id": notice["id"]},
            )
            require(result.rowcount == 0, "Notice role/tenant write isolation failed")
    try:
        with transaction(runtime) as db:
            identity_context(db, tenant_id="tenant-a", uid=actor)
            db.execute(
                text(
                    "SELECT set_config('classsync.role','administrator',true), "
                    "set_config('classsync.project_id',:project,true)"
                ),
                {"project": project},
            )
            db.execute(
                text("""UPDATE classsync_academic.announcements
                SET created_at=created_at-interval '1 hour',revision=revision+1,updated_by=:uid
                WHERE tenant_id='tenant-a' AND id=:id"""),
                {"uid": actor, "id": notice["id"]},
            )
    except DBAPIError as error:
        require(
            getattr(error.orig, "sqlstate", None) == "23514",
            "Notice immutable provenance denial had an unexpected cause",
        )
    else:
        raise RuntimeError("Notice creation provenance was mutable")
    publication = PostgresPublicationRepository(
        runtime,
        tenant_id="tenant-a",
        firebase_project_id=project,
        principal=VerifiedPrincipal(uid=actor),
    )
    try:
        publication.room_directory(period, {"role": "teacher", "faculty_id": actor})
    except DraftError as error:
        require(error.status == 403, "Unexpected dual-role directory denial")
    else:
        raise RuntimeError("Unassigned selected Teacher role inherited Administrator directory")
    return {
        "selected_role_audience_isolated": True,
        "teacher_write_denied": True,
        "cross_tenant_write_denied": True,
        "creation_provenance_immutable": True,
        "dual_role_unassigned_directory_denied": True,
    }
