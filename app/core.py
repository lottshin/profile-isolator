"""Engine-aware core logic for the multi-CLI profile isolator.

Supports two CLIs through the Engine abstraction (see engines.py):
  - Codex   : CODEX_HOME        , config.toml + auth.json
  - Claude  : CLAUDE_CONFIG_DIR , settings.json + .credentials.json

Every public function takes an `Engine` so the GUI can switch tools by
swapping which engine it passes in. Config/credentials stay isolated per
profile; session storage can be shared so `resume` sees a project's history
across providers.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from engines import (
    Engine,
    ENGINES,
    CODEX,
    CLAUDE,
    mask_secret,
    sanitize_primary,
    stub_primary,
    stub_secondary,
    summarize,
)

INVALID_NAME = re.compile(r'[\\/:*?"<>|]')

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class ProfileSummary:
    name: str
    path: str
    model: str = ""
    provider: str = ""
    provider_name: str = ""
    base_url: str = ""
    has_config: bool = False
    has_auth: bool = False
    has_catalog: bool = False
    is_active: bool = False
    sessions_shared: bool = False
    sessions_share_target: str = ""

def get_engine(key: str) -> Engine:
    return ENGINES[key]


def get_profiles_root(engine: Engine) -> Path:
    override = (os.environ.get(engine.profiles_root_env) or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / engine.profiles_dir_name).resolve()


def get_default_home(engine: Engine) -> Path:
    return (Path.home() / engine.default_home_name).resolve()


def get_shared_session_home(engine: Engine) -> Path:
    """Canonical home for shared sessions (default: the CLI's own ~ config dir)."""
    override = (os.environ.get(engine.shared_home_env) or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return get_default_home(engine)


def safe_profile_name(name: str) -> str:
    n = (name or "").strip()
    if not n:
        raise ValueError("Profile name is empty.")
    if INVALID_NAME.search(n) or n in {".", ".."}:
        raise ValueError(f"Invalid profile name '{n}'. Avoid: \\ / : * ? \" < > |")
    return n


def profile_path(engine: Engine, name: str) -> Path:
    return get_profiles_root(engine) / safe_profile_name(name)


def ensure_root(engine: Engine) -> Path:
    root = get_profiles_root(engine)
    root.mkdir(parents=True, exist_ok=True)
    return root

def parse_config_summary(engine: Engine, profile_dir: Path) -> dict:
    primary = profile_dir / engine.primary_file
    secondary = profile_dir / engine.secondary_file
    text = ""
    if primary.is_file():
        text = primary.read_text(encoding="utf-8", errors="replace")
    s = summarize(engine, text)
    s["has_config"] = primary.is_file()
    s["has_auth"] = secondary.is_file()
    return s


def list_profiles(engine: Engine) -> list[ProfileSummary]:
    root = get_profiles_root(engine)
    if not root.is_dir():
        return []
    current = (os.environ.get(engine.home_env) or "").strip()
    current_resolved = ""
    if current:
        try:
            current_resolved = str(Path(current).resolve())
        except OSError:
            current_resolved = current

    items: list[ProfileSummary] = []
    for d in sorted(
        [p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".") and not p.name.startswith("_")],
        key=lambda p: p.name.lower(),
    ):
        s = parse_config_summary(engine, d)
        is_active = False
        if current_resolved:
            try:
                is_active = str(d.resolve()) == current_resolved
            except OSError:
                is_active = False
        shared = is_sessions_shared(engine, d)
        items.append(
            ProfileSummary(
                name=d.name,
                path=str(d),
                model=s.get("model", ""),
                provider=s.get("provider", ""),
                provider_name=s.get("provider_name", ""),
                base_url=s.get("base_url", ""),
                has_config=s.get("has_config", False),
                has_auth=s.get("has_auth", False),
                has_catalog=s.get("has_catalog", False),
                is_active=is_active,
                sessions_shared=shared,
                sessions_share_target=str(get_shared_session_home(engine)) if shared else "",
            )
        )
    return items

def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def copy_profile_files(engine: Engine, source_dir: Path, dest_dir: Path, force: bool = False) -> None:
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")
    dest_dir.mkdir(parents=True, exist_ok=True)

    prim_src = source_dir / engine.primary_file
    sec_src = source_dir / engine.secondary_file
    prim_dst = dest_dir / engine.primary_file
    sec_dst = dest_dir / engine.secondary_file

    if not force:
        if prim_dst.exists():
            raise FileExistsError(f"{engine.primary_file} already exists in {dest_dir}")
        if sec_dst.exists():
            raise FileExistsError(f"{engine.secondary_file} already exists in {dest_dir}")

    if prim_src.is_file():
        write_text(prim_dst, sanitize_primary(engine, prim_src.read_text(encoding="utf-8", errors="replace")))
    if sec_src.is_file():
        shutil.copy2(sec_src, sec_dst)


def write_stub(engine: Engine, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    prim = dest_dir / engine.primary_file
    sec = dest_dir / engine.secondary_file
    if not prim.exists():
        write_text(prim, stub_primary(engine))
    if not sec.exists():
        write_text(sec, stub_secondary(engine))


def create_profile(
    engine: Engine,
    name: str,
    *,
    from_current: bool = False,
    source_dir: Optional[str] = None,
    force: bool = False,
) -> Path:
    safe = safe_profile_name(name)
    path = profile_path(engine, safe)
    ensure_root(engine)

    if path.exists() and not force:
        raise FileExistsError(f"Profile already exists: {path}")
    if path.exists() and force:
        shutil.rmtree(path)

    if from_current:
        copy_profile_files(engine, get_default_home(engine), path, force=True)
    elif source_dir:
        copy_profile_files(engine, Path(source_dir), path, force=True)
    else:
        write_stub(engine, path)

    try:
        enable_shared_sessions(engine, safe, shared_home=get_shared_session_home(engine))
    except Exception:
        pass
    return path


def delete_profile(engine: Engine, name: str) -> None:
    path = profile_path(engine, name)
    if not path.is_dir():
        raise FileNotFoundError(f"Profile '{name}' not found at {path}")
    shutil.rmtree(path)


def read_profile_file(engine: Engine, name: str, which: str = "config") -> str:
    path = profile_path(engine, name)
    if not path.is_dir():
        raise FileNotFoundError(f"Profile '{name}' not found")
    file = path / (engine.primary_file if which == "config" else engine.secondary_file)
    if not file.is_file():
        return ""
    return file.read_text(encoding="utf-8", errors="replace")


def save_profile_file(engine: Engine, name: str, which: str, content: str) -> Path:
    path = profile_path(engine, name)
    if not path.is_dir():
        raise FileNotFoundError(f"Profile '{name}' not found")
    file = path / (engine.primary_file if which == "config" else engine.secondary_file)
    data = sanitize_primary(engine, content) if which == "config" else content
    write_text(file, data)
    return file


def mask_api_key(engine: Engine, text: str) -> str:
    return mask_secret(engine, text)

def find_cli_command(engine: Engine) -> Optional[str]:
    for cmd in engine.command_names:
        which = shutil.which(cmd)
        if which:
            return which
    # Fallbacks for common npm/global install locations
    appdata = os.environ.get("APPDATA", "")
    localbin = Path.home() / ".local" / "bin"
    candidates: list[Path] = []
    for cmd in engine.command_names:
        candidates += [
            Path(appdata) / "npm" / f"{cmd}.cmd",
            Path(appdata) / "npm" / f"{cmd}.ps1",
            localbin / f"{cmd}.exe",
            localbin / f"{cmd}.cmd",
            Path(r"F:\nodejs") / f"{cmd}.ps1",
            Path(r"F:\nodejs") / f"{cmd}.cmd",
        ]
    for c in candidates:
        if c and c.is_file():
            return str(c)
    return None


def safe_launch_directory(preferred: Optional[str] = None) -> str:
    if preferred and Path(preferred).is_dir():
        return str(Path(preferred).resolve())
    cwd = Path.cwd().resolve()
    home = Path.home().resolve()
    if cwd == home:
        desktop = home / "Desktop"
        if desktop.is_dir():
            return str(desktop)
        return os.environ.get("TEMP", str(home))
    return str(cwd)


def _ps_quote(s: str) -> str:
    return s.replace("'", "''")


def start_profile_session(
    engine: Engine,
    name: str,
    *,
    work_dir: Optional[str] = None,
    run_cli: bool = False,
    cli_args: Optional[Iterable[str]] = None,
) -> None:
    path = profile_path(engine, name)
    if not path.is_dir():
        raise FileNotFoundError(f"Profile '{name}' not found at {path}")
    wd = safe_launch_directory(work_dir)
    home = str(path.resolve())
    env_var = engine.home_env

    header = (
        f"$env:{env_var} = '{_ps_quote(home)}'\n"
        f"Set-Location -LiteralPath '{_ps_quote(wd)}'\n"
        f"Write-Host ('[{engine.key}] profile = {_ps_quote(name)}') -ForegroundColor Green\n"
        f"Write-Host ('[{engine.key}] {env_var} = ' + $env:{env_var}) -ForegroundColor DarkGray\n"
        f"Write-Host ('[{engine.key}] CWD = ' + (Get-Location)) -ForegroundColor DarkGray\n"
    )

    if run_cli:
        cli = find_cli_command(engine)
        if not cli:
            raise RuntimeError(f"{engine.command_names[0]} command not found in PATH")
        arg_parts = []
        for a in list(cli_args or []):
            if re.search(r"\s", a):
                arg_parts.append('"' + a.replace('"', '`"') + '"')
            else:
                arg_parts.append(a)
        arg_line = " ".join(arg_parts)
        body = f"& '{_ps_quote(cli)}' {arg_line}\n"
    else:
        body = f"Write-Host 'Type: {engine.command_names[0]}' -ForegroundColor DarkGray\n"

    ps = header + body
    subprocess.Popen(
        ["powershell.exe", "-NoExit", "-NoLogo", "-Command", ps],
        close_fds=True,
    )


def open_in_explorer(path: str) -> None:
    p = Path(path)
    if p.is_file():
        subprocess.Popen(["explorer.exe", "/select,", str(p)])
    else:
        p.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer.exe", str(p)])


def doctor_report(engine: Engine, name: Optional[str] = None) -> str:
    root = get_profiles_root(engine)
    home = get_default_home(engine)
    lines = [
        f"Engine        : {engine.label}",
        f"Profiles root : {root}",
        f"Default home  : {home}",
        f"{engine.home_env} : {os.environ.get(engine.home_env) or '(unset)'}",
        "",
    ]
    cli = find_cli_command(engine)
    lines.append(f"[ok] {engine.command_names[0]} found: {cli}" if cli else f"[!!] {engine.command_names[0]} not found in PATH")
    lines.append("[ok] profiles root exists" if root.is_dir() else "[!!] profiles root missing")

    try:
        under = str(root.resolve()).lower().startswith(str(home.resolve()).lower() + os.sep)
    except OSError:
        under = False
    lines.append(
        f"[!!] profiles root is under {engine.default_home_name} - high risk"
        if under
        else f"[ok] profiles root outside {engine.default_home_name}"
    )

    if name:
        path = profile_path(engine, name)
        if not path.is_dir():
            lines.append(f"[!!] profile '{name}' not found")
        else:
            s = parse_config_summary(engine, path)
            lines += [
                "",
                f"--- profile: {name} ---",
                f"[ok] {engine.primary_file}" if s.get("has_config") else f"[!!] missing {engine.primary_file}",
                f"[ok] {engine.secondary_file}" if s.get("has_auth") else f"[!!] missing {engine.secondary_file}",
            ]
            if s.get("has_catalog"):
                lines.append("[!!] contains model_catalog_json")
            if s.get("model"):
                lines.append(f"[ok] model = {s['model']}")
            if s.get("base_url"):
                lines.append(f"[ok] base_url = {s['base_url']}")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Shared sessions (provider isolation + project session continuity)
# ---------------------------------------------------------------------------


def _is_reparse_point(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        import ctypes

        GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
        GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
        GetFileAttributesW.restype = ctypes.c_uint32
        INVALID = 0xFFFFFFFF
        FILE_ATTRIBUTE_REPARSE_POINT = 0x400
        attrs = GetFileAttributesW(str(path))
        if attrs == INVALID:
            return False
        return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)
    except Exception:
        return path.is_symlink()


def _same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return os.path.normcase(str(a)) == os.path.normcase(str(b))


def _junction_target(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    try:
        if path.is_symlink() or _is_reparse_point(path):
            return path.resolve()
    except OSError:
        pass
    return None


def is_sessions_shared(engine: Engine, profile_dir: Path | str, shared_home: Optional[Path] = None) -> bool:
    profile_dir = Path(profile_dir)
    shared_home = shared_home or get_shared_session_home(engine)
    if _same_path(profile_dir, shared_home):
        return True
    if not engine.session_dirs:
        return False
    # Consider shared if the first session dir is a junction into the shared home.
    primary = engine.session_dirs[0]
    link = profile_dir / primary
    if not link.exists():
        return False
    target = _junction_target(link)
    if target is None:
        return False
    return _same_path(target, shared_home / primary)


def _merge_tree_into(src: Path, dst: Path) -> int:
    if not src.is_dir():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    copied = 0
    for root, _dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        target_root = dst / rel
        target_root.mkdir(parents=True, exist_ok=True)
        for name in files:
            sfile = Path(root) / name
            dfile = target_root / name
            if dfile.exists():
                continue
            try:
                shutil.copy2(sfile, dfile)
                copied += 1
            except OSError:
                pass
    return copied


def _merge_jsonl(src: Path, dst: Path) -> None:
    if not src.is_file():
        return
    seen: set[str] = set()
    lines_out: list[str] = []
    if dst.is_file():
        for line in dst.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            lines_out.append(line)
            try:
                obj = json.loads(line)
                if isinstance(obj, dict) and obj.get("id"):
                    seen.add(str(obj["id"]))
            except json.JSONDecodeError:
                seen.add(line)
    for line in src.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        key = line
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and obj.get("id"):
                key = str(obj["id"])
        except json.JSONDecodeError:
            pass
        if key in seen:
            continue
        seen.add(key)
        lines_out.append(line)
    if lines_out:
        write_text(dst, "\n".join(lines_out) + "\n")


def _create_junction(link: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    if link.exists() or _is_reparse_point(link):
        if link.is_dir() and not _is_reparse_point(link) and not link.is_symlink():
            raise FileExistsError(f"Cannot create junction; real directory exists: {link}")
        try:
            link.unlink()
        except OSError:
            subprocess.check_call(
                ["cmd", "/c", "rmdir", str(link)],
                shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        shell=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or b"").decode("utf-8", errors="replace")
        raise RuntimeError(f"mklink /J failed: {err}")


def _link_or_copy_file(link: Path, target: Path, merge_jsonl: bool = False) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        if merge_jsonl and link.is_file() and target.exists():
            _merge_jsonl(link, target)
        elif merge_jsonl and link.is_file() and not target.exists():
            shutil.copy2(link, target)
        elif not target.exists() and link.is_file():
            shutil.copy2(link, target)
        try:
            link.unlink()
        except OSError as e:
            raise RuntimeError(
                f"Cannot replace {link.name} (file in use?). Close all CLI windows and retry. ({e})"
            ) from e
    if not target.exists():
        if merge_jsonl:
            write_text(target, "")
        else:
            return "skipped-missing-shared"
    try:
        os.link(target, link)
        return "hardlink"
    except OSError:
        shutil.copy2(target, link)
        return "copy"

def enable_shared_sessions(engine: Engine, name: str, *, shared_home: Optional[Path] = None) -> dict:
    """Point a profile's session storage at the shared home.

    Config/credentials stay isolated per provider; sessions become visible
    across providers for the same project folder.
    """
    profile = profile_path(engine, name)
    if not profile.is_dir():
        raise FileNotFoundError(f"Profile '{name}' not found at {profile}")

    shared = Path(shared_home) if shared_home else get_shared_session_home(engine)
    if _same_path(profile, shared):
        return {"profile": name, "status": "already-shared-home", "shared": str(shared), "ok": True}

    shared.mkdir(parents=True, exist_ok=True)
    report: dict = {"profile": name, "shared": str(shared), "dirs": {}, "files": {}}

    for dirname in engine.session_dirs:
        local = profile / dirname
        target = shared / dirname
        target.mkdir(parents=True, exist_ok=True)
        if local.exists() and not _is_reparse_point(local) and not local.is_symlink():
            if local.is_dir():
                n = _merge_tree_into(local, target)
                report["dirs"][dirname] = f"merged-{n}-files"
                shutil.rmtree(local)
            else:
                local.unlink()
                report["dirs"][dirname] = "removed-non-dir"
        elif local.exists() and (_is_reparse_point(local) or local.is_symlink()):
            try:
                local.unlink()
            except OSError:
                subprocess.check_call(["cmd", "/c", "rmdir", str(local)])
            report["dirs"][dirname] = "relinked"
        else:
            report["dirs"][dirname] = "created"
        _create_junction(local, target)

    for fname in engine.session_files:
        local = profile / fname
        target = shared / fname
        try:
            if fname.endswith(".jsonl"):
                mode = _link_or_copy_file(local, target, merge_jsonl=True)
            else:
                if local.is_file() and not target.exists():
                    shutil.copy2(local, target)
                mode = _link_or_copy_file(local, target, merge_jsonl=False)
            report["files"][fname] = mode
        except Exception as e:
            report["files"][fname] = f"error: {e}"

    report["ok"] = is_sessions_shared(engine, profile, shared)
    return report


def enable_shared_sessions_all(engine: Engine, *, shared_home: Optional[Path] = None) -> list[dict]:
    results = []
    for p in list_profiles(engine):
        try:
            results.append(enable_shared_sessions(engine, p.name, shared_home=shared_home))
        except Exception as e:
            results.append({"profile": p.name, "ok": False, "error": str(e)})
    return results


def session_share_status(engine: Engine, name: Optional[str] = None) -> str:
    shared = get_shared_session_home(engine)
    primary = engine.session_dirs[0] if engine.session_dirs else "sessions"
    sess_dir = shared / primary
    lines = [
        f"Shared session home : {shared}",
        f"{primary} dir       : {sess_dir} ({'exists' if sess_dir.exists() else 'missing'})",
        "",
        f"Tip: `{engine.resume_cmd}` filters by current project folder (cwd).",
        f"     Use the same Working directory across providers, or `{engine.resume_all_cmd}`.",
        "",
    ]
    profiles = list_profiles(engine) if name is None else [p for p in list_profiles(engine) if p.name == name]
    if name and not profiles:
        p = profile_path(engine, name)
        flag = is_sessions_shared(engine, p, shared)
        lines.append(f"{name}: {'SHARED' if flag else 'ISOLATED'}  ({p})")
    else:
        for p in profiles:
            lines.append(f"{p.name}: {'SHARED' if p.sessions_shared else 'ISOLATED'}")
    return "\n".join(lines)
