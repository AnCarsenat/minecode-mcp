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
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("minecode.emulator")

INSTALL_HINT = (
    "datapack-emulator is a dependency of minecode-mcp: reinstall it into the "
    "same Python as the minecode server with `pip install -U minecode-mcp` "
    "(or `pip install -U datapack-emulator`). It needs version 0.3.0 or newer."
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
                          severity: str = "info", download_client_jar: bool = False,
                          real_server: bool = False,
                          user_accepted_minecraft_eula: bool = False) -> dict:
    kwargs: Dict[str, Any] = dict(
        packs=_path(path), version=_version(version), versions=versions, declared=declared,
        boundaries=declared and not versions, severity=severity,
        download=download_client_jar,
    )
    if real_server:
        if not user_accepted_minecraft_eula:
            return {
                "success": False, "tool": "emulator_check",
                "error": "real_server=true runs a Minecraft server, which means accepting "
                         "the Minecraft EULA (https://aka.ms/MinecraftEULA)",
                "hint": "Ask the user whether they accept the Minecraft EULA. Only if they "
                        "say yes, call again with user_accepted_minecraft_eula=true.",
            }
        kwargs.update(server=True, accept_eula=True)
    result = _call("emulator_check", "check", **kwargs)
    if result.get("success") and result.get("load_blockers"):
        # put what stops the world loading where an agent reads first
        result["first"] = (
            "FATAL: fix load_blockers before anything else -- the server will not load "
            "the world (or the pack) at all while they remain"
        )
    return result


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


# ---------------------------------------------------------------------------
# Real timings: a server's /perf report
# ---------------------------------------------------------------------------

def _game_dirs() -> List[Path]:
    """Where a /perf report can be: the current folder (a server), the
    default launcher's game folder, every Prism instance (singleplayer writes
    to <game dir>/debug/profiling/)."""
    from .scrappers import minecraft_logs

    dirs = [Path.cwd(), minecraft_logs.get_default_minecraft_dir(),
            minecraft_logs.get_tlauncher_dir()]
    prism = minecraft_logs.get_prism_launcher_dir() / "instances"
    try:
        for instance in sorted(prism.iterdir()):
            if instance.is_dir():  # skip instgroups.json and the like
                dirs += [instance / "minecraft", instance / ".minecraft"]
    except OSError:  # no Prism, or unreadable
        pass
    return list(dict.fromkeys(dirs))  # the default launcher and TLauncher can coincide


def find_perf_reports(extra: Optional[str] = None) -> List[Path]:
    """Every /perf zip found, newest first.

    Only <root>/debug/profiling/*.zip is searched in the game folders (never
    recursively); the zips directly in ``extra`` count too, because the user
    pointed at that folder -- a workspace's release zips in the current folder
    must not be mistaken for reports."""
    folders: List[Path] = []
    if extra:
        root = Path(extra).expanduser()
        folders += [root / "debug" / "profiling", root]
    folders += [root / "debug" / "profiling" for root in _game_dirs()]
    found: Dict[Path, float] = {}
    for folder in folders:
        try:
            for zip_path in folder.glob("*.zip"):
                found[zip_path.resolve()] = zip_path.stat().st_mtime
        except OSError:  # missing, unreadable, or a dangling link
            continue
    return sorted(found, key=lambda p: -found[p])


def handle_emulator_server_profile(report: Optional[str] = None,
                                   path: Optional[str] = None,
                                   version: Optional[str] = None,
                                   ticks: int = 200, players: int = 1,
                                   search_dir: Optional[str] = None) -> dict:
    """Read a real /perf report; with a pack path, compare with the estimate."""
    if report:
        chosen = Path(report).expanduser()
        if chosen.is_dir():
            reports = find_perf_reports(str(chosen))
            if not reports:
                return {"success": False, "tool": "emulator_server_profile",
                        "error": f"no /perf report (*.zip) in {chosen} or its debug/profiling/"}
            chosen = reports[0]
    else:
        reports = find_perf_reports(search_dir)
        if not reports:
            return {
                "success": False,
                "tool": "emulator_server_profile",
                "error": "no /perf report found",
                "hint": ("In Minecraft (singleplayer or on the server console) run "
                         "`/perf start`, wait 10 seconds, then call this again. The report "
                         "lands in <game or server folder>/debug/profiling/. Pass "
                         "report=<zip> or search_dir=<folder> if it is elsewhere."),
                "searched": ([search_dir] if search_dir else [])
                            + [str(d / "debug" / "profiling") for d in _game_dirs()],
            }
        chosen = reports[0]
    try:
        agent = _agent()
    except _Unavailable as exc:
        return {"success": False, "tool": "emulator_server_profile",
                "error": f"datapack-emulator is not available: {exc}", "hint": INSTALL_HINT}
    if not hasattr(agent, "server_profile"):
        return {"success": False, "tool": "emulator_server_profile",
                "error": "this datapack-emulator is too old for server profiles (needs 0.3.0)",
                "hint": "pip install -U 'datapack-emulator>=0.3.0'"}
    result = _call("emulator_server_profile", "server_profile", report=str(chosen),
                   packs=path or None, version=_version(version), ticks=ticks,
                   players=players)
    if result.get("success"):
        result["report"] = str(chosen)
    return result
