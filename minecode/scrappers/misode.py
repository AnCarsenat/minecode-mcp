"""
Misode Data Pack Generators Client - Optimized for MCP Agents
Website: https://misode.github.io/
GitHub: https://github.com/misode/misode.github.io

This module provides clean, simple access to Minecraft data pack presets
and schemas. Designed for AI agents using the MCP protocol.
"""

import requests
from typing import Optional, List, Dict, Any
import re

import logging

from .. import cache

logger = logging.getLogger("minecode.misode")

USER_AGENT = "MineCode/1.0 (+https://github.com/AnCarsenat/minecode-mcp)"

# Base URLs
MISODE_SITE = "https://misode.github.io"
GITHUB_RAW = "https://raw.githubusercontent.com/misode/mcmeta"
GITHUB_SITEMAP = "https://raw.githubusercontent.com/misode/misode.github.io/master/public/sitemap.txt"
TECHNICAL_CHANGES_API = "https://api.github.com/repos/misode/technical-changes/contents"
TECHNICAL_CHANGES_RAW = "https://raw.githubusercontent.com/misode/technical-changes/main"

# Generator types available on the site
GENERATORS = {
    "loot_table": "loot-table",
    "predicate": "predicate", 
    "item_modifier": "item-modifier",
    "advancement": "advancement",
    "recipe": "recipe",
    "text_component": "text-component",
    "chat_type": "chat-type",
    "dimension": "dimension",
    "dimension_type": "dimension-type",
    "worldgen_biome": "worldgen/biome",
    "worldgen_configured_carver": "worldgen/configured-carver",
    "worldgen_configured_feature": "worldgen/configured-feature",
    "worldgen_density_function": "worldgen/density-function",
    "worldgen_placed_feature": "worldgen/placed-feature",
    "worldgen_noise": "worldgen/noise",
    "worldgen_noise_settings": "worldgen/noise-settings",
    "worldgen_structure": "worldgen/structure",
    "worldgen_structure_set": "worldgen/structure-set",
    "worldgen_processor_list": "worldgen/processor-list",
    "worldgen_template_pool": "worldgen/template-pool",
    "worldgen_world_preset": "worldgen/world-preset",
    "worldgen_flat_level_generator_preset": "worldgen/flat-level-generator-preset",
    "damage_type": "damage-type",
    "trim_material": "trim-material",
    "trim_pattern": "trim-pattern",
    "banner_pattern": "banner-pattern",
    "painting_variant": "painting-variant",
    "wolf_variant": "wolf-variant",
    "enchantment": "enchantment",
    "jukebox_song": "jukebox-song",
}


