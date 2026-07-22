# Contributing

Thanks for considering a contribution.

## Dev setup (Windows)

1. Install Node 18+, Rust (rustup), and VS Build Tools (C++).
2. `cd desktop && npm install`
3. `npm run tauri dev`

## Guidelines

- Do not commit secrets, `auth.json`, `.credentials.json`, or personal profile folders.
- Prefer small, focused PRs.
- Match existing code style in the file you touch.
- For UI changes, keep the IA simple: primary actions obvious, advanced actions under **More**.

## Pull requests

1. Fork + branch from `main`
2. Describe what changed and why
3. Note any Windows-only behavior

## Reporting issues

Include OS version, app version / commit, and steps to reproduce. Redact API keys.
