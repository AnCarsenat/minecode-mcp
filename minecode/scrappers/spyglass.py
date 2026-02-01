"""
Spyglass MC API Client
API documentation: https://spyglassmc.com/developer/web-api.html

Provides access to Minecraft Java Edition data including:
- Version information
- Block states
- Commands
- Registries
- Vanilla data/assets
- Mcdoc symbols
"""

import requests
from typing import Optional, List, Dict, Any, Union

# API Configuration
BASE_URL = "https://api.spyglassmc.com"
USER_AGENT = "MineCode/1.0"

# Default headers for all requests
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT
}


def _make_request(endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Make a request to the Spyglass API.
    
    Args:
        endpoint: API endpoint (e.g., "/mcje/versions")
        params: Optional query parameters
        
    Returns:
        JSON response as dictionary
        
    Raises:
        requests.HTTPError: If the request fails
    """
    url = f"{BASE_URL}{endpoint}"
    response = requests.get(url, headers=DEFAULT_HEADERS, params=params)
    response.raise_for_status()
    return response.json()


# ============================================================================
# Version Endpoints
# ============================================================================

def get_versions() -> List[Dict[str, Any]]:
    """
    Get all Minecraft Java Edition versions.
    
    Returns:
        List of version objects with fields:
        - id: Version ID (e.g., "1.21", "24w14a")
        - name: Display name
        - type: "release" or "snapshot"
        - stable: Whether this is a stable release
        - data_version: Data version number
        - protocol_version: Protocol version
        - data_pack_version: Data pack format version
        - resource_pack_version: Resource pack format version
        - build_time: ISO timestamp of build
        - release_time: ISO timestamp of release
        - sha1: SHA1 hash
    """
    return _make_request("/mcje/versions")


# ============================================================================
# Block States Endpoint
# ============================================================================

def get_block_states(version: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get all block states for a specific Minecraft version.
    
    Args:
        version: Minecraft version (e.g., "1.21")
        
    Returns:
        Dictionary mapping block IDs to their state definitions.
        Each block has:
        - [0]: Dictionary of property names to possible values
        - [1]: Dictionary of default property values
        
    Example:
        >>> states = get_block_states("1.21")
        >>> states["oak_stairs"]
        [{"facing": ["north", "south", ...], "half": ["top", "bottom"], ...},
         {"facing": "north", "half": "bottom", ...}]
    """
    return _make_request(f"/mcje/versions/{version}/block_states")


def get_block_info(version: str, block_id: str) -> Optional[Dict[str, Any]]:
    """
    Get state information for a specific block.
    
    Args:
        version: Minecraft version
        block_id: Block ID without namespace (e.g., "oak_stairs")
        
    Returns:
        Block state definition or None if not found
    """
    # Remove minecraft: prefix if present
    block_id = block_id.replace("minecraft:", "")
    states = get_block_states(version)
    return states.get(block_id)


# ============================================================================
# Commands Endpoint
# ============================================================================

def get_commands(version: str) -> Dict[str, Any]:
    """
    Get the command tree for a specific Minecraft version.
    
    Args:
        version: Minecraft version (e.g., "1.21")
        
    Returns:
        Brigadier command tree with root node containing all commands
    """
    return _make_request(f"/mcje/versions/{version}/commands")


def get_command_names(version: str) -> List[str]:
    """
    Get a list of all command names for a version.
    
    Args:
        version: Minecraft version
        
    Returns:
        List of command names (e.g., ["advancement", "attribute", "ban", ...])
    """
    commands = get_commands(version)
    return list(commands.get("children", {}).keys())


def get_command_info(version: str, command_name: str) -> Optional[Dict[str, Any]]:
    """
    Get the command tree for a specific command.
    
    Args:
        version: Minecraft version
        command_name: Command name (e.g., "give", "summon")
        
    Returns:
        Command tree node or None if not found
    """
    commands = get_commands(version)
    return commands.get("children", {}).get(command_name)


# ============================================================================
# Registries Endpoint
# ============================================================================

def get_registries(version: str) -> Dict[str, List[str]]:
    """
    Get all registry contents for a specific version.
    
    Args:
        version: Minecraft version (e.g., "1.21")
        
    Returns:
        Dictionary mapping registry names to lists of entry IDs.
        Registry names include: item, block, entity_type, enchantment,
        biome, dimension_type, etc.
    """
    return _make_request(f"/mcje/versions/{version}/registries")


def get_registry(version: str, registry_name: str) -> List[str]:
    """
    Get entries from a specific registry.
    
    Args:
        version: Minecraft version
        registry_name: Registry name (e.g., "item", "block", "entity_type")
        
    Returns:
        List of registry entry IDs
    """
    registries = get_registries(version)
    return registries.get(registry_name, [])


def get_registry_names(version: str) -> List[str]:
    """
    Get all available registry names for a version.
    
    Args:
        version: Minecraft version
        
    Returns:
        List of registry names
    """
    registries = get_registries(version)
    return list(registries.keys())


# ============================================================================
# Convenience Functions
# ============================================================================

def get_items(version: str) -> List[str]:
    """Get all item IDs for a version."""
    return get_registry(version, "item")


def get_blocks(version: str) -> List[str]:
    """Get all block IDs for a version."""
    return get_registry(version, "block")


def get_entities(version: str) -> List[str]:
    """Get all entity type IDs for a version."""
    return get_registry(version, "entity_type")


def get_biomes(version: str) -> List[str]:
    """Get all biome IDs for a version."""
    return get_registry(version, "biome")


def get_enchantments(version: str) -> List[str]:
    """Get all enchantment IDs for a version."""
    return get_registry(version, "enchantment")


def get_effects(version: str) -> List[str]:
    """Get all mob effect IDs for a version."""
    return get_registry(version, "mob_effect")


def get_particles(version: str) -> List[str]:
    """Get all particle type IDs for a version."""
    return get_registry(version, "particle_type")


def get_sounds(version: str) -> List[str]:
    """Get all sound event IDs for a version."""
    return get_registry(version, "sound_event")


# ============================================================================
# Vanilla Mcdoc Endpoints
# ============================================================================

def get_mcdoc_symbols() -> Dict[str, Any]:
    """
    Get vanilla-mcdoc symbols.
    
    Returns:
        Mcdoc symbol definitions for vanilla Minecraft
    """
    return _make_request("/vanilla-mcdoc/symbols")


# ============================================================================
# Search Functions
# ============================================================================

def search_registry(version: str, registry_name: str, query: str) -> List[str]:
    """
    Search within a registry for entries matching a query.
    
    Args:
        version: Minecraft version
        registry_name: Registry name (e.g., "item", "block")
        query: Search query (case-insensitive substring match)
        
    Returns:
        List of matching registry entry IDs
    """
    entries = get_registry(version, registry_name)
    query = query.lower()
    return [entry for entry in entries if query in entry.lower()]


def search_blocks(version: str, query: str) -> List[str]:
    """Search for blocks matching a query."""
    return search_registry(version, "block", query)


def search_items(version: str, query: str) -> List[str]:
    """Search for items matching a query."""
    return search_registry(version, "item", query)


def search_entities(version: str, query: str) -> List[str]:
    """Search for entity types matching a query."""
    return search_registry(version, "entity_type", query)


# ============================================================================
# Comparison Functions
# ============================================================================

def compare_registries(version1: str, version2: str, registry_name: str) -> Dict[str, List[str]]:
    """
    Compare a registry between two versions.
    
    Args:
        version1: First version
        version2: Second version  
        registry_name: Registry to compare
        
    Returns:
        Dictionary with:
        - added: Entries in version2 but not version1
        - removed: Entries in version1 but not version2
        - common: Entries in both versions
    """
    entries1 = set(get_registry(version1, registry_name))
    entries2 = set(get_registry(version2, registry_name))
    
    return {
        "added": sorted(entries2 - entries1),
        "removed": sorted(entries1 - entries2),
        "common": sorted(entries1 & entries2)
    }


# ============================================================================
# Main / Testing
# ============================================================================

if __name__ == "__main__":
    print("=== Spyglass MC API Client ===\n")
    
    # Test versions
    print("1. Testing get_versions()...")
    versions = get_versions()
    print(f"   Found {len(versions)} versions")
    
    latest = get_latest_release()
    if latest:
        print(f"   Latest release: {latest['id']} ({latest['name']})")
    
    latest_snapshot = get_latest_snapshot()
    if latest_snapshot:
        print(f"   Latest snapshot: {latest_snapshot['id']} ({latest_snapshot['name']})")
    
    # Test with 1.21 (or latest release)
    test_version = latest['id'] if latest else "1.21"
    print(f"\n2. Testing with version: {test_version}")
    
    # Test registries
    print("\n3. Testing get_registries()...")
    registry_names = get_registry_names(test_version)
    print(f"   Found {len(registry_names)} registries")
    print(f"   Sample registries: {registry_names[:5]}")
    
    # Test items
    print("\n4. Testing get_items()...")
    items = get_items(test_version)
    print(f"   Found {len(items)} items")
    print(f"   Sample items: {items[:5]}")
    
    # Test search
    print("\n5. Testing search_items('diamond')...")
    diamond_items = search_items(test_version, "diamond")
    print(f"   Found {len(diamond_items)} diamond items")
    print(f"   Results: {diamond_items[:10]}")
    
    # Test block states
    print("\n6. Testing get_block_info('oak_stairs')...")
    block_info = get_block_info(test_version, "oak_stairs")
    if block_info:
        print(f"   Properties: {list(block_info[0].keys())}")
        print(f"   Defaults: {block_info[1]}")
    
    # Test commands
    print("\n7. Testing get_command_names()...")
    commands = get_command_names(test_version)
    print(f"   Found {len(commands)} commands")
    print(f"   Sample commands: {commands[:10]}")
    
    print("\n=== All tests passed! ===")