def _request(url: str, json_response: bool = True,
             ttl: int = cache.IMMUTABLE) -> Any:
    """
    Make an HTTP request via the disk cache.

    Defaults to IMMUTABLE because most misode URLs are pinned to a released
    version tag and never change. Index endpoints (version lists, the
    technical-changes directory listing) pass an explicit TTL.
    """
    key = f"misode:{url}:{'json' if json_response else 'text'}"

    def fetch():
        response = requests.get(url, timeout=20,
                                headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        return response.json() if json_response else response.text

    try:
        return cache.cached_fetch(key, ttl, fetch)
    except Exception as e:
        raise Exception(f"Request failed for {url}: {str(e)}")


# ============================================================================
# Version Functions - Optimized for MCP
# ============================================================================

def list_versions() -> List[str]:
    """
    Get list of all Minecraft version IDs.
    
    Returns:
        List of version IDs ordered newest to oldest
        Example: ["1.21.11", "1.21.10", "24w14a", ...]
    """
    try:
        url = f"{GITHUB_RAW}/summary/versions/data.min.json"
        data = _request(url)
        
        if isinstance(data, list):
            # If it's a list of dicts with 'id' field
            if data and isinstance(data[0], dict) and 'id' in data[0]:
                return [v['id'] for v in data]
            # If it's a list of strings
            return data
        elif isinstance(data, dict):
            # If it's a dict, return keys
            return list(data.keys())
        
        return []
    except Exception as e:
        logger.warning("misode request failed: %s", e)
        return []


def get_version_info(version_id: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific version.
    
    Args:
        version_id: Version ID (e.g., "1.21.11")
        
    Returns:
        Dictionary with version metadata or None
    """
    try:
        url = f"{GITHUB_RAW}/summary/versions/data.min.json"
        data = _request(url)
        
        if isinstance(data, list):
            for v in data:
                if isinstance(v, dict) and v.get('id') == version_id:
                    return v
        elif isinstance(data, dict):
            return data.get(version_id)
        
        return None
    except Exception:
        return None


def get_latest_release() -> Optional[str]:
    """Get the latest stable release version ID."""
    versions = list_versions()
    for version in versions:
        if re.match(r"^\d+\.\d+(\.\d+)?$", version):
            return version
    return None


def get_latest_snapshot() -> Optional[str]:
    """Get the latest snapshot version ID."""
    versions = list_versions()
    for version in versions:
        if not re.match(r"^\d+\.\d+(\.\d+)?$", version):
            return version
    return None


# ============================================================================
# Generator Functions
# ============================================================================

def list_generators() -> List[str]:
    """
    Get list of all available generator IDs.
    
    Returns:
        List of generator IDs
        Example: ["loot_table", "recipe", "worldgen_biome", ...]
    """
    return list(GENERATORS.keys())


def get_generator_url(generator_id: str) -> str:
    """
    Get the Misode website URL for a generator.
    
    Args:
        generator_id: Generator ID (e.g., "loot_table")
        
    Returns:
        Full URL to generator page
    """
    path = GENERATORS.get(generator_id, generator_id.replace("_", "-"))
    return f"{MISODE_SITE}/{path}/"


# ============================================================================
# Data Access Functions - Core MCP Methods
# ============================================================================

def _get_data_url(version_id: str, data_type: str) -> str:
    """Construct URL for data file in mcmeta repository."""
    return f"{GITHUB_RAW}/{version_id}-summary/data/{data_type}/data.min.json"


def get_data(version_id: str, data_type: str) -> Dict[str, Any]:
    """
    Get data for a specific type and version.
    
    Args:
        version_id: Minecraft version (e.g., "1.21.11")
        data_type: Data type (e.g., "loot_table", "recipe", "worldgen/biome")
        
    Returns:
        Dictionary mapping entry IDs to their JSON data
    """
    url = _get_data_url(version_id, data_type)
    return _request(url)


def search_data(version_id: str, data_type: str, query: str) -> List[str]:
    """
    Search for entries matching a query.
    
    Args:
        version_id: Minecraft version
        data_type: Data type (e.g., "loot_table")
        query: Search query (case-insensitive)
        
    Returns:
        List of matching entry IDs
    """
    try:
        data = get_data(version_id, data_type)
        query = query.lower()
        return [k for k in data.keys() if query in k.lower()]
    except Exception:
        return []


# ============================================================================
# Registry Functions
# ============================================================================

def get_registries(version_id: str) -> Dict[str, List[str]]:
    """
    Get all registry data for a version.
    
    Args:
        version_id: Minecraft version
        
    Returns:
        Dictionary mapping registry names to entry ID lists
    """
    url = f"{GITHUB_RAW}/{version_id}-summary/registries/data.min.json"
    return _request(url)


def list_registry_names(version_id: str) -> List[str]:
    """Get list of all registry names for a version."""
    return list(get_registries(version_id).keys())


def get_registry(version_id: str, registry_name: str) -> List[str]:
    """
    Get entries from a specific registry.
    
    Args:
        version_id: Minecraft version
        registry_name: Registry name (e.g., "item", "block")
        
    Returns:
        List of entry IDs
    """
    registries = get_registries(version_id)
    return registries.get(registry_name, [])


# ============================================================================
# Block State Functions
# ============================================================================

def get_block_states(version_id: str) -> Dict[str, Any]:
    """Get all block state definitions."""
    url = f"{GITHUB_RAW}/{version_id}-summary/blocks/data.min.json"
    return _request(url)


def get_block_state(version_id: str, block_id: str) -> Optional[Dict[str, Any]]:
    """Get state definition for a specific block."""
    states = get_block_states(version_id)
    clean_id = block_id.replace("minecraft:", "")
    return states.get(clean_id)


# ============================================================================
# Specific Data Type Helpers
# ============================================================================

def get_loot_tables(version_id: str) -> Dict[str, Any]:
    """Get all loot tables."""
    return get_data(version_id, "loot_table")


def get_recipes(version_id: str) -> Dict[str, Any]:
    """Get all recipes."""
    return get_data(version_id, "recipe")


def get_advancements(version_id: str) -> Dict[str, Any]:
    """Get all advancements."""
    return get_data(version_id, "advancement")


def get_predicates(version_id: str) -> Dict[str, Any]:
    """Get all predicates."""
    return get_data(version_id, "predicate")


def get_item_modifiers(version_id: str) -> Dict[str, Any]:
    """Get all item modifiers."""
    return get_data(version_id, "item_modifier")


def get_damage_types(version_id: str) -> Dict[str, Any]:
    """Get all damage types."""
    return get_data(version_id, "damage_type")


def get_biomes(version_id: str) -> Dict[str, Any]:
    """Get all biomes."""
    return get_data(version_id, "worldgen/biome")


def get_structures(version_id: str) -> Dict[str, Any]:
    """Get all structures."""
    return get_data(version_id, "worldgen/structure")


def get_configured_features(version_id: str) -> Dict[str, Any]:
    """Get all configured features."""
    return get_data(version_id, "worldgen/configured_feature")


def get_placed_features(version_id: str) -> Dict[str, Any]:
    """Get all placed features."""
    return get_data(version_id, "worldgen/placed_feature")


# ============================================================================
# Changelog Functions
# ============================================================================

def list_changelog_releases() -> List[str]:
    """
    Get list of release versions that have changelogs.
    
    Returns:
        List of release versions (e.g., ["1.21", "1.20.5", ...])
    """
    try:
        response = _request(TECHNICAL_CHANGES_API, ttl=cache.TTL_CHANGELOG_INDEX)
        return [
            item["name"]
            for item in response
            if item["type"] == "dir" and not item["name"].startswith(".")
        ]
    except Exception as e:
        logger.warning("Error listing changelog releases: %s", e)
        return []


def list_changelogs(release: str) -> List[str]:
    """
    Get list of version IDs that have changelogs in a release.
    
    Args:
        release: Release version (e.g., "1.21")
        
    Returns:
        List of version IDs
    """
    try:
        url = f"{TECHNICAL_CHANGES_API}/{release}"
        response = _request(url, ttl=cache.TTL_CHANGELOG_INDEX)
        return [
            item["name"].replace(".md", "")
            for item in response
            if item["type"] == "file" and item["name"].endswith(".md")
        ]
    except Exception as e:
        logger.warning("Error listing changelogs for %s: %s", release, e)
        return []


def get_changelog(release: str, version_id: str) -> Optional[str]:
    """
    Get changelog content for a specific version.
    
    Args:
        release: Release version (e.g., "1.21")
        version_id: Version ID (e.g., "24w14a")
        
    Returns:
        Markdown content or None
    """
    try:
        url = f"{TECHNICAL_CHANGES_RAW}/{release}/{version_id}.md"
        return _request(url, json_response=False)
    except Exception:
        return None


def parse_changelog(content: str) -> List[Dict[str, Any]]:
    """
    Parse changelog markdown into structured data.
    
    Args:
        content: Markdown content
        
    Returns:
        List of entries with tags and descriptions
    """
    entries = []
    for line in content.strip().split('\n'):
        line = line.strip()
        if not line or '|' not in line:
            continue

        tags_part, description = line.split('|', 1)
        tags = [tag.strip() for tag in tags_part.split() if tag.strip()]

        entries.append({
            "tags": tags,
            "description": description.strip()
        })

    return entries


def _release_line(version_id: str) -> Optional[str]:
    """
    Map a version ID onto the technical-changes release directory holding it.

    Release IDs ("1.21.4") name their own directory or the directory of their
    parent line. Snapshot IDs ("24w14a") do not encode their release at all, so
    for those the caller must fall back to scanning directories.
    """
    releases = list_changelog_releases()
    if not releases:
        return None

    if version_id in releases:
        return version_id

    # Longest matching prefix: "1.21.4" lives under "1.21.4" or "1.21".
    candidates = [r for r in releases if version_id.startswith(r)]
    if candidates:
        return max(candidates, key=len)

    return None


def _all_changelog_entries() -> List[Dict[str, Any]]:
    """
    Build a flat index of every available changelog: release, version, order.

    Cached, because it costs one API call per release directory and the answer
    only changes when a new snapshot ships.
    """
    def build():
        index = []
        for release in list_changelog_releases():
            for version_id in list_changelogs(release):
                index.append({"release": release, "version": version_id})
        return index

    return cache.cached_fetch("misode:changelog-index",
                              cache.TTL_CHANGELOG_INDEX, build)


def get_changes_between(from_version: Optional[str], to_version: str,
                        topic: Optional[str] = None,
                        max_versions: int = 40) -> Dict[str, Any]:
    """
    Collect technical changelog entries across a version range.

    This is the function that answers the question an agent actually has:
    "my knowledge of Minecraft is older than this pack -- what changed?"

    Args:
        from_version: Exclusive lower bound. None means "everything up to
                      to_version", which is right for an agent starting cold.
        to_version:   Inclusive upper bound, the pack's target version.
        topic:        Optional case-insensitive filter over tags and text,
                      e.g. "component", "loot", "text", "recipe".
        max_versions: Cap on changelog files fetched, so a wide range cannot
                      turn into hundreds of requests. Truncation is reported,
                      never silent.

    Returns:
        Dict with the ordered entries, the versions covered, and -- if the
        range was capped -- what was left out.
    """
    from ..knowledge import parse_version

    index = _all_changelog_entries()
    if not index:
        return {
            "success": False,
            "error": "no changelogs available (misode/technical-changes unreachable)",
            "from_version": from_version,
            "to_version": to_version,
        }

    to_key = parse_version(to_version)
    from_key = parse_version(from_version) if from_version else None

    # Filter by the RELEASE the changelog belongs to, not by the changelog's
    # own version ID. Most entries are snapshots ("24w14a", "1.21.2-pre1")
    # whose IDs carry no usable ordering against a release number -- comparing
    # them directly put every snapshot below 1.0 and silently returned nothing.
    # The containing release directory is the reliable signal: everything under
    # "1.21/" describes changes that land in 1.21.
    in_range = []
    for item in index:
        release_key = parse_version(item["release"])
        if release_key > to_key:
            continue
        if from_key is not None and release_key <= from_key:
            continue
        in_range.append(item)

    # Order by release, then by version ID within the release so snapshots read
    # in roughly chronological order.
    in_range.sort(key=lambda i: (parse_version(i["release"]),
                                 parse_version(i["version"]),
                                 i["version"]))

    truncated = False
    omitted: List[str] = []
    if len(in_range) > max_versions:
        # Keep the versions NEAREST the target -- those are the ones whose
        # changes the agent's output must satisfy. Dropping the far end is the
        # least-bad truncation.
        omitted = [i["version"] for i in in_range[:-max_versions]]
        in_range = in_range[-max_versions:]
        truncated = True

    results = []
    for item in in_range:
        content = get_changelog(item["release"], item["version"])
        if not content:
            continue
        entries = parse_changelog(content)

        if topic:
            t = topic.lower()
            entries = [
                e for e in entries
                if t in e["description"].lower()
                or any(t in tag.lower() for tag in e["tags"])
            ]

        if entries:
            results.append({
                "version": item["version"],
                "release": item["release"],
                "entry_count": len(entries),
                "entries": entries,
            })

    total = sum(r["entry_count"] for r in results)

    return {
        "success": True,
        "from_version": from_version,
        "to_version": to_version,
        "topic": topic,
        "versions_covered": [r["version"] for r in results],
        "total_entries": total,
        "changes": results,
        "truncated": truncated,
        "omitted_versions": omitted if truncated else None,
        "note": (
            f"Range capped at {max_versions} versions; {len(omitted)} older "
            "versions were omitted. Narrow from_version to see them."
            if truncated else None
        ),
        "source": "https://github.com/misode/technical-changes",
    }


# ============================================================================
# Sitemap Functions
# ============================================================================

def get_sitemap() -> List[str]:
    """Get all URLs from the sitemap."""
    try:
        content = _request(GITHUB_SITEMAP, json_response=False)
        return [line.strip() for line in content.split('\n') if line.strip()]
    except Exception as e:
        logger.warning("misode request failed: %s", e)
        return []


# ============================================================================
# Utility Functions for MCP Agents
# ============================================================================

def get_entry(version_id: str, data_type: str, entry_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific entry by ID.
    
    Args:
        version_id: Minecraft version
        data_type: Data type (e.g., "loot_table")
        entry_id: Entry ID (e.g., "chests/ancient_city")
        
    Returns:
        Entry data or None
    """
    try:
        data = get_data(version_id, data_type)
        return data.get(entry_id)
    except Exception:
        return None


def list_entries(version_id: str, data_type: str) -> List[str]:
    """
    Get list of all entry IDs for a data type.
    
    Args:
        version_id: Minecraft version
        data_type: Data type
        
    Returns:
        List of entry IDs
    """
    try:
        data = get_data(version_id, data_type)
        return list(data.keys())
    except Exception:
        return []


def filter_entries(version_id: str, data_type: str, prefix: str) -> List[str]:
    """
    Get entries that start with a prefix.
    
    Args:
        version_id: Minecraft version
        data_type: Data type
        prefix: Prefix to filter by (e.g., "chests/")
        
    Returns:
        List of matching entry IDs
    """
    entries = list_entries(version_id, data_type)
    return [e for e in entries if e.startswith(prefix)]


# ============================================================================
# Main / Testing
# ============================================================================

if __name__ == "__main__":
    print("=== Misode Data Pack Generators Client - MCP Optimized ===\n")
    
    # Test versions
    print("1. Testing list_versions()...")
    try:
        versions = list_versions()
        print(f"   Found {len(versions)} versions")
        if versions:
            print(f"   First 5: {versions[:5]}")
        
        latest = get_latest_release()
        print(f"   Latest release: {latest}")
        test_version = latest or "1.21.4"
    except Exception as e:
        print(f"   Error: {e}")
        test_version = "1.21.4"
    
    print(f"\n2. Using version: {test_version}")
    
    # Test generators
    print("\n3. Testing list_generators()...")
    generators = list_generators()
    print(f"   Found {len(generators)} generators")
    print(f"   Sample: {generators[:5]}")
    
    # Test registries
    print("\n4. Testing get_registries()...")
    try:
        registries = get_registries(test_version)
        print(f"   Found {len(registries)} registries")
        registry_names = list(registries.keys())[:5]
        print(f"   Sample: {registry_names}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test loot tables
    print("\n5. Testing get_loot_tables()...")
    try:
        loot_tables = get_loot_tables(test_version)
        print(f"   Found {len(loot_tables)} loot tables")
        
        chest_tables = filter_entries(test_version, "loot_table", "chests/")
        print(f"   Chest loot tables: {len(chest_tables)}")
        print(f"   Sample: {chest_tables[:3]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test search
    print("\n6. Testing search_data()...")
    try:
        results = search_data(test_version, "loot_table", "diamond")
        print(f"   Found {len(results)} results for 'diamond'")
        if results:
            print(f"   Results: {results[:5]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test recipes
    print("\n7. Testing get_recipes()...")
    try:
        recipes = get_recipes(test_version)
        print(f"   Found {len(recipes)} recipes")
        
        diamond_recipes = search_data(test_version, "recipe", "diamond")
        print(f"   Diamond recipes: {len(diamond_recipes)}")
        print(f"   Sample: {diamond_recipes[:5]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test changelogs
    print("\n8. Testing changelog functions...")
    try:
        releases = list_changelog_releases()
        print(f"   Found {len(releases)} release folders")
        print(f"   Sample: {releases[:5]}")
        
        if releases:
            test_release = releases[0]
            changelogs = list_changelogs(test_release)
            print(f"   Changelogs in {test_release}: {len(changelogs)}")
            if changelogs:
                print(f"   Sample: {changelogs[:3]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n=== All tests completed! ===")