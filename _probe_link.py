import os, io, subprocess, ctypes
from ctypes import wintypes

ROOT = r"F:\CodexProfiles"
TARGET = os.path.join(ROOT, "随时跑路", "state_5.sqlite")
out = []

# --- file index (identifies same physical file) via GetFileInformationByHandle ---
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GENERIC_READ = 0x80000000
FILE_SHARE_READ = 1
FILE_SHARE_WRITE = 2
FILE_SHARE_DELETE = 4
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000

class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]

def file_id(path):
    # open with full share so we don't disturb anything using it
    h = kernel32.CreateFileW(
        path, 0,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, None)
    if h == wintypes.HANDLE(-1).value or h == -1:
        return None
    try:
        info = BY_HANDLE_FILE_INFORMATION()
        if not kernel32.GetFileInformationByHandle(h, ctypes.byref(info)):
            return None
        return (info.dwVolumeSerialNumber, info.nFileIndexHigh, info.nFileIndexLow, info.nNumberOfLinks)
    finally:
        kernel32.CloseHandle(h)

tgt = file_id(TARGET)
out.append(f"TARGET 随时跑路 state_5.sqlite id={tgt}")
if tgt:
    out.append(f"  link_count(nNumberOfLinks)={tgt[3]}")

# compare every profile's state_5.sqlite
out.append("\n=== per-profile state_5.sqlite ===")
for prof in os.listdir(ROOT):
    p = os.path.join(ROOT, prof, "state_5.sqlite")
    if not os.path.isfile(p):
        continue
    fid = file_id(p)
    same = "SAME-AS-TARGET" if (fid and tgt and fid[:3] == tgt[:3]) else "independent"
    out.append(f"  {prof:20s} id={fid[:3] if fid else None} {same}")

# also shared library one
sp = r"F:\CodexData\.codex\state_5.sqlite"
if os.path.isfile(sp):
    fid = file_id(sp)
    same = "SAME-AS-TARGET" if (fid and tgt and fid[:3] == tgt[:3]) else "independent"
    out.append(f"  {'[shared] .codex':20s} id={fid[:3] if fid else None} {same}")

with io.open(r"D:\New_god\tool\codex-profile\_probe_out.txt","w",encoding="utf-8") as f:
    f.write("\n".join(out))
print("done")
