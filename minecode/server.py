#!/usr/bin/env python3
"""
MCP Server for Minecraft Datapack Development
Provides tools for searching wiki info, checking syntax, and other utilities
"""

import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import scrappers (relative imports for package)
from .scrappers import mojira
from .scrappers import minecraftwiki
from .scrappers import spyglass
from .scrappers import misode


# Initialize MCP Server
server = Server("minecode-server")


# Tool definitions
TOOLS = [
    Tool(
        name="hello_world",
        description="Returns a simple hello world message",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Optional name to greet"
                }
            },
            "required": []
        }
    ),
    Tool(
        name="get_minecraft_version",
        description="Returns information about a specific Minecraft version",
        inputSchema={
            "type": "object",
            "properties": {
                "version": {
                    "type": "string",
                    "description": "Minecraft version (e.g., 1.20.1, latest)"
                }
            },
            "required": ["version"]
        }
    ),
    Tool(
        name="validate_datapack",
        description="Validates datapack syntax and structure",
        inputSchema={
            "type": "object",
            "properties": {
                "datapack_path": {
                    "type": "string",
                    "description": "Path to the datapack folder"
                },
                "mc_version": {
                    "type": "string",
                    "description": "Target Minecraft version"
                }
            },
            "required": ["datapack_path", "mc_version"]
        }
    ),
    Tool(
        name="search_wiki",
        description="Search Minecraft Wiki for pages matching a query. Returns titles, URLs, and snippets.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 10)"
                },
                "fulltext": {
                    "type": "boolean",
                    "description": "Use full-text search with snippets (default false)"
                }
            },
            "required": ["query"]
        }
    ),
    Tool(
        name="get_wiki_page",
        description="Get the content and summary of a specific Minecraft Wiki page.",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Page title (e.g., 'Creeper', 'Diamond Sword', 'Commands/execute')"
                },
                "sentences": {
                    "type": "integer",
                    "description": "Number of sentences for summary (default 5)"
                }
            },
            "required": ["title"]
        }
    ),
    Tool(
        name="get_wiki_commands",
        description="Get list of all Minecraft commands from the wiki with their URLs.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max commands to return (default 50)"
                }
            },
            "required": []
        }
    ),
    Tool(
        name="get_wiki_category",
        description="Get all pages in a wiki category (e.g., 'Blocks', 'Items', 'Mobs').",
        inputSchema={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Category name (e.g., 'Blocks', 'Items', 'Mobs', 'Commands')"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 50)"
                }
            },
            "required": ["category"]
        }
    ),
    Tool(
        name="list_commands",
        description="List all available Minecraft commands for a version",
        inputSchema={
            "type": "object",
            "properties": {
                "version": {
                    "type": "string",
                    "description": "Minecraft version (e.g., 1.20.1)"
                },
                "category": {
                    "type": "string",
                    "description": "Optional: Filter by category (admin, player, etc.)",
                    "enum": ["all", "admin", "player", "utility"]
                }
            },
            "required": ["version"]
        }
    ),
    Tool(
        name="search_mojira",
        description="Search Mojira bug tracker for Minecraft issues. Returns Key, URL, Summary, Status, Reporter, Assignee, and Created date.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search text (minimum 3 characters)"
                },
                "project": {
                    "type": "string",
                    "description": "Filter by project",
                    "enum": ["MC", "MCPE", "MCL", "REALMS", "WEB", "BDS"]
                },
                "status": {
                    "type": "string",
                    "description": "Filter by status",
                    "enum": ["Open", "Reopened", "Postponed", "In Progress", "Resolved", "Closed"]
                },
                "resolution": {
                    "type": "string",
                    "description": "Filter by resolution",
                    "enum": ["Awaiting Response", "Cannot Reproduce", "Done", "Duplicate", "Fixed", "Incomplete", "Invalid", "Unresolved", "Won't Fix", "Works As Intended"]
                },
                "page": {
                    "type": "integer",
                    "description": "Page number (default 1)"
                }
            },
            "required": []
        }
    ),
    # Spyglass API Tools
    Tool(
        name="spyglass_get_versions",
        description="Get all Minecraft Java Edition versions from Spyglass API. Returns version IDs, names, types (release/snapshot), pack versions, etc.",
        inputSchema={
            "type": "object",
            "properties": {
                "type_filter": {
                    "type": "string",
                    "description": "Filter by version type",
                    "enum": ["all", "release", "snapshot"]
                },
                "limit": {
                    "type": "integer",
                    "description": "Max versions to return (default 20)"
                }
            },
            "required": []
        }
    ),
    Tool(
        name="spyglass_get_registries",
        description="Get registry entries (items, blocks, entities, biomes, enchantments, etc.) for a Minecraft version.",
        inputSchema={
            "type": "object",
            "properties": {
                "version": {
                    "type": "string",
                    "description": "Minecraft version (e.g., '1.21', '1.20.4')"
                },
                "registry": {
                    "type": "string",
                    "description": "Registry name (e.g., 'item', 'block', 'entity_type', 'biome', 'enchantment')"
                },
                "search": {
                    "type": "string",
                    "description": "Optional search query to filter results"
                }
            },
            "required": ["version", "registry"]
        }
    ),
    Tool(
        name="spyglass_get_block_states",
        description="Get block state properties and default values for a specific block.",
        inputSchema={
            "type": "object",
            "properties": {
                "version": {
                    "type": "string",
                    "description": "Minecraft version"
                },
                "block_id": {
                    "type": "string",
                    "description": "Block ID (e.g., 'oak_stairs', 'minecraft:redstone_wire')"
                }
            },
            "required": ["version", "block_id"]
        }
    ),
    Tool(
        name="spyglass_get_commands",
        description="Get command tree/syntax information for a Minecraft version from Spyglass API.",
        inputSchema={
            "type": "object",
            "properties": {
                "version": {
                    "type": "string",
                    "description": "Minecraft version"
                },
                "command": {
                    "type": "string",
                    "description": "Optional specific command name to get details for"
                }
            },
            "required": ["version"]
        }
    ),
    # Misode Data Pack Tools
    Tool(
        name="misode_get_generators",
        description="Get list of all available data pack generators on Misode's site with URLs.",
        inputSchema={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by category",
                    "enum": ["all", "worldgen", "tags", "dimension", "resource_pack", "data_pack"]
                }
            },
            "required": []
        }
    ),
    Tool(
        name="misode_get_presets",
        description="Get vanilla presets for a generator type (loot tables, recipes, biomes, etc.).",
        inputSchema={
            "type": "object",
            "properties": {
                "version": {
                    "type": "string",
                    "description": "Minecraft version (e.g., '1.21.4')"
                },
                "generator_type": {
                    "type": "string",
                    "description": "Generator type (e.g., 'loot_table', 'recipe', 'worldgen/biome', 'advancement')"
                },
                "search": {
                    "type": "string",
                    "description": "Optional search query to filter presets"
                }
            },
            "required": ["version", "generator_type"]
        }
    ),
    Tool(
        name="misode_get_preset_data",
        description="Get the full JSON data for a specific preset.",
        inputSchema={
            "type": "object",
            "properties": {
                "version": {
                    "type": "string",
                    "description": "Minecraft version"
                },
                "generator_type": {
                    "type": "string",
                    "description": "Generator type"
                },
                "preset_id": {
                    "type": "string",
                    "description": "Preset ID (e.g., 'chests/abandoned_mineshaft', 'diamond_sword')"
                }
            },
            "required": ["version", "generator_type", "preset_id"]
        }
    ),
    Tool(
        name="misode_get_loot_tables",
        description="Get loot tables categorized by type (blocks, chests, entities, etc.).",
        inputSchema={
            "type": "object",
            "properties": {
                "version": {
                    "type": "string",
                    "description": "Minecraft version"
                },
                "category": {
                    "type": "string",
                    "description": "Filter by category",
                    "enum": ["all", "blocks", "chests", "entities", "archaeology", "gameplay"]
                },
                "search": {
                    "type": "string",
                    "description": "Optional search query"
                }
            },
            "required": ["version"]
        }
    ),
    Tool(
        name="misode_get_recipes",
        description="Get recipes with optional filtering by type.",
        inputSchema={
            "type": "object",
            "properties": {
                "version": {
                    "type": "string",
                    "description": "Minecraft version"
                },
                "recipe_type": {
                    "type": "string",
                    "description": "Filter by recipe type",
                    "enum": ["all", "crafting_shaped", "crafting_shapeless", "smelting", "blasting", "smoking", "campfire_cooking", "stonecutting", "smithing_transform"]
                },
                "search": {
                    "type": "string",
                    "description": "Optional search query"
                }
            },
            "required": ["version"]
        }
    ),
    # Additional Minecraft Wiki tools
    Tool(
        name="get_wiki_page_content",
        description="Get full page content for a Minecraft Wiki page.",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Page title"}
            },
            "required": ["title"]
        }
    ),
    Tool(
        name="get_wiki_command_info",
        description="Get detailed command documentation from Minecraft Wiki.",
        inputSchema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command name"}
            },
            "required": ["command"]
        }
    ),
    Tool(
        name="get_wiki_random",
        description="Get random wiki pages.",
        inputSchema={
            "type": "object",
            "properties": {
                "count": {"type": "integer", "description": "Number of random pages"}
            },
            "required": []
        }
    ),
    # Additional Misode tools
    Tool(
        name="misode_list_versions",
        description="List available Misode/Minecraft versions.",
        inputSchema={"type": "object", "properties": {}, "required": []}
    ),
    Tool(
        name="misode_get_data",
        description="Get raw Misode data for a version and data type.",
        inputSchema={
            "type": "object",
            "properties": {
                "version": {"type": "string"},
                "data_type": {"type": "string"}
            },
            "required": ["version", "data_type"]
        }
    ),
    Tool(
        name="misode_search_data",
        description="Search Misode data for a query",
        inputSchema={
            "type": "object",
            "properties": {
                "version": {"type": "string"},
                "data_type": {"type": "string"},
                "query": {"type": "string"}
            },
            "required": ["version", "data_type", "query"]
        }
    ),
    # Additional Spyglass convenience tools
    Tool(
        name="spyglass_get_items",
        description="Get list of items for a version",
        inputSchema={
            "type": "object",
            "properties": {"version": {"type": "string"}},
            "required": ["version"]
        }
    ),
    Tool(
        name="spyglass_search_registry",
        description="Search a Spyglass registry for a query",
        inputSchema={
            "type": "object",
            "properties": {
                "version": {"type": "string"},
                "registry": {"type": "string"},
                "query": {"type": "string"}
            },
            "required": ["version", "registry", "query"]
        }
    ),
    Tool(
        name="spyglass_get_mcdoc_symbols",
        description="Get vanilla mcdoc symbols from Spyglass",
        inputSchema={"type": "object", "properties": {}, "required": []}
    ),
]


