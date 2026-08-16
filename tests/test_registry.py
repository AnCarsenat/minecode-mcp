"""
Offline tests for the tool registry and schemas.

No network. These run on every push and catch the class of bug that let four
working changelog functions sit in misode.py for months with no tool exposing
them: nothing checked that TOOLS and HANDLERS agreed.
"""

import inspect
import json

import pytest

from minecode import handlers, tools


def test_every_tool_has_a_handler():
    missing = {t.name for t in tools.TOOLS} - set(tools.HANDLERS)
    assert not missing, f"tools advertised with no handler: {sorted(missing)}"


def test_every_handler_has_a_tool():
    missing = set(tools.HANDLERS) - {t.name for t in tools.TOOLS}
    assert not missing, (
        f"handlers with no tool -- unreachable dead code: {sorted(missing)}"
    )


def test_tool_names_are_unique():
    names = [t.name for t in tools.TOOLS]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"duplicate tool names: {sorted(dupes)}"


@pytest.mark.parametrize("tool", tools.TOOLS, ids=lambda t: t.name)
def test_tool_schema_is_wellformed(tool):
    schema = tool.inputSchema
    assert schema["type"] == "object"
    assert isinstance(schema.get("properties"), dict)
    assert isinstance(schema.get("required", []), list)

    # Every required key must actually be declared.
    for key in schema.get("required", []):
        assert key in schema["properties"], (
            f"{tool.name}: '{key}' is required but not declared in properties"
        )

    # Every property needs a description -- an undescribed parameter is one the
    # agent will fill in with a guess.
    for key, spec in schema["properties"].items():
        assert spec.get("description"), f"{tool.name}.{key} has no description"
        assert spec.get("type"), f"{tool.name}.{key} has no type"


@pytest.mark.parametrize("tool", tools.TOOLS, ids=lambda t: t.name)
def test_tool_description_is_substantial(tool):
    # Short descriptions produce wrong tool choices. This threshold is low
    # enough to be uncontroversial and high enough to catch a placeholder.
    assert len(tool.description) >= 60, (
        f"{tool.name} description is too short to guide a tool choice"
    )


@pytest.mark.parametrize("tool", tools.TOOLS, ids=lambda t: t.name)
def test_handler_accepts_declared_parameters(tool):
    """
    The handler's signature must accept every parameter the schema advertises.

    Without this, a schema/handler mismatch surfaces as a TypeError in front of
    the user at call time.
    """
    handler = tools.HANDLERS[tool.name]
    sig = inspect.signature(handler)

    accepts_kwargs = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())
    if accepts_kwargs:
        return

    for key in tool.inputSchema["properties"]:
        assert key in sig.parameters, (
            f"{tool.name} advertises '{key}' but {handler.__name__} does not accept it"
        )


@pytest.mark.parametrize("tool", tools.TOOLS, ids=lambda t: t.name)
def test_required_params_have_no_default(tool):
    """A schema-required parameter should not silently default in the handler."""
    handler = tools.HANDLERS[tool.name]
    sig = inspect.signature(handler)

    for key in tool.inputSchema.get("required", []):
        param = sig.parameters.get(key)
        if param is None:
            continue
        assert param.default is inspect.Parameter.empty, (
            f"{tool.name}: '{key}' is required by the schema but defaults to "
            f"{param.default!r} in the handler"
        )


def test_wiki_tools_carry_a_version_warning():
    """
    Every minecraft.wiki tool must warn that it is latest-version-only.

    This is the project's main source of wrong output: the wiki has no
    per-version history, and an agent given unqualified wiki syntax will write
    it into an older pack.
    """
    wiki_tools = [t for t in tools.TOOLS
                  if t.name.startswith(("search_wiki", "get_wiki"))]
    assert wiki_tools, "expected wiki tools to exist"

    for tool in wiki_tools:
        assert "LATEST VERSION ONLY" in tool.description, (
            f"{tool.name} does not warn that the wiki covers only the latest version"
        )
