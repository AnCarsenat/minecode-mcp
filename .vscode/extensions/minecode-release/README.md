# MineCode Release - VS Code Extension

This extension provides commands to run the MineCode MCP server locally and to run the release workflow from within VS Code.

Commands

- `MineCode: Start MCP Server` — starts the server (prefers `venv\Scripts\python.exe` when `minecode.server.useVenv` is true).
- `MineCode: Stop MCP Server` — stops the server process.
- `MineCode: Release (interactive)` — run the `scripts/release.ps1` workflow (bump/build/publish).
- `MineCode: Release and Publish` — runs bump + publish directly.

Configuration

- `minecode.server.command`: fallback python command (default `py`).
- `minecode.server.args`: arguments passed to the python command (default `[-m, minecode.server]`).
- `minecode.server.useVenv`: prefer workspace venv when present (default `true`).

Packaging & Publishing

- Package: `npx vsce package`
- Publish: `npx vsce publish --pat <PERSONAL_ACCESS_TOKEN>`

You will need a publisher and a Personal Access Token (PAT) from the Visual Studio Marketplace to publish the extension.
