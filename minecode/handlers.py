"""
Tool handler implementations.

Split out of server.py so that the server module is only wiring (transport,
dispatch, prompts, resources) and this module is only behaviour.

Two conventions every handler follows:

1. Return a plain dict. Success carries "success": True; failure carries
   "success": False and an "error" string. The dispatcher JSON-encodes it.
   Never return a bare string -- an agent that gets JSON on success and prose
   on failure cannot parse the tool at all, and typically abandons it.

2. Any handler taking a `version` resolves it through packmeta.resolve_version
   first, and reports what it resolved to. Agents pass "1.21" when Spyglass
   wants "1.21.1", or "latest", and an unresolved version previously surfaced
   as an opaque `404 Client Error` that nothing could recover from.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from . import brigadier, cache, knowledge, packmeta
from .scrappers import minecraft_logs, minecraftwiki, misode, mojira, spyglass

logger = logging.getLogger("minecode.handlers")

# Cap on registry/preset lists returned to an agent. The full item registry is
# ~1300 entries; dumping it crowds out the actual work. Truncation is always
# reported so a partial list is never mistaken for a complete one.
MAX_LIST_RESULTS = 150


def _fail(error: str, **extra) -> Dict[str, Any]:
    out = {"success": False, "error": error}
    out.update(extra)
    return out


def _resolve(version: str) -> Dict[str, Any]:
    """Resolve a version string, returning the resolution record."""
    return packmeta.resolve_version(version)


def _truncate(items: List[Any], limit: int = MAX_LIST_RESULTS) -> Dict[str, Any]:
    """
    Return truncation METADATA plus the capped list under "items".

    Callers spread the metadata with ** and then place the list under a
    domain-appropriate key ("entries", "presets", "recipes"). They must pop
    "items" rather than leaving it in, or every response carries the same list
    twice -- which on a 150-entry registry doubles the payload for nothing.
    Use _truncated_payload() below, which does that correctly.
    """
    total = len(items)
    shown = items[:limit]
    return {
        "count": total,
        "shown": len(shown),
        "truncated": total > limit,
        "items": shown,
        "note": (f"Showing {len(shown)} of {total}. Use the search parameter to narrow."
                 if total > limit else None),
    }


def _truncated_payload(items: List[Any], key: str,
                       limit: int = MAX_LIST_RESULTS) -> Dict[str, Any]:
    """Truncation metadata with the list under `key` only -- never duplicated."""
    payload = _truncate(items, limit)
    payload[key] = payload.pop("items")
    return payload


# ===========================================================================
# Session bootstrap -- the tool an agent should call first
# ===========================================================================

def handle_minecraft_start_session(workspace_path: Optional[str] = None) -> dict:
    """
    Detect the project's target version and return everything the agent needs
    before writing a single line.

    This exists because MCP servers cannot inject a system prompt. The
    methodology in assistant_preprompt.txt used to be loaded into a variable
    nothing read, so it never reached the model. A tool is the one channel an
    agent reaches for on its own.
    """
    detection = packmeta.detect(workspace_path)

    result: Dict[str, Any] = {
        "success": True,
        "detection": detection,
    }

    version = detection.get("target_version")

    if not version:
        result["target_version"] = None
        result["instructions"] = [
            "No pack.mcmeta was found, so the target Minecraft version is unknown.",
            "ASK THE USER which version to target. Do not assume the latest release "
            "-- most existing packs target something older, and syntax differs.",
            "Once you know the version, call get_technical_changes(to_version=...) "
            "before writing anything.",
        ]
        return result

    result["target_version"] = version
    result["pack_format"] = detection.get("pack_format")
    result["multi_version"] = detection.get("multi_version", False)

    # Curated notes for this version -- offline, instant, no network.
    result["version_notes"] = knowledge.version_notes(version)
    curated = knowledge.applicable_to(version)
    result["known_migrations"] = [
        {
            "id": m["id"],
            "title": m["title"],
            "changed_in": m.get("changed_in"),
            "severity": m.get("severity"),
            "before": m.get("before"),
            "after": m.get("after"),
        }
        for m in curated
    ]

    result["instructions"] = [
        f"This project targets Minecraft {version}.",
        f"Pass version='{version}' to every version-taking tool. Do not guess a version.",
        "Your training data is older than this version. The syntax you remember may "
        "be wrong. Before writing item components, text components, loot tables, "
        "predicates, or recipes, call get_technical_changes(to_version='"
        + version + "') to see what changed.",
        "For command syntax use get_command_usage (rendered, version-exact) rather "
        "than recalling it. Verify every command you write with validate_command.",
        "Run check_version_syntax over any command or JSON you produce before saving it.",
        "minecraft.wiki covers the LATEST version only -- use it for concepts, never "
        "for syntax on an older target.",
    ]

    if detection.get("multi_version"):
        result["instructions"].append(
            "This pack declares a RANGE of supported formats. Syntax must be valid "
            "across the whole range, or be split with pack.mcmeta overlays. Check "
            "both ends of the range before committing to a syntax."
        )

    return result


# ===========================================================================
# Version + workspace
# ===========================================================================

def handle_detect_pack_version(path: Optional[str] = None) -> dict:
    return packmeta.detect(path)


def handle_resolve_minecraft_version(version: str) -> dict:
    return packmeta.resolve_version(version)


def handle_pack_format_to_version(pack_format: int, kind: str = "data") -> dict:
    return packmeta.pack_format_to_versions(int(pack_format), kind=kind)


def handle_version_to_pack_format(version: str) -> dict:
    resolved = _resolve(version)
    if not resolved.get("success"):
        return resolved
    return packmeta.version_to_pack_formats(resolved["resolved"])


# ===========================================================================
# Technical changes -- the version-drift fix
# ===========================================================================

def handle_get_technical_changes(to_version: str,
                                 from_version: Optional[str] = None,
                                 topic: Optional[str] = None) -> dict:
    """
    Combine the curated migration table with misode/technical-changes.

    The curated table is instant and offline and covers the migrations models
    get wrong most; the changelog is exhaustive and community-maintained. An
    agent wants both, and wants to know which is which.
    """
    resolved = _resolve(to_version)
    if not resolved.get("success"):
        return resolved
    target = resolved["resolved"]

    from_resolved = None
    if from_version:
        fr = _resolve(from_version)
        from_resolved = fr["resolved"] if fr.get("success") else from_version

    curated = knowledge.changes_between(from_resolved, target, topic)

    try:
        changelog = misode.get_changes_between(from_resolved, target, topic)
    except Exception as e:
        logger.warning("technical-changes fetch failed: %s", e)
        changelog = {"success": False, "error": str(e)}

    return {
        "success": True,
        "from_version": from_resolved,
        "to_version": target,
        "resolved_from_request": resolved,
        "topic": topic,
        "curated_migrations": {
            "count": len(curated),
            "note": (
                "Hand-curated before/after pairs for the changes AI agents get "
                "wrong most often. Fast and offline, but NOT exhaustive -- see "
                "official_changelog below for the full record."
            ),
            "migrations": curated,
        },
        "official_changelog": changelog,
        "how_to_use": (
            "Read curated_migrations first -- they are the traps. Then scan "
            "official_changelog for anything touching what you are about to "
            "write. When the two disagree, the official changelog wins."
        ),
    }


def handle_list_technical_change_versions() -> dict:
    try:
        releases = misode.list_changelog_releases()
    except Exception as e:
        return _fail(f"could not list changelog releases: {e}")

    return {
        "success": True,
        "release_count": len(releases),
        "releases": releases,
        "curated_versions": [n["version"] for n in knowledge.version_notes()],
        "source": "https://github.com/misode/technical-changes",
    }


def handle_check_version_syntax(content: str, version: str,
                                kind: str = "any") -> dict:
    resolved = _resolve(version)
    if not resolved.get("success"):
        return resolved
    return knowledge.check_syntax(content, resolved["resolved"], kind)


def handle_check_pack_structure(path: Optional[str] = None,
                                version: Optional[str] = None) -> dict:
    """
    Check a datapack's folder layout against the target version.

    Separate from check_version_syntax because the 1.21 folder-singularization
    change shows up in paths, not file contents -- and a pack with the old
    plural folders loads silently with nothing in it, producing no error
    anywhere for an agent to notice.
    """
    from pathlib import Path

    if not version:
        detection = packmeta.detect(path)
        version = detection.get("target_version")
        if not version:
            return _fail(
                "could not determine target version",
                detection=detection,
                hint="Pass version explicitly, or point path at a pack root.",
            )

    resolved = _resolve(version)
    if not resolved.get("success"):
        return resolved
    version = resolved["resolved"]

    root = Path(path).expanduser() if path else Path.cwd()
    if not root.exists():
        return _fail(f"path does not exist: {root}")

    files = []
    try:
        for p in root.rglob("*"):
            if p.is_file() and ".git" not in p.parts:
                files.append(str(p.relative_to(root)))
    except (PermissionError, OSError) as e:
        return _fail(f"could not walk {root}: {e}")

    result = knowledge.check_paths(files, version)
    result["root"] = str(root.resolve())
    result["files_scanned"] = len(files)
    return result


# ===========================================================================
# Commands -- rendered usage and validation
# ===========================================================================

def handle_get_command_usage(version: str, command: str,
                             max_lines: int = brigadier.MAX_USAGE_LINES) -> dict:
    """
    Return readable usage strings for a command, compiled from the game's own
    Brigadier tree.

    Spyglass has always had the authoritative data; the problem was its shape.
    Handing an agent a nested parser tree makes it compile the syntax mentally,
    and that is precisely where remembered (wrong-version) syntax creeps back
    in. Compiling server-side removes the step.
    """
    resolved = _resolve(version)
    if not resolved.get("success"):
        return resolved
    version = resolved["resolved"]

    try:
        node = spyglass.get_command_info(version, command)
    except Exception as e:
        return _fail(f"could not fetch command tree: {e}", version=version)

    if not node:
        try:
            available = spyglass.get_command_names(version)
        except Exception:
            available = []
        close = [c for c in available if command.lower() in c.lower()][:10]
        return _fail(
            f"command '{command}' does not exist in Minecraft {version}",
            version=version,
            did_you_mean=close or available[:20],
        )

    rendered = brigadier.render_usage(command, node, max_lines=max_lines)
    rendered["success"] = True
    rendered["version"] = version
    rendered["source"] = "Brigadier command tree via Spyglass -- version-exact"
    return rendered


def handle_validate_command(command: str, version: str) -> dict:
    """Parse a command against the version's real command grammar."""
    resolved = _resolve(version)
    if not resolved.get("success"):
        return resolved
    version = resolved["resolved"]

    try:
        root = spyglass.get_commands(version)
    except Exception as e:
        return _fail(f"could not fetch command tree: {e}", version=version)

    verdict = brigadier.validate(command, root)
    verdict["success"] = True
    verdict["version"] = version

    # Layer the curated migration check on top: a command can parse cleanly and
    # still be wrong for the version (correct grammar, deprecated field names).
    curated = knowledge.check_syntax(command, version, kind="command")
    if curated["issue_count"]:
        verdict["version_warnings"] = curated["issues"]
        verdict["note"] = (
            "The command parses, but matched known version migrations -- see "
            "version_warnings."
            if verdict.get("valid") else
            "The command does not parse AND matched known version migrations."
        )

    return verdict


