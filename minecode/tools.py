"""
MCP tool definitions and the name -> handler registry.

Two things live here on purpose:

  TOOLS    -- the schemas advertised to the client
  HANDLERS -- the name -> callable map the dispatcher uses

Keeping them adjacent, plus the equality assertion at the bottom of this
module, makes it impossible to ship a tool with no handler or a handler with no
tool. That failure mode is not hypothetical: four working changelog functions
sat in misode.py unreachable because the old 19-branch if/elif dispatcher had
to be kept in sync by hand and wasn't.

Description style, learned from what actually goes wrong:

  * Say WHEN to call it, not just what it does. Agents pick tools by matching
    situation to description.
  * Put limitations FIRST. A caveat at the end of a long description is not
    read in time to change the decision.
  * Name the better tool when one exists. "Use X instead for Y" prevents the
    wrong-tool choice that a neutral description invites.
"""

from __future__ import annotations

from mcp.types import Tool

from . import handlers

# Reused so the warning is worded identically everywhere. Divergent phrasings
# of the same caveat read as different caveats.
_WIKI_CAVEAT = (
    "LATEST VERSION ONLY -- minecraft.wiki keeps no per-version history. "
    "Use for CONCEPTS and mechanics. Do NOT use for syntax, JSON schemas, NBT "
    "structure, or IDs unless your target IS the current release; for those use "
    "get_command_usage, spyglass_get_registries, or misode_get_preset_data. "
)

_VERSION_ARG = {
    "type": "string",
    "description": (
        "Minecraft version, e.g. '1.21.4', '1.20.4'. Also accepts 'latest', or a "
        "partial like '1.21' which resolves to the newest release on that line. "
        "Get the project's real version from detect_pack_version -- do not guess."
    ),
}


