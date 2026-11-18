"""Build review-only BSIT cohort and source reconciliation artifacts.

Reads only the supplied staging workbook, extracted CSVs and the immutable
curriculum-review catalog. No database connections or source mutations.
"""

# This report generator embeds Markdown prose as source literals; keep natural line wrapping in
# the generated artifact while retaining all other Ruff checks on the script.
# ruff: noqa: E501

from __future__ import annotations

import csv
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/academic/real-academic-readiness-20261103"
CATALOG = ROOT / "packages/api-contracts/classync_contracts/catalogs/curriculum-review.json"
WORKBOOK = ROOT / "docs/academic/ClassSync_Institutional_Cohort_Staging_2026.xlsx"
GREEN = ROOT / "docs/academic/review-20261031/current-bsit3a.json"
NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def workbook_sheets(path: Path) -> dict[str, list[list[str]]]:
    """Read a supplied xlsx using its public OOXML parts and Python stdlib."""
    with zipfile.ZipFile(path) as book:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in book.namelist():
            root = ET.fromstring(book.read("xl/sharedStrings.xml"))
            shared = [
                "".join(t.text or "" for t in item.findall(".//m:t", NS))
                for item in root.findall("m:si", NS)
            ]
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        rel_root = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        rels = {r.attrib["Id"]: r.attrib["Target"] for r in rel_root}
        result: dict[str, list[list[str]]] = {}
        rid = f"{{{NS['r']}}}id"
        for sheet in workbook.findall("m:sheets/m:sheet", NS):
            target = rels[sheet.attrib[rid]].lstrip("/")
            if not target.startswith("xl/"):
                target = f"xl/{target}"
            root = ET.fromstring(book.read(target))
            rows: list[list[str]] = []
            for row in root.findall(".//m:sheetData/m:row", NS):
                values: list[str] = []
                for cell in row.findall("m:c", NS):
                    value = cell.find("m:v", NS)
                    text = value.text if value is not None and value.text else ""
                    if cell.attrib.get("t") == "s" and text:
                        text = shared[int(text)]
                    elif cell.attrib.get("t") == "inlineStr":
                        text = "".join(t.text or "" for t in cell.findall(".//m:t", NS))
                    values.append(text)
                rows.append(values)
            result[sheet.attrib["name"]] = rows
        return result


