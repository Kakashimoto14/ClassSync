"""Bounded private subprocess processing; no cloud provider or retained original."""

import ctypes
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException


class WindowsJob:
    def __init__(self, process):
        from ctypes import wintypes

        class Limits(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_int64),
                ("job_time", ctypes.c_int64),
                ("flags", wintypes.DWORD),
                ("minimum", ctypes.c_size_t),
                ("maximum", ctypes.c_size_t),
                ("processes", wintypes.DWORD),
                ("affinity", ctypes.c_size_t),
                ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD),
            ]

        class IO(ctypes.Structure):
            _fields_ = [
                (key, ctypes.c_uint64)
                for key in ("read", "write", "other", "read_bytes", "write_bytes", "other_bytes")
            ]

        class Extended(ctypes.Structure):
            _fields_ = [
                ("basic", Limits),
                ("io", IO),
                ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t),
                ("peak_process", ctypes.c_size_t),
                ("peak_job", ctypes.c_size_t),
            ]

        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError("private_processing_unavailable")
        limits = Extended()
        # Kill all nested OCR processes on handle close; bound total memory,
        # process count and CPU without changing host/user process settings.
        limits.basic.flags = 0x2000 | 0x0200 | 0x0008 | 0x0004
        limits.basic.processes = 4
        limits.basic.job_time = 15 * 10_000_000
        limits.job_memory = 512 * 1024 * 1024
        if not self.api.SetInformationJobObject(
            self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ) or not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            self.close()
            raise OSError("private_processing_unavailable")

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def stop_worker(process, *, windows):
    if windows:
        if process.poll() is None:
            process.kill()
    else:
        # The group can retain native OCR children after its Python leader exits.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.communicate(timeout=5)


def process_document(data, extension, *, max_pages, timeout):
    job, process = None, None
    # Profile-local temporary directory, restrictive tempfile permissions, random
    # names and immediate cleanup. No user filename, web root or public URL.
    with tempfile.TemporaryDirectory(prefix="classsync-private-registration-") as directory:
        path = Path(directory) / (uuid4().hex + extension)
        path.write_bytes(data)
        try:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "services.gateway.app.registration_worker",
                    str(path),
                    str(max_pages),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=Path(__file__).resolve().parents[3],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                start_new_session=os.name != "nt",
            )
            if os.name == "nt":
                job = WindowsJob(process)
            # The child waits for this byte before reading the untrusted file.
            output, _ = process.communicate(input=b"G", timeout=timeout)
            if process.returncode or len(output) > 150_000:
                raise ValueError("document_processing_failed")
            result = json.loads(output)
            if "data" not in result:
                raise ValueError("document_processing_failed")
            return result["data"]
        except subprocess.TimeoutExpired as error:
            raise HTTPException(
                422,
                "This document exceeded the safe processing limit. "
                "Try a smaller, clearer document or enter your courses manually.",
            ) from error
        except (ValueError, OSError, KeyError) as error:
            raise HTTPException(
                422,
                "This file could not be safely read. Use a valid PDF, JPEG or PNG "
                "with fewer pages, or enter your courses manually.",
            ) from error
        finally:
            if job:
                job.close()
            if process:
                stop_worker(process, windows=os.name == "nt")
