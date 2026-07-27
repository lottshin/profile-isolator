# -*- coding: utf-8 -*-
from pathlib import Path
import os, shutil, ctypes

shared = Path(r"F:\CodexData\.codex\sessions")
profiles = Path(r"F:\CodexProfiles")
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
promoted = 0
for prof in profiles.iterdir():
    if not prof.is_dir() or prof.name.startswith("."):
        continue
    local = prof / "sessions"
    if not local.is_dir():
        continue
    attrs = ctypes.windll.kernel32.GetFileAttributesW(str(local))
    if attrs != -1 and (attrs & FILE_ATTRIBUTE_REPARSE_POINT):
        print("skip-junction", prof.name)
        continue
    for f in local.rglob("*.jsonl"):
        rel = f.relative_to(local)
        dest = shared / rel
        if dest.exists() and dest.stat().st_size >= f.stat().st_size:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            try:
                dest.unlink()
            except Exception as e:
                print("unlink-fail", dest, e)
                continue
        try:
            os.link(f, dest)
            mode = "hardlink"
        except OSError:
            shutil.copy2(f, dest)
            mode = "copy"
        promoted += 1
        print(mode, prof.name, str(rel), f.stat().st_size)
    # clear session-view marker to force rebuild
    marker = prof / ".session-view.json"
    if marker.exists():
        try:
            marker.unlink()
            print("cleared-marker", prof.name)
        except Exception as e:
            print("marker-fail", prof.name, e)
print("PROMOTED", promoted)
n = 0
for f in shared.rglob("*.jsonl"):
    try:
        head = f.read_bytes()[:500]
        if b"my_project 3.6" in head:
            n += 1
            print("SHARED_OK", f)
    except Exception:
        pass
print("shared_with_3.6_in_head", n)