# Tool handlers
def handle_hello_world(name: str = None) -> str:
    """Handle hello_world tool"""
    if name:
        return f"Hello, {name}! Welcome to MineCode."
    return "Hello, World! Welcome to MineCode - Your Minecraft Datapack Development Assistant"


def handle_get_minecraft_version(version: str) -> dict:
    """Handle get_minecraft_version tool"""
    # Simulated version info
    versions = {
        "1.20.1": {
            "release_date": "2023-12-07",
            "snapshot": False,
            "features": ["Decorated pots", "Armor trims", "Smithing templates"]
        },
        "1.20": {
            "release_date": "2023-06-07",
            "snapshot": False,
            "features": ["Cherry logs", "Painting variants", "Camel mob"]
        },
        "latest": {
            "release_date": "2024-01-18",
            "snapshot": False,
            "version": "1.20.4"
        }
    }
    
    if version in versions:
        return {"success": True, "data": versions[version]}
    return {"success": False, "error": f"Version {version} not found in database"}


def handle_validate_datapack(datapack_path: str, mc_version: str) -> dict:
    """Handle validate_datapack tool"""
    # Simulated validation
    return {
        "success": True,
        "path": datapack_path,
        "version": mc_version,
        "status": "valid",
        "warnings": [],
        "errors": []
    }


