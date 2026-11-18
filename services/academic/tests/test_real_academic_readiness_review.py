import csv

import pytest

from scripts import build_real_academic_readiness_review as builder

from .synthetic_review_inputs import install_synthetic_review, write_workbook


@pytest.fixture
def synthetic_review(monkeypatch, tmp_path):
    return install_synthetic_review(monkeypatch, tmp_path)


def test_workbook_and_catalog_reconcile_without_promoting_courses_to_offerings(synthetic_review):
    evidence = builder.build()
    assert evidence == {
        "status": "PASS_REVIEW_ONLY",
        "workbook_versions": 39,
        "catalog_versions": 39,
        "workbook_course_rows": 2062,
        "catalog_course_rows": 2062,
        "programs": 8,
        "distinct_pdf_hashes": 20,
        "bsit_versions": 5,
        "bsit_first_semester_pilot_requirements": 27,
        "adjacent_version_code_change_candidates": 36,
        "green_bsit3a_sessions": 12,
        "workbook_catalog_course_difference_count": 0,
        "registrar_approvals": False,
        "actual_offerings_verified": False,
        "source_zip_raw_pdf_rechecked": False,
        "synthetic_generation_allowed_as_real": False,
    }
    pilot = read_csv(synthetic_review.output, "bsit-first-semester-requirements-review-only.csv")
    assert len(pilot) == 27
    assert {r["actual_offering_this_term"] for r in pilot} == {
        "UNVERIFIED — not created automatically"
    }
    assert {r["contact_minutes_approved"] for r in pilot} == {"NO EVIDENCE"}


def test_all_bsits_versions_remain_distinct_and_code_leads_are_not_aliases(synthetic_review):
    builder.build()
    cohorts = read_csv(synthetic_review.output, "bsit-cohort-curriculum-review.csv")
    assert [r["entry_cohort_candidate"] for r in cohorts] == [
        "2022",
        "2023",
        "2024",
        "2025",
        "2026",
    ]
    assert len({r["curriculum_version_id"] for r in cohorts}) == 5
    assert len({r["source_sha256"] for r in cohorts}) == 3
    assert all("UNVERIFIED" in r["cohort_assignment_status"] for r in cohorts)
    candidates = read_csv(synthetic_review.output, "bsit-code-equivalency-candidates.csv")
    assert len(candidates) == 36
    assert all("UNRESOLVED" in r["review_status"] for r in candidates)
    assert {(r["from_cohort_candidate"], r["to_cohort_candidate"]) for r in candidates} == {
        ("2022", "2023")
    }
    green = read_csv(synthetic_review.output, "green-bsit3a-curriculum-reconciliation.csv")
    by_code = {r["green_code_raw"]: r for r in green}
    assert by_code["ITASE1"]["candidate_2024_code_exact"] == "ITIASE1"
    assert by_code["ITELECT3"]["candidate_2024_code_exact"] == "ITELEC3"
    assert "POSSIBLE CODE EQUIVALENCY" in by_code["ITASE1"]["mapping_status"]
    assert "ABSENT FROM 2024 SOURCE" in by_code["ITDMATH"]["mapping_status"]
    assert "EXACT CODE PRESENT" in by_code["SYN-CURRENT-03"]["mapping_status"]
    assert "NOT FOUND" in by_code["SYN-NOTFOUND"]["mapping_status"]


@pytest.mark.parametrize("sheet", ["Sources", "All Curricula"])
def test_review_rejects_workbook_catalog_mismatch(synthetic_review, sheet):
    write_workbook(
        synthetic_review.workbook,
        synthetic_review.sources,
        synthetic_review.courses,
        mismatch=sheet,
    )
    with pytest.raises(ValueError, match="Workbook/source catalog .* mismatch"):
        builder.build()
    assert not (synthetic_review.output / "reconciliation-evidence.json").exists()


def read_csv(output, name: str) -> list[dict[str, str]]:
    path = output / name
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))
