import os, json, io

SHARED = r"F:\CodexData\.codex\sessions"
ROOT = r"F:\CodexProfiles"

out = []

def scan_sessions(base):
    total = 0
    ok_meta = 0
    bad_parse = 0
    empty = 0
    truncated = 0
    total_bytes = 0
    bad_files = []
    for dp, dn, fn in os.walk(base):
        for f in fn:
            if not f.endswith(".jsonl"):
                continue
            full = os.path.join(dp, f)
            total += 1
            try:
                sz = os.path.getsize(full)
                total_bytes += sz
                if sz == 0:
                    empty += 1
                    bad_files.append(("empty", full))
                    continue
                with io.open(full, "r", encoding="utf-8", errors="replace") as fh:
                    first = fh.readline()
                    # read last non-empty line to check truncation
                    fh.seek(0)
                    last = ""
                    for line in fh:
                        s = line.strip()
                        if s:
                            last = s
                # first line should be session_meta
                try:
                    v = json.loads(first)
                    if v.get("type") == "session_meta":
                        ok_meta += 1
                except Exception:
                    bad_parse += 1
                    bad_files.append(("bad_first_json", full))
                # check last line parses (truncation detector)
                if last:
                    try:
                        json.loads(last)
                    except Exception:
                        truncated += 1
                        bad_files.append(("truncated_last_line", full))
            except Exception as e:
                bad_files.append((f"error:{e}", full))
    return {
        "total": total,
        "ok_meta": ok_meta,
        "bad_parse": bad_parse,
        "empty": empty,
        "truncated": truncated,
        "total_bytes": total_bytes,
        "bad_files": bad_files,
    }

r = scan_sessions(SHARED)
out.append("=== SHARED library: F:\\CodexData\\.codex\\sessions ===")
out.append(f"  jsonl_files      = {r['total']}")
out.append(f"  first=session_meta = {r['ok_meta']}")
out.append(f"  bad_first_json   = {r['bad_parse']}")
out.append(f"  empty_files      = {r['empty']}")
out.append(f"  truncated_last   = {r['truncated']}")
out.append(f"  total_size_MB    = {r['total_bytes']/1048576:.1f}")
if r["bad_files"]:
    out.append("  --- suspicious files ---")
    for kind, full in r["bad_files"][:40]:
        out.append(f"    [{kind}] {full}")
else:
    out.append("  ALL jsonl parse OK (no empty / bad / truncated)")

with io.open(r"D:\New_god\tool\codex-profile\_verify_out.txt", "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))

print("done total=%d ok_meta=%d bad=%d empty=%d trunc=%d" % (
    r["total"], r["ok_meta"], r["bad_parse"], r["empty"], r["truncated"]))