# ===========================================================================
# Minecraft Wiki
# ===========================================================================

def _with_wiki_warning(payload: dict) -> dict:
    """Attach the latest-version-only warning to every wiki result."""
    payload["version_warning"] = minecraftwiki.WIKI_VERSION_WARNING
    return payload


def handle_search_wiki(query: str, limit: int = 10, fulltext: bool = False) -> dict:
    try:
        results = (minecraftwiki.search_fulltext(query, limit=limit) if fulltext
                   else minecraftwiki.search(query, limit=limit))
        return _with_wiki_warning({
            "success": True,
            "query": query,
            "count": len(results),
            "results": minecraftwiki.search_to_dict(results),
        })
    except Exception as e:
        return _fail(str(e))


def handle_get_wiki_page(title: str, sentences: int = 5, full: bool = False) -> dict:
    """
    Get a wiki page, as a summary or in full.

    Merged from the old get_wiki_page and get_wiki_page_content, which took the
    same input and differed only in verbosity. Two tools answering one question
    is a decision the agent has to make and can get wrong.
    """
    try:
        if full:
            content = minecraftwiki.get_page_content(title)
            if not content:
                return _fail(f"page '{title}' not found or could not be parsed")
            return _with_wiki_warning({
                "success": True,
                "title": title,
                "mode": "full",
                "content": minecraftwiki.page_content_to_dict(content),
            })

        extract = minecraftwiki.get_page_extract(title, sentences=sentences)
        if not extract:
            return _fail(f"page '{title}' not found")

        return _with_wiki_warning({
            "success": True,
            "title": title,
            "mode": "summary",
            "url": f"https://minecraft.wiki/w/{title.replace(' ', '_')}",
            "extract": extract,
            "sections": minecraftwiki.get_page_sections(title),
            "hint": "Pass full=true for the complete page content.",
        })
    except Exception as e:
        return _fail(str(e))


