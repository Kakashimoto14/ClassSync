"""Synthetic local PDF/photo OCR and private-processing qualification. No cloud calls."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from services.gateway.app.registration import match_review
from services.gateway.app.registration_ocr import image_dimensions
from services.gateway.app.registration_processing import process_document
from services.gateway.app.registration_schema import RegistrationReview
from services.gateway.tests.registration_fixtures import pdf_bytes


def scanned_pdf(image, width=1600, height=900):
    page_height = 800 * height / width
    stream = f"q 800 0 0 {page_height:g} 0 0 cm /Im0 Do Q".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 800 {page_height:g}] ".encode()
        + b"/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>",
        f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} ".encode()
        + b"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length "
        + str(len(image)).encode()
        + b" >>\nstream\n"
        + image
        + b"\nendstream",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
    ]
    output, offsets = bytearray(b"%PDF-1.7\n"), [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return bytes(output)


def fixture_images(root):
    # Static invented content and a new owned temp root. No source form is used.
    if os.name != "nt":
        renderer = shutil.which("pdftoppm")
        if not renderer:
            raise RuntimeError("Local PDF rasterizer is unavailable")
        source = root / "synthetic-fixture.pdf"
        source.write_bytes(pdf_bytes())
        for kind, option in (("png", "-png"), ("jpg", "-jpeg")):
            subprocess.run(
                [
                    renderer,
                    "-singlefile",
                    "-scale-to",
                    "2000",
                    option,
                    str(source),
                    str(root / "synthetic-registration"),
                ],
                check=True,
                timeout=5,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if not (root / f"synthetic-registration.{kind}").is_file():
                raise RuntimeError("Synthetic raster fixture generation failed")
        return
    script = r"""
Add-Type -AssemblyName System.Drawing
$m2Image = New-Object System.Drawing.Bitmap(1600,900)
$m2Graphics = [System.Drawing.Graphics]::FromImage($m2Image)
$m2Font = New-Object System.Drawing.Font(
 'Consolas',26,[System.Drawing.FontStyle]::Regular,[System.Drawing.GraphicsUnit]::Pixel)
try {
 $m2Graphics.Clear([System.Drawing.Color]::White)
 $m2Lines = @(
 'SYNTHETIC REGISTRATION FORM',
 'Academic Year/Term: 2026-2027 / Semester: 1',
 'Student ID: SYN-001  Program: SYNTHETIC',
 'Year Level: 2',
 'Code       Description                 Section  Lec Lab CLab Units',
 'TEST101    Invented seminar             2        3   0   0    3',
 'TEST102    Invented laboratory          2        1   0   2    3',
 'Total Units: 6')
 for($m2Index=0; $m2Index -lt $m2Lines.Count; $m2Index++) {
  $m2Graphics.DrawString($m2Lines[$m2Index],$m2Font,[System.Drawing.Brushes]::Black,40,40+60*$m2Index)
 }
 $m2Png = Join-Path $env:CLASSSYNC_OCR_FIXTURE_ROOT 'synthetic-registration.png'
 $m2Jpg = Join-Path $env:CLASSSYNC_OCR_FIXTURE_ROOT 'synthetic-registration.jpg'
 $m2Image.Save($m2Png,[System.Drawing.Imaging.ImageFormat]::Png)
 $m2Image.Save($m2Jpg,[System.Drawing.Imaging.ImageFormat]::Jpeg)
} finally { $m2Font.Dispose(); $m2Graphics.Dispose(); $m2Image.Dispose() }
"""
    result = subprocess.run(
        [
            str(Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"),
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ],
        env={**os.environ, "CLASSSYNC_OCR_FIXTURE_ROOT": str(root)},
        capture_output=True,
        timeout=15,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise RuntimeError("Synthetic raster fixture generation failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or not args.output.parent.is_dir():
        raise ValueError("New evidence output in existing directory required")
    results = []
    with tempfile.TemporaryDirectory(prefix="classsync-synthetic-ocr-") as directory:
        root = Path(directory).resolve()
        if root.parent != Path(tempfile.gettempdir()).resolve():
            raise ValueError("Owned OS-temp fixture directory required")
        fixture_images(root)
        cases = [
            ("digital-pdf", pdf_bytes(), ".pdf"),
            ("png-photo", (root / "synthetic-registration.png").read_bytes(), ".png"),
            ("jpeg-photo", (root / "synthetic-registration.jpg").read_bytes(), ".jpg"),
            (
                "scanned-pdf",
                scanned_pdf(
                    (root / "synthetic-registration.jpg").read_bytes(),
                    *image_dimensions(root / "synthetic-registration.jpg"),
                ),
                ".pdf",
            ),
        ]
        for label, data, extension in cases:
            result = process_document(data, extension, max_pages=5, timeout=20)
            codes = {course["code"]["value"].replace(" ", "") for course in result["courses"]}
            expected = {"TEST101", "TEST102"} if label == "digital-pdf" else {"TESTIOI", "TEST102"}
            if codes != expected:
                raise RuntimeError("Synthetic course extraction mismatch: " + label)
            if set(result["fields"]) != {
                "academic_year",
                "semester",
                "student_identifier",
                "program",
                "year_level",
            }:
                raise RuntimeError("Synthetic field extraction mismatch: " + label)
            if not all(course["section"]["value"] == "2" for course in result["courses"]):
                raise RuntimeError("Numeric section was not preserved: " + label)
            # Keep the ambiguous OCR output unchanged. Exercise the required human
            # correction rather than silently converting I/O to academic digits.
            corrected = RegistrationReview(
                academic_year="2026-2027",
                semester="first",
                student_identifier="SYN-001",
                courses=[{"code": code, "section": "2"} for code in ("TEST101", "TEST102")],
            )
            periods = [
                {"id": "synthetic", "calendar": {"academic_year": "2026-2027", "semester": "first"}}
            ]
            calendars = {
                "synthetic": {
                    "occurrences": [
                        {
                            "offering_id": code,
                            "subject": {"code": code, "code_source": "academic-record"},
                            "section": {
                                "id": "synthetic-section",
                                "name": "Synthetic approved section",
                            },
                        }
                        for code in ("TEST101", "TEST102")
                    ]
                }
            }
            if match_review(corrected, periods=periods, calendars=calendars)["status"] != "matched":
                raise RuntimeError("Explicit synthetic manual correction did not match")
            results.append(
                {
                    "case": label,
                    "method": result["method"],
                    "course_count": 2,
                    "all_academic_fields": True,
                    "numeric_sections_preserved": True,
                    "character_correction_required": label != "digital-pdf",
                    "manual_corrected_match": True,
                }
            )
    args.output.write_text(
        json.dumps(
            {
                "cases": results,
                "synthetic_only": True,
                "temporary_fixtures_removed": True,
                "cloud_calls": 0,
            },
            indent=2,
        )
    )
    print("Synthetic PDF/PNG/JPEG/scanned-PDF qualification passed; private temp fixtures removed")


if __name__ == "__main__":
    main()
