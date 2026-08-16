"""
Disk cache for MineCode scrapers.

Every scraper in this package fetches from an external service on every call.
Without caching, a single agent session refetches the same multi-megabyte
registry payload half a dozen times, which is slow enough that agents time out
and abandon the tool, and which hammers volunteer-funded infrastructure
(Spyglass, misode's GitHub raw endpoints, minecraft.wiki).

Two cache classes:

- IMMUTABLE: data pinned to a released Minecraft version never changes.
  Spyglass registries for 1.21.4 are the same today as next year. Cached
  forever.
- TTL: wiki pages, Mojira issues, and version *lists* do change. Cached with
  an expiry.

The cache is keyed by URL hash and stored as plain files, so it is trivially
inspectable and safe to delete at any time.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("minecode.cache")

# Sentinel TTL meaning "never expires".
IMMUTABLE = -1

# Default TTLs in seconds.
TTL_VERSION_LIST = 6 * 3600      # new snapshots appear weekly
TTL_WIKI = 24 * 3600             # wiki edits are frequent but not urgent
TTL_MOJIRA = 3600                # issue status changes matter
TTL_CHANGELOG_INDEX = 6 * 3600   # new changelog files appear with snapshots

_DISABLED = os.environ.get("MINECODE_NO_CACHE", "").lower() in ("1", "true", "yes")


def _default_cache_dir() -> Path:
    """Return the OS-appropriate cache directory without extra dependencies."""
    override = os.environ.get("MINECODE_CACHE_DIR")
    if override:
        return Path(override)

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "minecode-mcp" / "cache"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "minecode-mcp"
    else:
        base = os.environ.get("XDG_CACHE_HOME")
        if base:
            return Path(base) / "minecode-mcp"
        return Path.home() / ".cache" / "minecode-mcp"

    return Path(tempfile.gettempdir()) / "minecode-mcp-cache"


CACHE_DIR = _default_cache_dir()


def _path_for(key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    # Shard by first two chars so a big cache does not become one huge directory.
    return CACHE_DIR / digest[:2] / f"{digest}.json"


class _Miss:
    """
    Sentinel for "not in the cache".

    Distinct from a cached value of None: an upstream endpoint returning JSON
    `null` would otherwise be indistinguishable from a miss, and every call
    would refetch forever while appearing to work.
    """

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<cache miss>"


MISS = _Miss()


def get(key: str, ttl: int) -> Any:
    """
    Return the cached value for `key`, or the MISS sentinel.

    Returns MISS -- not None -- on miss, expiry, or corruption, so that a
    legitimately cached None is preserved. A corrupt or unreadable entry is
    treated as a miss rather than an error; the caller simply refetches.
    """
    if _DISABLED:
        return MISS

    path = _path_for(key)
    if not path.exists():
        return MISS

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("Discarding unreadable cache entry %s", path)
        try:
            path.unlink()
        except OSError:
            pass
        return MISS

    if not isinstance(raw, dict) or "value" not in raw:
        # Written by an older or broken version; treat as a miss.
        return MISS

    if ttl != IMMUTABLE:
        stored_at = raw.get("stored_at", 0)
        if time.time() - stored_at > ttl:
            return MISS

    return raw["value"]


def put(key: str, value: Any) -> None:
    """
    Store `value` under `key`.

    Written via a temp file and atomic rename so a crashed or concurrent write
    can never leave a half-written entry that a later read would choke on.
    Cache writes are best-effort: a failure here must never break a tool call.
    """
    if _DISABLED:
        return

    path = _path_for(key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"stored_at": time.time(), "key": key, "value": value})
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception as e:
        logger.debug("Cache write failed for %s: %s", key, e)


def cached_fetch(key: str, ttl: int, fetch: Callable[[], Any]) -> Any:
    """
    Return the cached value for `key`, calling `fetch()` and storing the result
    on a miss.

    `fetch` exceptions propagate -- a failed fetch must surface to the caller,
    not be silently cached as a success.
    """
    hit = get(key, ttl)
    if hit is not MISS:
        logger.debug("Cache hit: %s", key)
        return hit

    value = fetch()
    put(key, value)
    return value


def clear() -> dict:
    """Delete the entire cache. Returns a summary for the maintenance tool."""
    if not CACHE_DIR.exists():
        return {"cleared": False, "reason": "cache directory does not exist",
                "path": str(CACHE_DIR)}

    files = sum(1 for _ in CACHE_DIR.rglob("*.json"))
    size = sum(p.stat().st_size for p in CACHE_DIR.rglob("*.json") if p.is_file())
    shutil.rmtree(CACHE_DIR, ignore_errors=True)
    return {"cleared": True, "path": str(CACHE_DIR),
            "entries_removed": files, "bytes_freed": size}


def stats() -> dict:
    """Return cache size info without modifying anything."""
    if not CACHE_DIR.exists():
        return {"path": str(CACHE_DIR), "exists": False, "entries": 0, "bytes": 0,
                "disabled": _DISABLED}

    files = [p for p in CACHE_DIR.rglob("*.json") if p.is_file()]
    return {
        "path": str(CACHE_DIR),
        "exists": True,
        "entries": len(files),
        "bytes": sum(p.stat().st_size for p in files),
        "disabled": _DISABLED,
    }
