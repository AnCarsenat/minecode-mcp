"""
Version knowledge base.

Loads migrations.json and answers two questions:

  1. "What breaks between version A and version B?"  -> changes_between()
  2. "Is this snippet valid for version X?"           -> check_syntax()

Design note: this module is deliberately a thin, small, hand-curated layer.
The exhaustive per-version record lives in misode/technical-changes and is
reached through the get_technical_changes tool. This file exists only to catch
the handful of migrations where a model's training data actively fights the
correct answer, and to do so fast and offline. Every result points at an
authoritative tool for confirmation.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("minecode.knowledge")

_DATA_FILE = Path(__file__).resolve().parent / "migrations.json"

_cache: Optional[Dict[str, Any]] = None


def _load() -> Dict[str, Any]:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.exception("Failed to load migrations.json")
            _cache = {"schema_version": 0, "migrations": [], "version_notes": [],
                      "_load_error": str(e)}
    return _cache


# ---------------------------------------------------------------------------
# Version comparison
# ---------------------------------------------------------------------------

_SNAPSHOT_RE = re.compile(r"^(\d\d)w(\d\d)([a-z])$")


def parse_version(v: str) -> tuple:
    """
    Turn a Minecraft version string into a sortable tuple.

    Handles releases ("1.21.4") and snapshots ("24w14a"). Snapshots sort by
    their year/week, which places them correctly relative to releases in the
    common case but is not exact -- a snapshot always sorts *before* the
    release it leads to, which is what callers of this module need.

    Unparseable input sorts last, so an unknown version is never silently
    treated as ancient.
    """
    if not v:
        return (9999,)

    v = v.strip().lower()

    m = _SNAPSHOT_RE.match(v)
    if m:
        year, week, rev = int(m.group(1)), int(m.group(2)), m.group(3)
        # Map a snapshot onto an approximate release ordinal. Snapshots are
        # rare as *targets*, so approximate placement is acceptable here.
        return (1, 0, 0, year, week, ord(rev))

    parts = v.split(".")
    nums: List[int] = []
    for p in parts:
        digits = re.match(r"^(\d+)", p)
        if not digits:
            return (9999,)
        nums.append(int(digits.group(1)))
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])


def version_gte(a: str, b: str) -> bool:
    """True if version a is at least version b."""
    return parse_version(a) >= parse_version(b)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def all_migrations() -> List[Dict[str, Any]]:
    return list(_load().get("migrations", []))


def version_notes(version: Optional[str] = None) -> List[Dict[str, Any]]:
    """Headline notes, optionally filtered to those at or below `version`."""
    notes = _load().get("version_notes", [])
    if not version:
        return list(notes)
    return [n for n in notes if version_gte(version, n.get("version", "0"))]


def changes_between(from_version: Optional[str], to_version: str,
                    topic: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Return curated migrations that land in (from_version, to_version].

    With no from_version, returns everything at or below to_version -- i.e.
    "everything that applies to this version", which is what an agent starting
    fresh on a pack actually wants.
    """
    out = []
    for m in all_migrations():
        changed_in = m.get("changed_in", "")

        if changed_in == "various":
            # Version-independent advisories always apply.
            applies = True
        else:
            applies = version_gte(to_version, changed_in)
            if applies and from_version:
                # Exclude anything the source version already had.
                applies = not version_gte(from_version, changed_in)

        if not applies:
            continue

        if topic:
            t = topic.lower()
            haystack = " ".join([
                m.get("id", ""), m.get("title", ""),
                " ".join(m.get("affects", [])),
                m.get("explanation", ""),
            ]).lower()
            if t not in haystack:
                continue

        out.append(m)

    out.sort(key=lambda m: parse_version(m.get("changed_in", "0")))
    return out