def handle_get_wiki_commands(limit: int = 50) -> dict:
    try:
        commands = minecraftwiki.get_commands(limit=limit)
        return _with_wiki_warning({
            "success": True,
            "count": len(commands),
            "commands": minecraftwiki.commands_to_dict(commands),
            "better_tool": (
                "For the command list of a SPECIFIC version use "
                "spyglass_get_commands; for syntax use get_command_usage."
            ),
        })
    except Exception as e:
        return _fail(str(e))


def handle_get_wiki_category(category: str, limit: int = 50) -> dict:
    try:
        pages = minecraftwiki.get_category_members(category, limit=limit)
        return _with_wiki_warning({
            "success": True,
            "category": category,
            "count": len(pages),
            "pages": minecraftwiki.page_info_to_dict(pages),
        })
    except Exception as e:
        return _fail(str(e))


def handle_get_wiki_command_explanation(command: str) -> dict:
    """
    Prose explanation of a command from the wiki.

    Renamed from get_wiki_command_info. The old name implied it was the
    authority on command syntax, competing directly with spyglass_get_commands
    -- and losing, because it describes only the latest version.
    """
    try:
        info = minecraftwiki.get_command_info(command)
        return _with_wiki_warning({
            "success": True,
            "command": command,
            "explanation": info,
            "authoritative_alternative": (
                f"For version-exact syntax call "
                f"get_command_usage(version=<target>, command='{command}'). "
                "This wiki text describes the latest release only."
            ),
        })
    except Exception as e:
        return _fail(str(e))


