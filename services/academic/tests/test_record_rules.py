import pytest
from classync_contracts.academic import PeriodCreate

from services.academic.app.record_rules import AcademicError, adapter, validate_record
from services.academic.app.repository import AcademicRepository
from services.scheduling.tests.test_calendar import configuration


def test_initial_calendar_cannot_claim_published_authority(tmp_path):
    repository = AcademicRepository(tmp_path / "synthetic.sqlite3")
    repository.migrate()
    calendar = configuration().calendar.model_copy(update={"published_version": "forged"})
    with pytest.raises(AcademicError) as denied:
        repository.create_period(
            PeriodCreate(title="Synthetic", include_cdm_catalog=False, calendar=calendar),
            "sandbox",
            "synthetic",
        )
    assert denied.value.code == "publication_version"
    assert repository.periods("sandbox", "synthetic") == []


def test_shared_rules_reject_out_of_scope_references_without_mutating_lookup():
    subject = adapter.validate_python(
        {
            "kind": "subjects",
            "id": "subject",
            "code": "SYN",
            "name": "Synthetic",
            "program_ids": ["private-program"],
        }
    )
    seen = []

    def lookup(kind, identity):
        seen.append((kind, identity))
        return None

    with pytest.raises(AcademicError) as denied:
        validate_record(subject, "period", lookup)
    assert denied.value.code == "missing_reference"
    assert seen == [("programs", "private-program")]
