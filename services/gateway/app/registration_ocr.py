"""Local OCR adapters inside the bounded private worker; never a cloud upload."""

import asyncio
import csv
import os
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path


def image_dimensions(path):
    """Reject oversized raster headers before invoking native decoders."""
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24 and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
    elif data.startswith(b"\xff\xd8\xff"):
        offset, width, height = 2, 0, 0
        while offset + 4 <= len(data):
            if data[offset] != 255:
                raise ValueError("invalid_image")
            while offset < len(data) and data[offset] == 255:
                offset += 1
            if offset >= len(data):
                break
            marker = data[offset]
            offset += 1
            if marker in (0x01, 0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                continue
            if marker == 0xDA:
                break
            length = int.from_bytes(data[offset : offset + 2], "big")
            if length < 2 or offset + length > len(data):
                raise ValueError("invalid_image")
            if marker in {
                0xC0,
                0xC1,
                0xC2,
                0xC3,
                0xC5,
                0xC6,
                0xC7,
                0xC9,
                0xCA,
                0xCB,
                0xCD,
                0xCE,
                0xCF,
            }:
                if length < 8:
                    raise ValueError("invalid_image")
                height, width = struct.unpack(">HH", data[offset + 3 : offset + 7])
                break
            offset += length
    else:
        raise ValueError("invalid_image")
    if not (0 < width <= 5000 and 0 < height <= 5000 and width * height <= 16_000_000):
        raise ValueError("image_limit")
    return width, height


def linux_ocr(path, max_pages):
    """Poppler rasterization and Tesseract TSV, bounded by the worker's process group."""
    tesseract, renderer = shutil.which("tesseract"), shutil.which("pdftoppm")
    if not tesseract or (path.suffix == ".pdf" and not renderer):
        raise ValueError("ocr_unavailable")
    if not 1 <= max_pages <= 8:
        raise ValueError("page_limit")
    if path.suffix == ".pdf":
        from pypdf import PdfReader

        count = len(PdfReader(path, strict=True).pages)
        if not 1 <= count <= max_pages:
            raise ValueError("page_limit")
    else:
        image_dimensions(path)
        count = 1
    pages = []
    env = {**os.environ, "OMP_THREAD_LIMIT": "1", "OMP_NUM_THREADS": "1"}

    def run(arguments, timeout):
        subprocess.run(
            arguments,
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            env=env,
            cwd=path.parent,
        )

    # Nested files are in the same private input directory and removed on every exit.
    with tempfile.TemporaryDirectory(prefix="ocr-", dir=path.parent) as folder:
        root = Path(folder)
        for index in range(count):
            raster = path
            if path.suffix == ".pdf":
                prefix = root / f"page-{index}"
                run(
                    [
                        renderer,
                        "-f",
                        str(index + 1),
                        "-l",
                        str(index + 1),
                        "-singlefile",
                        "-scale-to",
                        "2000",
                        "-png",
                        str(path),
                        str(prefix),
                    ],
                    5,
                )
                raster = prefix.with_suffix(".png")
                image_dimensions(raster)
            output = root / f"words-{index}"
            run([tesseract, str(raster), str(output), "-l", "eng", "--psm", "6", "tsv"], 8)
            result = output.with_suffix(".tsv")
            if result.stat().st_size > 2_000_000:
                raise ValueError("text_limit")
            words = []
            with result.open(encoding="utf-8", newline="") as source:
                for row in csv.DictReader(source, delimiter="\t"):
                    text = row.get("text", "").strip()
                    if not text:
                        continue
                    if len(words) >= 15000 or len(text) > 500:
                        raise ValueError("text_limit")
                    words.append(
                        {
                            "text": text,
                            "x": int(row["left"]),
                            "y": int(row["top"]),
                            "width": int(row["width"]),
                            "height": int(row["height"]),
                        }
                    )
            pages.append(words)
    return pages


async def windows_pages(path, max_pages):
    from winrt.windows.data.pdf import PdfDocument, PdfPageRenderOptions
    from winrt.windows.graphics.imaging import BitmapDecoder, BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage import FileAccessMode, StorageFile
    from winrt.windows.storage.streams import InMemoryRandomAccessStream

    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        raise ValueError("ocr_unavailable")

    async def read(stream):
        decoder = await BitmapDecoder.create_async(stream)
        if (
            decoder.pixel_width > 5000
            or decoder.pixel_height > 5000
            or decoder.pixel_width * decoder.pixel_height > 16_000_000
        ):
            raise ValueError("image_limit")
        bitmap = await decoder.get_software_bitmap_async()
        try:
            converted = SoftwareBitmap.convert(bitmap, BitmapPixelFormat.GRAY8)
            try:
                result = await engine.recognize_async(converted)
                return [
                    {
                        "text": word.text,
                        "x": word.bounding_rect.x,
                        "y": word.bounding_rect.y,
                        "width": word.bounding_rect.width,
                        "height": word.bounding_rect.height,
                    }
                    for line in result.lines
                    for word in line.words
                ]
            finally:
                converted.close()
        finally:
            bitmap.close()

    file = await StorageFile.get_file_from_path_async(str(path.resolve()))
    stream = await file.open_async(FileAccessMode.READ)
    try:
        if path.suffix != ".pdf":
            return [await read(stream)]
        pdf = await PdfDocument.load_from_stream_async(stream)
        if not 1 <= pdf.page_count <= max_pages:
            raise ValueError("page_limit")
        pages = []
        for index in range(pdf.page_count):
            page = pdf.get_page(index)
            rendered = InMemoryRandomAccessStream()
            try:
                options = PdfPageRenderOptions()
                options.destination_width = 2000
                options.destination_height = min(
                    3000, round(2000 * page.size.height / page.size.width)
                )
                await page.render_to_stream_async(rendered, options)
                rendered.seek(0)
                pages.append(await read(rendered))
            finally:
                rendered.close()
                page.close()
        return pages
    finally:
        stream.close()


def windows_ocr(path, max_pages):
    return asyncio.run(windows_pages(path, max_pages))
