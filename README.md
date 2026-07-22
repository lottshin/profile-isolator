# AI CLI Profile Isolator

Desktop app + scripts to isolate **Codex** and **Claude Code** configs per provider, while optionally sharing project sessions so `resume` works across providers.

| CLI | Env var | Config | Credentials | Sessions |
|-----|---------|--------|-------------|----------|
| **Codex** | `CODEX_HOME` | `config.toml` | `auth.json` | `sessions/` |
| **Claude Code** | `CLAUDE_CONFIG_DIR` | `settings.json` | `.credentials.json` (MCP OAuth only) | `projects/` |

Claude API key / base URL / model live in **`settings.json` → `env`** (`ANTHROPIC_*`), not in `.credentials.json`.

---

## Features

- GUI (Tauri) for managing profiles, editing configs, launching CLI with isolated env
- Shared sessions (junctions to the default home, e.g. `~/.codex`) for cross-provider resume
- Move entire profiles trees to another disk (Codex + Claude under one parent folder)
- Cache inspection / clean (`.sandbox-bin`, `.tmp`) without deleting configs or sessions
- Rename / duplicate / drag-reorder profiles
- Working directory remembered **per profile**
- Theme: Light / Dark / Auto

---

## Download (Windows)

Prebuilt exe (Release): see [Releases](https://github.com/lottshin/profile-isolator/releases).

Or build from source below.

## Requirements

- Windows 10/11 (primary target)
- For development:
  - [Node.js](https://nodejs.org/) 18+
  - [Rust](https://rustup.rs/) stable
  - Visual Studio Build Tools (C++ desktop workload) **or** MSVC linker available
  - WebView2 (usually preinstalled on Win11)

Optional: Python 3.11+ for the legacy CustomTkinter GUI under `app/`.

---

## Quick start (GUI from source)

```powershell
cd desktop
npm install
npm run tauri dev
```

Build release exe:

```powershell
cd desktop
npm run tauri build -- --no-bundle
# output:
# desktop/src-tauri/target/release/ai_cli_profile_isolator.exe
```

Regenerate app icons (optional):

```powershell
python desktop/make_ios_icon.py
```

---

## Usage (concept)

1. Create or import a profile (from `~/.codex` or `~/.claude`).
2. Edit provider config / keys in the GUI.
3. Set working directory → **Launch**.
4. Sessions are shared by default so the same project folder can `resume` under another profile.

Profiles default to:

```text
%USERPROFILE%\CodexProfiles\<name>
%USERPROFILE%\ClaudeProfiles\<name>
```

You can move both under a shared parent (e.g. `F:\AI-Profiles\CodexProfiles` + `ClaudeProfiles`) via **More → Cache & storage**.

Settings are stored in:

```text
%USERPROFILE%\.profile-isolator\
```

---

## Project layout

```text
codex-profile/
├── desktop/                 # Tauri + React GUI (main)
│   ├── src/                 # Frontend
│   └── src-tauri/           # Rust backend
├── app/                     # Legacy Python GUI (optional)
├── share-sessions.cmd       # CLI helper for session sharing
├── cx.ps1 / cx.cmd          # Codex-oriented CLI helpers
└── README.md
```

---

## Security notes

- Never commit `auth.json`, `.credentials.json`, or real API keys.
- Built `.exe` under `dist/` is not required for source distribution.
- Review local paths and secrets before publishing.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Acknowledgements

Codex isolation approach is commonly discussed in community guides (e.g. `CODEX_HOME` per terminal). Claude Code isolation uses `CLAUDE_CONFIG_DIR`.
