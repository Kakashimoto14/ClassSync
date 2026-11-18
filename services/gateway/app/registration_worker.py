"""Passive PDF and bounded local OCR child. Output only allowlisted academic fields."""

import json
import logging
import os
import sys
from io import BytesIO
from pathlib import Path

from pypdf import Configuration, PdfReader, apply_configuration

from services.gateway.app.registration_parser import parse_pages

# Keep decompression bounded before text parsing; the parent also limits process
# memory and elapsed time. Never execute embedded actions or use a browser viewer.
logging.disable(logging.CRITICAL)


@apply_configuration(
    Configuration(
        maximum_declared_stream_length=5_000_000,
        array_based_stream_maximum_output_length=2_000_000,
        zlib_maximum_output_length=2_000_000,
        lzw_maximum_output_length=2_000_000,
        run_length_maximum_output_length=2_000_000,
        brotli_maximum_output_length=2_000_000,
        stream_decoding_work_maximum_length=10_000_000,
        page_tree_maximum_entries=1000,
        page_tree_maximum_page_entries=1000,
        xform_maximum_invocations_per_extraction=100,
        jbig2dec_binary=None,
    )
)
def pdf_text(data, max_pages):
    if not data.startswith(b"%PDF-") or not data.rstrip().endswith(b"%%EOF"):
        raise ValueError("invalid_pdf")
    reader = PdfReader(BytesIO(data), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= max_pages:
        raise ValueError("encrypted_or_page_limit")
    # Reject active/document-embedded payloads throughout the parsed object tree,
    # including annotations, not just the root catalog.
    visited = set()

    def inspect(value, depth=0):
        if depth > 40 or len(visited) > 6000:
            raise ValueError("pdf_complexity_limit")
        identity = id(value)
        if identity in visited:
            return
        visited.add(identity)
        if hasattr(value, "get_object"):
            resolved = value.get_object()
            if resolved is not value:
                inspect(resolved, depth + 1)
                return
        if isinstance(value, dict):
            if any(
                key in value
                for key in (
                    "/JS",
                    "/JavaScript",
                    "/OpenAction",
                    "/AA",
                    "/EmbeddedFiles",
                    "/XFA",
                    "/EF",
                    "/Launch",
                )
            ):
                raise ValueError("active_pdf_not_allowed")
            if value.get("/S") in {"/Launch", "/JavaScript", "/SubmitForm", "/ImportData"}:
                raise ValueError("active_pdf_not_allowed")
            for item in value.values():
                inspect(item, depth + 1)
        elif isinstance(value, (list, tuple)):
            for item in value:
                inspect(item, depth + 1)

    inspect(reader.trailer)
    pages = []
    for page in reader.pages:
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if not 1 <= width <= 4000 or not 1 <= height <= 4000:
            raise ValueError("page_dimensions_limit")
        value = page.extract_text(extraction_mode="layout") or ""
        if len(value) > 100_000:
            raise ValueError("text_limit")
        pages.append(value)
    return pages


def reconstruct(words):
    if len(words) > 15_000:
        raise ValueError("text_limit")
    rows = []
    for word in sorted(words, key=lambda item: (item["y"], item["x"])):
        if not word.get("text") or len(word["text"]) > 500:
            continue
        row = next(
            (
                item
                for item in reversed(rows[-4:])
                if abs(item[0]["y"] - word["y"]) <= max(5, word["height"] * 0.6)
            ),
            None,
        )
        if row is None:
            rows.append([word])
        else:
            row.append(word)
    lines = []
    for row in rows:
        row.sort(key=lambda item: item["x"])
        parts, end = [], None
        for word in row:
            gap = word["x"] - end if end is not None else 0
            parts.append(("  " if gap > word["height"] * 1.6 else " ") + word["text"])
            end = word["x"] + word["width"]
        lines.append("".join(parts).strip())
    return "\n".join(lines)


def local_ocr(path, max_pages):
    from services.gateway.app.registration_ocr import linux_ocr, windows_ocr

    pages = windows_ocr(path, max_pages) if os.name == "nt" else linux_ocr(path, max_pages)
    if not 1 <= len(pages) <= max_pages:
        raise ValueError("page_limit")
    return [reconstruct(words) for words in pages]


def extract(path, max_pages):
    data = path.read_bytes()
    if path.suffix == ".pdf":
        pages = pdf_text(data, max_pages)
        result = parse_pages(pages, "digital-pdf")
        if result["courses"]:
            return result
    elif path.suffix == ".png":
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or not data.endswith(b"IEND\xaeB`\x82"):
            raise ValueError("invalid_image")
    elif path.suffix == ".jpg":
        if not data.startswith(b"\xff\xd8\xff") or not data.endswith(b"\xff\xd9"):
            raise ValueError("invalid_image")
    else:
        raise ValueError("unsupported_file")
    return parse_pages(local_ocr(path, max_pages), "local-ocr")


if __name__ == "__main__":
    try:
        if os.name != "nt":
            import resource

            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
            resource.setrlimit(resource.RLIMIT_FSIZE, (16_000_000, 16_000_000))
            resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        if sys.stdin.buffer.read(1) != b"G":
            raise ValueError("private_processing_unavailable")
        value = extract(Path(sys.argv[1]), int(sys.argv[2]))
        sys.stdout.write(json.dumps({"data": value}, ensure_ascii=True))
    except Exception:
        # Neither Python exception reprs nor OCR/parser stderr can contain a
        # student's original filename, name, document text, or financial values.
        sys.stdout.write(json.dumps({"error": "document_processing_failed"}))
        sys.exit(2)
