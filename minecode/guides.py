"""
The skills in skills/<name>/SKILL.md, served to every MCP client.

Claude Code reads those files directly when this repository is installed as a
plugin. Every other client (Copilot, Claude Desktop, Cursor, ...) has no idea
what a skill is, so the same text is exposed three ways here:

  * the get_minecode_guide tool   -- the channel an agent reaches for itself
  * one prompt per guide          -- for clients that surface prompts to users
  * minecode://guide/<name>       -- for clients that attach resources

One source of truth: the wheel carries the repository's skills/ folder as
minecode/skills (see [tool.hatch.build.targets.wheel.force-include]), and an
editable checkout reads the repository folder directly.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

_PKG_DIR = Path(__file__).resolve().parent
_CANDIDATES = (
    _PKG_DIR / "skills",          # installed wheel
    _PKG_DIR.parent / "skills",   # source checkout / editable install
)

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def skills_dir() -> Optional[Path]:
    for candidate in _CANDIDATES:
        if candidate.is_dir() and any(candidate.glob("*/SKILL.md")):
            return candidate
    return None


def _parse(text: str) -> Dict[str, str]:
    """name/description from the YAML frontmatter (flat keys only), and the body."""
    meta: Dict[str, str] = {}
    body = text
    match = _FRONTMATTER.match(text)
    if match:
        for line in match.group(1).splitlines():
            key, sep, value = line.partition(":")
            if sep and key.strip() and not key.startswith((" ", "\t")):
                meta[key.strip()] = value.strip()
        body = text[match.end():]
    meta["body"] = body.strip() + "\n"
    return meta


@lru_cache(maxsize=1)
def all_guides() -> Dict[str, Dict[str, str]]:
    """name -> {name, description, body}, sorted by name. Empty if not shipped."""
    root = skills_dir()
    if root is None:
        return {}
    guides: Dict[str, Dict[str, str]] = {}
    for path in sorted(root.glob("*/SKILL.md")):
        parsed = _parse(path.read_text(encoding="utf-8"))
        name = parsed.get("name") or path.parent.name
        guides[name] = {
            "name": name,
            "description": parsed.get("description", ""),
            "body": parsed["body"],
        }
    return guides


def index() -> List[Dict[str, str]]:
    return [{"topic": g["name"], "description": g["description"]} for g in all_guides().values()]


def get(topic: str) -> Optional[Dict[str, str]]:
    guides = all_guides()
    key = topic.strip().lower().removeprefix("minecode://guide/")
    return guides.get(key)
