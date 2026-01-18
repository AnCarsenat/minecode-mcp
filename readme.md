# 🎮 MineCode

**MCP Server for Minecraft Datapack Development**

[![PyPI](https://img.shields.io/pypi/v/minecode-mcp)](https://pypi.org/project/minecode-mcp/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

MineCode is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that gives AI assistants like **GitHub Copilot** and **Claude** real-time access to Minecraft data, documentation, and datapack generators.

---

## ✨ Features

- 🔧 **19 MCP Tools** for Minecraft development
- 📚 **Minecraft Wiki** integration (search, pages, categories)
- 🐛 **Mojira** bug tracker search
- 🔍 **Spyglass API** (registries, commands, block states, function validation)
- 🎨 **Misode Generators** (loot tables, recipes, worldgen presets)

---

## 🚀 Installation

```bash
pip install minecode-mcp
```

---

## ⚙️ Configuration

### VS Code (GitHub Copilot)

Add to **User Settings** (`Ctrl+Shift+P` → "Preferences: Open User Settings (JSON)"):

```json
{
  "mcp": {
    "servers": {
      "minecode": {
        "type": "stdio",
        "command": "minecode"
      }
    }
  }
}
```

Or create `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "minecode": {
      "type": "stdio", 
      "command": "minecode"
    }
  }
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

## 🛠️ Available Tools

### Minecraft Wiki
| Tool | Description |
|------|-------------|
| `search_wiki` | Search for wiki pages |
| `get_wiki_page` | Get page content and summary |
| `get_wiki_commands` | List all Minecraft commands |
| `get_wiki_category` | Get pages in a category |

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
| `validate_function` | Validate function file syntax using Spyglass |

### Misode Generators
| Tool | Description |
|------|-------------|
| `misode_get_generators` | List all datapack generators |
| `misode_get_presets` | Get vanilla presets for a generator |
| `misode_get_preset_data` | Get full JSON for a preset |
| `misode_get_loot_tables` | Get loot tables by category |
| `misode_get_recipes` | Get recipes with filtering |

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
│   ├── server.py          # MCP server with 19 tools
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

## 📄 License

MIT License - see [LICENSE](LICENSE)

---

<p align="center">
Made with 💜 for the Minecraft community
</p>