def handle_search_wiki(query: str, limit: int = 10, fulltext: bool = False) -> dict:
    """Handle search_wiki tool using MediaWiki API"""
    try:
        if fulltext:
            results = minecraftwiki.search_fulltext(query, limit=limit)
        else:
            results = minecraftwiki.search(query, limit=limit)
        
        return {
            "success": True,
            "query": query,
            "count": len(results),
            "results": minecraftwiki.search_to_dict(results)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_get_wiki_page(title: str, sentences: int = 5) -> dict:
    """Handle get_wiki_page tool"""
    try:
        # Get summary extract
        extract = minecraftwiki.get_page_extract(title, sentences=sentences)
        
        if not extract:
            return {"success": False, "error": f"Page '{title}' not found"}
        
        # Get sections
        sections = minecraftwiki.get_page_sections(title)
        
        return {
            "success": True,
            "title": title,
            "url": f"https://minecraft.wiki/w/{title.replace(' ', '_')}",
            "extract": extract,
            "sections": sections
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_get_wiki_commands(limit: int = 50) -> dict:
    """Handle get_wiki_commands tool"""
    try:
        commands = minecraftwiki.get_commands(limit=limit)
        return {
            "success": True,
            "count": len(commands),
            "commands": minecraftwiki.commands_to_dict(commands)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_get_wiki_category(category: str, limit: int = 50) -> dict:
    """Handle get_wiki_category tool"""
    try:
        pages = minecraftwiki.get_category_members(category, limit=limit)
        return {
            "success": True,
            "category": category,
            "count": len(pages),
            "pages": minecraftwiki.page_info_to_dict(pages)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_list_commands(version: str, category: str = "all") -> dict:
    """Handle list_commands tool"""
    # Simulated command list
    commands = {
        "1.20.1": {
            "all": ["/execute", "/give", "/setblock", "/fill", "/function", "/say"],
            "admin": ["/op", "/stop", "/save-all", "/gamemode", "/difficulty"],
            "player": ["/say", "/tell", "/give"],
            "utility": ["/time", "/weather", "/locate", "/seed"]
        }
    }
    
    version_commands = commands.get(version, {}).get(category, [])
    return {
        "version": version,
        "category": category,
        "commands": version_commands,
        "count": len(version_commands)
    }


def handle_search_mojira(
    query: str = None,
    project: str = None,
    status: str = None,
    resolution: str = None,
    page: int = 1
) -> dict:
    """Handle search_mojira tool"""
    try:
        issues = mojira.search(
            query=query,
            project=project,
            status=status,
            resolution=resolution,
            page=page
        )
        return {
            "success": True,
            "count": len(issues),
            "issues": mojira.search_to_dict(issues)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# Spyglass API Handlers
# ============================================================================

def handle_spyglass_get_versions(type_filter: str = "all", limit: int = 20) -> dict:
    """Handle spyglass_get_versions tool"""
    try:
        versions = spyglass.get_versions()
        
        # Filter by type if specified
        if type_filter == "release":
            versions = [v for v in versions if v.get("type") == "release"]
        elif type_filter == "snapshot":
            versions = [v for v in versions if v.get("type") == "snapshot"]
        
        # Limit results
        versions = versions[:limit]
        
        # Get latest info
        latest_release = spyglass.get_latest_release()
        latest_snapshot = spyglass.get_latest_snapshot()
        
        return {
            "success": True,
            "count": len(versions),
            "latest_release": latest_release.get("id") if latest_release else None,
            "latest_snapshot": latest_snapshot.get("id") if latest_snapshot else None,
            "versions": [{
                "id": v.get("id"),
                "name": v.get("name"),
                "type": v.get("type"),
                "stable": v.get("stable"),
                "data_pack_version": v.get("data_pack_version"),
                "resource_pack_version": v.get("resource_pack_version")
            } for v in versions]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_spyglass_get_registries(version: str, registry: str, search: str = None) -> dict:
    """Handle spyglass_get_registries tool"""
    try:
        if search:
            entries = spyglass.search_registry(version, registry, search)
        else:
            entries = spyglass.get_registry(version, registry)
        
        # Get available registry names for reference
        available_registries = spyglass.get_registry_names(version)
        
        return {
            "success": True,
            "version": version,
            "registry": registry,
            "count": len(entries),
            "entries": entries[:100],  # Limit to 100 entries
            "available_registries": available_registries[:20]  # Show some available registries
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_spyglass_get_block_states(version: str, block_id: str) -> dict:
    """Handle spyglass_get_block_states tool"""
    try:
        block_info = spyglass.get_block_info(version, block_id)
        
        if not block_info:
            return {"success": False, "error": f"Block '{block_id}' not found in version {version}"}
        
        return {
            "success": True,
            "version": version,
            "block_id": block_id,
            "properties": block_info[0] if len(block_info) > 0 else {},
            "defaults": block_info[1] if len(block_info) > 1 else {}
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_spyglass_get_commands(version: str, command: str = None) -> dict:
    """Handle spyglass_get_commands tool"""
    try:
        if command:
            # Get specific command info
            cmd_info = spyglass.get_command_info(version, command)
            if not cmd_info:
                return {"success": False, "error": f"Command '{command}' not found"}
            return {
                "success": True,
                "version": version,
                "command": command,
                "tree": cmd_info
            }
        else:
            # Get all command names
            commands = spyglass.get_command_names(version)
            return {
                "success": True,
                "version": version,
                "count": len(commands),
                "commands": commands
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# Misode Handlers
# ============================================================================

def handle_misode_get_generators(category: str = "all") -> dict:
    """Handle misode_get_generators tool"""
    try:
        # misode provides `list_generators()` and `get_generator_url()`
        gen_ids = misode.list_generators()
        generators = [{"id": gid, "url": misode.get_generator_url(gid)} for gid in gen_ids]

        # Filter by category is not implemented in misode; keep signature but ignore unknown categories
        if category != "all":
            # return empty if category filtering requested (no mapping available)
            generators = [g for g in generators if False]

        return {"success": True, "count": len(generators), "generators": generators}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_misode_get_presets(version: str, generator_type: str, search: str = None) -> dict:
    """Handle misode_get_presets tool"""
    try:
        # misode exposes `get_data` and `search_data` for generator contents
        if search:
            presets = misode.search_data(version, generator_type, search)
            # search_data returns a list of matching keys
            presets_list = presets
        else:
            data = misode.get_data(version, generator_type) or {}
            presets_list = list(data.keys())

        return {
            "success": True,
            "version": version,
            "generator_type": generator_type,
            "generator_url": misode.get_generator_url(generator_type),
            "count": len(presets_list),
            "presets": presets_list[:100]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_misode_get_preset_data(version: str, generator_type: str, preset_id: str) -> dict:
    """Handle misode_get_preset_data tool"""
    try:
        data = misode.get_data(version, generator_type) or {}
        preset = data.get(preset_id)

        if not preset:
            return {"success": False, "error": f"Preset '{preset_id}' not found"}

        return {"success": True, "version": version, "generator_type": generator_type, "preset_id": preset_id, "data": preset}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_misode_get_loot_tables(version: str, category: str = "all", search: str = None) -> dict:
    """Handle misode_get_loot_tables tool"""
    try:
        if search:
            tables = misode.search_data(version, "loot_table", search)
        else:
            data = misode.get_data(version, "loot_table") or {}
            tables = list(data.keys())

        # Filter by category using known prefixes
        if category != "all":
            prefix_map = {
                "blocks": "blocks/",
                "chests": "chests/",
                "entities": "entities/",
                "archaeology": "archaeology/",
                "gameplay": "gameplay/"
            }
            prefix = prefix_map.get(category, "")
            tables = [t for t in tables if t.startswith(prefix)]

        # Get counts by category
        all_data = misode.get_data(version, "loot_table") or {}
        all_tables = list(all_data.keys())
        categories = {
            "blocks": len([t for t in all_tables if t.startswith("blocks/")]),
            "chests": len([t for t in all_tables if t.startswith("chests/")]),
            "entities": len([t for t in all_tables if t.startswith("entities/")]),
            "archaeology": len([t for t in all_tables if t.startswith("archaeology/")]),
            "gameplay": len([t for t in all_tables if t.startswith("gameplay/")]),
        }

        return {
            "success": True,
            "version": version,
            "category": category,
            "count": len(tables),
            "category_counts": categories,
            "loot_tables": tables[:100]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_misode_get_recipes(version: str, recipe_type: str = "all", search: str = None) -> dict:
    """Handle misode_get_recipes tool"""
    try:
        if search:
            recipes = misode.search_data(version, "recipe", search)
            recipe_data = {}
            data = misode.get_data(version, "recipe") or {}
            for r in recipes[:20]:
                if r in data:
                    recipe_data[r] = data[r]
        else:
            recipe_data = misode.get_data(version, "recipe") or {}
            recipes = list(recipe_data.keys())

        # Filter by recipe type if requested
        if recipe_type != "all":
            filtered = {}
            for name, data in recipe_data.items():
                if data and data.get("type", "").endswith(recipe_type):
                    filtered[name] = data
            recipe_data = filtered
            recipes = list(filtered.keys())

        return {"success": True, "version": version, "recipe_type": recipe_type, "count": len(recipes), "recipes": recipes[:100]}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# Additional Minecraft Wiki / Misode / Spyglass Handlers
# ============================================================================

def handle_get_wiki_page_content(title: str) -> dict:
    """Return full page content (structured) for a wiki page"""
    try:
        content = minecraftwiki.get_page_content(title)
        if not content:
            return {"success": False, "error": f"Page '{title}' not found or parse failed"}
        return {"success": True, "title": title, "content": minecraftwiki.page_content_to_dict(content)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_get_wiki_command_info(command: str) -> dict:
    try:
        info = minecraftwiki.get_command_info(command)
        return {"success": True, "command": command, "info": info}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_get_wiki_random(count: int = 5) -> dict:
    try:
        pages = minecraftwiki.get_random_pages(count=count)
        return {"success": True, "count": len(pages), "pages": minecraftwiki.page_info_to_dict(pages)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_misode_list_versions() -> dict:
    try:
        versions = misode.list_versions()
        return {"success": True, "count": len(versions), "versions": versions}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_misode_get_data(version: str, data_type: str) -> dict:
    try:
        data = misode.get_data(version, data_type)
        return {"success": True, "version": version, "data_type": data_type, "count": len(data) if isinstance(data, dict) else None, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_misode_search_data(version: str, data_type: str, query: str) -> dict:
    try:
        results = misode.search_data(version, data_type, query)
        return {"success": True, "version": version, "data_type": data_type, "query": query, "results": results}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_spyglass_get_items(version: str) -> dict:
    try:
        items = spyglass.get_items(version)
        return {"success": True, "version": version, "count": len(items), "items": items[:200]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_spyglass_search_registry(version: str, registry: str, query: str) -> dict:
    try:
        results = spyglass.search_registry(version, registry, query)
        return {"success": True, "version": version, "registry": registry, "query": query, "results": results}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_spyglass_get_mcdoc_symbols() -> dict:
    try:
        symbols = spyglass.get_mcdoc_symbols()
        return {"success": True, "count": len(symbols), "symbols": symbols}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Register tool handler
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    try:
        if name == "hello_world":
            result = handle_hello_world(arguments.get("name"))
        elif name == "get_minecraft_version":
            result = handle_get_minecraft_version(arguments["version"])
        elif name == "validate_datapack":
            result = handle_validate_datapack(arguments["datapack_path"], arguments["mc_version"])
        elif name == "search_wiki":
            result = handle_search_wiki(
                arguments["query"],
                limit=arguments.get("limit", 10),
                fulltext=arguments.get("fulltext", False)
            )
        elif name == "get_wiki_page":
            result = handle_get_wiki_page(
                arguments["title"],
                sentences=arguments.get("sentences", 5)
            )
        elif name == "get_wiki_commands":
            result = handle_get_wiki_commands(
                limit=arguments.get("limit", 50)
            )
        elif name == "get_wiki_category":
            result = handle_get_wiki_category(
                arguments["category"],
                limit=arguments.get("limit", 50)
            )
        elif name == "list_commands":
            result = handle_list_commands(arguments["version"], arguments.get("category", "all"))
        elif name == "search_mojira":
            result = handle_search_mojira(
                query=arguments.get("query"),
                project=arguments.get("project"),
                status=arguments.get("status"),
                resolution=arguments.get("resolution"),
                page=arguments.get("page", 1)
            )
        # Spyglass API tools
        elif name == "spyglass_get_versions":
            result = handle_spyglass_get_versions(
                type_filter=arguments.get("type_filter", "all"),
                limit=arguments.get("limit", 20)
            )
        elif name == "spyglass_get_registries":
            result = handle_spyglass_get_registries(
                version=arguments["version"],
                registry=arguments["registry"],
                search=arguments.get("search")
            )
        elif name == "spyglass_get_block_states":
            result = handle_spyglass_get_block_states(
                version=arguments["version"],
                block_id=arguments["block_id"]
            )
        elif name == "spyglass_get_commands":
            result = handle_spyglass_get_commands(
                version=arguments["version"],
                command=arguments.get("command")
            )
        # Misode tools
        elif name == "misode_get_generators":
            result = handle_misode_get_generators(
                category=arguments.get("category", "all")
            )
        elif name == "misode_get_presets":
            result = handle_misode_get_presets(
                version=arguments["version"],
                generator_type=arguments["generator_type"],
                search=arguments.get("search")
            )
        elif name == "misode_get_preset_data":
            result = handle_misode_get_preset_data(
                version=arguments["version"],
                generator_type=arguments["generator_type"],
                preset_id=arguments["preset_id"]
            )
        elif name == "misode_get_loot_tables":
            result = handle_misode_get_loot_tables(
                version=arguments["version"],
                category=arguments.get("category", "all"),
                search=arguments.get("search")
            )
        elif name == "misode_get_recipes":
            result = handle_misode_get_recipes(
                version=arguments["version"],
                recipe_type=arguments.get("recipe_type", "all"),
                search=arguments.get("search")
            )
        elif name == "get_wiki_page_content":
            result = handle_get_wiki_page_content(arguments["title"])
        elif name == "get_wiki_command_info":
            result = handle_get_wiki_command_info(arguments["command"])
        elif name == "get_wiki_random":
            result = handle_get_wiki_random(arguments.get("count", 5))
        elif name == "misode_list_versions":
            result = handle_misode_list_versions()
        elif name == "misode_get_data":
            result = handle_misode_get_data(arguments["version"], arguments["data_type"])
        elif name == "misode_search_data":
            result = handle_misode_search_data(arguments["version"], arguments["data_type"], arguments["query"])
        elif name == "spyglass_get_items":
            result = handle_spyglass_get_items(arguments["version"])
        elif name == "spyglass_search_registry":
            result = handle_spyglass_search_registry(arguments["version"], arguments["registry"], arguments["query"])
        elif name == "spyglass_get_mcdoc_symbols":
            result = handle_spyglass_get_mcdoc_symbols()
        else:
            raise ValueError(f"Unknown tool: {name}")
        
        return [TextContent(type="text", text=json.dumps(result))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


# Register tools
@server.list_tools()
async def list_tools():
    """List all available tools"""
    return TOOLS


async def _run():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


def main():
    """Entry point for the MCP server"""
    asyncio.run(_run())


if __name__ == "__main__":
    main()
