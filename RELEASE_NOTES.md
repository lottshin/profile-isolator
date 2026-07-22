# Profile Isolator v1.0.0

Windows desktop tool for **Codex** and **Claude Code** profile isolation.

## Highlights

- Isolate providers / API keys / configs per profile (`CODEX_HOME` / `CLAUDE_CONFIG_DIR`)
- Shared sessions for cross-provider `resume`
- Move Codex + Claude profile trees together under one parent folder
- Rename, **duplicate**, and drag-reorder profiles
- Working directory **remembered per profile**
- Fast Launch (cached CLI path); custom scrollbars; native folder picker
- Cache & storage tools (inspect / clean sandbox, no auto-clean of sessions)

## Download

- `ProfileIsolator.exe` — run directly (WebView2 required; usually preinstalled on Win11)

## Notes

- Close running Codex / Claude windows before renaming profiles or moving profile folders
- Do not commit `auth.json` / real API keys when sharing configs
- Source: https://github.com/lottshin/profile-isolator
