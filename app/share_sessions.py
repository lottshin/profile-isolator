"""CLI: share sessions across provider profiles for Codex and/or Claude Code."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from core import (  # noqa: E402
    enable_shared_sessions,
    enable_shared_sessions_all,
    get_engine,
    session_share_status,
)
from engines import ENGINES  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(
        description="Share CLI sessions across provider profiles (config/auth stay isolated)."
    )
    p.add_argument("profile", nargs="?", help="Profile name (omit with --all)")
    p.add_argument(
        "--engine",
        choices=sorted(ENGINES.keys()),
        default="codex",
        help="Which CLI engine (default: codex)",
    )
    p.add_argument("--all", action="store_true", help="Share all profiles for this engine")
    p.add_argument("--status", action="store_true", help="Show share status only")
    args = p.parse_args()

    engine = get_engine(args.engine)

    if args.status or (not args.all and not args.profile):
        print(session_share_status(engine, args.profile))
        if not args.status and not args.all and not args.profile:
            print("\nUsage:")
            print("  python share_sessions.py --engine codex --status")
            print("  python share_sessions.py --engine claude --all")
            print("  python share_sessions.py --engine claude <profile>")
        return 0

    print(f"Engine: {engine.label}")
    print(f"Note: close running {engine.label} windows first if DB files are locked.\n")

    if args.all:
        results = enable_shared_sessions_all(engine)
        for r in results:
            print(r)
    else:
        print(enable_shared_sessions(engine, args.profile))

    print()
    print(session_share_status(engine))
    print()
    print("Resume tips:")
    print("  cd <your-project>")
    print(f"  {engine.resume_cmd}")
    print(f"  {engine.resume_all_cmd}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