# ===========================================================================
# Mojira
# ===========================================================================

def handle_search_mojira(query: Optional[str] = None, project: Optional[str] = None,
                         status: Optional[str] = None, resolution: Optional[str] = None,
                         page: int = 1) -> dict:
    try:
        issues = mojira.search(query=query, project=project, status=status,
                               resolution=resolution, page=page)
        return {
            "success": True,
            "count": len(issues),
            "issues": mojira.search_to_dict(issues),
            "version_note": (
                "Mojira filters by project (Java, Bedrock, ...), not by Minecraft "
                "version. Results span every version -- check each issue's affected "
                "version before concluding it applies to your target."
            ),
        }
    except mojira.ScraperStructureError as e:
        return _fail(str(e), scraper_broken=True)
    except Exception as e:
        return _fail(str(e))


# ===========================================================================
# Spyglass
# ===========================================================================

def handle_spyglass_get_versions(type_filter: str = "all", limit: int = 20) -> dict:
    try:
        versions = spyglass.get_versions()
        if type_filter in ("release", "snapshot"):
            versions = [v for v in versions if v.get("type") == type_filter]

        latest_release = spyglass.get_latest_release()
        latest_snapshot = spyglass.get_latest_snapshot()

        return {
            "success": True,
            "count": len(versions[:limit]),
            "total_available": len(versions),
            "latest_release": latest_release.get("id") if latest_release else None,
            "latest_snapshot": latest_snapshot.get("id") if latest_snapshot else None,
            "versions": [{
                "id": v.get("id"),
                "type": v.get("type"),
                "data_pack_format": v.get("data_pack_version"),
                "resource_pack_format": v.get("resource_pack_version"),
                "release_time": v.get("release_time"),
            } for v in versions[:limit]],
        }
    except Exception as e:
        return _fail(str(e))


