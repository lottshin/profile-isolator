# -*- coding: utf-8 -*-
import json
from pathlib import Path

files = list(Path(r"F:\CodexProfiles").rglob("rollout-2026-07-26*.jsonl"))
# also any today files with my_project 3.6 already found
extra = [
    Path(r"F:\CodexProfiles"),
]
print("today rollouts under profiles:", len(files))
for f in sorted(files, key=lambda p: p.stat().st_mtime):
    try:
        line = f.read_bytes().split(b"\n", 1)[0].decode("utf-8", errors="replace")
        o = json.loads(line)
        payload = (o.get("payload") or {}) if o.get("type")=="session_meta" else {}
        cwd = payload.get("cwd")
        print("---")
        print("file", f)
        print("size", f.stat().st_size, "mtime", f.stat().st_mtime)
        print("type", o.get("type"), "cwd_repr", repr(cwd))
        if cwd:
            print("cwd_utf8", cwd.encode("utf-8"))
    except Exception as e:
        print("ERR", f, e)

# specifically read the three known files
known = [
    r"F:\CodexProfiles\temp\sessions\2026\07\26\rollout-2026-07-26T11-12-25-019f9c68-dc0f-70e0-9412-ecbf58f84254.jsonl",
]
# discover 简直了 path via glob
for f in Path(r"F:\CodexProfiles").iterdir():
    if f.is_dir():
        for hit in f.glob("sessions/2026/07/26/rollout-2026-07-26*.jsonl"):
            if hit not in files:
                files.append(hit)

print("\nALL profile-local 2026-07-26 rollouts:")
for f in sorted(Path(r"F:\CodexProfiles").rglob("sessions/2026/07/26/*.jsonl"), key=lambda p: p.stat().st_mtime):
    line = f.read_bytes().split(b"\n", 1)[0].decode("utf-8", errors="replace")
    try:
        o = json.loads(line)
        cwd = (o.get("payload") or {}).get("cwd") if o.get("type")=="session_meta" else None
    except Exception:
        cwd = None
    # is it in shared?
    shared = Path(r"F:\CodexData\.codex") / f.relative_to(f.parents[4] if False else f)
    # simpler: check same filename under shared
    name = f.name
    shared_hits = list(Path(r"F:\CodexData\.codex\sessions").rglob(name))
    print(f"profile_local={f} cwd={cwd!r} in_shared={bool(shared_hits)} size={f.stat().st_size}")