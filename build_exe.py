# Build single-file Windows GUI exe
# Usage:
#   D:\Dev\Python\python-3.13.3\python.exe build_exe.py

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app"
DIST = ROOT / "dist"
ICON = APP / "assets" / "app.ico"
PY = sys.executable
EXE_NAME = "AICliProfileIsolator"
# keep old name as alias copy for existing shortcuts
LEGACY_NAME = "CodexProfileIsolator"


def run(cmd: list[str]) -> None:
    print(">", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(ROOT))


def main() -> None:
    DIST.mkdir(exist_ok=True)
    run([PY, str(APP / "make_icon.py")])
    if not ICON.is_file():
        raise SystemExit("icon missing")

    cmd = [
        PY,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onefile",
        "--name",
        EXE_NAME,
        "--icon",
        str(ICON),
        "--paths",
        str(APP),
        "--hidden-import",
        "customtkinter",
        "--hidden-import",
        "engines",
        "--hidden-import",
        "core",
        "--collect-all",
        "customtkinter",
        "--collect-all",
        "darkdetect",
        str(APP / "main.py"),
    ]
    run(cmd)

    exe = DIST / f"{EXE_NAME}.exe"
    if not exe.is_file():
        raise SystemExit(f"Build failed: {exe} missing")

    # Compatibility copy for older desktop shortcuts
    legacy = DIST / f"{LEGACY_NAME}.exe"
    try:
        legacy.write_bytes(exe.read_bytes())
    except OSError as e:
        print(f"legacy copy skipped: {e}")

    print()
    print("=" * 60)
    print(f"EXE: {exe}")
    print(f"Size: {exe.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"Also: {legacy} (compat alias)")
    print("=" * 60)


if __name__ == "__main__":
    main()
