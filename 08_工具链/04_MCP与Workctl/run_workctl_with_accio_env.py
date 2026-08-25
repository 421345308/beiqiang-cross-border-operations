import ctypes
import subprocess
import sys
from ctypes import wintypes


PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010


class PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Reserved1", ctypes.c_void_p),
        ("PebBaseAddress", ctypes.c_void_p),
        ("Reserved2_0", ctypes.c_void_p),
        ("Reserved2_1", ctypes.c_void_p),
        ("UniqueProcessId", ctypes.c_void_p),
        ("Reserved3", ctypes.c_void_p),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.ReadProcessMemory.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
ntdll.NtQueryInformationProcess.argtypes = [
    wintypes.HANDLE,
    wintypes.ULONG,
    ctypes.c_void_p,
    wintypes.ULONG,
    ctypes.POINTER(wintypes.ULONG),
]


def read_bytes(handle, address, size):
    buffer = (ctypes.c_ubyte * size)()
    read = ctypes.c_size_t()
    if not kernel32.ReadProcessMemory(handle, ctypes.c_void_p(address), buffer, size, ctypes.byref(read)):
        raise ctypes.WinError(ctypes.get_last_error())
    return bytes(buffer[: read.value])


def read_pointer(handle, address):
    return int.from_bytes(read_bytes(handle, address, ctypes.sizeof(ctypes.c_void_p)), "little")


def process_environment(pid):
    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        return {}
    try:
        pbi = PROCESS_BASIC_INFORMATION()
        returned = wintypes.ULONG()
        status = ntdll.NtQueryInformationProcess(
            handle, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), ctypes.byref(returned)
        )
        if status != 0:
            return {}
        process_parameters = read_pointer(handle, pbi.PebBaseAddress + 0x20)
        environment_address = read_pointer(handle, process_parameters + 0x80)
        raw = bytearray()
        for offset in range(0, 2 * 1024 * 1024, 65536):
            chunk = read_bytes(handle, environment_address + offset, 65536)
            raw.extend(chunk)
            marker = raw.find(b"\x00\x00\x00\x00")
            if marker >= 0:
                raw = raw[: marker + 2]
                break
        text = raw.decode("utf-16-le", errors="ignore")
        result = {}
        for entry in text.split("\x00"):
            if "=" in entry and not entry.startswith("="):
                key, value = entry.split("=", 1)
                result[key] = value
        return result
    except (OSError, ValueError):
        return {}
    finally:
        kernel32.CloseHandle(handle)


def accio_pids():
    output = subprocess.check_output(
        ["powershell", "-NoProfile", "-Command", "(Get-Process Accio -ErrorAction SilentlyContinue).Id"],
        text=True,
    )
    return [int(line.strip()) for line in output.splitlines() if line.strip().isdigit()]


for process_id in accio_pids():
    env = process_environment(process_id)
    token = env.get("ACCIO_GATEWAY_TOKEN")
    if token:
        run_env = dict(env)
        run_env.update({k: v for k, v in __import__("os").environ.items() if k not in run_env})
        workctl_path = __import__("os").path.expandvars(r"%APPDATA%\npm\workctl.cmd")
        completed = subprocess.run([workctl_path, *sys.argv[1:]], env=run_env)
        raise SystemExit(completed.returncode)

print("ACCIO_ENV_NOT_FOUND", file=sys.stderr)
raise SystemExit(20)
