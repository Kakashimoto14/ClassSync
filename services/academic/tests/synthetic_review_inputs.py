"""Invented builder inputs, written only into a caller-owned pytest directory.

The inventory size deliberately exercises the builders' existing source-count guards.
No rows, hashes, filenames, workbook bytes or schedule data come from staging files.
"""

import csv
import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class SyntheticReviewInputs:
    kit: Path
    catalog_path: Path
    workbook: Path
    green: Path
    output: Path
    sources: list[dict[str, str]]
    courses: list[dict[str, str]]
    catalog: dict


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def invented_rows():
    sources, courses = [], []
    for index in range(39):
        bsit = index < 5
        cohort = str(2022 + index) if bsit else str(2030 + index)
        group = (0, 1, 1, 2, 2)[index] if bsit else 3 + (index - 5) % 17
        program = "BSIT" if bsit else f"SYNTHETIC-PROGRAM-{(index - 5) % 7}"
        source = {
            "institute": "SYNTHETIC-INSTITUTE",
            "program": program,
            "entry_cohort": cohort,
            "source_pdf": f"SYNTHETIC-{program}-{cohort}.pdf",
            "source_archive_member": f"SYNTHETIC/{program}/{cohort}/source.pdf",
            "source_sha256": hashlib.sha256(f"invented-source-bytes-{group}".encode()).hexdigest(),
            "pages": "3",
            "printed_curriculum_ay": "2020-2021",
        }
        rows = []

        def course(code, title, year, semester, source=source, program=program, cohort=cohort):
            return {
                "institute": source["institute"],
                "program": program,
                "cohort": cohort,
                "curriculum_source": source["source_pdf"],
                "pdf_sha256": source["source_sha256"],
                "pdf_page": "1",
                "year_level": str(year),
                "semester": str(semester),
                "subject_code": code,
                "subject_title": title,
                "lec_hours_printed": "1",
                "lab_hours_printed": "0",
                "units_printed": "1",
                "prerequisite_printed": "",
            }

        if bsit:
            # Only the 2022 -> 2023 transition has 36 title/level/term code leads.
            # Equal-byte cohort pairs retain the same invented source contents.
            for number in range(36):
                code = f"SYN-{'OLD' if group == 0 else 'CURRENT'}-{number:02}"
                title = f"Synthetic second-term topic {number:02}"
                if group and number in (0, 1):
                    # Exercise the builder's two explicit unresolved-code leads.
                    code = ("ITIASE1", "ITELEC3")[number]
                if group == 2 and number == 2:
                    code, title = "ITDMATH", "Synthetic later mathematics topic"
                rows.append(course(code, title, 2, 2))
            # The hard-coded pilot cohorts select 6 + 7 + 7 + 7 first-term rows.
            for year, count in ((1, 6), (2, 7), (3, 7), (4, 7)):
                for number in range(count):
                    rows.append(
                        course(
                            f"SYN-Y{year}-{number:02}",
                            f"Synthetic first-term year {year} topic {number:02}",
                            year,
                            1,
                        )
                    )
        else:
            # Five BSIT versions contain 315 rows; 34 other versions contain1747.
            for number in range(52 if index - 5 < 13 else 51):
                rows.append(
                    course(
                        f"SYN-P{index}-{number:02}",
                        f"Synthetic other topic {number:02}",
                        1,
                        1,
                    )
                )
        source["extracted_rows"] = str(len(rows))
        sources.append(source)
        courses.extend(rows)
    return sources, courses


SOURCE_COLUMNS = {
    "Institute": "institute",
    "Program": "program",
    "Entry cohort": "entry_cohort",
    "Source PDF": "source_pdf",
    "PDF SHA256": "source_sha256",
}
COURSE_COLUMNS = {
    "Institute": "institute",
    "Program": "program",
    "Cohort": "cohort",
    "Source PDF": "curriculum_source",
    "Year": "year_level",
    "Sem": "semester",
    "Code": "subject_code",
    "Subject title": "subject_title",
    "Lec hours*": "lec_hours_printed",
    "Lab hours*": "lab_hours_printed",
    "Units*": "units_printed",
    "Prerequisites": "prerequisite_printed",
    "PDF page": "pdf_page",
}


