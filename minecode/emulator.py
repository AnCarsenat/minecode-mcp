"""
The emulator_* tools: run a datapack without the game, via Datapack Emulator.

datapack-emulator (https://github.com/AnCarsenat/Datapack-Emulator, a git
submodule of this repository) does the work; its `datapack_emulator.agent`
module already speaks plain-dict JSON, so these handlers only:

  * resolve the version the way every other MineCode tool does (pack.mcmeta
    when omitted, "1.21" -> a real release), and say what it resolved to;
  * turn AgentError (bad path, unknown version, malformed test) into the
    {"success": False, "error": ...} shape every MineCode tool returns;
  * keep the import lazy, so a broken or missing emulator degrades to a clear
    error on these tools instead of taking the whole server down.

The emulator's own result keys (`ok`, `summary`, `records`, ...) are passed
through unchanged and documented in its docs/agents.md; `success` here means
"the tool ran", `ok` means "the pack is fine". They are different questions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("minecode.emulator")

INSTALL_HINT = (
    "Install it into the same Python as the minecode server. It is an optional "
    "extra and not on PyPI yet: from a minecode-mcp checkout run "
    "`git submodule update --init` then `pip install -e ./datapack-emulator` "
    "(or `pip install git+https://github.com/AnCarsenat/Datapack-Emulator.git`)."
)


def _agent():
    try:
        from datapack_emulator import agent
    except ImportError as exc:  # missing, or too old to have the agent API
        raise _Unavailable(str(exc)) from exc
    return agent


class _Unavailable(Exception):
    pass


def _call(name: str, function: str, **kwargs: Any) -> Dict[str, Any]:
    try:
        agent = _agent()
    except _Unavailable as exc:
        return {"success": False, "tool": name,
                "error": f"datapack-emulator is not available: {exc}",
                "hint": INSTALL_HINT}
    try:
        result = getattr(agent, function)(**kwargs)
    except agent.AgentError as exc:
        return {"success": False, "tool": name, "error": str(exc)}
    out: Dict[str, Any] = {"success": True}
    out.update(result)
    return out


def _version(version: Optional[str]) -> Optional[str]:
    """None stays None (the emulator reads pack.mcmeta); anything else is
    passed through -- the emulator resolves "latest" and lines like "1.21"
    against its own version table, which is the one it can emulate."""
    if version is None or not str(version).strip():
        return None
    return str(version).strip()


def _path(path: Optional[str]) -> str:
    return path or "."


def handle_emulator_check(path: Optional[str] = None, version: Optional[str] = None,
                          versions: Optional[List[str]] = None, declared: bool = False,
                          severity: str = "info", download_client_jar: bool = False) -> dict:
    return _call("emulator_check", "check", packs=_path(path), version=_version(version),
                 versions=versions, declared=declared, boundaries=declared and not versions,
                 severity=severity, download=download_client_jar)


def handle_emulator_run(path: Optional[str] = None, version: Optional[str] = None,
                        ticks: int = 20, commands: Optional[List[str]] = None,
                        players: int = 1, level: str = "info", max_records: int = 100,
                        entities: bool = False, download_client_jar: bool = False) -> dict:
    return _call("emulator_run", "run", packs=_path(path), version=_version(version),
                 ticks=ticks, commands=list(commands or []), players=players, level=level,
                 max_records=max_records, entities=entities, download=download_client_jar)


def handle_emulator_test(tests: List[Any], path: Optional[str] = None,
                         version: Optional[str] = None, versions: Optional[List[str]] = None,
                         checks: Optional[List[str]] = None, expect: str = "",
                         expect_value: str = "", ticks: Optional[int] = None,
                         players: int = 1, download_client_jar: bool = False) -> dict:
    return _call("emulator_test", "test", packs=_path(path), tests=list(tests or []),
                 version=_version(version), versions=versions, checks=list(checks or []),
                 expect=expect, expect_value=expect_value, ticks=ticks, players=players,
                 download=download_client_jar)


def handle_emulator_matrix(path: Optional[str] = None, versions: Optional[List[str]] = None,
                           from_version: Optional[str] = None,
                           to_version: Optional[str] = None, boundaries: bool = True,
                           ticks: int = 20, tests: Optional[List[Any]] = None,
                           download_client_jars: bool = False) -> dict:
    return _call("emulator_matrix", "matrix", packs=_path(path), versions=versions,
                 start=_version(from_version), end=_version(to_version),
                 # exact versions are run as given; boundaries only thins ranges
                 boundaries=boundaries and not versions, ticks=ticks, tests=list(tests or []),
                 download=download_client_jars)


def handle_emulator_explain(command: str, version: Optional[str] = None,
                            path: Optional[str] = None) -> dict:
    return _call("emulator_explain", "explain", packs=path or None, command=command,
                 version=_version(version))
