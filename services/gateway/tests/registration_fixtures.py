"""Entirely invented registration data; no source document or personal records."""

TEXT = """SYNTHETIC REGISTRATION FORM
Academic Year/Term: 2026-2027 / Semester: 1
Student ID: SYN-001  Program: SYNTHETIC
Year Level: 2
Code       Description                 Section  Lec Lab CLab Units
TEST101    Invented seminar             2        3   0   0    3
TEST102    Invented laboratory          2        1   0   2    3
Total Units: 6
Tuition: DO NOT EXTRACT
Name: DO NOT EXTRACT
Signature: DO NOT EXTRACT
"""


def pdf_bytes(text=TEXT, *, pages=1, active=False):
    # Minimal valid Courier PDF; stable layout and no image/font/network deps.
    content = [b"BT /F1 10 Tf 40 780 Td"]
    for index, line in enumerate(text.splitlines()):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index:
            content.append(b"0 -16 Td")
        content.append(("(" + escaped + ") Tj").encode("ascii"))
    content.append(b"ET")
    stream = b"\n".join(content)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R "
        + (b"/OpenAction << /S /JavaScript /JS (not executed) >> " if active else b"")
        + b">>",
        (
            f"<< /Type /Pages /Count {pages} /Kids ["
            + " ".join(f"{5 + i} 0 R" for i in range(pages))
            + "] >>"
        ).encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
    ]
    for _ in range(pages):
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents 4 0 R >>"
        )
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