TOOLS = [
    # -----------------------------------------------------------------------
    # Session bootstrap
    # -----------------------------------------------------------------------
    Tool(
        name="minecraft_start_session",
        description=(
            "CALL THIS FIRST, before reading or writing any Minecraft datapack, "
            "resource pack, or mcfunction file. Detects the project's target "
            "Minecraft version from pack.mcmeta and returns that version, the "
            "breaking changes that apply to it, and the workflow to follow. "
            "Minecraft's syntax changed substantially in recent versions (items "
            "moved from NBT to components, datapack folders were renamed, text "
            "components became strictly typed). Your training data predates some "
            "of this. Skipping this step is the single most common cause of "
            "confidently-written, version-wrong output."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "workspace_path": {
                    "type": "string",
                    "description": "Path to the datapack root or a directory above it. Defaults to the current directory.",
                },
            },
            "required": [],
        },
    ),

    # -----------------------------------------------------------------------
    # Version awareness
    # -----------------------------------------------------------------------
    Tool(
        name="get_technical_changes",
        description=(
            "THE FIX FOR OUTDATED SYNTAX KNOWLEDGE. Returns every technical change "
            "to the datapack and resource pack format between two Minecraft "
            "versions -- renamed fields, moved registries, changed JSON schemas, "
            "format migrations such as item NBT becoming components (1.20.5), "
            "datapack folders becoming singular (1.21), and text components "
            "becoming strictly typed (1.21.5). "
            "CALL THIS BEFORE writing item components, text components, loot "
            "tables, predicates, recipes, or advancements -- and any time your "
            "recollection of Minecraft syntax might predate the target version. "
            "Combines a curated table of the traps agents fall into most with the "
            "full community-maintained changelog."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "to_version": {
                    "type": "string",
                    "description": "Target version -- the version the pack is being written for.",
                },
                "from_version": {
                    "type": "string",
                    "description": (
                        "Optional lower bound. Omit to get everything that applies "
                        "to to_version, which is what you want when starting cold."
                    ),
                },
                "topic": {
                    "type": "string",
                    "description": "Optional filter, e.g. 'component', 'text', 'loot', 'recipe', 'predicate', 'attribute'.",
                },
            },
            "required": ["to_version"],
        },
    ),

    Tool(
        name="check_version_syntax",
        description=(
            "Scan a command, JSON document, or NBT snippet for syntax that is "
            "wrong for a target Minecraft version, and get the correct "
            "replacement. RUN THIS ON EVERYTHING YOU WRITE before saving it. "
            "Fast and offline. Note it is a pre-filter over a curated table, not a "
            "parser -- a clean result means no KNOWN trap matched, not that the "
            "content is valid. Use validate_command for real command checking."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The content to check."},
                "version": _VERSION_ARG,
                "kind": {
                    "type": "string",
                    "description": "What kind of content this is.",
                    "enum": ["command", "json", "nbt", "mcfunction", "any"],
                },
            },
            "required": ["content", "version"],
        },
    ),

    Tool(
        name="check_pack_structure",
        description=(
            "Check a datapack's FOLDER LAYOUT against its target version. "
            "In 1.21 every datapack directory was renamed to singular "
            "(advancements/ became advancement/, recipes/ became recipe/, and so "
            "on). A pack using the old plural folders loads with NO ERROR and NO "
            "CONTENT -- it simply does nothing, which makes this hard to diagnose "
            "from logs. Run this whenever a datapack 'does nothing' on 1.21+."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Pack root. Defaults to the current directory."},
                "version": {"type": "string", "description": "Target version. Auto-detected from pack.mcmeta if omitted."},
            },
            "required": [],
        },
    ),

    Tool(
        name="detect_pack_version",
        description=(
            "Read pack.mcmeta and return the target Minecraft version, pack "
            "format, supported format range, and pack type. Every version-taking "
            "tool needs a version, and this is where it comes from -- call this "
            "rather than assuming the latest release, since most existing packs "
            "target something older."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Pack root, a directory above it, or a pack.mcmeta path. Defaults to the current directory."},
            },
            "required": [],
        },
    ),

    Tool(
        name="pack_format_to_version",
        description=(
            "Map a pack_format number to the Minecraft versions using it. Use when "
            "you have a pack.mcmeta but need the version name it corresponds to. "
            "Data pack and resource pack formats are numbered separately -- pass "
            "the right `kind` or you will get the wrong version."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "pack_format": {"type": "integer", "description": "The pack_format number, e.g. 61."},
                "kind": {"type": "string", "description": "Which numbering scheme.", "enum": ["data", "resource"]},
            },
            "required": ["pack_format"],
        },
    ),

    Tool(
        name="version_to_pack_format",
        description=(
            "Get the data and resource pack format numbers for a Minecraft "
            "version. Use when writing a new pack.mcmeta -- a wrong pack_format "
            "makes the game refuse or warn about the pack."
        ),
        inputSchema={
            "type": "object",
            "properties": {"version": _VERSION_ARG},
            "required": ["version"],
        },
    ),

    Tool(
        name="list_technical_change_versions",
        description=(
            "List the Minecraft versions with available technical changelogs. Use "
            "to check coverage before relying on get_technical_changes for an "
            "unusual or very old version."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),

    # -----------------------------------------------------------------------
    # Commands
    # -----------------------------------------------------------------------
    Tool(
        name="get_command_usage",
        description=(
            "Get READABLE, VERSION-EXACT syntax for a Minecraft command, compiled "
            "from the game's own Brigadier grammar -- e.g. "
            "'/give <targets> <item> [<count>]' plus what each argument accepts. "
            "USE THIS INSTEAD OF RECALLING COMMAND SYNTAX. Command arguments change "
            "between versions and remembered syntax is the main source of broken "
            "commands. Prefer this over get_wiki_command_explanation, which covers "
            "the latest release only."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "version": _VERSION_ARG,
                "command": {"type": "string", "description": "Command name without the slash, e.g. 'give', 'execute'."},
                "max_lines": {"type": "integer", "description": "Cap on usage forms returned (default 60). /execute has thousands."},
            },
            "required": ["version", "command"],
        },
    ),

    Tool(
        name="validate_command",
        description=(
            "Parse a command against the real Brigadier grammar for a version and "
            "report whether it is valid, with the failing token and what was "
            "expected there. RUN THIS ON EVERY COMMAND YOU WRITE before saving it "
            "to an .mcfunction file. Catching an error here costs one tool call; "
            "catching it after the user runs the pack costs a debugging session."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The command, with or without a leading slash."},
                "version": _VERSION_ARG,
            },
            "required": ["command", "version"],
        },
    ),

    # -----------------------------------------------------------------------
    # Spyglass -- authoritative, version-exact
    # -----------------------------------------------------------------------
    Tool(
        name="spyglass_get_versions",
        description=(
            "List Minecraft Java Edition versions with their data and resource "
            "pack format numbers. Use to discover valid version strings or find "
            "the latest release."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "type_filter": {"type": "string", "description": "Filter by version type.", "enum": ["all", "release", "snapshot"]},
                "limit": {"type": "integer", "description": "Max versions to return (default 20)."},
            },
            "required": [],
        },
    ),

    Tool(
        name="spyglass_get_registries",
        description=(
            "Get the exact list of valid IDs in a registry for a specific version "
            "-- items, blocks, entity types, biomes, enchantments, attributes, "
            "particles, and more. AUTHORITATIVE: use this to confirm an ID exists "
            "in the target version rather than assuming. IDs are added and renamed "
            "between versions (attributes lost their generic. prefix in 1.21.2). "
            "An unknown registry name returns the valid list."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "version": _VERSION_ARG,
                "registry": {"type": "string", "description": "Registry name, e.g. 'item', 'block', 'entity_type', 'biome', 'enchantment', 'attribute'."},
                "search": {"type": "string", "description": "Optional case-insensitive substring filter. Use it -- registries have thousands of entries."},
            },
            "required": ["version", "registry"],
        },
    ),

    Tool(
        name="spyglass_get_block_states",
        description=(
            "Get every block state property (facing, waterlogged, power, half, ...) "
            "and its default value for one block, in a specific version. Use before "
            "writing a block state in /setblock, /fill, or a predicate -- an "
            "invalid property silently fails to match."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "version": _VERSION_ARG,
                "block_id": {"type": "string", "description": "Block ID, e.g. 'oak_stairs' or 'minecraft:redstone_wire'."},
            },
            "required": ["version", "block_id"],
        },
    ),

    Tool(
        name="spyglass_get_commands",
        description=(
            "List all commands in a version, or get one command's raw Brigadier "
            "tree plus rendered usage. For readable syntax alone, prefer "
            "get_command_usage -- this tool's raw tree is large and only worth "
            "requesting when you need the exact parser types."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "version": _VERSION_ARG,
                "command": {"type": "string", "description": "Optional command name. Omit to list all command names."},
            },
            "required": ["version"],
        },
    ),

    Tool(
        name="spyglass_search_mcdoc_symbols",
        description=(
            "Search for mcdoc symbol paths by keyword. mcdoc is the machine-"
            "readable type definition for every Minecraft data structure -- item "
            "components, NBT, loot tables, predicates, text components. Returns "
            "paths only. Use this first when you do not know a symbol's full path, "
            "then call spyglass_get_mcdoc_symbol for the definition."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword, e.g. 'ItemStack', 'LootTable', 'Text', 'AttributeModifiers'."},
                "limit": {"type": "integer", "description": "Max paths to return (default 40)."},
            },
            "required": ["query"],
        },
    ),

    Tool(
        name="spyglass_get_mcdoc_symbol",
        description=(
            "Get the exact field-level schema of one Minecraft data structure from "
            "mcdoc -- which fields exist, their types, and which are optional. "
            "THE AUTHORITY on 'what fields does this accept'. Use when writing item "
            "components, NBT, or any datapack JSON whose shape you are unsure of. "
            "Find the path with spyglass_search_mcdoc_symbols first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Fully-qualified path, e.g. 'java::world::item::ItemStack'. A unique tail name also works."},
                "depth": {"type": "integer", "description": "Levels of nested types to expand (1-6, default 3). Raise only if the answer is truncated."},
            },
            "required": ["symbol"],
        },
    ),

    # -----------------------------------------------------------------------
    # Misode -- vanilla presets per version
    # -----------------------------------------------------------------------
    Tool(
        name="misode_get_preset_data",
        description=(
            "Get the real vanilla JSON for a preset in a specific version -- an "
            "actual loot table, recipe, biome, or advancement as Mojang ships it. "
            "THE BEST SHAPE REFERENCE AVAILABLE: matching a real vanilla file for "
            "the target version beats recalling the schema, because it is correct "
            "by construction. Discover preset IDs with misode_get_presets."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "version": _VERSION_ARG,
                "generator_type": {"type": "string", "description": "e.g. 'loot_table', 'recipe', 'advancement', 'worldgen/biome'."},
                "preset_id": {"type": "string", "description": "e.g. 'chests/simple_dungeon', 'diamond_sword'."},
            },
            "required": ["version", "generator_type", "preset_id"],
        },
    ),

    Tool(
        name="misode_get_presets",
        description=(
            "List vanilla preset IDs for a generator type in a version. Use to "
            "find a preset worth copying, then fetch it with "
            "misode_get_preset_data."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "version": _VERSION_ARG,
                "generator_type": {"type": "string", "description": "e.g. 'loot_table', 'recipe', 'worldgen/biome', 'advancement'."},
                "search": {"type": "string", "description": "Optional substring filter."},
            },
            "required": ["version", "generator_type"],
        },
    ),

    Tool(
        name="misode_get_loot_tables",
        description=(
            "List vanilla loot table IDs by category (blocks, chests, entities, "
            "archaeology, gameplay) for a version. Convenience wrapper over "
            "misode_get_presets for the most-used data type. Fetch a table's JSON "
            "with misode_get_preset_data."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "version": _VERSION_ARG,
                "category": {"type": "string", "description": "Filter by category.", "enum": ["all", "blocks", "chests", "entities", "archaeology", "gameplay"]},
                "search": {"type": "string", "description": "Optional substring filter."},
            },
            "required": ["version"],
        },
    ),

    Tool(
        name="misode_get_recipes",
        description=(
            "List vanilla recipe IDs for a version, optionally filtered by recipe "
            "type. Convenience wrapper over misode_get_presets. Note the recipe "
            "format changed in 1.20.5 (result.item became result.id) -- check "
            "get_technical_changes before writing recipes for a version you have "
            "not worked in."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "version": _VERSION_ARG,
                "recipe_type": {"type": "string", "description": "Filter by type.", "enum": ["all", "crafting_shaped", "crafting_shapeless", "smelting", "blasting", "smoking", "campfire_cooking", "stonecutting", "smithing_transform"]},
                "search": {"type": "string", "description": "Optional substring filter."},
            },
            "required": ["version"],
        },
    ),

    Tool(
        name="misode_get_generators",
        description=(
            "List Misode's web-based datapack generators with their URLs. These "
            "are links to SHOW THE USER when a visual editor would serve them "
            "better than hand-written JSON (complex worldgen especially). They are "
            "not APIs -- do not fetch them. For vanilla JSON use "
            "misode_get_preset_data."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Optional substring filter over generator names, or 'all'."},
            },
            "required": [],
        },
    ),

    Tool(
        name="misode_list_versions",
        description="List Minecraft versions with vanilla data available through Misode.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),

    # -----------------------------------------------------------------------
    # Minecraft Wiki -- latest version only
    # -----------------------------------------------------------------------
    Tool(
        name="search_wiki",
        description=(
            _WIKI_CAVEAT +
            "Search minecraft.wiki for pages. Good for finding an explanation of a "
            "game mechanic."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
                "limit": {"type": "integer", "description": "Max results (default 10)."},
                "fulltext": {"type": "boolean", "description": "Full-text search with snippets (default false)."},
            },
            "required": ["query"],
        },
    ),

    Tool(
        name="get_wiki_page",
        description=(
            _WIKI_CAVEAT +
            "Get a wiki page as a summary, or in full with full=true. Good for "
            "understanding how a mechanic works."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Page title, e.g. 'Creeper', 'Raid'."},
                "full": {"type": "boolean", "description": "Return the complete structured page instead of a summary (default false)."},
                "sentences": {"type": "integer", "description": "Summary length in sentences (default 5). Ignored when full=true."},
            },
            "required": ["title"],
        },
    ),

    Tool(
        name="get_wiki_command_explanation",
        description=(
            _WIKI_CAVEAT +
            "Get PROSE explanation of what a command does and how it behaves. "
            "This is NOT a syntax reference -- for syntax use get_command_usage, "
            "which is version-exact and compiled from the game's own grammar."
        ),
        inputSchema={
            "type": "object",
            "properties": {"command": {"type": "string", "description": "Command name."}},
            "required": ["command"],
        },
    ),

    Tool(
        name="get_wiki_commands",
        description=(
            _WIKI_CAVEAT +
            "List Minecraft commands from the wiki. For the command list of a "
            "SPECIFIC version use spyglass_get_commands instead."
        ),
        inputSchema={
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Max commands (default 50)."}},
            "required": [],
        },
    ),

    Tool(
        name="get_wiki_category",
        description=(
            _WIKI_CAVEAT +
            "List pages in a wiki category, e.g. 'Blocks', 'Items', 'Mobs'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Category name."},
                "limit": {"type": "integer", "description": "Max results (default 50)."},
            },
            "required": ["category"],
        },
    ),

    # -----------------------------------------------------------------------
    # Mojira
    # -----------------------------------------------------------------------
    Tool(
        name="search_mojira",
        description=(
            "Search the Mojira bug tracker. Use to check whether behaviour the "
            "user reports is a known Mojang bug rather than a datapack error -- "
            "worth checking before a long debugging session. NOTE: filters by "
            "project (Java, Bedrock, ...), NOT by Minecraft version, so results "
            "span every version; check each issue's affected version."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search text (minimum 3 characters)."},
                "project": {"type": "string", "description": "Project filter.", "enum": ["MC", "MCPE", "MCL", "REALMS", "WEB", "BDS"]},
                "status": {"type": "string", "description": "Status filter.", "enum": ["Open", "Reopened", "Postponed", "In Progress", "Resolved", "Closed"]},
                "resolution": {"type": "string", "description": "Resolution filter.", "enum": ["Awaiting Response", "Cannot Reproduce", "Done", "Duplicate", "Fixed", "Incomplete", "Invalid", "Unresolved", "Won't Fix", "Works As Intended"]},
                "page": {"type": "integer", "description": "Page number (default 1)."},
            },
            "required": [],
        },
    ),

    # -----------------------------------------------------------------------
    # Logs and maintenance
    # -----------------------------------------------------------------------
    Tool(
        name="get_logs",
        description=(
            "Read Minecraft logs from the LOCAL machine (auto-detects the default "
            "launcher, Prism, or TLauncher). Use when diagnosing a reported error. "
            "Pass filter='errors' to skip JVM and mod-loader boilerplate -- raw "
            "logs are mostly noise. Note: a datapack with wrong folder names logs "
            "NOTHING; if the logs are clean but the pack does nothing, run "
            "check_pack_structure."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "launcher": {"type": "string", "description": "Launcher type, or omit to auto-detect.", "enum": ["default", "prism", "tlauncher"]},
                "instance": {"type": "string", "description": "Instance name (Prism Launcher only)."},
                "lines": {"type": "integer", "description": "Lines to return (default 100, max 1000)."},
                "tail": {"type": "boolean", "description": "Last N lines if true (default), first N if false."},
                "filter": {"type": "string", "description": "Keep only matching lines.", "enum": ["all", "errors", "warnings"]},
            },
            "required": [],
        },
    ),

    Tool(
        name="cache_status",
        description=(
            "Inspect or clear MineCode's on-disk response cache. Version-pinned "
            "data is cached permanently since it cannot change. Clear it only if "
            "you suspect a stale or corrupt entry."
        ),
        inputSchema={
            "type": "object",
            "properties": {"clear": {"type": "boolean", "description": "Delete the whole cache (default false)."}},
            "required": [],
        },
    ),
]


