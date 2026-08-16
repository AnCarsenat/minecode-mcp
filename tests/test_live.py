"""
Live tests against the upstream APIs.

Marked `network` and excluded from the default run. Intended for a scheduled
job, not for every push -- these depend on volunteer-run services and would
make CI flaky and noisy if run constantly.

They assert SHAPE, never content. Asserting that 1.21.4 has N items would break
every time upstream corrects anything; asserting that the response is a
non-empty list of strings catches the failure that matters -- an API changing
shape underneath us and every scraper silently returning nothing.

Run with:  pytest -m network
"""

import pytest

from minecode import handlers
from minecode.scrappers import misode, spyglass

pytestmark = pytest.mark.network

# A released version, so upstream data for it is frozen and this file does not
# need editing every time Minecraft ships a new version.
STABLE = "1.21.4"


def test_spyglass_versions_have_pack_formats():
    versions = spyglass.get_versions()
    assert isinstance(versions, list) and versions

    first = versions[0]
    for field in ("id", "type", "data_pack_version", "resource_pack_version"):
        assert field in first, f"Spyglass version objects no longer carry '{field}'"


def test_spyglass_registries_return_ids():
    items = spyglass.get_registry(STABLE, "item")
    assert isinstance(items, list) and len(items) > 100
    assert all(isinstance(i, str) for i in items[:20])


def test_spyglass_command_tree_has_expected_shape():
    tree = spyglass.get_commands(STABLE)
    assert "children" in tree
    assert "give" in tree["children"]

    give = tree["children"]["give"]
    assert give.get("type") == "literal"
    assert "children" in give


def test_command_usage_renders_for_give():
    result = handlers.handle_get_command_usage(STABLE, "give")
    assert result["success"] is True
    assert result["usage"], "no usage lines rendered from the command tree"
    assert all(u.startswith("/give") for u in result["usage"])


def test_validate_command_accepts_a_real_command():
    result = handlers.handle_validate_command("/say hello", STABLE)
    assert result["success"] is True
    assert result["valid"] is True


def test_validate_command_rejects_a_bad_command():
    result = handlers.handle_validate_command("/thiscommanddoesnotexist", STABLE)
    assert result["valid"] is False


def test_version_resolution_handles_partials_and_misses():
    assert handlers.handle_resolve_minecraft_version("latest")["success"] is True

    miss = handlers.handle_resolve_minecraft_version("definitely-not-a-version")
    assert miss["success"] is False
    assert miss["did_you_mean"], "a version miss must offer alternatives"


def test_pack_format_maps_to_a_version():
    result = handlers.handle_version_to_pack_format(STABLE)
    assert result["success"] is True
    assert isinstance(result["data_pack_format"], int)

    back = handlers.handle_pack_format_to_version(result["data_pack_format"])
    assert back["success"] is True
    assert STABLE in back["versions"]


def test_technical_changes_index_is_populated():
    releases = misode.list_changelog_releases()
    assert releases, "misode/technical-changes returned no release directories"

    index = misode._all_changelog_entries()
    assert len(index) > 50


def test_technical_changes_finds_the_components_migration():
    """
    1.20.5 is the components rewrite. If a range covering it comes back empty,
    the range filter is broken -- which it silently was, because snapshot IDs
    like '24w14a' cannot be ordered against release numbers directly.
    """
    result = misode.get_changes_between("1.20.4", "1.20.5")
    assert result["success"] is True
    assert result["total_entries"] > 0, "no changelog entries across the 1.20.5 rewrite"

    text = " ".join(
        e["description"].lower()
        for change in result["changes"] for e in change["entries"]
    )
    assert "component" in text


def test_misode_preset_data_returns_real_json():
    result = handlers.handle_misode_get_preset_data(
        STABLE, "loot_table", "blocks/dirt")
    assert result["success"] is True
    assert isinstance(result["data"], dict)


def test_mcdoc_symbol_search_and_fetch():
    """
    The mcdoc endpoint has been observed 502-ing while the rest of the Spyglass
    API is healthy. That is an upstream outage, not our defect, so it skips
    rather than fails -- but it must never pass silently, hence the explicit
    skip reason.
    """
    import requests

    try:
        matches = spyglass.search_mcdoc_symbols("ItemStack", limit=10)
    except requests.HTTPError as e:
        pytest.skip(f"Spyglass mcdoc endpoint is down upstream: {e}")

    assert matches, "no mcdoc symbols matched 'ItemStack'"

    definition = spyglass.get_mcdoc_symbol(matches[0], depth=2)
    assert definition is not None
    assert definition["symbol"] == matches[0]


def test_mcdoc_outage_returns_actionable_guidance():
    """
    When mcdoc is unavailable the handler must name working alternatives.

    A bare transport error leaves the agent with nothing but its own recall of
    field names, which is precisely the version-wrong behaviour this server
    exists to prevent.
    """
    result = handlers.handle_spyglass_search_mcdoc_symbols("ItemStack")

    if result.get("success"):
        pytest.skip("mcdoc endpoint is healthy; outage path not exercised")

    assert result.get("upstream_outage") is True
    assert result.get("fallbacks"), "outage response offers no alternative"
    assert "misode_get_preset_data" in " ".join(result["fallbacks"])


def test_wiki_search_carries_the_version_warning():
    result = handlers.handle_search_wiki("creeper", limit=3)
    assert result["success"] is True
    assert "LATEST" in result["version_warning"]