def applicable_to(version: str, topic: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every curated migration that a pack targeting `version` must satisfy."""
    return changes_between(None, version, topic)


# ---------------------------------------------------------------------------
# Syntax checking
# ---------------------------------------------------------------------------

_KIND_ALIASES = {
    "mcfunction": "command",
    "function": "command",
    "nbt": "command",
    "snbt": "command",
}


def _kind_matches(rule_kind: str, content_kind: str) -> bool:
    if rule_kind == "any":
        return True
    return rule_kind == _KIND_ALIASES.get(content_kind, content_kind)


def check_syntax(content: str, version: str,
                 kind: str = "any") -> Dict[str, Any]:
    """
    Scan `content` for syntax that is wrong for `version`.

    Returns a dict with an `issues` list. Each issue names the migration, the
    line and matched text, why it is wrong, the before/after pair, and the tool
    to confirm with.

    This is a REGEX PRE-FILTER, not a parser. It is fast, offline, and has no
    false negatives worth relying on -- absence of issues is not proof of
    correctness. `validate_command` and `validate_datapack_file` are the real
    checks. That caveat is returned in the payload so the agent does not read
    a clean result as a guarantee.
    """
    kind = (kind or "any").lower()
    lines = content.split("\n")
    issues: List[Dict[str, Any]] = []

    for m in applicable_to(version):
        for rule in m.get("detect", []):
            pattern = rule.get("pattern")
            if not pattern:
                continue
            if not _kind_matches(rule.get("kind", "any"), kind):
                continue

            try:
                rx = re.compile(pattern)
            except re.error as e:
                logger.warning("Bad detect pattern in migration %s: %s",
                               m.get("id"), e)
                continue

            for lineno, line in enumerate(lines, start=1):
                found = rx.search(line)
                if not found:
                    continue
                issues.append({
                    "migration_id": m.get("id"),
                    "title": m.get("title"),
                    "severity": m.get("severity", "breaking"),
                    "confidence": m.get("confidence", "medium"),
                    "changed_in": m.get("changed_in"),
                    "line": lineno,
                    "matched": found.group(0)[:200],
                    "problem": rule.get("message", m.get("explanation", "")),
                    "before": m.get("before"),
                    "after": m.get("after"),
                    "explanation": m.get("explanation"),
                    "verify_with": m.get("verify_with"),
                })

    issues.sort(key=lambda i: (i["line"], i["migration_id"] or ""))

    return {
        "success": True,
        "version": version,
        "kind": kind,
        "lines_scanned": len(lines),
        "issue_count": len(issues),
        "issues": issues,
        "caveat": (
            "Regex pre-filter over a small curated table. Finding nothing does "
            "NOT mean the content is valid -- it means none of the ~15 curated "
            "migrations matched. For real validation use validate_command "
            "(commands) or validate_datapack_file (JSON). For the exhaustive "
            "list of changes use get_technical_changes."
        ),
    }


def check_paths(paths: List[str], version: str) -> Dict[str, Any]:
    """
    Check datapack file paths against path-shaped migrations.

    Split out from check_syntax because the folder-singularization change in
    1.21 is detected in paths, not file contents, and it is the single most
    common silent failure on modern versions.
    """
    issues: List[Dict[str, Any]] = []

    for m in applicable_to(version):
        for rule in m.get("detect", []):
            if rule.get("kind") != "path":
                continue
            try:
                rx = re.compile(rule["pattern"])
            except (re.error, KeyError):
                continue
            for p in paths:
                normalized = p.replace("\\", "/")
                found = rx.search(normalized)
                if found:
                    issues.append({
                        "migration_id": m.get("id"),
                        "title": m.get("title"),
                        "severity": m.get("severity", "breaking"),
                        "path": p,
                        "matched": found.group(0),
                        "problem": rule.get("message", ""),
                        "before": m.get("before"),
                        "after": m.get("after"),
                        "verify_with": m.get("verify_with"),
                    })

    return {
        "success": True,
        "version": version,
        "paths_checked": len(paths),
        "issue_count": len(issues),
        "issues": issues,
    }
