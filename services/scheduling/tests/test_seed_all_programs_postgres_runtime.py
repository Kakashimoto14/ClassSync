"""All-program defense seed on a throwaway PostgreSQL cluster: idempotent, edit-preserving,
and generating a complete, independently valid, deterministic campus timetable.

Guardrails (owner-approved 27 November 2026): wall time bounded on CI runners, with the
measured duration printed; peak RSS under 400 MB where the platform reports it (Linux). The
wall ceiling was widened from 10 s to 20 s for slow runners (Slice C2 instruction); the
deterministic search budget and memory gate are unchanged.
"""

import sys
from time import perf_counter

import pytest
from classync_contracts.academic import RecordWrite
from classync_contracts.identity import VerifiedPrincipal
from classync_persistence.database import transaction
from classync_persistence.membership_changes import audit_actor
from classync_persistence.memberships import identity_context

from scripts.seed_campus_data import PERIOD_ID, apply_seed
from services.academic.app.postgres_repository import PostgresAcademicRepository
from services.scheduling.app.academic_input import academic_readiness
from services.scheduling.app.engine import generate_week
from services.scheduling.app.validation import validate_timetable
from services.testing.postgres_cluster import cluster, execute, provision  # noqa: F401

TENANT, PROJECT, ADMIN = "cdm", "demo-classsync-campus", "admin-uid"
WALL_SECONDS = 20
PEAK_RSS_MB = 400


@pytest.fixture(scope="module")
def campus(cluster):  # noqa: F811
    provisioned = provision(cluster)
    engine = provisioned.engine
    with transaction(engine("boot")) as db:
        execute(db, "INSERT INTO classsync_identity.tenants VALUES (:t,:p)", t=TENANT, p=PROJECT)
        identity_context(db, tenant_id=TENANT, uid=ADMIN)
        audit_actor(db, VerifiedPrincipal(uid="synthetic-provisioner"))
        execute(db, "INSERT INTO classsync_identity.people(tenant_id,id) VALUES (:t,'p-admin')",
                t=TENANT)
        execute(db, "INSERT INTO classsync_identity.memberships "
                    "(tenant_id,uid,person_id,roles,state,revision) VALUES "
                    "(:t,:u,'p-admin',ARRAY['administrator'],'active',1)", t=TENANT, u=ADMIN)

    def repository(user):
        return PostgresAcademicRepository(engine(user), tenant_id=TENANT,
                                          firebase_project_id=PROJECT,
                                          principal=VerifiedPrincipal(uid=ADMIN))

    first = apply_seed(repository("operator"))
    try:
        yield repository, first
    finally:
        for item in provisioned.engines.values():
            item.dispose()


def test_seed_is_idempotent_and_keeps_administrator_edits(campus):
    repository, first = campus
    assert first[1] == 432 and first[0] > 0
    repo = repository("operator")
    with repo.session(write=True) as db:
        snapshot = repo.snapshot_in(db, PERIOD_ID)
        entry = next(e for e in snapshot.records if e.record.kind == "offerings"
                     and len(e.record.room_ids) > 1)
        edited = entry.record.model_copy(update={"room_ids": entry.record.room_ids[:1]})
        repo.write_in(db, PERIOD_ID, RecordWrite(expected_revision=entry.revision, record=edited))
    assert apply_seed(repository("operator")) == (0, 0)
    after = repository("runtime").snapshot(PERIOD_ID)
    kept = next(e.record for e in after.records if e.record.id == entry.record.id)
    assert kept.room_ids == edited.room_ids
    kinds = {}
    for e in after.records:
        kinds[e.record.kind] = kinds.get(e.record.kind, 0) + 1
    assert (kinds["offerings"], kinds["sections"], kinds["resources"]) == (247, 36, 53)


def test_campus_generation_is_complete_valid_deterministic_and_in_budget(campus):
    repository, _ = campus
    checked = academic_readiness(repository("runtime").snapshot(PERIOD_ID))
    assert checked.ready, [i.message for i in checked.issues if i.severity == "blocking"]
    inputs = checked.inputs
    started = perf_counter()
    first = generate_week(inputs)
    elapsed = perf_counter() - started
    print(f"\nCampus generation: {len(inputs.offerings)} offerings, "
          f"{len(first.assignments)} sessions, {elapsed:.2f} s wall")
    assert first.solver_status in {"feasible", "optimal"}, first.diagnostics
    assert first.total_offerings_scheduled == first.total_offerings_requested == 247
    assert first.hard_conflict_count == 0
    assert validate_timetable(inputs, first.assignments).valid
    assert elapsed <= WALL_SECONDS, f"generation took {elapsed:.2f} s"
    second = generate_week(inputs)
    assert second.assignments == first.assignments  # deterministic search, same timetable
    report = first.metadata.polish
    assert report is not None, first.diagnostics
    print(f"Polish: {report.moves} moves, {report.evaluations} evaluations, "
          f"{report.elapsed_ms} ms, truncated={report.truncated}")
    print(f"before={report.before.model_dump()}")
    print(f"after ={report.after.model_dump()}")
    for item in report.unmet:
        print(f"unmet {item.model_dump()}")
    # A wall-clock cut-off would make the result machine dependent.
    assert not report.truncated
    assert report.after.short_section_days <= report.before.short_section_days
    assert report.after.over_span_section_days <= report.before.over_span_section_days
    assert report.after.orphan_section_days == 0
    if sys.platform.startswith("linux"):
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        print(f"Peak RSS: {peak:.0f} MB")
        assert peak < PEAK_RSS_MB
