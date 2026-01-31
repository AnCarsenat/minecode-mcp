# 🎮 MineCode MCP

**MCP Server for Minecraft Datapack Development**
Written for Hackaton about CMP sponsored by dustt, alpic, etc. Please star if you would like to help out.
Please write issues for me to fix.

[![PyPI](https://img.shields.io/pypi/v/minecode-mcp)](https://pypi.org/project/minecode-mcp/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

MineCode is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that gives AI assistants like **GitHub Copilot** and **Claude** real-time access to Minecraft data, documentation, and datapack generators.

![alt text](https://github.com/AnCarsenat/minecode-mcp/raw/main/assets/readme/example3.png)
---

## ✨ Features

- 🔧 **27 MCP Tools** for Minecraft development
- 📚 **Minecraft Wiki** integration (search, pages, categories)
- 🐛 **Mojira** bug tracker search
- 🔍 **Spyglass API** (registries, commands, block states)
- 🎨 **Misode Generators** (loot tables, recipes, worldgen presets)

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
| `search_wiki` | Search for wiki pages |
| `get_wiki_page` | Get page content and summary |
| `get_wiki_commands` | List all Minecraft commands |
| `get_wiki_category` | Get pages in a category |
| `get_wiki_page_content` | Get full page content for a wiki page |
| `get_wiki_command_info` | Get detailed command documentation from the wiki |
| `get_wiki_random` | Get random wiki pages |

### Mojira Bug Tracker
| Tool | Description |
|------|-------------|
| `search_mojira` | Search bug reports |

### Spyglass API
| Tool | Description |
|------|-------------|
| `spyglass_get_versions` | Get all MC versions with pack formats |
| `spyglass_get_registries` | Get registry entries (items, blocks, entities) |
| `spyglass_get_block_states` | Get block state properties |
| `spyglass_get_commands` | Get command syntax trees |
| `spyglass_get_items` | Get list of items for a version |
| `spyglass_search_registry` | Search a Spyglass registry for a query |
| `spyglass_get_mcdoc_symbols` | Get vanilla mcdoc symbols from Spyglass |

### Misode Generators
| Tool | Description |
|------|-------------|
| `misode_get_generators` | List all datapack generators |
| `misode_get_presets` | Get vanilla presets for a generator |
| `misode_get_preset_data` | Get full JSON for a preset |
| `misode_get_loot_tables` | Get loot tables by category |
| `misode_get_recipes` | Get recipes with filtering |
| `misode_list_versions` | List available Misode/Minecraft versions |
| `misode_get_data` | Get raw Misode data for a version and data type |
| `misode_search_data` | Search Misode data for a query |

### Utility
| Tool | Description |
|------|-------------|
| `hello_world` | Test connectivity |
| `get_minecraft_version` | Get version info |
| `validate_datapack` | Validate datapack structure |
| `list_commands` | List commands for a version |

---

## 💡 Example Prompts

> "Create a custom dimension with floating islands"

> "What are the block states for a redstone repeater?"

> "Show me the loot table for a desert temple chest"

> "Search Mojira for elytra bugs"

> "What's the syntax for the /execute command?"

---

## 📁 Project Structure

```
minecode-mcp/
├── minecode/
│   ├── __init__.py
│   ├── server.py          # MCP server with 27 tools
│   └── scrappers/
│       ├── minecraftwiki.py
│       ├── mojira.py
│       ├── spyglass.py
│       └── misode.py
├── example/
│   └── crystal_dimension/ # Example datapack
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

## 🐍 Plans

- [ ] Getting logs using prism's api for log sharing https://mclo.gs
If impossible, perform a search for where minecraft assets are generally located at

- [ ] Better spyglass tools

- [ ] Better multiversion support

- [ ] Pre-prompts to increase agent accuracy



---

## 📄 License

MIT License - see [LICENSE](LICENSE)

---

<p align="center">
Made with 💜 for the Minecraft community
</p>