def handle_spyglass_get_registries(version: str, registry: str,
                                   search: Optional[str] = None) -> dict:
    resolved = _resolve(version)
    if not resolved.get("success"):
        return resolved
    version = resolved["resolved"]

    try:
        available = spyglass.get_registry_names(version)
        if registry not in available:
            close = [r for r in available if registry.lower() in r.lower()][:10]
            return _fail(
                f"registry '{registry}' does not exist in {version}",
                version=version,
                did_you_mean=close or available[:30],
            )

        entries = (spyglass.search_registry(version, registry, search) if search
                   else spyglass.get_registry(version, registry))

        payload = _truncated_payload(entries, "entries")
        return {
            "success": True,
            "version": version,
            "resolved_version": resolved,
            "registry": registry,
            "search": search,
            **payload,
            "available_registries": available,
        }
    except Exception as e:
        return _fail(str(e), version=version)


def handle_spyglass_get_block_states(version: str, block_id: str) -> dict:
    resolved = _resolve(version)
    if not resolved.get("success"):
        return resolved
    version = resolved["resolved"]

    try:
        info = spyglass.get_block_info(version, block_id)
        if not info:
            close = spyglass.search_blocks(version, block_id.replace("minecraft:", ""))[:10]
            return _fail(
                f"block '{block_id}' not found in {version}",
                version=version,
                did_you_mean=close,
            )

        return {
            "success": True,
            "version": version,
            "block_id": block_id,
            "properties": info[0] if len(info) > 0 else {},
            "defaults": info[1] if len(info) > 1 else {},
        }
    except Exception as e:
        return _fail(str(e), version=version)


def handle_spyglass_get_commands(version: str, command: Optional[str] = None) -> dict:
    resolved = _resolve(version)
    if not resolved.get("success"):
        return resolved
    version = resolved["resolved"]

    try:
        if command:
            node = spyglass.get_command_info(version, command)
            if not node:
                available = spyglass.get_command_names(version)
                close = [c for c in available if command.lower() in c.lower()][:10]
                return _fail(f"command '{command}' not found in {version}",
                             version=version, did_you_mean=close or available[:30])

            # Return the rendered usage alongside the raw tree. The raw tree is
            # authoritative but hard to read; the usage lines are what an agent
            # can actually act on without re-deriving syntax.
            rendered = brigadier.render_usage(command, node)
            return {
                "success": True,
                "version": version,
                "command": command,
                "usage": rendered["usage"],
                "arguments": rendered["arguments"],
                "usage_truncated": rendered["truncated"],
                "tree": node,
                "hint": "Read `usage`. `tree` is the raw Brigadier data behind it.",
            }

        names = spyglass.get_command_names(version)
        return {
            "success": True,
            "version": version,
            "count": len(names),
            "commands": names,
            "hint": "Call get_command_usage(version, command) for readable syntax.",
        }
    except Exception as e:
        return _fail(str(e), version=version)


def _mcdoc_unavailable(error: Exception) -> dict:
    """
    Explain an mcdoc outage and route the agent to a working alternative.

    Spyglass's /vanilla-mcdoc/symbols endpoint has been observed returning 502
    while the rest of the API is healthy. Returning a bare transport error
    leaves the agent with nothing to do but fall back on remembered (and likely
    version-wrong) field names -- which is the exact failure this server
    exists to prevent. Naming the alternatives keeps it on a good path.
    """
    return _fail(
        f"Spyglass mcdoc endpoint unavailable: {error}",
        upstream_outage=True,
        fallbacks=[
            "misode_get_preset_data -- real vanilla JSON for the target version. "
            "The best available substitute: a working example shows the true shape.",
            "get_technical_changes -- tells you which fields changed and when.",
            "spyglass_get_registries -- confirms valid IDs, which is unaffected.",
        ],
        do_not=(
            "Do NOT fall back on remembered field names. That is how "
            "version-wrong output happens. Use a real vanilla example instead."
        ),
    )


def handle_spyglass_search_mcdoc_symbols(query: str, limit: int = 40) -> dict:
    try:
        matches = spyglass.search_mcdoc_symbols(query, limit=limit)
        if not matches:
            return {
                "success": True, "query": query, "count": 0, "symbols": [],
                "hint": "No symbol matched. Try a shorter keyword, e.g. 'Item' rather than 'ItemStackData'.",
            }
        return {
            "success": True,
            "query": query,
            "count": len(matches),
            "symbols": matches,
            "next_step": "Call spyglass_get_mcdoc_symbol(symbol=...) for a definition.",
        }
    except Exception as e:
        return _mcdoc_unavailable(e)


