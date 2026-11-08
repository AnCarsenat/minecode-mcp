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

import json

import requests
from typing import Optional, List, Dict, Any, Union

from .. import cache

# API Configuration
BASE_URL = "https://api.spyglassmc.com"
USER_AGENT = "MineCode/1.0 (+https://github.com/AnCarsenat/minecode-mcp)"
TIMEOUT = 30  # registry payloads are large; a short timeout fails on slow links

# Default headers for all requests
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT
}


def _make_request(endpoint: str, params: Optional[Dict] = None,
                  ttl: int = cache.IMMUTABLE) -> Dict[str, Any]:
    """
    Make a request to the Spyglass API, via the disk cache.

    Args:
        endpoint: API endpoint (e.g., "/mcje/versions")
        params: Optional query parameters
        ttl: Cache lifetime. Defaults to IMMUTABLE, which is correct for
             version-pinned endpoints -- the registries for 1.21.4 are the
             same today as next year. Endpoints whose content moves (the
             version list, mcdoc symbols) pass an explicit TTL.

    Returns:
        JSON response as dictionary

    Raises:
        requests.HTTPError: If the request fails
    """
    url = f"{BASE_URL}{endpoint}"
    key = f"spyglass:{endpoint}:{sorted((params or {}).items())}"

    def fetch():
        response = requests.get(url, headers=DEFAULT_HEADERS, params=params,
                                timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()

    return cache.cached_fetch(key, ttl, fetch)


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
    # Not immutable: new snapshots appear weekly.
    return _make_request("/mcje/versions", ttl=cache.TTL_VERSION_LIST)


def get_latest_release() -> Optional[Dict[str, Any]]:
    """Return the newest stable release, or None if the list is empty."""
    for v in get_versions():
        if v.get("type") == "release":
            return v
    return None


def get_latest_snapshot() -> Optional[Dict[str, Any]]:
    """Return the newest snapshot, or None if the list is empty."""
    for v in get_versions():
        if v.get("type") == "snapshot":
            return v
    return None


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
    Get the full vanilla-mcdoc symbol table.

    WARNING: this response is very large (megabytes). Never return it to an
    agent unfiltered -- it will either exhaust the context window or be
    truncated into unusable fragments. Use search_mcdoc_symbols() to find a
    symbol path and get_mcdoc_symbol() to fetch one definition.

    Cached with a TTL rather than immutably: mcdoc tracks the latest game
    version and is updated continuously.
    """
    return _make_request("/vanilla-mcdoc/symbols", ttl=cache.TTL_VERSION_LIST)


def _symbol_map() -> Dict[str, Any]:
    """
    Normalize the mcdoc response to a flat {symbol_path: definition} map.

    The API nests symbols under a category key ("mcdoc", "mcdoc/dispatcher").
    Callers only ever want the flat lookup, and flattening in one place keeps
    the shape change contained if the API restructures.
    """
    raw = get_mcdoc_symbols()
    if not isinstance(raw, dict):
        return {}

    flat: Dict[str, Any] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        if key in ("mcdoc", "mcdoc/dispatcher"):
            for sym, definition in value.items():
                flat[sym] = definition
        else:
            # Unrecognised top-level key: keep it addressable rather than
            # dropping data we do not understand.
            flat[key] = value
    return flat or (raw if isinstance(raw, dict) else {})


def _dispatcher_entries() -> Dict[str, Dict[str, Any]]:
    """{"minecraft:entity": {"item_display": <type>, ...}, ...}"""
    raw = get_mcdoc_symbols()
    table = raw.get("mcdoc/dispatcher") if isinstance(raw, dict) else None
    return table if isinstance(table, dict) else {}


def search_mcdoc_symbols(query: str, limit: int = 40) -> List[str]:
    """
    Find mcdoc symbol paths matching a query. Returns paths only, no bodies.

    Dispatcher entries are searched too and returned as "dispatcher[key]",
    e.g. "minecraft:entity[item_display]". Entity, block entity and component
    ids live only there, so before this a search for "item_display" found
    nothing.

    Args:
        query: Case-insensitive substring, e.g. "ItemStack", "loot", "text"
        limit: Maximum paths to return

    Returns:
        Matching symbol paths, exact-ish matches first
    """
    q = (query or "").lower()
    if q.startswith("minecraft:") and "[" not in q:
        q = q[len("minecraft:"):]
    candidates = list(_symbol_map())
    for dispatcher, entries in _dispatcher_entries().items():
        if isinstance(entries, dict):
            candidates.extend(f"{dispatcher}[{key}]" for key in entries
                              if not key.startswith("%"))
    matches = [c for c in candidates if q in c.lower()]

    # Rank by how close the match is to the tail of the path, which is the
    # part a caller usually knows ("ItemStack" rather than the full namespace).
    def rank(path: str) -> tuple:
        tail = path.rsplit("::", 1)[-1].lower()
        if path.endswith("]") and "[" in path:
            tail = path[path.index("[") + 1:-1].lower()
        return (0 if tail == q else 1 if tail.startswith(q) else 2, len(path), path)

    matches.sort(key=rank)
    return matches[:limit]


# ---------------------------------------------------------------------------
# Rendering a symbol for an agent
#
# The old renderer pruned the raw mcdoc JSON by dict nesting depth. A struct
# field's type sits four dicts down (definition -> fields -> pair -> type), so
# at the default depth=3 every field type -- even a two-key reference such as
# {"kind": "reference", "path": "...ItemStack"} -- became "_truncated", and the
# `...DisplayBase` spread that carries most of item_display's fields was never
# followed. The renderer below flattens a struct into a field list, follows
# spreads (inheritance) to the end, writes each type as one line of mcdoc-like
# text, and reports any cut it makes with `truncated: true`.
# ---------------------------------------------------------------------------

# Upper bounds that keep one answer usable. Hitting one is always reported.
_MAX_SPREAD_DEPTH = 10      # inheritance chain length
_MAX_UNION_MEMBERS = 16
_MAX_ENUM_VALUES = 40


def _attr_value(attr: Dict[str, Any]) -> Any:
    v = attr.get("value")
    while isinstance(v, dict) and "value" in v:
        v = v["value"]
    return v


def _version_attrs(node: Any) -> Dict[str, Any]:
    """since / until / deprecated from an mcdoc attribute list."""
    out: Dict[str, Any] = {}
    attrs = node.get("attributes") if isinstance(node, dict) else None
    for a in attrs or []:
        if not isinstance(a, dict):
            continue
        name = a.get("name")
        if name in ("since", "until"):
            out[name] = _attr_value(a)
        elif name == "deprecated":
            out["deprecated"] = _attr_value(a) or True
    return out


def _range(r: Any) -> str:
    if not isinstance(r, dict):
        return ""
    lo, hi, kind = r.get("min"), r.get("max"), r.get("kind") or 0
    if lo is not None and lo == hi:
        return str(lo)
    # Spyglass RangeKind: bit 2 = min exclusive, bit 1 = max exclusive.
    delim = ("<" if kind & 2 else "") + ".." + ("<" if kind & 1 else "")
    return f"{'' if lo is None else lo}{delim}{'' if hi is None else hi}"


def _accessor(acc: Any) -> str:
    parts = []
    for a in acc or []:
        parts.append(f"%{a['keyword']}" if isinstance(a, dict) and "keyword" in a else str(a))
    return ".".join(parts)


def _index(idx: Any) -> str:
    if not isinstance(idx, dict):
        return str(idx)
    if idx.get("kind") == "dynamic":
        return f"[{_accessor(idx.get('accessor'))}]"
    return str(idx.get("value"))


def _with_version(text: str, node: Any) -> str:
    v = _version_attrs(node)
    tags = [f"{k} {v[k]}" for k in ("since", "until") if k in v]
    return f"{text} ({', '.join(tags)})" if tags else text


class _Renderer:
    def __init__(self, symbols: Dict[str, Any], depth: int):
        self.symbols = symbols
        self.depth = depth
        self.truncated: List[str] = []
        self.referenced: List[str] = []
        self.unresolved_spreads: List[Dict[str, Any]] = []

    def _ref(self, path: str) -> None:
        if path and path not in self.referenced:
            self.referenced.append(path)

    # -- types ----------------------------------------------------------------
    def type_str(self, t: Any) -> str:
        if not isinstance(t, dict):
            return str(t)
        k = t.get("kind")
        if k == "reference":
            self._ref(t.get("path", ""))
            return t.get("path", "?")
        if k in ("boolean", "byte", "short", "int", "long", "float", "double",
                 "string", "any"):
            if "value" in t:  # a constant of that type
                return json.dumps(t["value"])
            r = _range(t.get("valueRange") or t.get("lengthRange"))
            return f"{k} @ {r}" if r else k
        if k == "literal":
            v = t.get("value")
            return json.dumps(v.get("value") if isinstance(v, dict) else v)
        if k in ("byte_array", "int_array", "long_array"):
            r = _range(t.get("lengthRange"))
            base = k.split("_")[0] + "[]"
            return f"{base} @ {r}" if r else base
        if k == "list":
            r = _range(t.get("lengthRange"))
            inner = f"[{self.type_str(t.get('item'))}]"
            return f"{inner} @ {r}" if r else inner
        if k == "tuple":
            return "[" + ", ".join(self.type_str(i) for i in t.get("items") or []) + "]"
        if k == "union":
            members = t.get("members") or []
            shown = [_with_version(self.type_str(m), m) for m in members[:_MAX_UNION_MEMBERS]]
            if len(members) > _MAX_UNION_MEMBERS:
                shown.append(f"... {len(members) - _MAX_UNION_MEMBERS} more")
            return "(" + " | ".join(shown) + ")" if shown else "never"
        if k == "enum":
            values = t.get("values") or []
            shown = [_with_version(json.dumps(v.get("value")), v) for v in values[:_MAX_ENUM_VALUES]
                     if isinstance(v, dict)]
            if len(values) > _MAX_ENUM_VALUES:
                shown.append(f"... {len(values) - _MAX_ENUM_VALUES} more")
            return f"enum({t.get('enumKind', '?')}) " + " | ".join(shown)
        if k == "dispatcher":
            idx = "".join(_index(i) for i in t.get("parallelIndices") or [])
            return f"{t.get('registry', '?')}[{idx}]"
        if k == "indexed":
            idx = "".join(_index(i) for i in t.get("parallelIndices") or [])
            return f"{self.type_str(t.get('child'))}[{idx}]"
        if k == "concrete":
            args = ", ".join(self.type_str(a) for a in t.get("typeArgs") or [])
            return f"{self.type_str(t.get('child'))}<{args}>"
        if k == "template":
            params = ", ".join(str(p.get("path", p)) if isinstance(p, dict) else str(p)
                               for p in t.get("typeParams") or [])
            return f"template<{params}> {self.type_str(t.get('child'))}"
        if k == "struct":
            keys = [str(f.get("key")) for f in t.get("fields") or []
                    if isinstance(f, dict) and f.get("kind") == "pair"]
            return "struct {" + ", ".join(keys) + "}"
        return str(k or "?")

    # -- structs --------------------------------------------------------------
    def fields(self, struct: Dict[str, Any], level: int = 1,
               inherited_from: Optional[str] = None,
               inherited_attrs: Optional[Dict[str, Any]] = None,
               seen: Optional[set] = None, chain: int = 0) -> List[Dict[str, Any]]:
        """Flatten a struct's fields, following spreads."""
        seen = set() if seen is None else seen
        out: List[Dict[str, Any]] = []
        for f in struct.get("fields") or []:
            if not isinstance(f, dict):
                continue
            if f.get("kind") == "spread":
                out.extend(self._spread(f, level, inherited_from, inherited_attrs, seen, chain))
                continue
            if f.get("kind") != "pair":
                continue
            key = f.get("key")
            entry: Dict[str, Any] = {
                "key": key if isinstance(key, str) else f"[{self.type_str(key)}]",
                "type": self.type_str(f.get("type")),
                "optional": bool(f.get("optional", False)),
            }
            attrs = dict(inherited_attrs or {})
            attrs.update(_version_attrs(f))
            entry.update(attrs)
            if f.get("desc"):
                entry["desc"] = f["desc"].strip()
            if inherited_from:
                entry["inherited_from"] = inherited_from
            self._nested(entry, f.get("type"), level)
            out.append(entry)
        return out

    def _nested(self, entry: Dict[str, Any], t: Any, level: int) -> None:
        """Expand an inline struct (or list of one) up to `depth` levels."""
        inner = t
        if isinstance(inner, dict) and inner.get("kind") == "list":
            inner = inner.get("item")
        if not (isinstance(inner, dict) and inner.get("kind") == "struct"):
            return
        if level >= self.depth:
            self.truncated.append(entry["key"])
            entry["fields_omitted"] = "raise depth to expand"
            return
        entry["fields"] = self.fields(inner, level + 1)

    def _spread(self, f, level, inherited_from, inherited_attrs, seen, chain):
        t = f.get("type") if isinstance(f.get("type"), dict) else {}
        attrs = dict(inherited_attrs or {})
        attrs.update(_version_attrs(f))
        if t.get("kind") == "concrete":  # generic struct: spread its body
            t = t.get("child") if isinstance(t.get("child"), dict) else {}
        if t.get("kind") == "struct":
            return self.fields(t, level, inherited_from, attrs, seen, chain)
        path = t.get("path") if t.get("kind") == "reference" else None
        target = self.symbols.get(path) if path else None
        if isinstance(target, dict) and target.get("kind") == "template":
            target = target.get("child")
        if not (isinstance(target, dict) and target.get("kind") == "struct"):
            self.unresolved_spreads.append(
                dict(type=self.type_str(t), **attrs,
                     note=("fields depend on a runtime key; fetch them with "
                           f"symbol='{t.get('registry')}[<key>]'")
                     if t.get("kind") == "dispatcher"
                     else "not a struct; fetch it separately"))
            return []
        if path in seen:
            return []
        if chain >= _MAX_SPREAD_DEPTH:
            self.truncated.append(f"...{path}")
            self.unresolved_spreads.append({"type": path, **attrs,
                                            "note": "inheritance chain too deep; fetch it separately"})
            return []
        self._ref(path)
        return self.fields(target, level, path, attrs, seen | {path}, chain + 1)


def _resolve_mcdoc_symbol(symbol: str, symbols: Dict[str, Any]):
    """
    Resolve what an agent typed to (path, definition, candidates).

    Accepts a full path with or without the leading "::", a unique tail name
    ("ItemDisplay"), "dispatcher[key]" ("minecraft:entity[item_display]"), or
    a bare dispatcher key ("item_display", "minecraft:item_display").
    """
    s = (symbol or "").strip()
    for cand in (s, "::" + s.lstrip(":")):
        if cand in symbols:
            return cand, symbols[cand], []

    dispatchers = _dispatcher_entries()
    if s.endswith("]") and "[" in s:
        name, key = s[:-1].split("[", 1)
        name = name if ":" in name else f"minecraft:{name}"
        entry = (dispatchers.get(name) or {}).get(key)
        return (f"{name}[{key}]", entry, []) if entry is not None else (None, None, [])

    tail = [p for p in symbols if p.rsplit("::", 1)[-1] == s]
    if len(tail) == 1:
        return tail[0], symbols[tail[0]], []

    key = s[len("minecraft:"):] if s.startswith("minecraft:") else s
    hits = [f"{d}[{key}]" for d, entries in dispatchers.items()
            if isinstance(entries, dict) and key in entries]
    if len(hits) == 1:
        d = hits[0].split("[", 1)[0]
        return hits[0], dispatchers[d][key], []
    return None, None, tail + hits


def get_mcdoc_symbol(symbol: str, depth: int = 3) -> Optional[Dict[str, Any]]:
    """
    Get one mcdoc symbol definition, rendered for reading.

    A struct comes back as a flat `fields` list. Fields inherited through
    spreads (`...super::DisplayBase`, then `EntityBase`) are included and
    marked `inherited_from`. Each field's type is one line of mcdoc-like text
    ("float @ 0..1", "[double] @ 3", "::java::world::item::ItemStack");
    referenced named types are listed in `referenced_symbols` to fetch next.

    Args:
        symbol: Fully-qualified path ("::java::world::item::ItemStack", the
            leading "::" is optional), a unique tail name ("ItemStack"), or a
            dispatcher entry ("minecraft:entity[item_display]", "item_display")
        depth: Levels of INLINE nested structs to expand (1-6). Named types
            are never expanded inline; fetch them by path.

    Returns:
        The rendered symbol; None if it does not exist; or
        {"ambiguous": [...]} when a short name matches several symbols.
    """
    depth = max(1, min(int(depth), 6))
    symbols = _symbol_map()
    path, definition, candidates = _resolve_mcdoc_symbol(symbol, symbols)
    if definition is None:
        return {"ambiguous": candidates} if candidates else None

    result: Dict[str, Any] = {"symbol": path, "depth": depth}
    if path != symbol:
        result["requested"] = symbol

    # A dispatcher entry that just names a type ("item_display" ->
    # ItemDisplay): show the type itself.
    if isinstance(definition, dict) and definition.get("kind") == "reference" \
            and definition.get("path") in symbols:
        result["resolves_to"] = definition["path"]
        definition = symbols[definition["path"]]

    # A whole dispatcher ("minecraft:entity"): list its keys.
    if isinstance(definition, dict) and "kind" not in definition:
        keys = sorted(k for k in definition if not k.startswith("%"))
        result.update(kind="dispatcher", count=len(keys), keys=keys, truncated=False,
                      hint=f"Fetch one entry with symbol='{path}[<key>]'.")
        return result

    r = _Renderer(symbols, depth)
    body = definition
    if isinstance(body, dict) and body.get("kind") == "template":
        result["template"] = r.type_str({**body, "child": {"kind": "any"}}).rsplit(" ", 1)[0]
        body = body.get("child")

    kind = body.get("kind") if isinstance(body, dict) else None
    result["kind"] = kind
    result.update(_version_attrs(body))
    if kind == "struct":
        fields = r.fields(body)
        result["fields"] = fields
        result["field_count"] = len(fields)
        own = sum(1 for f in fields if "inherited_from" not in f)
        result["own_field_count"] = own
        if own != len(fields):
            result["inherited_from"] = list(dict.fromkeys(
                f["inherited_from"] for f in fields if "inherited_from" in f))
    else:
        result["type"] = r.type_str(body)
        # Unions/enums of structs are only readable from the raw definition.
        result["definition"] = body

    if r.unresolved_spreads:
        result["unresolved_spreads"] = r.unresolved_spreads
    if r.referenced:
        result["referenced_symbols"] = r.referenced
    result["truncated"] = bool(r.truncated)
    if r.truncated:
        result["truncated_at"] = r.truncated
        result["how_to_expand"] = (
            f"Inline structs deeper than depth={depth} were left out. Call again "
            f"with a higher depth (max 6), or fetch the named symbol directly."
        )
    return result


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
