"""Windows: run the verified setup program inside a job it can never leave.

Used by the update helper (`desktop/update_apply.py`) for a per-user install
in `%LOCALAPPDATA%\\Programs\\Refinix`. Before anything is set aside the helper
creates a job object that only it holds (not inheritable), configured to kill
every process in it when that handle closes, with no breakaway allowed. The
installer is then created *inside* the job from its first instruction
(`PROC_THREAD_ATTRIBUTE_JOB_LIST`), so neither it nor any child it starts can
outlive the helper: if the helper exits or crashes, Windows ends the whole
installer tree. If the job cannot be made, nothing is installed.

Also here: the uninstall-registration snapshot and its exact restore, and the
"completely installed" check against the file list written at build time
(`_internal/refinix-files.json`).

Standard library only (ctypes and winreg); importable anywhere, usable only on
Windows.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path

APP_ID = "{6F4C2E7A-6E3B-4C55-9C8E-2B6B9E9B5A31}"
UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}_is1"
# Inno Setup writes these into {app}; nothing else may be there besides the
# listed application files.
INNO_EXTRAS = frozenset({"unins000.exe", "unins000.dat", "unins000.msg"})
INSTALLER_SECONDS = 900
SETUP_ARGUMENTS = ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER",
                   "/NOCLOSEAPPLICATIONS", "/NORESTARTAPPLICATIONS")

# Documented Win32 values.
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00000800
JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK = 0x00001000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1
PROC_THREAD_ATTRIBUTE_JOB_LIST = 0x0002000D
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_NO_WINDOW = 0x08000000
WAIT_OBJECT_0, WAIT_TIMEOUT = 0x0, 0x102
STILL_ACTIVE = 259


class WindowsInstallError(RuntimeError):
    pass


def _api():
    from ctypes import wintypes

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class BASIC_LIMIT(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class EXTENDED_LIMIT(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BASIC_LIMIT), ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    class ACCOUNTING(ctypes.Structure):
        _fields_ = [("TotalUserTime", ctypes.c_int64), ("TotalKernelTime", ctypes.c_int64),
                    ("ThisPeriodTotalUserTime", ctypes.c_int64),
                    ("ThisPeriodTotalKernelTime", ctypes.c_int64),
                    ("TotalPageFaultCount", wintypes.DWORD),
                    ("TotalProcesses", wintypes.DWORD),
                    ("ActiveProcesses", wintypes.DWORD),
                    ("TotalTerminatedProcesses", wintypes.DWORD)]

    class STARTUPINFOW(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
                    ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
                    ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
                    ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
                    ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
                    ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
                    ("lpReserved2", ctypes.c_void_p), ("hStdInput", wintypes.HANDLE),
                    ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE)]

    class STARTUPINFOEXW(ctypes.Structure):
        _fields_ = [("StartupInfo", STARTUPINFOW), ("lpAttributeList", ctypes.c_void_p)]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
                    ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateJobObjectW.restype = wintypes.HANDLE
    k.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    k.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                          wintypes.DWORD]
    k.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                            wintypes.DWORD, ctypes.c_void_p]
    k.InitializeProcThreadAttributeList.argtypes = [ctypes.c_void_p, wintypes.DWORD,
                                                    wintypes.DWORD,
                                                    ctypes.POINTER(ctypes.c_size_t)]
    k.UpdateProcThreadAttribute.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t,
                                            ctypes.c_void_p, ctypes.c_size_t,
                                            ctypes.c_void_p, ctypes.c_void_p]
    k.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    k.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p,
                                 ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD,
                                 ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_void_p,
                                 ctypes.c_void_p]
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.WaitForSingleObject.restype = wintypes.DWORD
    k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    return {"k": k, "wintypes": wintypes, "EXTENDED_LIMIT": EXTENDED_LIMIT,
            "ACCOUNTING": ACCOUNTING, "STARTUPINFOEXW": STARTUPINFOEXW,
            "PROCESS_INFORMATION": PROCESS_INFORMATION}


def _fail(what: str) -> WindowsInstallError:
    return WindowsInstallError(f"{what} failed (Windows error {ctypes.get_last_error()})")


class Job:
    """A kill-on-close job held by this process only; no breakaway."""

    def __init__(self, api=None):
        self.api = api or _api()
        k = self.api["k"]
        handle = k.CreateJobObjectW(None, None)       # no security attributes: not inherited
        if not handle:
            raise _fail("CreateJobObjectW")
        self.handle = handle
        info = self.api["EXTENDED_LIMIT"]()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k.SetInformationJobObject(handle, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                                         ctypes.byref(info), ctypes.sizeof(info)):
            error = _fail("SetInformationJobObject")
            self.close()
            raise error

    def limits(self) -> int:
        info = self.api["EXTENDED_LIMIT"]()
        if not self.api["k"].QueryInformationJobObject(
                self.handle, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(info),
                ctypes.sizeof(info), None):
            raise _fail("QueryInformationJobObject")
        return int(info.BasicLimitInformation.LimitFlags)

    def active(self) -> int:
        info = self.api["ACCOUNTING"]()
        if not self.api["k"].QueryInformationJobObject(
                self.handle, JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION, ctypes.byref(info),
                ctypes.sizeof(info), None):
            raise _fail("QueryInformationJobObject")
        return int(info.ActiveProcesses)

    def terminate(self) -> None:
        self.api["k"].TerminateJobObject(self.handle, 1)

    def close(self) -> None:
        if getattr(self, "handle", None):
            self.api["k"].CloseHandle(self.handle)
            self.handle = None


def start_in_job(job: Job, program: Path, arguments: list[str], cwd: Path) -> dict:
    """Create `program` as a member of `job` from its first instruction."""
    api, wintypes = job.api, job.api["wintypes"]
    k = api["k"]
    size = ctypes.c_size_t(0)
    k.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
    buffer = (ctypes.c_byte * size.value)()
    if not k.InitializeProcThreadAttributeList(buffer, 1, 0, ctypes.byref(size)):
        raise _fail("InitializeProcThreadAttributeList")
    try:
        jobs = (wintypes.HANDLE * 1)(job.handle)
        if not k.UpdateProcThreadAttribute(buffer, 0, PROC_THREAD_ATTRIBUTE_JOB_LIST,
                                           jobs, ctypes.sizeof(jobs), None, None):
            raise _fail("UpdateProcThreadAttribute(JOB_LIST)")
        startup = api["STARTUPINFOEXW"]()
        startup.StartupInfo.cb = ctypes.sizeof(startup)
        startup.lpAttributeList = ctypes.cast(buffer, ctypes.c_void_p)
        info = api["PROCESS_INFORMATION"]()
        command = subprocess.list2cmdline([str(program), *arguments])
        line = ctypes.create_unicode_buffer(command)
        if not k.CreateProcessW(str(program), line, None, None, False,
                                EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT
                                | CREATE_NO_WINDOW, None, str(cwd),
                                ctypes.byref(startup), ctypes.byref(info)):
            raise _fail("CreateProcessW")
    finally:
        k.DeleteProcThreadAttributeList(buffer)
    k.CloseHandle(info.hThread)
    return {"handle": info.hProcess, "pid": int(info.dwProcessId)}


def wait_for(job: Job, process: dict, seconds: float) -> int | None:
    """The installer's exit code once it and every process it started are gone;
    None when the time ran out (the caller then ends the job)."""
    k = job.api["k"]
    deadline = time.monotonic() + seconds
    while True:
        left = max(0, int((deadline - time.monotonic()) * 1000))
        result = k.WaitForSingleObject(process["handle"], min(left, 1000))
        if result == WAIT_OBJECT_0:
            break
        if result != WAIT_TIMEOUT or left == 0:
            return None
    code = job.api["wintypes"].DWORD(0)
    if not k.GetExitCodeProcess(process["handle"], ctypes.byref(code)):
        raise _fail("GetExitCodeProcess")
    k.CloseHandle(process["handle"])
    while job.active():
        if time.monotonic() > deadline:
            return None
        time.sleep(0.25)
    return int(code.value)


# --------------------------------------------------------------------------
# The uninstall registration
# --------------------------------------------------------------------------

def registry_snapshot(winreg=None) -> dict | None:
    """Every value of Refinix's per-user uninstall entry, or None when absent."""
    if winreg is None:
        import winreg  # noqa: PLC0415
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        return None
    values = []
    with key:
        index = 0
        while True:
            try:
                name, data, kind = winreg.EnumValue(key, index)
            except OSError:
                break
            if isinstance(data, bytes):
                data = {"hex": data.hex()}
            values.append([name, data, kind])
            index += 1
    return {"values": values}