def handle_spyglass_get_mcdoc_symbol(symbol: str, depth: int = 3) -> dict:
    try:
        result = spyglass.get_mcdoc_symbol(symbol, depth=depth)
        if result is None:
            close = spyglass.search_mcdoc_symbols(symbol.rsplit("::", 1)[-1], limit=15)
            return _fail(f"mcdoc symbol '{symbol}' not found", did_you_mean=close)

        result["success"] = True
        result["note"] = (
            "mcdoc tracks the latest game version. For older targets confirm "
            "field names against get_technical_changes."
        )
        return result
    except Exception as e:
        return _mcdoc_unavailable(e)


# ===========================================================================
# Misode
# ===========================================================================

def handle_misode_get_generators(category: str = "all") -> dict:
    try:
        gen_ids = misode.list_generators()
        generators = [{"id": g, "url": misode.get_generator_url(g)} for g in gen_ids]

        if category != "all":
            # The generator table has no category metadata, so filter on the
            # id/path text. Previously this branch returned an empty list for
            # every category, which read as "no generators exist".
            c = category.lower().replace("_", "")
            generators = [g for g in generators
                          if c in g["id"].lower().replace("_", "")
                          or c in g["url"].lower().replace("-", "")]

        return {
            "success": True,
            "category": category,
            "count": len(generators),
            "generators": generators,
            "usage_note": (
                "These are links to Misode's web UI, meant to be SHOWN TO THE USER "
                "when a visual editor would serve them better than hand-written "
                "JSON. They are not API endpoints -- do not fetch them. For vanilla "
                "JSON use misode_get_preset_data."
            ),
        }
    except Exception as e:
        return _fail(str(e))


def handle_misode_get_presets(version: str, generator_type: str,
                              search: Optional[str] = None) -> dict:
    resolved = _resolve(version)
    if not resolved.get("success"):
        return resolved
    version = resolved["resolved"]

    try:
        if search:
            presets = misode.search_data(version, generator_type, search)
        else:
            presets = list((misode.get_data(version, generator_type) or {}).keys())

        payload = _truncated_payload(presets, "presets")
        return {
            "success": True,
            "version": version,
            "generator_type": generator_type,
            "generator_url": misode.get_generator_url(generator_type),
            **payload,
        }
    except Exception as e:
        return _fail(str(e), version=version, generator_type=generator_type)


def handle_misode_get_preset_data(version: str, generator_type: str,
                                  preset_id: str) -> dict:
    resolved = _resolve(version)
    if not resolved.get("success"):
        return resolved
    version = resolved["resolved"]

    try:
        data = misode.get_data(version, generator_type) or {}
        preset = data.get(preset_id)

        if preset is None:
            close = [k for k in data if preset_id.lower() in k.lower()][:10]
            return _fail(
                f"preset '{preset_id}' not found in {generator_type} for {version}",
                version=version, did_you_mean=close,
            )

        return {
            "success": True,
            "version": version,
            "generator_type": generator_type,
            "preset_id": preset_id,
            "data": preset,
            "note": (
                f"This is real vanilla JSON for {version}. It is the most reliable "
                "shape reference available -- match its structure rather than "
                "recalling the schema."
            ),
        }
    except Exception as e:
        return _fail(str(e), version=version)


def handle_misode_get_loot_tables(version: str, category: str = "all",
                                  search: Optional[str] = None) -> dict:
    resolved = _resolve(version)
    if not resolved.get("success"):
        return resolved
    version = resolved["resolved"]

    try:
        all_tables = list((misode.get_data(version, "loot_table") or {}).keys())
        tables = (misode.search_data(version, "loot_table", search) if search
                  else list(all_tables))

        prefixes = {"blocks": "blocks/", "chests": "chests/", "entities": "entities/",
                    "archaeology": "archaeology/", "gameplay": "gameplay/"}
        if category != "all":
            prefix = prefixes.get(category)
            if prefix is None:
                return _fail(f"unknown category '{category}'",
                             valid_categories=["all", *prefixes])
            tables = [t for t in tables if t.startswith(prefix)]

        payload = _truncated_payload(tables, "loot_tables")
        return {
            "success": True,
            "version": version,
            "category": category,
            "category_counts": {k: sum(1 for t in all_tables if t.startswith(p))
                                for k, p in prefixes.items()},
            **payload,
        }
    except Exception as e:
        return _fail(str(e), version=version)


