[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/ancarsenat-minecode-mcp-badge.png)](https://mseep.ai/app/ancarsenat-minecode-mcp)

# 🎮 MineCode MCP

**MCP Server for Minecraft Datapack Development**
Written for Hackaton about CMP sponsored by dustt, alpic, etc. Please star if you would like to help out.
Please write issues for me to fix.

[![PyPI](https://img.shields.io/pypi/v/minecode-mcp)](https://pypi.org/project/minecode-mcp/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

MineCode is a **local** [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that gives AI assistants like **GitHub Copilot** and **Claude** real-time access to Minecraft data, documentation, datapack generators, and your minecraft logs.

![alt text](https://github.com/AnCarsenat/minecode-mcp/raw/main/assets/readme/example6.png)
---

## ✨ Features

- 🔧 **19 MCP Tools** for Minecraft development
- 📚 **Minecraft Wiki** integration (search, pages, categories, command docs)
- 🐛 **Mojira** bug tracker search
- 🔍 **Spyglass API** (registries, commands, block states, mcdoc symbols)
- 🎨 **Misode Generators** (loot tables, recipes, worldgen presets)
- 📄 **Log Reading** — auto-detect and read logs from default, Prism, and TLauncher instances
- 🧠 **Assistant Pre-prompts** — configurable system prompts for better AI accuracy

---

## 🚀 Installation

```bash
pip install minecode-mcp
```

---

## ⚙️ Configuration

### VS Code (GitHub Copilot)

Add to **User Settings** (`Ctrl+Shift+P` → "MCP: Open User Configuration"):

```json
{
	"servers": {
		"minecode": {
			"type": "stdio",
			"command": "py",
			"args": [
				"-m",
				"minecode.server"
			]
		}
	},
	"inputs": []
}
```

Or create `.vscode/mcp.json` in your workspace:

```json
{
	"servers": {
		"minecode": {
			"type": "stdio",
			"command": "py",
			"args": [
				"-m",
				"minecode.server"
			]
		}
	},
	"inputs": []
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "minecode": {
      "command": "minecode"
    }
  }
}
```

| OS | Config Path |
|----|-------------|
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

---

## ⚙️ Development

Follow these steps to set up a local development environment, run the MCP server, and publish releases.
- Development environment:

	PowerShell (Windows):
	```powershell
  
	python -m venv venv
	.\venv\Scripts\Activate.ps1
	python -m pip install --upgrade pip build twine
	python -m pip install -e .
	```

	Bash (macOS/Linux):
	```bash
	python -m venv venv
	source venv/bin/activate
	python -m pip install --upgrade pip build twine
	python -m pip install -e .
	```

- Run the MCP server locally:

	- Using the venv Python:
		```powershell
		.\venv\Scripts\python.exe -m minecode.server
		```
	- Or with `py` on Windows / `python` on other OSes:
		```bash
		python -m minecode.server
		```

- Configure VS Code to use the running server (GitHub Copilot MCP): create `.vscode/mcp.json` in the workspace (example above) so Copilot/other MCP clients can connect to `minecode.server`.

- Release workflow (single-script): use the provided `scripts/release.ps1` to bump, build and publish.

- Release (recommended): a single PowerShell script handles bumping, building, tagging, pushing, and publishing.

  Prerequisites:
  - Create and activate a Python virtualenv and install `build` + `twine`.
  - Put your PyPI API token in `pip_token.txt` (single line) or set `PYPI_API_TOKEN` as an environment/secret.

  Usage examples (PowerShell):
  - Build only: `.\scripts\release.ps1`
  - Bump patch, tag, push, and publish: `.\scripts\release.ps1 -Bump -Publish`
  - Publish without bump: `.\scripts\release.ps1 -Publish`

  The script prefers `venv\Scripts\python.exe` when present and will fall back to the system `python`.

  CI: a GitHub Actions workflow (`.github/workflows/publish.yml`) publishes on tag push; add `PYPI_API_TOKEN` to repository secrets.

- Manual build & publish (alternative):

	```bash
	python -m build
	export TWINE_USERNAME=__token__
	export TWINE_PASSWORD=<PYPI_API_TOKEN>
	python -m twine upload dist/*
	```

- CI: a GitHub Actions workflow (`.github/workflows/publish.yml`) is included to publish on tag push; add `PYPI_API_TOKEN` to repository secrets.


## 🛠️ Available Tools

### Minecraft Wiki
| Tool | Description |
|------|-------------|
| `search_wiki` | Search for wiki pages (supports full-text search with snippets) |
| `get_wiki_page` | Get page summary and section list |
| `get_wiki_commands` | List all Minecraft commands |
| `get_wiki_category` | Get pages in a category |
| `get_wiki_page_content` | Get full structured page content |
| `get_wiki_command_info` | Get detailed command syntax documentation |

### Mojira Bug Tracker
| Tool | Description |
|------|-------------|
| `search_mojira` | Search bug reports (filter by project, status, resolution) |

### Spyglass API
| Tool | Description |
|------|-------------|
| `spyglass_get_versions` | Get all MC versions with pack formats |
| `spyglass_get_registries` | Get registry entries (items, blocks, entities, biomes, etc.) |
| `spyglass_get_block_states` | Get block state properties and defaults |
| `spyglass_get_commands` | Get command syntax trees |
| `spyglass_get_mcdoc_symbols` | Get vanilla mcdoc type symbols for NBT/data structures |

### Misode Generators
| Tool | Description |
|------|-------------|
| `misode_get_generators` | List all datapack generators |
| `misode_get_presets` | Get vanilla presets for a generator |
| `misode_get_preset_data` | Get full JSON for a preset |
| `misode_get_loot_tables` | Get loot tables by category |
| `misode_get_recipes` | Get recipes with filtering |
| `misode_list_versions` | List available Misode/Minecraft versions |

### Logs
| Tool | Description |
|------|-------------|
| `get_logs` | Read Minecraft logs (auto-detects default, Prism, or TLauncher) |

---

## 💡 Example Prompts

> "Create a custom dimension with floating islands"

> "What are the block states for a redstone repeater?"

> "Show me the loot table for a desert temple chest"

> "Search Mojira for elytra bugs"

> "What's the syntax for the /execute command?"

> "Check my Minecraft logs for errors"

---

## 📁 Project Structure

```
minecode-mcp/
├── minecode/
│   ├── __init__.py
│   ├── server.py              # MCP server with 19 tools
│   ├── config/
│   │   ├── config.json        # Central configuration
│   │   └── prompt_config.json
│   ├── preprompts/
│   │   └── assistant_preprompt.txt  # AI assistant pre-prompt
│   └── scrappers/
│       ├── minecraftwiki.py
│       ├── mojira.py
│       ├── spyglass.py
│       ├── misode.py
│       └── minecraft_logs.py  # Multi-launcher log reader
├── example/
│   └── crystal_dimension/     # Example datapack
├── scripts/
│   └── release.ps1            # Build, bump & publish script
├── pyproject.toml
├── LICENSE
└── readme.md
```

---

## 🌐 Data Sources

| Source | Description |
|--------|-------------|
| [Minecraft Wiki](https://minecraft.wiki) | Game documentation |
| [Mojira](https://bugs.mojang.com) | Bug tracker |
| [Spyglass MC](https://api.spyglassmc.com) | Registries & commands |
| [Misode](https://github.com/misode/mcmeta) | Vanilla presets |

---

## 🐍 Changelog Highlights

- [X] **Log reading** — Multi-launcher support (default, Prism, TLauncher) with auto-detection
- [X] **Better Spyglass tools** — mcdoc symbols, improved registry search
- [X] **Multi-version support** — pack_format-based version handling
- [X] **Assistant pre-prompts** — Configurable system prompts for more accurate AI responses



---

## 📄 License

MIT License - see [LICENSE](LICENSE)

---

<p align="center">
Made with 💜 for the Minecraft community
</p>

