"""The skills in skills/ are served to every MCP client (offline)."""

import asyncio

import pytest

from minecode import guides, handlers, server

EXPECTED = {
    "minecode-mcp",
    "minecraft-feature-workflow",
    "minecraft-diagnose",
    "minecraft-recurring-issues",
    "minecraft-version-differences",
    "datapack-emulator",
}


def test_every_skill_is_found_with_a_description():
    found = {g["topic"]: g["description"] for g in guides.index()}
    assert EXPECTED <= set(found)
    for topic, description in found.items():
        # the description is what an agent picks a guide by
        assert len(description) > 40, topic


def test_skill_names_match_their_folders():
    root = guides.skills_dir()
    for path in root.glob("*/SKILL.md"):
        assert guides.get(path.parent.name) is not None, path


def test_guide_body_has_no_frontmatter():
    body = guides.get("minecraft-diagnose")["body"]
    assert not body.startswith("---")
    assert body.startswith("# ")


def test_get_minecode_guide_tool():
    listing = handlers.handle_get_minecode_guide()
    assert listing["success"] and len(listing["guides"]) >= len(EXPECTED)
    one = handlers.handle_get_minecode_guide("minecraft-version-differences")
    assert one["success"] and "1.20.5" in one["guide"]
    missing = handlers.handle_get_minecode_guide("nope")
    assert missing["success"] is False and missing["guides"]


def test_guides_are_prompts_and_resources():
    prompts = {p.name for p in asyncio.run(server.list_prompts())}
    assert "guide_minecraft_diagnose" in prompts
    result = asyncio.run(server.get_prompt("guide_minecraft_diagnose"))
    assert "Diagnosing" in result.messages[0].content.text
    uris = {str(r.uri) for r in asyncio.run(server.list_resources())}
    assert "minecode://guide/datapack-emulator" in uris
    assert "Datapack Emulator" in asyncio.run(
        server.read_resource("minecode://guide/datapack-emulator"))


def test_start_session_points_at_the_guides(tmp_path):
    result = handlers.handle_minecraft_start_session(str(tmp_path))
    assert any(g["topic"] == "minecraft-diagnose" for g in result["guides"])
