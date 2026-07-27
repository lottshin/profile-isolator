# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime

needles = [
    b"my_project 3.6",
    "项目\\my_project 3.6".encode("utf-8"),
    "项目/my_project 3.6".encode("utf-8"),
    b"my_project%203.6",
]
roots = [
    Path(r"F:\CodexData\.codex"),
    Path(r"F:\CodexProfiles\muyuan"),
    Path(r"F:\CodexProfiles"),
]
# only search jsonl and sqlite somewhat carefully
exts = {".jsonl", ".json", ".toml"}
hits = []
for root in roots:
    if not root.exists():
        continue
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() not in exts and f.name not in ("history.jsonl", "session_index.jsonl"):
            # still scan jsonl under sessions always
            if f.suffix.lower() != ".jsonl":
                continue
        try:
            data = f.read_bytes()
        except Exception:
            continue
        for n in needles:
            if n in data:
                hits.append((str(f), n.decode("utf-8", errors="replace"), f.stat().st_mtime, f.stat().st_size))
                break

print("HITS", len(hits))
for path, needle, mt, sz in sorted(hits, key=lambda x: -x[2])[:40]:
    print(datetime.fromtimestamp(mt).isoformat(timespec="seconds"), sz, needle, path)

# list ALL files modified today under CodexProfiles/muyuan
print("\n=== muyuan files mtime today ===")
muyuan = Path(r"F:\CodexProfiles\muyuan")
today = datetime.now().date()
for f in muyuan.rglob("*"):
    if not f.is_file():
        continue
    d = datetime.fromtimestamp(f.stat().st_mtime).date()
    if d == today:
        print(datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds"), f.stat().st_size, f)