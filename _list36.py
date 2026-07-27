from pathlib import Path
import json, shutil
profiles = Path(r"F:\CodexProfiles")
shared = Path(r"F:\CodexData\.codex\sessions")
for f in profiles.rglob("sessions/**/*.jsonl"):
    try:
        line = f.read_bytes().split(b"\n",1)[0].decode("utf-8","replace")
        o = json.loads(line)
        cwd = (o.get("payload") or {}).get("cwd") or ""
    except Exception:
        continue
    if "my_project 3.6" not in cwd:
        continue
    rel = None
    # rel path under sessions/
    parts = f.parts
    if "sessions" in parts:
        i = parts.index("sessions")
        rel = Path(*parts[i+1:])
    print("LOCAL", f)
    print("  cwd", cwd)
    print("  rel", rel)
    if rel:
        dest = shared / rel
        print("  dest_exists", dest.exists(), dest)