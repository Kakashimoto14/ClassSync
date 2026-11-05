"""Portable boundary tests; native Linux OCR evidence is produced by the image probe."""

import struct
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from services.gateway.app import registration_ocr as ocr
from services.gateway.app import registration_processing as processing
from services.gateway.app.registration_worker import reconstruct


def png(width=1600, height=900):
    return b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR" + struct.pack(">II", width, height)


@pytest.mark.parametrize(
    "data",
    [
        png(6000, 900),
        png(5000, 5000),
        png(0, 20),
        b"\xff\xd8\xff\xc0\x00\x20truncated",
        b"not-an-image",
    ],
)
def test_untrusted_raster_dimensions_fail_before_native_decode(tmp_path, data):
    file = tmp_path / "synthetic.png"
    file.write_bytes(data)
    with pytest.raises(ValueError):
        ocr.image_dimensions(file)


def test_native_tsv_uses_fixed_arguments_limits_and_private_cleanup(tmp_path, monkeypatch):
    file = tmp_path / "invented.png"
    file.write_bytes(png())
    monkeypatch.setattr(ocr.shutil, "which", lambda name: "/usr/bin/" + name)
    calls = []

    def native(arguments, **options):
        calls.append((arguments, options))
        Path(arguments[2]).with_suffix(".tsv").write_text(
            "level\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t10\t10\t70\t20\t95\tTEST101\n"
            "5\t400\t10\t20\t20\t90\t2\n",
            encoding="utf8",
        )

    monkeypatch.setattr(ocr.subprocess, "run", native)
    pages = ocr.linux_ocr(file, 5)
    assert "TEST101" in reconstruct(pages[0]) and "2" in reconstruct(pages[0])
    args, options = calls[0]
    assert args[0] == "/usr/bin/tesseract" and args[-5:] == ["-l", "eng", "--psm", "6", "tsv"]
    assert options["timeout"] == 8 and options["env"]["OMP_THREAD_LIMIT"] == "1"
    assert options["stderr"] == subprocess.DEVNULL and options["stdout"] == subprocess.DEVNULL
    assert options.get("shell", False) is False
    assert list(tmp_path.iterdir()) == [file]


def test_native_failure_cleans_nested_private_outputs(tmp_path, monkeypatch):
    file = tmp_path / "invented.png"
    file.write_bytes(png())
    monkeypatch.setattr(ocr.shutil, "which", lambda name: "/usr/bin/" + name)

    def failed(*args, **kwargs):
        raise subprocess.TimeoutExpired("synthetic-ocr", 8)

    monkeypatch.setattr(ocr.subprocess, "run", failed)
    with pytest.raises(subprocess.TimeoutExpired):
        ocr.linux_ocr(file, 5)
    assert list(tmp_path.iterdir()) == [file]


def test_missing_native_adapter_never_calls_a_cloud_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr.shutil, "which", lambda _: None)
    with pytest.raises(ValueError, match="ocr_unavailable"):
        ocr.linux_ocr(tmp_path / "invented.png", 5)


def test_exited_worker_still_terminates_owned_native_process_group(monkeypatch):
    monkeypatch.setattr(processing.signal, "SIGKILL", 9, raising=False)
    worker = Mock(pid=12345)
    worker.poll.return_value = 2
    kill = Mock()
    monkeypatch.setattr(processing.os, "killpg", kill, raising=False)
    processing.stop_worker(worker, windows=False)
    kill.assert_called_once_with(12345, processing.signal.SIGKILL)
    worker.communicate.assert_not_called()


def test_finished_process_group_is_already_absent(monkeypatch):
    monkeypatch.setattr(processing.signal, "SIGKILL", 9, raising=False)
    worker = Mock(pid=12345)
    worker.poll.return_value = 0
    monkeypatch.setattr(
        processing.os, "killpg", Mock(side_effect=ProcessLookupError), raising=False
    )
    processing.stop_worker(worker, windows=False)
