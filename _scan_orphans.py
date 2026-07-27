import os, json, io, sys

ROOT = r"F:\CodexProfiles"
SHARED = r"F:\CodexData\.codex\sessions"

def shared_names():
    names = set()
    for dp, dn, fn in os.walk(SHARED):
        for f in fn:
            if f.endswith(".jsonl"):
                names.add(f)
    return names

def head_cwd(path):
    try:
        with io.open(path, "r", encoding="utf-8") as fh:
            line = fh.readline()
        v = json.loads(line)
        if v.get("type") != "session_meta":
            return None
        return v.get("payload", {}).get("cwd")
    except Exception:
        return None

out = []
sn = shared_names()
out.append(f"shared_jsonl_count={len(sn)}")

total_orphan = 0
for prof in os.listdir(ROOT):
    pdir = os.path.join(ROOT, prof)
    sess = os.path.join(pdir, "sessions")
    if not os.path.isdir(sess):
        continue
    # is it a reparse point (junction)? if junction it points to shared -> skip
    try:
        is_link = os.path.islink(sess) or bool(os.readlink(sess))
    except OSError:
        is_link = False
    orphans = []
    for dp, dn, fn in os.walk(sess):
        for f in fn:
            if not f.endswith(".jsonl"):
                continue
            full = os.path.join(dp, f)
            if f not in sn:
                orphans.append((full, head_cwd(full), os.path.getsize(full)))
    if orphans:
        total_orphan += len(orphans)
        out.append(f"\n=== profile {prof!r} junction={is_link} orphans={len(orphans)} ===")
        for full, cwd, sz in orphans:
            out.append(f"  cwd={cwd!r} size={sz} {full}")

out.append(f"\nTOTAL_ORPHANS={total_orphan}")

with io.open(r"D:\New_god\tool\codex-profile\_orphans_out.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("done", total_orphan)