# Name -> handler. Checked against TOOLS below, so the two cannot drift.
HANDLERS = {
    "minecraft_start_session": handlers.handle_minecraft_start_session,

    "get_technical_changes": handlers.handle_get_technical_changes,
    "check_version_syntax": handlers.handle_check_version_syntax,
    "check_pack_structure": handlers.handle_check_pack_structure,
    "detect_pack_version": handlers.handle_detect_pack_version,
    "pack_format_to_version": handlers.handle_pack_format_to_version,
    "version_to_pack_format": handlers.handle_version_to_pack_format,
    "list_technical_change_versions": handlers.handle_list_technical_change_versions,

    "get_command_usage": handlers.handle_get_command_usage,
    "validate_command": handlers.handle_validate_command,

    "spyglass_get_versions": handlers.handle_spyglass_get_versions,
    "spyglass_get_registries": handlers.handle_spyglass_get_registries,
    "spyglass_get_block_states": handlers.handle_spyglass_get_block_states,
    "spyglass_get_commands": handlers.handle_spyglass_get_commands,
    "spyglass_search_mcdoc_symbols": handlers.handle_spyglass_search_mcdoc_symbols,
    "spyglass_get_mcdoc_symbol": handlers.handle_spyglass_get_mcdoc_symbol,

    "misode_get_preset_data": handlers.handle_misode_get_preset_data,
    "misode_get_presets": handlers.handle_misode_get_presets,
    "misode_get_loot_tables": handlers.handle_misode_get_loot_tables,
    "misode_get_recipes": handlers.handle_misode_get_recipes,
    "misode_get_generators": handlers.handle_misode_get_generators,
    "misode_list_versions": handlers.handle_misode_list_versions,

    "search_wiki": handlers.handle_search_wiki,
    "get_wiki_page": handlers.handle_get_wiki_page,
    "get_wiki_command_explanation": handlers.handle_get_wiki_command_explanation,
    "get_wiki_commands": handlers.handle_get_wiki_commands,
    "get_wiki_category": handlers.handle_get_wiki_category,

    "search_mojira": handlers.handle_search_mojira,

    "get_logs": handlers.handle_get_logs,
    "cache_status": handlers.handle_cache_status,
}


def _assert_consistent() -> None:
    """
    Fail at import time if TOOLS and HANDLERS disagree.

    This is the guard that would have caught the orphaned changelog functions:
    a tool advertised with no handler errors at call time in front of the user,
    and a handler with no tool is dead code nobody notices for months.
    """
    tool_names = {t.name for t in TOOLS}
    handler_names = set(HANDLERS)

    missing_handler = tool_names - handler_names
    missing_tool = handler_names - tool_names

    problems = []
    if missing_handler:
        problems.append(f"tools with no handler: {sorted(missing_handler)}")
    if missing_tool:
        problems.append(f"handlers with no tool: {sorted(missing_tool)}")

    duplicates = [n for n in tool_names if sum(1 for t in TOOLS if t.name == n) > 1]
    if duplicates:
        problems.append(f"duplicate tool names: {sorted(set(duplicates))}")

    if problems:
        raise RuntimeError("Tool registry is inconsistent -- " + "; ".join(problems))


_assert_consistent()
