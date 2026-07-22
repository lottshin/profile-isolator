"""CLI engine definitions for the multi-tool profile isolator.

Two engines share one isolation model (a per-terminal config-dir env var):

  codex  -> CODEX_HOME         , config.toml + auth.json
  claude -> CLAUDE_CONFIG_DIR  , settings.json + .credentials.json

Everything format-specific (how to read model/provider, how to mask secrets,
what a blank profile looks like, which files make up "sessions") lives here so
core.py can stay generic.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class Engine:
    key: str                 # "codex" | "claude"
    label: str               # display name
    home_env: str            # env var that points the CLI at a config dir
    profiles_root_env: str   # override for where profiles live
    shared_home_env: str     # override for the shared-session home
    profiles_dir_name: str   # default profiles root folder under ~
    default_home_name: str   # the CLI's default config dir under ~
    primary_file: str        # main config file
    secondary_file: str      # credential file
    primary_label: str
    secondary_label: str
    command_names: tuple     # executable names to probe on PATH
    session_dirs: tuple      # dirs junctioned into the shared home
    session_files: tuple     # files hardlinked/merged into the shared home
    resume_cmd: str
    resume_all_cmd: str


CODEX = Engine(
    key="codex",
    label="Codex",
    home_env="CODEX_HOME",
    profiles_root_env="CODEX_PROFILES_ROOT",
    shared_home_env="CODEX_SHARED_HOME",
    profiles_dir_name="CodexProfiles",
    default_home_name=".codex",
    primary_file="config.toml",
    secondary_file="auth.json",
    primary_label="config.toml",
    secondary_label="auth.json",
    command_names=("codex",),
    session_dirs=("sessions", "archived_sessions"),
    session_files=("session_index.jsonl", "state_5.sqlite", "state_5.sqlite-shm", "state_5.sqlite-wal"),
    resume_cmd="codex resume",
    resume_all_cmd="codex resume --all",
)

CLAUDE = Engine(
    key="claude",
    label="Claude Code",
    home_env="CLAUDE_CONFIG_DIR",
    profiles_root_env="CLAUDE_PROFILES_ROOT",
    shared_home_env="CLAUDE_SHARED_HOME",
    profiles_dir_name="ClaudeProfiles",
    default_home_name=".claude",
    primary_file="settings.json",
    secondary_file=".credentials.json",
    primary_label="settings.json",
    secondary_label=".credentials.json",
    command_names=("claude",),
    session_dirs=("projects", "todos"),
    session_files=(),
    resume_cmd="claude --resume",
    resume_all_cmd="claude --continue",
)

ENGINES = {CODEX.key: CODEX, CLAUDE.key: CLAUDE}


# ---------------------------------------------------------------------------
# Codex parsing (TOML-ish, regex-based — matches the original core.py behavior)
# ---------------------------------------------------------------------------

_TOML_MODEL = re.compile(r'(?m)^\s*model\s*=\s*"([^"]+)"')
_TOML_PROVIDER = re.compile(r'(?m)^\s*model_provider\s*=\s*"([^"]+)"')
_TOML_BASE_URL = re.compile(r'(?m)^\s*base_url\s*=\s*"([^"]+)"')
_TOML_NAME = re.compile(r'(?m)^\s*name\s*=\s*"([^"]+)"')
_OPENAI_KEY_MASK = re.compile(r'("OPENAI_API_KEY"\s*:\s*")([^"]{4})[^"]*(")')

# Generic "sk-...."/token masking used for Claude settings/creds
_TOKEN_MASK = re.compile(r'("(?:[A-Z_]*API_KEY|[A-Z_]*AUTH_TOKEN|token|access_token|refresh_token)"\s*:\s*")([^"]{4})[^"]*(")', re.IGNORECASE)


def _codex_summary(primary_text: str) -> dict:
    model = provider = base_url = provider_name = ""
    if primary_text:
        m = _TOML_MODEL.search(primary_text)
        if m:
            model = m.group(1)
        m = _TOML_PROVIDER.search(primary_text)
        if m:
            provider = m.group(1)
        m = _TOML_BASE_URL.search(primary_text)
        if m:
            base_url = m.group(1)
        m = _TOML_NAME.search(primary_text)
        if m:
            provider_name = m.group(1)
    return {
        "model": model,
        "provider": provider,
        "provider_name": provider_name,
        "base_url": base_url,
        "has_catalog": "model_catalog_json" in (primary_text or ""),
    }


def _codex_sanitize(text: str) -> str:
    if not text:
        return text
    lines = text.splitlines()
    kept = [ln for ln in lines if not re.match(r"^\s*model_catalog_json\s*=", ln)]
    return "\n".join(kept) + ("\n" if text.endswith("\n") or kept else "")


def _codex_stub_primary() -> str:
    return (
        '# Codex profile config - edit me\n'
        '# model_provider = "custom"\n'
        '# model = "gpt-5.5"\n'
        '# model_reasoning_effort = "high"\n'
        '#\n'
        '# [model_providers.custom]\n'
        '# name = "MyProvider"\n'
        '# wire_api = "responses"\n'
        '# base_url = "https://api.example.com/v1"\n'
        '# requires_openai_auth = true\n'
    )


def _codex_stub_secondary() -> str:
    return '{\n  "OPENAI_API_KEY": "sk-REPLACE_ME"\n}\n'


# ---------------------------------------------------------------------------
# Claude Code parsing (settings.json — model/provider live in the env block)
# ---------------------------------------------------------------------------


def _claude_summary(primary_text: str) -> dict:
    model = provider = base_url = provider_name = ""
    if primary_text:
        try:
            data = json.loads(primary_text)
        except (json.JSONDecodeError, ValueError):
            data = {}
        env = data.get("env", {}) if isinstance(data, dict) else {}
        if isinstance(env, dict):
            model = env.get("ANTHROPIC_MODEL", "") or data.get("model", "") if isinstance(data, dict) else ""
            base_url = env.get("ANTHROPIC_BASE_URL", "")
        elif isinstance(data, dict):
            model = data.get("model", "")
        if base_url:
            host = urlparse(base_url).hostname or ""
            provider_name = host
            provider = host
    return {
        "model": model,
        "provider": provider,
        "provider_name": provider_name,
        "base_url": base_url,
        "has_catalog": False,
    }


def _claude_sanitize(text: str) -> str:
    # No known destructive keys for Claude; keep as-is.
    return text


def _claude_stub_primary() -> str:
    return (
        "{\n"
        '  "env": {\n'
        '    "ANTHROPIC_BASE_URL": "https://api.example.com",\n'
        '    "ANTHROPIC_AUTH_TOKEN": "sk-REPLACE_ME",\n'
        '    "ANTHROPIC_MODEL": "claude-opus-4-8"\n'
        "  }\n"
        "}\n"
    )


def _claude_stub_secondary() -> str:
    # Claude stores OAuth creds here when logging in; leave empty for token-based providers.
    return "{}\n"


_PARSERS = {
    "codex": _codex_summary,
    "claude": _claude_summary,
}
_SANITIZERS = {
    "codex": _codex_sanitize,
    "claude": _claude_sanitize,
}
_STUBS = {
    "codex": (_codex_stub_primary, _codex_stub_secondary),
    "claude": (_claude_stub_primary, _claude_stub_secondary),
}


def summarize(engine: Engine, primary_text: str) -> dict:
    return _PARSERS[engine.key](primary_text)


def sanitize_primary(engine: Engine, text: str) -> str:
    return _SANITIZERS[engine.key](text)


def stub_primary(engine: Engine) -> str:
    return _STUBS[engine.key][0]()


def stub_secondary(engine: Engine) -> str:
    return _STUBS[engine.key][1]()


def mask_secret(engine: Engine, text: str) -> str:
    if not text:
        return text
    if engine.key == "codex":
        return _OPENAI_KEY_MASK.sub(r"\1\2...\3", text)
    return _TOKEN_MASK.sub(r"\1\2...\3", text)