def registry_restore(snapshot: dict | None, winreg=None) -> None:
    """Put the uninstall entry back exactly as recorded (or remove it)."""
    if winreg is None:
        import winreg  # noqa: PLC0415
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass
    if snapshot is None:
        return
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    with key:
        for name, data, kind in snapshot["values"]:
            if isinstance(data, dict) and "hex" in data:
                data = bytes.fromhex(data["hex"])
            winreg.SetValueEx(key, name, 0, kind, data)


def registration_problem(snapshot: dict | None, version: str, app: Path) -> str | None:
    """The fresh registration names this version and this folder."""
    if snapshot is None:
        return "the uninstall registration is missing"
    values = {name: data for name, data, _kind in snapshot["values"]}
    if values.get("DisplayVersion") != version:
        return f"the registration names version {values.get('DisplayVersion')!r}"
    location = str(values.get("InstallLocation") or "").rstrip("\\/")
    if os.path.normcase(location) != os.path.normcase(str(app).rstrip("\\/")):
        return f"the registration names folder {location!r}"
    return None


# --------------------------------------------------------------------------
# "Completely installed"
# --------------------------------------------------------------------------

def completeness_problem(app: Path, version: str) -> str | None:
    """Every listed file present and unchanged; only Inno's uninstaller added."""
    from desktop import install_check
    return install_check.completeness_problem(app, version, extras=INNO_EXTRAS)


def run_installer(setup: Path, app: Path, log: Path, *, job: Job,
                  record=None, seconds: float = INSTALLER_SECONDS) -> int | None:
    """Start the setup in `job`, record it, wait for the whole tree."""
    arguments = [*SETUP_ARGUMENTS, f"/DIR={app}", f"/LOG={log}"]
    process = start_in_job(job, setup, arguments, setup.parent)
    if record is not None:
        record({"pid": process["pid"], "job_limits": job.limits()})
    code = wait_for(job, process, seconds)
    if code is None:
        job.terminate()
    return code


def open_program(program: Path, environment: dict) -> None:
    """Open the installed Refinix for the person, detached from the helper."""
    env = dict(os.environ)
    env.update(environment)
    flags = 0x00000008 | 0x00000200            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(program)], cwd=str(program.parent), env=env, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, creationflags=flags if sys.platform ==
                     "win32" else 0)