def normalized_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def row_counter(rows: list[dict[str, str]], fields: tuple[str, ...]) -> Counter:
    return Counter(tuple(row.get(field, "") for field in fields) for row in rows)


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build() -> dict[str, object]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    workbook = workbook_sheets(WORKBOOK)
    source_sheet = workbook["Sources"]
    source_headers = source_sheet[0]
    workbook_versions = [
        dict(zip(source_headers, row, strict=True)) for row in source_sheet[1:] if any(row)
    ]
    course_sheet = workbook["All Curricula"]
    course_headers = course_sheet[0]
    workbook_courses = [
        dict(zip(course_headers, row, strict=True)) for row in course_sheet[1:] if any(row)
    ]
    courses = catalog["courses"]
    versions = catalog["versions"]
    if len(versions) != 39 or len(courses) != 2062:
        raise ValueError("Unexpected source version/course row count; review extraction inputs.")
    version_fields = ("Institute", "Program", "Entry cohort", "Source PDF", "PDF SHA256")
    catalog_version_rows = [
        {
            "Institute": v["institute"],
            "Program": v["program"],
            "Entry cohort": v["entry_cohort"],
            "Source PDF": v["source_pdf"],
            "PDF SHA256": v["source_sha256"],
        }
        for v in versions
    ]
    version_differences = row_counter(workbook_versions, version_fields) - row_counter(
        catalog_version_rows, version_fields
    )
    reverse_version_differences = row_counter(catalog_version_rows, version_fields) - row_counter(
        workbook_versions, version_fields
    )

    course_fields = (
        "Institute",
        "Program",
        "Cohort",
        "Source PDF",
        "Year",
        "Sem",
        "Code",
        "Subject title",
        "Lec hours*",
        "Lab hours*",
        "Units*",
        "Prerequisites",
        "PDF page",
    )
    catalog_course_rows = [
        {
            "Institute": c["institute"],
            "Program": c["program"],
            "Cohort": c["cohort"],
            "Source PDF": c["curriculum_source"],
            "Year": c["year_level"],
            "Sem": c["semester"],
            "Code": c["subject_code"],
            "Subject title": c["subject_title"],
            "Lec hours*": c["lec_hours_printed"],
            "Lab hours*": c["lab_hours_printed"],
            "Units*": c["units_printed"],
            "Prerequisites": c["prerequisite_printed"],
            "PDF page": c["pdf_page"],
        }
        for c in courses
    ]
    course_differences = row_counter(workbook_courses, course_fields) - row_counter(
        catalog_course_rows, course_fields
    )
    reverse_course_differences = row_counter(catalog_course_rows, course_fields) - row_counter(
        workbook_courses, course_fields
    )

    bsit_versions = sorted(
        (v for v in versions if v["program"] == "BSIT"),
        key=lambda v: (int(v["entry_cohort"]), v["source_pdf"]),
    )
    hashes: dict[str, list[str]] = defaultdict(list)
    for version in bsit_versions:
        hashes[version["source_sha256"]].append(version["source_pdf"])
    source_rows = [
        {
            "entry_cohort_candidate": v["entry_cohort"],
            "curriculum_version_id": v["id"],
            "source_pdf": v["source_pdf"],
            "source_sha256": v["source_sha256"],
            "printed_curriculum_ay": v["printed_curriculum_ay"],
            "duplicate_bytes_with": " | ".join(hashes[v["source_sha256"]]),
            "cohort_assignment_status": "UNVERIFIED — folder/workbook candidate; Registrar confirmation required",
            "academic_use": "Curriculum requirements only; not a current-semester offering",
        }
        for v in bsit_versions
    ]

    # Adjacent cohort/source versions only. Exact normalized title and level/semester
    # coincidences are leads for human review, never equivalency decisions.
    code_changes: list[dict[str, object]] = []
    courses_by_version: dict[str, list[dict[str, str]]] = defaultdict(list)
    for course in courses:
        courses_by_version[course["curriculum_version_id"]].append(course)
    for old, new in zip(bsit_versions, bsit_versions[1:], strict=False):
        new_index: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
        for course in courses_by_version[new["id"]]:
            new_index[
                (
                    course["year_level"],
                    course["semester"],
                    normalized_title(course["subject_title"]),
                )
            ].append(course)
        for old_course in courses_by_version[old["id"]]:
            key = (
                old_course["year_level"],
                old_course["semester"],
                normalized_title(old_course["subject_title"]),
            )
            for new_course in new_index.get(key, []):
                if old_course["subject_code"] != new_course["subject_code"]:
                    code_changes.append(
                        {
                            "from_cohort_candidate": old["entry_cohort"],
                            "from_source": old["source_pdf"],
                            "year_level": old_course["year_level"],
                            "semester": old_course["semester"],
                            "from_code_exact": old_course["subject_code"],
                            "to_cohort_candidate": new["entry_cohort"],
                            "to_source": new["source_pdf"],
                            "to_code_exact": new_course["subject_code"],
                            "title_from_exact": old_course["subject_title"],
                            "title_to_exact": new_course["subject_title"],
                            "review_status": "UNRESOLVED — matching title/level is not Registrar equivalency",
                        }
                    )

    # The 27-row document is a cohort/year/semester prospectus slice. Do not
    # promote it to actual period offerings.
    pilot_candidates = ((2026, 1), (2025, 2), (2024, 3), (2023, 4))
    pilot_rows: list[dict[str, object]] = []
    for cohort, year in pilot_candidates:
        version = next(v for v in bsit_versions if int(v["entry_cohort"]) == cohort)
        for c in courses_by_version[version["id"]]:
            if c["year_level"] == str(year) and c["semester"] == "1":
                pilot_rows.append(
                    {
                        "entry_cohort_candidate": cohort,
                        "year_level_candidate": year,
                        "semester": "first",
                        "curriculum_version_id": version["id"],
                        "source_pdf": version["source_pdf"],
                        "source_sha256": version["source_sha256"],
                        "subject_code_exact": c["subject_code"],
                        "subject_title_exact": c["subject_title"],
                        "lec_hours_printed": c["lec_hours_printed"],
                        "lab_hours_printed": c["lab_hours_printed"],
                        "units_printed": c["units_printed"],
                        "prerequisite_printed": c["prerequisite_printed"],
                        "pdf_page": c["pdf_page"],
                        "contact_minutes_approved": "NO EVIDENCE",
                        "actual_offering_this_term": "UNVERIFIED — not created automatically",
                        "generation_eligible": "NO — cohort/term/section/Registrar review pending",
                    }
                )

    green = json.loads(GREEN.read_text(encoding="utf-8"))
    version_2024 = next(v for v in bsit_versions if v["entry_cohort"] == "2024")
    v24 = courses_by_version[version_2024["id"]]
    exact_24: dict[str, list[dict[str, str]]] = defaultdict(list)
    for c in v24:
        exact_24[c["subject_code"]].append(c)
    green_mappings: list[dict[str, object]] = []
    candidate_codes = {"ITASE1": "ITIASE1", "ITELECT3": "ITELEC3"}
    for code in sorted({s["subject_code_raw"] for s in green["sessions"]}):
        exact = exact_24.get(code, [])
        candidate_code = candidate_codes.get(code)
        candidate = next((c for c in v24 if c["subject_code"] == candidate_code), None)
        if exact:
            c = exact[0]
            status = (
                "EXACT CODE PRESENT IN 2024 SOURCE; exact section/term applicability unverified"
            )
            out_code, out_title = c["subject_code"], c["subject_title"]
        elif candidate:
            out_code, out_title = candidate["subject_code"], candidate["subject_title"]
            status = "POSSIBLE CODE EQUIVALENCY — Registrar decision required; do not alias"
        elif code == "ITDMATH":
            later = next(
                (
                    c
                    for v in bsit_versions
                    if int(v["entry_cohort"]) >= 2025
                    for c in courses_by_version[v["id"]]
                    if c["subject_code"] == code
                ),
                None,
            )
            out_code = later["subject_code"] if later else ""
            out_title = later["subject_title"] if later else ""
            status = (
                "ABSENT FROM 2024 SOURCE; later source places it at a different level/term; "
                "retake/equivalency/other explanation unverified"
            )
        else:
            out_code, out_title = "", ""
            status = "NOT FOUND IN 2024 SOURCE; Registrar reconciliation required"
        green_mappings.append(
            {
                "green_code_raw": code,
                "cohort_source_candidate": version_2024["source_pdf"],
                "candidate_2024_code_exact": out_code,
                "candidate_2024_title_exact": out_title,
                "mapping_status": status,
                "source_assignment": "No equivalency or offering is approved by this review",
            }
        )

    checklist = [
        (
            "Registrar authority",
            "Registrar-approved source/version and cohort assignment for each BSIT entry cohort; archive authenticity",
            "No original 39-PDF archive is available at its supplied path for fresh raw-byte review",
            "BLOCKED",
        ),
        (
            "Course equivalencies",
            "Signed decisions for code/title/version changes; especially ITASE1/ITIASE1, ITELECT3/ITELEC3, ITDMATH and the 2022→2023 code changes",
            "No aliases or equivalencies are approved",
            "BLOCKED",
        ),
        (
            "Academic period",
            "Official academic year, semester, dates, instructional days, timezone/calendar exceptions",
            "Green timetable effective term/date is unknown",
            "BLOCKED",
        ),
        (
            "Active sections",
            "Actual BSIT sections per year, letters/IDs, entry-cohort bindings and source version",
            "BSIT1A–4A are placeholders; only the green BSIT3A operational schedule is supplied",
            "BLOCKED",
        ),
        (
            "Student population",
            "Verified aggregate headcount by section; no student roster required for this checklist",
            "No actual counts supplied",
            "BLOCKED",
        ),
        (
            "Semester offerings",
            "Approved subject list per section this term, including electives, retakes, irregular study and cross-listed offerings",
            "Prospectus rows and pilot rows are requirements, not active offerings",
            "BLOCKED",
        ),
        (
            "Contact minutes/patterns",
            "Registrar-approved weekly contact minutes and permitted session patterns for each offering",
            "PDF lecture/lab hours are not meeting minutes",
            "BLOCKED",
        ),
        (
            "Faculty",
            "Authentic faculty identity, subject eligibility, weekly/daily workload caps, availability/unavailability",
            "81 candidates are synthetic only; no authentic faculty records supplied",
            "BLOCKED",
        ),
        (
            "Rooms",
            "Physical room ID, operational status, type, verified capacity/equipment, operating windows, restrictions/blocks",
            "59-space catalog is provisional; green room labels and NB107 identity/date unresolved",
            "BLOCKED",
        ),
        (
            "Shared institute scope",
            "One period containing intended ICS/IBE/ITE offerings and every shared faculty/room commitment, with Administrator review and source/reference",
            "No approved cross-institute scope/commitment inventory supplied",
            "BLOCKED",
        ),
        (
            "Fixed assignments",
            "Admin-reviewed locked sessions with valid offering, section, faculty, room, date/day/time and resource availability",
            "Only green BSIT3A observations; no institute-wide locks",
            "BLOCKED",
        ),
        (
            "Supervised pilot authority",
            "Named authorized academic Admin, privacy/data authority, review witnesses, rollback and no-publication procedure",
            "Local test identities only",
            "BLOCKED",
        ),
    ]

    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(
        OUT / "bsit-cohort-curriculum-review.csv",
        list(source_rows[0]),
        source_rows,
    )
    write_csv(
        OUT / "bsit-code-equivalency-candidates.csv",
        list(code_changes[0]) if code_changes else ["from_cohort_candidate"],
        code_changes,
    )
    write_csv(
        OUT / "bsit-first-semester-requirements-review-only.csv",
        list(pilot_rows[0]),
        pilot_rows,
    )
    write_csv(
        OUT / "green-bsit3a-curriculum-reconciliation.csv", list(green_mappings[0]), green_mappings
    )
    write_csv(
        OUT / "real-pilot-input-checklist.csv",
        ["category", "required_verified_input", "current_evidence", "status"],
        [
            dict(
                zip(
                    ("category", "required_verified_input", "current_evidence", "status"),
                    row,
                    strict=True,
                )
            )
            for row in checklist
        ],
    )
    if len(bsit_versions) != 5 or len(pilot_rows) != 27 or len(green["sessions"]) != 12:
        raise ValueError("BSIT source/session matrix differs from the approved staging inventory.")
    if version_differences or reverse_version_differences:
        raise ValueError(f"Workbook/source catalog version mismatch: {version_differences}")
    if course_differences or reverse_course_differences:
        raise ValueError(
            "Workbook/source catalog course mismatch: "
            f"workbook-only={course_differences}, catalog-only={reverse_course_differences}"
        )

    report = (
        f"""# BSIT Years 1–4 real academic-data readiness review

Review-only, generated 3 November 2026 from the supplied staging workbook, extracted CSV, versioned review catalog and owner-confirmed green timetable transcription. It is not a Registrar certification, active-offering list, student roster, or publication.

## Source reconciliation

- Workbook `Sources` sheet and curriculum catalog agree on **{len(versions)} versions**; workbook `All Curricula` and catalog agree row-for-row on **{len(courses)} extracted course rows** across **{len(set(v["program"] for v in versions))} programs**. Source hashes have **{len(set(v["source_sha256"] for v in versions))} distinct values**.
- The 39-version catalog retains **{len(bsit_versions)} BSIT source versions** for candidate entry cohorts 2022–2026. The supplied workbook itself labels these as cohort-folder candidates that require Registrar confirmation. **No candidate is marked Registrar-approved by this report.** Printed curriculum AY and entry-cohort folder are separate fields.
- `{bsit_versions[1]["source_pdf"]}` and `{bsit_versions[2]["source_pdf"]}` have identical SHA-256 bytes but remain distinct 2023/2024 source-version IDs. `{bsit_versions[3]["source_pdf"]}` and `{bsit_versions[4]["source_pdf"]}` likewise remain distinct 2025/2026 cohort versions despite identical bytes. Do not merge or migrate student bindings.
- There are **{len(code_changes)} adjacent-version, same-normalized-title/year/semester code-change candidates**, all between the 2022 and 2023 source files. See the CSV; they are unresolved comparison leads, not approved equivalencies. No source code is silently replaced.
- The prospectus ZIP is not present at the supplied repository path for this fresh review. Workbook/catalog hashes and row content agree, but raw-PDF authenticity and page-by-page human review are **not freshly verified**. Existing extraction issue: `22_BSCPE.pdf`, page 2, Summer table title unmatched; keep that source row set under review.

## Candidate curriculum by BSIT entry cohort

| Entry-cohort candidate | Source version candidate | Printed AY | Status |
|---:|---|---|---|
"""
        + "\n".join(
            f"| {v['entry_cohort']} | `{v['source_pdf']}` | {v['printed_curriculum_ay']} | Registrar applicability **UNVERIFIED**; preserve this source identity |"
            for v in bsit_versions
        )
        + """

The candidate binding rule is `entry cohort → explicit version ID`; a later source release does not change an existing student/section binding. The owner-confirmed green timetable is the current BSIT3A operational reference, but its effective term and Registrar curriculum assignment remain unknown. The staging workbook proposes the 2024 source for that cohort; the workbook labels that mapping pending. Do not treat it as approved.

The 27-row BSIT Years 1–4 first-semester pilot slice is **prospectus requirements only**, built as 8 course rows for candidate 2026/Y1, 8 for 2025/Y2, 8 for 2024/Y3 and 3 for 2023/Y4. It does not confirm current students, real sections, actual term offerings, contact minutes, faculty or rooms. Exact codes/titles, source hashes, printed lecture/lab hours, units, prerequisites and pages are in `bsit-first-semester-requirements-review-only.csv`; no printed hour is converted to meeting minutes.

## Green BSIT3A reconciliation

The green schedule remains a separate owner-confirmed current operational evidence source with 12 sessions. No pink superseded assignment is merged. Nine raw course codes compare to the 2024 cohort source candidate as detailed in `green-bsit3a-curriculum-reconciliation.csv`. In particular, `ITASE1` vs source `ITIASE1` and `ITELECT3` vs `ITELEC3` are unresolved candidate mappings; green `ITDMATH` is absent from the 2024 source and appears in later source material at a different year/semester, so retake/equivalency/other explanation remains unknown. The other exact-code hits do not themselves confirm term offering. Tuesday `ITOPSYS` remains tentative and has no confirmed room. The pink BSIT3B schedule remains superseded and does not establish current BSIT3B assignments; 3B currency is unconfirmed.

The separate NB 107 room timetable image is retained as undated room evidence. It does not establish PRRC 107 availability or identity; its effective date/revision, issuing authority and physical-room distinction still require confirmation. See `../review-20261031/README.md` and the preserved source register for the image and hash.

## Administrator workflow and readiness gates

Use the current persisted workflow in order: create the period → enter the official calendar → register institute/program → select exact version/course for source-linked subjects → bind each real section to its entry cohort/version and verify aggregate population → enter only approved current-period offerings → add authentic faculty eligibility, availability and workload → verify classroom identity/capacity/equipment/operating and blocked windows → set subject contact minutes and allowed patterns from approved evidence → include shared ICS/IBE/ITE commitments and fixed assignments in the same period → run readiness → generate → independently validate → review/save draft. Readiness or generation does not publish.

The existing period input snapshot contains every active offering, section, faculty and room in that period. Solver/validator resource conflicts therefore apply across institute IDs when their records share stable faculty/room IDs. To validate a shared classroom/instructor commitment, include all concerned institute offerings/locks in the same academic period, declare the intended scope complete, and record the shared-scope review reference. Separate periods are **not** compared for weekly conflicts. The Administrator records the review; this is not an independent campus-wide attestation.

Institutional readiness now requires an approved period calendar; section cohort/version, official identity and population verification with source; exact subject/version review and approved contact-minute/pattern source; current-term offering confirmation and source; faculty eligibility/availability/workload flags and source; verified room availability/blocks; operating-window approval/source; and same-period shared-scope review/source. Edits to reviewed academic inputs clear the corresponding verification flag. Generation remains blocked until these records are supplied and reviewed.

`real-pilot-input-checklist.csv` lists the required evidence. Current status by category is **BLOCKED**: actual calendar, active sections/enrollments, populations, term offerings, Registrar mappings/minutes, authentic faculty and workloads, verified room identities/blocks, cross-institute commitments, and supervised-pilot authority have not been supplied. Synthetic faculty, rooms and placeholder sections are limited to isolated tests and cannot pass institutional publication checks.

## Verified / hypothetical / missing / conflicting

- **VERIFIED:** source workbook/catalog rows and cohort/source labels reconcile structurally; source bytes are preserved by hash; green BSIT3A was owner-confirmed current, its 12 sessions and tentative ITOPSYS stay in the isolated review dataset; pink is superseded. Existing code has period-scoped AcademicSnapshot, version binding, readiness blockers, shared-resource OR-Tools constraints and independent output validation.
- **HYPOTHETICAL:** 27 BSIT first-semester pilot rows, 4 placeholder A sections, 81 synthetic faculty, illustrative workloads/availability, 4 synthetic rooms and test calendar belong only to the synthetic pilot. The previously verified 54-session feasible draft remains separate evidence; it is not a real schedule.
- **MISSING:** Registrar sign-off for each cohort/version, the actual current AY/semester/calendar, real section IDs/letters/populations, approved current-semester offering lists, exact code equivalencies, contact minutes/patterns, faculty eligibility/workload/availability, room identities/capacity/equipment/status/blocks, full institute shared commitments and authorized supervised-pilot reviewer.
- **CONFLICTING/UNCONFIRMED:** green versus 2024 source codes `ITASE1`/`ITIASE1` and `ITELECT3`/`ITELEC3`; `ITDMATH` absent from candidate 2024 source; duplicates of identical PDF bytes across distinct entry cohorts; pink is stale; no current 3B timetable confirmation; green time effectiveness is undated; green room-label identity/availability is provisional; NB 107 timetable effective date is unknown and is separate from PRRC 107.

No institutional import, individual student data ingestion, authentic account creation, real publication, cloud change, deployment, commit or push occurred. This report prepares the verified-input boundary; it does not assert real scheduling readiness.
"""
    )
    (OUT / "BSIT_YEARS_1_TO_4_READINESS.md").write_text(report, encoding="utf-8")
    evidence = {
        "status": "PASS_REVIEW_ONLY",
        "workbook_versions": len(workbook_versions),
        "catalog_versions": len(versions),
        "workbook_course_rows": len(workbook_courses),
        "catalog_course_rows": len(courses),
        "programs": len(set(v["program"] for v in versions)),
        "distinct_pdf_hashes": len(set(v["source_sha256"] for v in versions)),
        "bsit_versions": len(bsit_versions),
        "bsit_first_semester_pilot_requirements": len(pilot_rows),
        "adjacent_version_code_change_candidates": len(code_changes),
        "green_bsit3a_sessions": len(green["sessions"]),
        "workbook_catalog_course_difference_count": 0,
        "registrar_approvals": False,
        "actual_offerings_verified": False,
        "source_zip_raw_pdf_rechecked": False,
        "synthetic_generation_allowed_as_real": False,
    }
    (OUT / "reconciliation-evidence.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )
    return evidence


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
