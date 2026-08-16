"""
Workspace awareness: read pack.mcmeta and map between pack formats and
Minecraft versions.

The assistant preprompt tells the agent to "get the pack_format (generally in
/pack.mcmeta)" -- but until now there was no tool to do it, so the agent had to
guess the target version, and every version-aware tool downstream inherited
that guess. This module removes the guess.

The pack_format <-> version mapping is derived from live Spyglass data
(data_pack_version / resource_pack_version per version), never hardcoded, so it
stays correct as new versions ship.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import cache
from .scrappers import spyglass

logger = logging.getLogger("minecode.packmeta")

# Directories never worth descending into when hunting for pack.mcmeta.
_SKIP_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "venv", ".venv", "__pycache__",
    ".idea", ".vscode", "dist", "build", ".gradle", "target", "site-packages",
}

MAX_SEARCH_DEPTH = 4


# ---------------------------------------------------------------------------
# pack.mcmeta discovery and parsing
# ---------------------------------------------------------------------------

def find_pack_mcmeta(start: str | Path, max_depth: int = MAX_SEARCH_DEPTH) -> List[Path]:
    """
    Find pack.mcmeta files at or under `start`.

    Returns every match, shallowest first. A workspace holding both a datapack
    and a resource pack is normal, and picking one arbitrarily would silently
    target the wrong one.
    """
    start = Path(start).expanduser().resolve()

    if start.is_file():
        return [start] if start.name == "pack.mcmeta" else []

    if not start.is_dir():
        return []

    direct = start / "pack.mcmeta"
    found: List[Path] = [direct] if direct.exists() else []

    def descend(directory: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = list(directory.iterdir())
        except (PermissionError, OSError):
            return
        for entry in entries:
            if not entry.is_dir() or entry.name in _SKIP_DIRS or entry.name.startswith("."):
                continue
            candidate = entry / "pack.mcmeta"
            if candidate.exists() and candidate not in found:
                found.append(candidate)
            descend(entry, depth + 1)

    descend(start, 1)
    return found


def _classify_pack(mcmeta_path: Path) -> str:
    """Tell a datapack from a resource pack by which sibling directory exists."""
    root = mcmeta_path.parent
    has_data = (root / "data").is_dir()
    has_assets = (root / "assets").is_dir()
    if has_data and has_assets:
        return "combined"
    if has_data:
        return "data_pack"
    if has_assets:
        return "resource_pack"
    return "unknown"


def read_pack_mcmeta(path: str | Path) -> Dict[str, Any]:
    """Parse one pack.mcmeta into a structured summary."""
    p = Path(path).expanduser().resolve()

    try:
        raw = p.read_text(encoding="utf-8-sig")  # tolerate a BOM
    except Exception as e:
        return {"success": False, "path": str(p), "error": f"could not read: {e}"}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "path": str(p),
            "error": f"invalid JSON at line {e.lineno} column {e.colno}: {e.msg}",
            "hint": "pack.mcmeta must be strict JSON. Trailing commas and comments are not allowed.",
        }

    pack = data.get("pack", {})
    if not isinstance(pack, dict):
        return {"success": False, "path": str(p),
                "error": "'pack' key is missing or not an object"}

    pack_format = pack.get("pack_format")
    supported = pack.get("supported_formats")

    fmt_min = fmt_max = pack_format
    range_source = "pack_format"

    # `supported_formats` accepts three shapes across versions: an object with
    # min_inclusive/max_inclusive, a two-element array, or a bare int.
    if isinstance(supported, dict):
        fmt_min = supported.get("min_inclusive", pack_format)
        fmt_max = supported.get("max_inclusive", pack_format)
        range_source = "supported_formats"
    elif isinstance(supported, list) and len(supported) == 2:
        fmt_min, fmt_max = supported[0], supported[1]
        range_source = "supported_formats"
    elif isinstance(supported, int):
        fmt_min = fmt_max = supported
        range_source = "supported_formats"

    # Newer packs express the same range as flat `min_format` / `max_format`
    # keys instead. Missing these reported a multi-version pack as
    # single-version, which is worse than not reading the file at all -- the
    # agent then writes syntax valid only at the low end of a range it does
    # not know exists.
    min_format = pack.get("min_format")
    max_format = pack.get("max_format")
    if isinstance(min_format, int) or isinstance(max_format, int):
        if isinstance(min_format, int):
            fmt_min = min_format
        if isinstance(max_format, int):
            fmt_max = max_format
        range_source = "min_format/max_format"

    # Guard against a malformed file declaring an inverted range.
    inverted = (isinstance(fmt_min, int) and isinstance(fmt_max, int)
                and fmt_min > fmt_max)
    if inverted:
        fmt_min, fmt_max = fmt_max, fmt_min

    result = {
        "success": True,
        "path": str(p),
        "pack_root": str(p.parent),
        "pack_type": _classify_pack(p),
        "pack_format": pack_format,
        "supported_formats": supported,
        "min_format": min_format,
        "max_format": max_format,
        "format_range_source": range_source,
        "format_min": fmt_min,
        "format_max": fmt_max,
        "multi_version": fmt_min != fmt_max,
        "description": pack.get("description"),
        "has_overlays": "overlays" in data,
        "overlays": data.get("overlays"),
        "raw": data,
    }

    if inverted:
        result["warning"] = (
            f"pack.mcmeta declares an inverted format range "
            f"({max_format} to {min_format}); treating it as {fmt_min}-{fmt_max}."
        )

    return result


# ---------------------------------------------------------------------------
# pack_format <-> version mapping, from live Spyglass data
# ---------------------------------------------------------------------------

def _version_table() -> List[Dict[str, Any]]:
    """All Spyglass versions, cached. Refreshed periodically for new snapshots."""
    return cache.cached_fetch(
        "spyglass:versions:full",
        cache.TTL_VERSION_LIST,
        spyglass.get_versions,
    )


def pack_format_to_versions(pack_format: int, kind: str = "data") -> Dict[str, Any]:
    """
    Map a pack format number to the Minecraft versions that use it.

    `kind` is "data" or "resource" -- the two numbering schemes diverged and
    conflating them is a common source of wrong-version work.
    """
    field = "data_pack_version" if kind == "data" else "resource_pack_version"

    try:
        versions = _version_table()
    except Exception as e:
        return {"success": False, "error": f"could not fetch version table: {e}"}

    matches = [v for v in versions if v.get(field) == pack_format]
    releases = [v for v in matches if v.get("type") == "release"]

    if not matches:
        known = sorted({v.get(field) for v in versions if v.get(field) is not None})
        return {
            "success": False,
            "pack_format": pack_format,
            "kind": kind,
            "error": f"no Minecraft version uses {kind} pack format {pack_format}",
            "known_formats": known,
        }

    return {
        "success": True,
        "pack_format": pack_format,
        "kind": kind,
        "versions": [v["id"] for v in matches],
        "releases": [v["id"] for v in releases],
        "recommended_version": (releases or matches)[0]["id"],
        "note": (
            "Use recommended_version for every other version-taking tool. It is "
            "the newest stable release on this pack format."
        ),
    }


def version_to_pack_formats(version: str) -> Dict[str, Any]:
    """Return the data and resource pack formats for a Minecraft version."""
    try:
        versions = _version_table()
    except Exception as e:
        return {"success": False, "error": f"could not fetch version table: {e}"}

    for v in versions:
        if v.get("id") == version:
            return {
                "success": True,
                "version": version,
                "type": v.get("type"),
                "data_pack_format": v.get("data_pack_version"),
                "resource_pack_format": v.get("resource_pack_version"),
                "data_version": v.get("data_version"),
                "release_time": v.get("release_time"),
            }

    return {
        "success": False,
        "version": version,
        "error": f"unknown version '{version}'",
        "did_you_mean": suggest_versions(version, versions),
    }


def suggest_versions(requested: str, versions: Optional[List[Dict]] = None,
                     limit: int = 6) -> List[str]:
    """
    Suggest close version IDs for a miss.

    An agent recovers from "did you mean 1.21.1?" It does not recover from
    "404 Client Error", which is what an unresolved version produced before.
    """
    if versions is None:
        try:
            versions = _version_table()
        except Exception:
            return []

    ids = [v.get("id", "") for v in versions if v.get("id")]
    requested = (requested or "").strip().lower()
    if not requested:
        return ids[:limit]

    exact_prefix = [i for i in ids if i.lower().startswith(requested)]
    if exact_prefix:
        return exact_prefix[:limit]

    # Fall back to the same major.minor line.
    m = re.match(r"^(\d+\.\d+)", requested)
    if m:
        line = m.group(1)
        same_line = [i for i in ids if i.startswith(line)]
        if same_line:
            return same_line[:limit]

    return [i for i in ids if requested in i.lower()][:limit] or ids[:limit]


def resolve_version(version: str) -> Dict[str, Any]:
    """
    Normalize a user- or agent-supplied version string to one Spyglass knows.

    Accepts "latest", "latest_snapshot", an exact ID, or a partial like "1.21"
    that should resolve to the newest matching release. Returns what it
    resolved to, so the agent can see any substitution rather than silently
    getting data for a different version than it asked for.
    """
    try:
        versions = _version_table()
    except Exception as e:
        return {"success": False, "requested": version,
                "error": f"could not fetch version table: {e}"}

    if not versions:
        return {"success": False, "requested": version,
                "error": "version table is empty"}

    requested = (version or "").strip()

    if requested.lower() in ("latest", "latest_release", "release"):
        for v in versions:
            if v.get("type") == "release":
                return {"success": True, "requested": requested,
                        "resolved": v["id"], "exact": False,
                        "reason": "newest stable release"}

    if requested.lower() in ("latest_snapshot", "snapshot"):
        for v in versions:
            if v.get("type") == "snapshot":
                return {"success": True, "requested": requested,
                        "resolved": v["id"], "exact": False,
                        "reason": "newest snapshot"}

    for v in versions:
        if v.get("id") == requested:
            return {"success": True, "requested": requested,
                    "resolved": requested, "exact": True}

    # Partial like "1.21" -> newest release on that line.
    candidates = [v for v in versions
                  if v.get("id", "").startswith(requested + ".")
                  and v.get("type") == "release"]
    if candidates:
        return {
            "success": True,
            "requested": requested,
            "resolved": candidates[0]["id"],
            "exact": False,
            "reason": f"'{requested}' is not itself a version ID; resolved to the "
                      f"newest release on that line",
        }

    return {
        "success": False,
        "requested": requested,
        "error": f"unknown Minecraft version '{requested}'",
        "did_you_mean": suggest_versions(requested, versions),
    }


# ---------------------------------------------------------------------------
# The combined entry point
# ---------------------------------------------------------------------------

def detect(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Detect the target Minecraft version(s) for a workspace.

    This is the tool an agent should call before anything else in a Minecraft
    project: everything downstream needs a version, and this is where the
    version comes from.
    """
    search_root = Path(path).expanduser() if path else Path.cwd()

    found = find_pack_mcmeta(search_root)
    if not found:
        return {
            "success": False,
            "searched": str(search_root.resolve()),
            "error": "no pack.mcmeta found",
            "hint": (
                "Point `path` at the pack root, or the directory containing it. "
                "Without a pack.mcmeta the target version cannot be detected -- "
                "ask the user which Minecraft version to target rather than "
                "assuming the latest."
            ),
        }

    packs = []
    for mcmeta in found:
        info = read_pack_mcmeta(mcmeta)
        if not info.get("success"):
            packs.append(info)
            continue

        kind = "resource" if info["pack_type"] == "resource_pack" else "data"
        if info.get("format_min") is not None:
            mapped = pack_format_to_versions(info["format_min"], kind=kind)
            info["version_info"] = mapped
            if mapped.get("success"):
                info["target_version"] = mapped["recommended_version"]

            if info.get("multi_version") and info.get("format_max") is not None:
                info["max_version_info"] = pack_format_to_versions(
                    info["format_max"], kind=kind)

        packs.append(info)

    usable = [p for p in packs if p.get("target_version")]
    primary = usable[0] if usable else None

    result = {
        "success": True,
        "searched": str(search_root.resolve()),
        "packs_found": len(packs),
        "packs": packs,
    }

    if primary:
        result["target_version"] = primary["target_version"]
        result["pack_format"] = primary.get("pack_format")
        result["pack_root"] = primary.get("pack_root")
        result["multi_version"] = primary.get("multi_version", False)
        result["next_step"] = (
            f"Pass version='{primary['target_version']}' to every version-taking "
            f"tool. Call get_technical_changes(to_version='{primary['target_version']}') "
            "before writing anything, to learn what changed since your training data."
        )
        if primary.get("multi_version"):
            result["warning"] = (
                "This pack declares a range of supported formats. Any syntax you "
                "write must be valid across the whole range, or be split using "
                "pack.mcmeta overlays. Check both ends before choosing a syntax."
            )
    else:
        result["success"] = False
        result["error"] = "found pack.mcmeta but could not resolve a target version"

    return result