def write_workbook(path, sources, courses, *, mismatch=None):
    """Create real OOXML sheets; exercise both inline and shared-string decoding."""
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package = "http://schemas.openxmlformats.org/package/2006/relationships"
    book = ET.Element(f"{{{main}}}workbook")
    sheets = ET.SubElement(book, f"{{{main}}}sheets")
    relationships = ET.Element(f"{{{package}}}Relationships")
    shared = ET.Element(f"{{{main}}}sst")
    values = {}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        content_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
        types = ET.Element(f"{{{content_ns}}}Types")
        ET.SubElement(
            types,
            f"{{{content_ns}}}Default",
            {
                "Extension": "rels",
                "ContentType": "application/vnd.openxmlformats-package.relationships+xml",
            },
        )
        ET.SubElement(
            types,
            f"{{{content_ns}}}Default",
            {
                "Extension": "xml",
                "ContentType": "application/xml",
            },
        )
        spreadsheet_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml."
        for part, kind in (
            ("workbook.xml", "sheet.main"),
            ("sharedStrings.xml", "sharedStrings"),
            ("worksheets/sheet1.xml", "worksheet"),
            ("worksheets/sheet2.xml", "worksheet"),
        ):
            ET.SubElement(
                types,
                f"{{{content_ns}}}Override",
                {
                    "PartName": "/xl/" + part,
                    "ContentType": f"{spreadsheet_mime}{kind}+xml",
                },
            )
        archive.writestr("[Content_Types].xml", ET.tostring(types))
        root_relationships = ET.Element(f"{{{package}}}Relationships")
        ET.SubElement(
            root_relationships,
            f"{{{package}}}Relationship",
            {
                "Id": "root-workbook",
                "Target": "xl/workbook.xml",
                "Type": rel + "/officeDocument",
            },
        )
        archive.writestr("_rels/.rels", ET.tostring(root_relationships))
        for number, (name, rows, columns) in enumerate(
            (
                ("Sources", sources, SOURCE_COLUMNS),
                ("All Curricula", courses, COURSE_COLUMNS),
            ),
            1,
        ):
            ET.SubElement(
                sheets,
                f"{{{main}}}sheet",
                {
                    "name": name,
                    "sheetId": str(number),
                    f"{{{rel}}}id": f"rId{number}",
                },
            )
            ET.SubElement(
                relationships,
                f"{{{package}}}Relationship",
                {
                    "Id": f"rId{number}",
                    "Target": f"worksheets/sheet{number}.xml",
                    "Type": rel + "/worksheet",
                },
            )
            sheet = ET.Element(f"{{{main}}}worksheet")
            data = ET.SubElement(sheet, f"{{{main}}}sheetData")
            raw_rows = [list(columns)] + [[row[key] for key in columns.values()] for row in rows]
            if mismatch == name:
                raw_rows[1][0] = "SYNTHETIC-MISMATCH"
            for row_number, row_values in enumerate(raw_rows, 1):
                row = ET.SubElement(data, f"{{{main}}}row", {"r": str(row_number)})
                for value in row_values:
                    cell = ET.SubElement(
                        row,
                        f"{{{main}}}c",
                        {
                            "t": "inlineStr" if row_number == 1 else "s",
                        },
                    )
                    if row_number == 1:
                        inline = ET.SubElement(cell, f"{{{main}}}is")
                        ET.SubElement(inline, f"{{{main}}}t").text = value
                    else:
                        if value not in values:
                            values[value] = len(values)
                            item = ET.SubElement(shared, f"{{{main}}}si")
                            ET.SubElement(item, f"{{{main}}}t").text = value
                        ET.SubElement(cell, f"{{{main}}}v").text = str(values[value])
            archive.writestr(f"xl/worksheets/sheet{number}.xml", ET.tostring(sheet))
        archive.writestr("xl/workbook.xml", ET.tostring(book))
        archive.writestr("xl/_rels/workbook.xml.rels", ET.tostring(relationships))
        archive.writestr("xl/sharedStrings.xml", ET.tostring(shared))


def install_synthetic_review(monkeypatch, root):
    from scripts import build_curriculum_review_catalog as catalog_builder
    from scripts import build_real_academic_readiness_review as readiness_builder

    kit = root / "invented-inputs"
    kit.mkdir()
    sources, courses = invented_rows()
    write_csv(kit / "prospectus_source_manifest_39.csv", sources)
    write_csv(kit / "all_programs_curriculum_extracted_REVIEW_ONLY.csv", courses)
    (kit / "SUMMARY.json").write_text(json.dumps({"source_zip_sha256": "a" * 64}))
    catalog_path = root / "synthetic-catalog.json"
    monkeypatch.setattr(catalog_builder, "KIT", kit)
    monkeypatch.setattr(catalog_builder, "TARGET", catalog_path)
    catalog = catalog_builder.build()
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    workbook = root / "synthetic-workbook.xlsx"
    write_workbook(workbook, sources, courses)
    green = root / "synthetic-schedule-codes.json"
    codes = (
        ["ITASE1", "ITELECT3", "ITDMATH"]
        + [f"SYN-CURRENT-{number:02}" for number in range(3, 8)]
        + ["SYN-NOTFOUND"]
    )
    green.write_text(
        json.dumps(
            {
                "sessions": [{"subject_code_raw": code} for code in codes + codes[:3]],
            }
        ),
        encoding="utf-8",
    )
    output = root / "synthetic-reports"
    for name, path in (
        ("CATALOG", catalog_path),
        ("WORKBOOK", workbook),
        ("GREEN", green),
        ("OUT", output),
    ):
        monkeypatch.setattr(readiness_builder, name, path)
    return SyntheticReviewInputs(
        kit,
        catalog_path,
        workbook,
        green,
        output,
        sources,
        courses,
        catalog,
    )
