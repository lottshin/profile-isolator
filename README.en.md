# Profile Isolator

[**中文**](README.md) | **English**

Windows desktop app for **Codex** and **Claude Code** multi-profile isolation: separate providers, keys, and models, with optional shared sessions so `resume` works across profiles.

<p align="center">
  <img src="docs/screenshots/main-ui.png" alt="Profile Isolator main UI (demo data, redacted)" width="900" />
</p>

> Demo screenshot only — profile names and endpoints are placeholders, no real keys.

<p align="center">
  <a href="https://github.com/lottshin/profile-isolator/releases"><img src="https://img.shields.io/github/v/release/lottshin/profile-isolator?label=release" alt="release" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="license" /></a>
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey" alt="platform" />
</p>

## Why

You often need to switch:

- Different API providers / base URLs  
- Different keys and models  
- Codex and Claude Code side by side  

Default installs keep one home config each, so mixing them is messy. This tool gives every profile its own folder and launches the CLI with the right environment variable, optionally sharing session storage.

| CLI | Env | Config | Credentials | Sessions |
|-----|-----|--------|-------------|----------|
| **Codex** | `CODEX_HOME` | `config.toml` | `auth.json` | `sessions/` |
| **Claude Code** | `CLAUDE_CONFIG_DIR` | `settings.json` | `.credentials.json` (MCP OAuth) | `projects/` |

> Claude API key / base URL / model live in **`settings.json` → `env`** (`ANTHROPIC_*`), not in `.credentials.json`.

## Features

- GUI: create, import, **rename**, **duplicate**, delete  
- **Drag-handle reorder** (saved in `.profile-order.json`)  
- **Launch** into a single console with isolated env  
- **Working directory remembered per profile**  
- Shared sessions via junctions for cross-provider resume  
- Move Codex + Claude trees under one parent folder  
- Cache inspect / clean (no auto-delete of sessions)  
- Light / Dark / System theme  

## Download

Prebuilt Windows exe: [Releases](https://github.com/lottshin/profile-isolator/releases).

Run `ProfileIsolator-v*.exe` (WebView2 required; usually preinstalled on Windows 11).

## Quick start

1. Open the app → pick **Codex** or **Claude Code**  
2. **Import** from `~/.codex` / `~/.claude`, or **New Profile**  
3. Edit Config / Auth and save  
4. Set **Working directory** (remembered per profile)  
5. Click **Launch**  

Default paths:

```text
%USERPROFILE%\CodexProfiles\<name>
%USERPROFILE%\ClaudeProfiles\<name>
```

Move both trees together under a parent folder (e.g. `F:\AI-Profiles\`) via **More → Cache & storage**.

App settings:

```text
%USERPROFILE%\.profile-isolator\
```

## Build from source

```powershell
# Needs: Node 18+, Rust stable, VS Build Tools (C++)
cd desktop
npm install
npm run tauri dev
npm run tauri build -- --no-bundle
# desktop/src-tauri/target/release/ai_cli_profile_isolator.exe
```

Optional: `python desktop/make_ios_icon.py` to regenerate icons.

## Security

- Never commit live `auth.json` / keys / tokens  
- Redact secrets before sharing configs or screenshots  
- The public repo does not include personal credentials  

## Project layout

```text
├── desktop/          # Main app (Tauri + React)
├── app/              # Legacy Python GUI (optional)
├── docs/screenshots/ # README images
├── share-sessions.cmd
├── README.md         # Chinese (default)
└── README.en.md      # English
```

## License

MIT — see [LICENSE](LICENSE).
