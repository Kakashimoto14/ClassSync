"""Package supplied extraction as immutable REVIEW evidence, never as active offerings."""

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "docs/academic"
TARGET = ROOT / "packages/api-contracts/classync_contracts/catalogs/curriculum-review.json"


def rows(name):
    with (KIT / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def build():
    sources = rows("prospectus_source_manifest_39.csv")
    courses = rows("all_programs_curriculum_extracted_REVIEW_ONLY.csv")
    versions, records, keys = [], [], {}
    for source in sources:
        identity = (
            "curr-"
            + hashlib.sha256(
                (source["source_archive_member"] + ":" + source["source_sha256"]).encode()
            ).hexdigest()[:24]
        )
        versions.append({"id": identity, **source, "review_status": "unreviewed"})
        key = (source["institute"], source["program"], source["entry_cohort"], source["source_pdf"])
        assert key not in keys
        keys[key] = versions[-1]
    for row in courses:
        version = keys[(row["institute"], row["program"], row["cohort"], row["curriculum_source"])]
        assert row["pdf_sha256"] == version["source_sha256"]
        assert 1 <= int(row["pdf_page"]) <= int(version["pages"])
        identity = (
            "course-"
            + hashlib.sha256(
                json.dumps(
                    {"version": version["id"], **row}, sort_keys=True, ensure_ascii=False
                ).encode()
            ).hexdigest()[:24]
        )
        records.append({"id": identity, "curriculum_version_id": version["id"], **row})
    assert len(versions) == 39 and len(records) == 2062
    assert len({c["id"] for c in records}) == len(records)
    assert len({v["program"] for v in versions}) == 8
    assert len({v["source_sha256"] for v in versions}) == 20
    for version in versions:
        assert sum(c["curriculum_version_id"] == version["id"] for c in records) == int(
            version["extracted_rows"]
        )
    return {
        "status": "unreviewed-extraction-not-active-offerings",
        "versions": versions,
        "courses": records,
        "source_zip_sha256": json.loads((KIT / "SUMMARY.json").read_text())["source_zip_sha256"],
    }


if __name__ == "__main__":
    TARGET.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("39 source versions / 8 programs / 2062 unreviewed courses packaged; no database writes")
