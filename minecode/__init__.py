"""
MineCode - MCP Server for Minecraft Datapack Development
"""


def _version() -> str:
    """The installed distribution's version; pyproject.toml is the only place
    it is written, so this cannot drift from what PyPI shows."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("minecode-mcp")
    except PackageNotFoundError:  # a source tree that was never installed
        return "0.0.0+checkout"


__version__ = _version()
__author__ = "AnCarsenat"
