# -*- coding: utf-8 -*-
import json, os
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

root = Path(r"F:\CodexData\.codex\sessions")
profiles = Path(r"F:\CodexProfiles")
today = datetime.now().date()

def first_meta(path: Path):
    try:
        with open(path, "rb") as f:
            line = f.readline()
        o = json.loads(line.decode("utf-8", errors="replace"))
        if o.get("type") != "session_meta":
            return None
        return o.get("payload") or {}
    except Exception:
        return None

# 1) sessions modified today
today_files = []
for f in root.rglob("*.jsonl"):
    try:
        m = datetime.fromtimestamp(f.stat().st_mtime).date()
    except Exception:
        continue
    if m == today:
        today_files.append(f)

print("TODAY_FILE_COUNT", len(today_files))
by_cwd = defaultdict(list)
for f in sorted(today_files, key=lambda p: p.stat().st_mtime, reverse=True):
    meta = first_meta(f)
    cwd = (meta or {}).get("cwd", "")
    sid = (meta or {}).get("id") or (meta or {}).get("session_id") or f.stem
    mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%H:%M:%S")
    by_cwd[cwd].append((mtime, sid, str(f), f.stat().st_size))

print("TODAY_UNIQUE_CWDS", len(by_cwd))
for cwd, items in sorted(by_cwd.items(), key=lambda x: -len(x[1])):
    print(f"\nCWD count={len(items)} repr={cwd!r}")
    print("  utf8=", cwd.encode("utf-8", errors="replace"))
    for mtime, sid, path, sz in items[:5]:
        print(f"  {mtime} size={sz} id={sid} file={path}")

# 2) any file path or meta containing 3.6
print("\n=== any meta cwd containing '3.6' ===")
n36 = 0
for f in root.rglob("*.jsonl"):
    meta = first_meta(f)
    if not meta:
        continue
    cwd = meta.get("cwd") or ""
    if "3.6" in cwd:
        n36 += 1
        print("FOUND", repr(cwd), f)
print("total_with_3.6_in_cwd", n36)

# 3) filename containing 3.6
print("\n=== filename contains 3.6 ===")
for f in root.rglob("*3.6*"):
    print(f)

# 4) check profile local sessions (may have been wiped by project view)
print("\n=== profile session dirs ===")
for p in profiles.iterdir():
    if not p.is_dir() or p.name.startswith("."):
        continue
    sess = p / "sessions"
    marker = p / ".session-view.json"
    n = 0
    if sess.is_dir():
        n = sum(1 for _ in sess.rglob("*.jsonl"))
    link = ""
    try:
        if sess.is_symlink() or (sess.exists() and os.stat(sess).st_nlink):
            pass
    except Exception:
        pass
    # reparse?
    is_junc = False
    try:
        import ctypes
        GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
        FILE_ATTRIBUTE_REPARSE_POINT = 0x400
        attrs = GetFileAttributesW(str(sess))
        is_junc = attrs != -1 and bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)
    except Exception:
        pass
    marker_txt = ""
    if marker.exists():
        marker_txt = marker.read_text(encoding="utf-8", errors="replace").replace("\n", " ")[:120]
    print(f"{p.name}: jsonl_in_sessions={n} reparse={is_junc} marker={marker_txt}")

# 5) session_index lines mentioning 3.6 or 项目
idx = Path(r"F:\CodexData\.codex\session_index.jsonl")
if idx.exists():
    print("\n=== session_index hits ===")
    hits = 0
    for line in idx.read_text(encoding="utf-8", errors="replace").splitlines():
        if "3.6" in line or "项目" in line or "my_project" in line:
            hits += 1
            if hits <= 15:
                print(line[:200])
    print("index_hits", hits)