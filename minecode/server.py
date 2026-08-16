#!/usr/bin/env python3
"""
MCP server for Minecraft datapack development.

This module is wiring only -- transport, dispatch, prompts, resources. Tool
schemas live in tools.py and behaviour lives in handlers.py.

On preprompt delivery: an MCP server cannot inject a system prompt into the
client. There is no such mechanism in the protocol. The previous version loaded
assistant_preprompt.txt into `server.default_preprompt` and defined
`get_preprompt_messages()`, but nothing ever called either, so the guidance
never reached the model -- which is why agents kept writing version-wrong
syntax despite the guidance existing.

The protocol offers three real channels, and this server uses all three:

  1. Prompts   -- user-invoked, appears as a slash command in the client
  2. Resources -- client-attachable context
  3. A TOOL    -- minecraft_start_session, in tools.py

The tool matters most. Agents call tools autonomously; they do not
autonomously invoke prompts or attach resources.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptMessage,
    Resource,
    TextContent,
    Tool,
)

from .tools import HANDLERS, TOOLS

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("minecode.server")

server = Server("minecode-server")

_PKG_DIR = Path(__file__).resolve().parent
_CONFIG_FILE = _PKG_DIR / "config" / "config.json"
_DEFAULT_PREPROMPT = _PKG_DIR / "preprompts" / "assistant_preprompt.txt"


# ---------------------------------------------------------------------------
# Preprompt loading
# ---------------------------------------------------------------------------

def _load_preprompt() -> str | None:
    """
    Load the assistant preprompt.

    Resolution order: the path in config.json if set and found, then the
    packaged default. The packaged fallback matters -- config.json holds a
    repo-relative path that does not exist in a pip-installed wheel, so
    without it every installed user silently got no preprompt.
    """
    candidates: list[Path] = []

    try:
        if _CONFIG_FILE.exists():
            cfg = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            if cfg.get("preprompt_enabled", True):
                configured = cfg.get("preprompt_path")
                if configured:
                    p = Path(configured)
                    if p.is_absolute():
                        candidates.append(p)
                    candidates.append(_PKG_DIR / configured)
                    candidates.append(_PKG_DIR.parent / configured)
                    if "minecode/" in configured:
                        candidates.append(_PKG_DIR / configured.split("minecode/", 1)[1])
            else:
                logger.info("Preprompt disabled in config.json")
                return None
    except Exception:
        logger.exception("Could not read config.json; falling back to the packaged preprompt")

    candidates.append(_DEFAULT_PREPROMPT)

    for candidate in candidates:
        try:
            if candidate.exists():
                text = candidate.read_text(encoding="utf-8")
                logger.info("Loaded assistant preprompt from %s", candidate)
                return text
        except Exception as e:
            logger.debug("Preprompt candidate %s unreadable: %s", candidate, e)

    logger.warning(
        "No assistant preprompt found (tried %d locations). The minecraft_start_session "
        "tool still works; only the prompt and resource channels are affected.",
        len(candidates),
    )
    return None


PREPROMPT = _load_preprompt()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


def _error_payload(name: str, error: Exception) -> str:
    """
    Build a failure response with the SAME shape as a success response.

    Previously failures returned a bare `f"Error: {e}"` string while successes
    returned JSON. An agent parsing the output hit a JSONDecodeError and
    typically abandoned the tool rather than retrying.
    """
    return json.dumps({
        "success": False,
        "tool": name,
        "error": str(error),
        "error_type": type(error).__name__,
    })


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handler = HANDLERS.get(name)

    if handler is None:
        return [TextContent(type="text", text=json.dumps({
            "success": False,
            "tool": name,
            "error": f"Unknown tool: {name}",
            "available_tools": sorted(HANDLERS),
        }))]

    try:
        # Handlers use blocking `requests`. Without this the whole server
        # stalls on a slow upstream and cannot even answer a ping.
        result: Any = await asyncio.to_thread(handler, **(arguments or {}))
        return [TextContent(type="text", text=json.dumps(result, default=str))]
    except TypeError as e:
        # Almost always a bad argument name from the client.
        logger.warning("Bad arguments for %s: %s", name, e)
        return [TextContent(type="text", text=json.dumps({
            "success": False,
            "tool": name,
            "error": f"Invalid arguments: {e}",
            "expected_schema": next(
                (t.inputSchema for t in TOOLS if t.name == name), None),
        }))]
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return [TextContent(type="text", text=_error_payload(name, e))]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_PROMPTS = [
    Prompt(
        name="minecraft_datapack_session",
        description=(
            "Load MineCode's datapack development methodology and version-safety "
            "rules. Use at the start of a Minecraft project."
        ),
        arguments=[],
    ),
]


@server.list_prompts()
async def list_prompts() -> list[Prompt]:
    return _PROMPTS


@server.get_prompt()
async def get_prompt(name: str, arguments: dict | None = None) -> GetPromptResult:
    if name != "minecraft_datapack_session":
        raise ValueError(f"Unknown prompt: {name}")

    text = PREPROMPT or (
        "MineCode's assistant preprompt could not be loaded. Call the "
        "minecraft_start_session tool instead -- it returns the same guidance "
        "plus the detected target version."
    )

    return GetPromptResult(
        description="MineCode datapack session bootstrap",
        messages=[
            PromptMessage(role="user", content=TextContent(type="text", text=text)),
        ],
    )


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

_RESOURCES = [
    Resource(
        uri="minecode://preprompt",
        name="MineCode datapack methodology",
        description="Development methodology and version-safety rules for Minecraft packs.",
        mimeType="text/plain",
    ),
    Resource(
        uri="minecode://migrations",
        name="Minecraft version migration table",
        description=(
            "Curated before/after pairs for the datapack breaking changes AI "
            "agents get wrong most often."
        ),
        mimeType="application/json",
    ),
]


@server.list_resources()
async def list_resources() -> list[Resource]:
    return _RESOURCES


@server.read_resource()
async def read_resource(uri: Any) -> str:
    uri = str(uri)

    if uri == "minecode://preprompt":
        return PREPROMPT or "Preprompt unavailable."

    if uri == "minecode://migrations":
        path = _PKG_DIR / "knowledge" / "migrations.json"
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            return json.dumps({"error": f"could not read migrations.json: {e}"})

    raise ValueError(f"Unknown resource: {uri}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        logger.info("MineCode MCP server starting (stdio)")
        logger.info("Registered %d tools, %d prompts, %d resources",
                    len(TOOLS), len(_PROMPTS), len(_RESOURCES))
        try:
            await server.run(read_stream, write_stream,
                             server.create_initialization_options())
        finally:
            logger.info("MineCode MCP server stopped")


def main() -> None:
    """Entry point for the `minecode` console script."""
    logger.info("Starting MineCode MCP server")
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Interrupted")


if __name__ == "__main__":
    main()