def handle_misode_get_recipes(version: str, recipe_type: str = "all",
                              search: Optional[str] = None) -> dict:
    resolved = _resolve(version)
    if not resolved.get("success"):
        return resolved
    version = resolved["resolved"]

    try:
        data = misode.get_data(version, "recipe") or {}
        names = (misode.search_data(version, "recipe", search) if search
                 else list(data.keys()))

        if recipe_type != "all":
            names = [n for n in names
                     if isinstance(data.get(n), dict)
                     and str(data[n].get("type", "")).endswith(recipe_type)]

        payload = _truncated_payload(names, "recipes")
        return {
            "success": True,
            "version": version,
            "recipe_type": recipe_type,
            **payload,
        }
    except Exception as e:
        return _fail(str(e), version=version)


def handle_misode_list_versions() -> dict:
    try:
        versions = misode.list_versions()
        return {"success": True, "count": len(versions), "versions": versions[:200]}
    except Exception as e:
        return _fail(str(e))


# ===========================================================================
# Logs and maintenance
# ===========================================================================

# Substrings that mark a log line as interesting. "\tat " catches Java stack
# trace frames, which are useless alone but essential context for the
# exception above them.
_ERROR_MARKERS = ["ERROR", "FATAL", "SEVERE", "Exception", "Caused by", "\tat "]
_WARNING_MARKERS = _ERROR_MARKERS + ["WARN"]


def handle_get_logs(launcher: Optional[str] = None, instance: Optional[str] = None,
                    lines: int = 100, tail: bool = True,
                    filter: str = "all") -> dict:
    """
    Read Minecraft logs from the LOCAL machine.

    `filter` exists because dumping 1000 raw lines spends most of the context
    on JVM and mod-loader boilerplate; an agent debugging a datapack wants the
    errors.

    Note the shape returned by minecraft_logs.get_logs: a `logs` LIST, one
    entry per instance, each with its own `content`. There is no top-level
    `content` key -- filtering that key silently did nothing for every
    launcher, since Prism and the default launcher both use the list form.
    """
    try:
        result = minecraft_logs.get_logs(launcher=launcher, instance=instance,
                                         lines=lines, tail=tail)

        entries = result.get("logs") or []

        if filter in ("errors", "warnings"):
            markers = _ERROR_MARKERS if filter == "errors" else _WARNING_MARKERS
            total_kept = 0

            for entry in entries:
                content = entry.get("content") or ""
                kept = [ln for ln in content.split("\n")
                        if any(m in ln for m in markers)]
                entry["content"] = "\n".join(kept)
                entry["lines_shown"] = len(kept)
                total_kept += len(kept)

            result["filter"] = filter
            result["lines_after_filter"] = total_kept

            if total_kept == 0 and entries:
                result["note"] = (
                    f"No lines matched filter '{filter}'. The logs were read "
                    "successfully -- there are simply no matching lines in the "
                    f"{lines} line(s) examined. Increase `lines`, or use "
                    "filter='all' to see everything. "
                    "IMPORTANT: a datapack with wrong folder names produces NO "
                    "log output at all -- if the pack does nothing but the logs "
                    "are clean, run check_pack_structure."
                )

        result["instances_found"] = len(entries)
        if entries:
            result["instance_names"] = [e.get("instance") for e in entries]

        if not entries and result.get("success"):
            result["note"] = (
                "No log files were found. Is Minecraft installed on this machine "
                "and has it been run at least once?"
            )

        result.setdefault("source_note",
                          "Logs are read from the local filesystem. On a remote or "
                          "containerized setup there may be no Minecraft install here.")
        return result
    except Exception as e:
        return _fail(str(e))


def handle_cache_status(clear: bool = False) -> dict:
    """Inspect or clear the on-disk response cache."""
    if clear:
        return {"success": True, **cache.clear()}
    return {"success": True, **cache.stats()}
