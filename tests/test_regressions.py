"""
Regression tests for bugs found during self-review and live testing.

Each test here corresponds to a defect that shipped and was caught afterwards.
They exist so the same mistake cannot return quietly.
"""

import json

import pytest

from minecode import cache, handlers, packmeta


# ---------------------------------------------------------------------------
# cache: a cached None must not be indistinguishable from a miss
# ---------------------------------------------------------------------------

def test_cached_none_is_not_treated_as_a_miss(tmp_path, monkeypatch):
    """
    `get()` returning None for both "no entry" and "entry holds null" meant an
    upstream returning JSON null refetched forever while appearing to work.
    """
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cache, "_DISABLED", False)

    assert cache.get("absent-key", cache.IMMUTABLE) is cache.MISS

    cache.put("null-key", None)
    assert cache.get("null-key", cache.IMMUTABLE) is None

    calls = []

    def fetch():
        calls.append(1)
        return None

    cache.cached_fetch("null-key", cache.IMMUTABLE, fetch)
    assert calls == [], "cached None caused a refetch"


def test_cached_falsy_values_survive(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cache, "_DISABLED", False)

    for value in ([], {}, 0, "", False):
        key = f"falsy-{value!r}"
        cache.put(key, value)
        assert cache.get(key, cache.IMMUTABLE) == value


def test_corrupt_cache_entry_is_a_miss_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cache, "_DISABLED", False)

    cache.put("corrupt", {"real": "value"})
    path = cache._path_for("corrupt")
    path.write_text("{not valid json", encoding="utf-8")

    assert cache.get("corrupt", cache.IMMUTABLE) is cache.MISS


# ---------------------------------------------------------------------------
# pack.mcmeta: min_format / max_format
# ---------------------------------------------------------------------------

def _write_mcmeta(tmp_path, pack: dict):
    (tmp_path / "data").mkdir(exist_ok=True)
    target = tmp_path / "pack.mcmeta"
    target.write_text(json.dumps({"pack": pack}), encoding="utf-8")
    return target


def test_min_format_max_format_is_read_as_a_range(tmp_path):
    """
    Found on a real pack: newer packs express the supported range as flat
    min_format/max_format keys rather than a supported_formats object.
    Ignoring them reported a multi-version pack as single-version, so the
    agent would write syntax valid only at the low end.
    """
    path = _write_mcmeta(tmp_path, {
        "pack_format": 88, "min_format": 88, "max_format": 102,
        "description": "test",
    })

    info = packmeta.read_pack_mcmeta(path)
    assert info["success"] is True
    assert info["format_min"] == 88
    assert info["format_max"] == 102
    assert info["multi_version"] is True
    assert info["format_range_source"] == "min_format/max_format"


def test_supported_formats_object_still_works(tmp_path):
    path = _write_mcmeta(tmp_path, {
        "pack_format": 48,
        "supported_formats": {"min_inclusive": 48, "max_inclusive": 61},
    })
    info = packmeta.read_pack_mcmeta(path)
    assert (info["format_min"], info["format_max"]) == (48, 61)
    assert info["multi_version"] is True


def test_supported_formats_array_still_works(tmp_path):
    path = _write_mcmeta(tmp_path, {"pack_format": 48, "supported_formats": [48, 61]})
    info = packmeta.read_pack_mcmeta(path)
    assert (info["format_min"], info["format_max"]) == (48, 61)


def test_single_pack_format_is_not_multi_version(tmp_path):
    path = _write_mcmeta(tmp_path, {"pack_format": 61})
    info = packmeta.read_pack_mcmeta(path)
    assert info["multi_version"] is False


def test_inverted_format_range_is_corrected_and_flagged(tmp_path):
    path = _write_mcmeta(tmp_path, {
        "pack_format": 88, "min_format": 102, "max_format": 88,
    })
    info = packmeta.read_pack_mcmeta(path)
    assert info["format_min"] == 88 and info["format_max"] == 102
    assert "inverted" in info["warning"]


def test_malformed_mcmeta_reports_a_useful_error(tmp_path):
    target = tmp_path / "pack.mcmeta"
    target.write_text('{"pack": {"pack_format": 61,}}', encoding="utf-8")

    info = packmeta.read_pack_mcmeta(target)
    assert info["success"] is False
    assert "line" in info["error"]
    assert "Trailing commas" in info["hint"]


def test_mcmeta_with_bom_is_readable(tmp_path):
    target = tmp_path / "pack.mcmeta"
    target.write_text('﻿{"pack": {"pack_format": 61}}', encoding="utf-8")
    assert packmeta.read_pack_mcmeta(target)["success"] is True


# ---------------------------------------------------------------------------
# get_logs: content lives in a `logs` list, not at the top level
# ---------------------------------------------------------------------------

_FAKE_LOGS = {
    "success": True,
    "launcher": "prism",
    "logs": [
        {"instance": "A", "file": "latest.log", "path": "/x", "size": 1,
         "lines_shown": 4,
         "content": "[INFO]: loading\n[ERROR]: bad thing\n[INFO]: more\n[WARN]: hmm"},
        {"instance": "B", "file": "latest.log", "path": "/y", "size": 1,
         "lines_shown": 2,
         "content": "[INFO]: quiet\n[INFO]: also quiet"},
    ],
}


def test_log_filter_applies_to_every_instance(monkeypatch):
    """
    The filter read result["content"], a key the log reader never returns --
    every launcher uses a `logs` list. Filtering silently did nothing.
    """
    monkeypatch.setattr(handlers.minecraft_logs, "get_logs",
                        lambda **kw: json.loads(json.dumps(_FAKE_LOGS)))

    result = handlers.handle_get_logs(filter="errors")

    assert result["lines_after_filter"] == 1
    assert result["logs"][0]["content"] == "[ERROR]: bad thing"
    assert result["logs"][1]["content"] == ""
    assert result["instances_found"] == 2
    assert result["instance_names"] == ["A", "B"]


def test_log_filter_warnings_includes_warn(monkeypatch):
    monkeypatch.setattr(handlers.minecraft_logs, "get_logs",
                        lambda **kw: json.loads(json.dumps(_FAKE_LOGS)))

    result = handlers.handle_get_logs(filter="warnings")
    assert result["lines_after_filter"] == 2


def test_log_filter_all_leaves_content_untouched(monkeypatch):
    monkeypatch.setattr(handlers.minecraft_logs, "get_logs",
                        lambda **kw: json.loads(json.dumps(_FAKE_LOGS)))

    result = handlers.handle_get_logs(filter="all")
    assert "[INFO]: loading" in result["logs"][0]["content"]
    assert "lines_after_filter" not in result


def test_no_matching_lines_explains_the_silent_failure_mode(monkeypatch):
    """Clean logs plus a dead pack means folder names -- say so."""
    quiet = {"success": True, "launcher": "prism", "logs": [
        {"instance": "A", "content": "[INFO]: nothing wrong", "lines_shown": 1}]}
    monkeypatch.setattr(handlers.minecraft_logs, "get_logs",
                        lambda **kw: json.loads(json.dumps(quiet)))

    result = handlers.handle_get_logs(filter="errors")
    assert result["lines_after_filter"] == 0
    assert "check_pack_structure" in result["note"]


# ---------------------------------------------------------------------------
# _truncate: the list must not be returned twice
# ---------------------------------------------------------------------------

def test_truncated_payload_does_not_duplicate_the_list():
    """
    Callers spread _truncate() then set a renamed key, leaving both "items"
    and the renamed key holding the same list -- doubling every list response.
    """
    payload = handlers._truncated_payload(["a", "b", "c"], "entries")

    assert payload["entries"] == ["a", "b", "c"]
    assert "items" not in payload
    assert payload["count"] == 3
    assert payload["truncated"] is False


def test_truncated_payload_reports_truncation():
    payload = handlers._truncated_payload(list(range(500)), "entries")
    assert payload["truncated"] is True
    assert payload["count"] == 500
    assert len(payload["entries"]) == handlers.MAX_LIST_RESULTS
    assert "500" in payload["note"]


# ---------------------------------------------------------------------------
# brigadier: redirects and backtracking
# ---------------------------------------------------------------------------

from minecode import brigadier  # noqa: E402

# Mirrors the two redirect forms Spyglass actually emits:
#   execute.at.targets -> {"redirect": ["execute"]}   (explicit path)
#   execute.run        -> {"type": "literal"}         (implicit root redirect)
_REDIRECT_TREE = {
    "type": "root",
    "children": {
        "execute": {"type": "literal", "children": {
            "at": {"type": "literal", "children": {
                "targets": {"type": "argument", "parser": "minecraft:entity",
                            "redirect": ["execute"], "children": {}}}},
            "as": {"type": "literal", "children": {
                "targets": {"type": "argument", "parser": "minecraft:entity",
                            "redirect": ["execute"], "children": {}}}},
            "run": {"type": "literal"},
        }},
        "say": {"type": "literal", "children": {
            "message": {"type": "argument", "parser": "minecraft:message",
                        "executable": True}}},
        # Overlapping arguments: "@s" matches both, so a greedy first-match
        # parser commits to <destination> and then cannot place "~ ~ ~".
        "tp": {"type": "literal", "children": {
            "destination": {"type": "argument", "parser": "minecraft:entity",
                            "executable": True},
            "targets": {"type": "argument", "parser": "minecraft:entity",
                        "children": {
                            "location": {"type": "argument",
                                         "parser": "minecraft:vec3",
                                         "executable": True}}},
        }},
    },
}


@pytest.mark.parametrize("command", [
    "/execute run say hi",              # implicit root redirect
    "/execute at @s run say hi",        # explicit redirect, then root redirect
    "/execute as @e at @s run say hi",  # chained redirects
    "/tp @s ~ ~ ~",                     # requires backtracking
    "/tp @s",                           # the other branch of the same overlap
])
def test_redirects_and_backtracking_accept_valid_commands(command):
    result = brigadier.validate(command, _REDIRECT_TREE)
    assert result["valid"] is True, result


@pytest.mark.parametrize("command", [
    "/execute",              # incomplete
    "/execute run",          # redirect with nothing after it
    "/execute at",           # missing argument
    "/tp",                   # missing argument
    "/execute run frobnicate",   # redirect target is not a real command
    "/frobnicate",
])
def test_redirects_and_backtracking_still_reject_bad_commands(command):
    result = brigadier.validate(command, _REDIRECT_TREE)
    assert result["valid"] is False, (
        f"{command!r} was accepted -- backtracking must not accept everything"
    )


def test_backtracking_terminates_on_pathological_input():
    """A deeply chained command must not hang or recurse without bound."""
    command = "/execute " + "at @s " * 40 + "run say hi"
    result = brigadier.validate(command, _REDIRECT_TREE)
    assert "valid" in result


# ---------------------------------------------------------------------------
# wiki: full=true failed on every page with a nested infobox
# ---------------------------------------------------------------------------

from pathlib import Path  # noqa: E402

from minecode.scrappers import minecraftwiki, spyglass  # noqa: E402

_DATA = Path(__file__).parent / "data"


def _wiki_fixture(monkeypatch, payload=None):
    if payload is None:
        payload = json.loads((_DATA / "wiki_parse_redstone_repeater.json").read_text("utf-8"))
    monkeypatch.setattr(minecraftwiki, "_make_request", lambda params: payload)
    return payload


def test_wiki_full_page_with_nested_infobox(monkeypatch):
    """
    get_wiki_page("Redstone Repeater", full=true) returned
    "'NoneType' object has no attribute 'get'": the cleanup loop decomposed the
    infobox and then read the class of a table nested inside it, which bs4 had
    already destroyed. Fixture: the real parse response, trimmed.
    """
    _wiki_fixture(monkeypatch)
    result = handlers.handle_get_wiki_page("Redstone Repeater", full=True)

    assert result["success"] is True, result
    assert result["mode"] == "full"
    content = result["content"]
    assert content["title"] == "Redstone Repeater"
    assert content["infobox"]["Blast resistance"] == "0"
    assert content["infobox"]["Stackable"] == "Yes (64)"
    text = content["extract"]
    assert "produces a full-strength redstone signal" in text
    assert "Hardness | 0" in text
    # Page furniture is gone: edit links, navbox, history JSON, hidden inputs.
    assert "edit source" not in text
    assert "Redstone Comparator" not in text  # only in the navbox
    assert '"title"' not in text
    assert "10.05" not in text and "0.05 (JE)" in text
    assert content["truncated"] is False
    assert [s["name"] for s in content["sections"]][:2] == ["Obtaining", "Breaking"]


def test_wiki_full_page_truncation_is_reported(monkeypatch):
    _wiki_fixture(monkeypatch)
    monkeypatch.setattr(minecraftwiki, "MAX_PAGE_CHARS", 300)
    content = handlers.handle_get_wiki_page("Redstone Repeater", full=True)["content"]
    assert content["truncated"] is True
    assert len(content["extract"]) <= 300 < content["full_length"]
    assert any("truncated" in n for n in content["notes"])


def test_wiki_full_page_follows_redirect(monkeypatch):
    payload = _wiki_fixture(monkeypatch)
    payload["parse"]["redirects"] = [{"from": "Repeater", "to": "Redstone Repeater"}]
    result = handlers.handle_get_wiki_page("Repeater", full=True)
    assert result["title"] == "Redstone Repeater"
    assert result["content"]["redirected_from"] == "Repeater"
    assert result["content"]["url"].endswith("/Redstone_Repeater")


def test_wiki_full_page_degrades_to_summary(monkeypatch):
    """A full page that cannot be fetched still answers, with a note."""
    def boom(title):
        raise RuntimeError("upstream changed shape")

    monkeypatch.setattr(minecraftwiki, "get_page_content", boom)
    monkeypatch.setattr(minecraftwiki, "get_page_extract",
                        lambda title, sentences=5: "A redstone repeater is a block.")
    result = handlers.handle_get_wiki_page("Redstone Repeater", full=True)
    assert result["success"] is True
    assert result["mode"] == "summary"
    assert result["extract"]
    assert "upstream changed shape" in result["note"]


def test_wiki_html_to_text_never_raises_on_odd_markup():
    html = ('<div class="infobox"><div class="infobox"><table><tr><th>A</th>'
            '<td>1</td></tr></table></div></div><p>Body <b>text</b>.</p>')
    text, infobox, notes = minecraftwiki.html_to_page_text(html)
    assert text == "Body text."
    assert infobox == {"A": "1"}
    assert minecraftwiki.html_to_page_text("") == ("", {}, ["the wiki returned no page HTML"])


# ---------------------------------------------------------------------------
# mcdoc: item_display came back truncated, without its inherited fields
# ---------------------------------------------------------------------------

@pytest.fixture
def mcdoc_fixture(monkeypatch):
    """Trimmed real mcdoc: ItemDisplay -> DisplayBase -> EntityBase."""
    raw = json.loads((_DATA / "mcdoc_item_display.json").read_text("utf-8"))
    monkeypatch.setattr(spyglass, "get_mcdoc_symbols", lambda: raw)
    return raw


@pytest.mark.parametrize("symbol", [
    "item_display",
    "minecraft:entity[item_display]",
    "::java::world::entity::display::ItemDisplay",
    "java::world::entity::display::ItemDisplay",
    "ItemDisplay",
])
def test_mcdoc_item_display_has_own_and_inherited_fields(mcdoc_fixture, symbol):
    """
    Field types were replaced by "_truncated" at the default depth (dict
    nesting was counted, not type nesting), the `...DisplayBase` spread was
    never followed, and "item_display" itself did not resolve.
    """
    result = handlers.handle_spyglass_get_mcdoc_symbol(symbol)
    assert result["success"] is True, result
    assert result["truncated"] is False
    fields = {f["key"]: f for f in result["fields"]}

    # Own fields, with their real types.
    assert fields["item"]["type"] == "::java::world::item::ItemStack"
    assert "inherited_from" not in fields["item"]
    assert fields["item_display"]["type"] == "::java::assets::model::ItemDisplayContext"
    # Inherited from DisplayBase and, through it, EntityBase.
    assert fields["shadow_strength"]["type"] == "float @ 0..1"
    assert fields["teleport_duration"]["since"] == "1.20.2"
    assert fields["billboard"]["inherited_from"].endswith("::DisplayBase")
    assert fields["Pos"]["type"] == "[double] @ 3"
    assert fields["Tags"]["inherited_from"].endswith("::EntityBase")
    assert fields["FallDistance"]["until"] == "1.21.5"
    assert fields["Team"]["since"] == "26.3"
    assert "_truncated" not in json.dumps(result)
    assert result["own_field_count"] == 2


def test_mcdoc_search_finds_dispatcher_keys(mcdoc_fixture):
    result = handlers.handle_spyglass_search_mcdoc_symbols("item_display")
    assert result["symbols"][0] == "minecraft:entity[item_display]"


def test_mcdoc_depth_cut_is_reported(mcdoc_fixture):
    shallow = handlers.handle_spyglass_get_mcdoc_symbol("::test::Nested", depth=1)
    assert shallow["truncated"] is True
    assert shallow["truncated_at"] == ["outer"]
    assert "depth" in shallow["how_to_expand"]

    deep = handlers.handle_spyglass_get_mcdoc_symbol("::test::Nested", depth=3)
    assert deep["truncated"] is False
    outer = next(f for f in deep["fields"] if f["key"] == "outer")
    assert outer["fields"][0]["fields"][0] == {"key": "leaf", "type": "int", "optional": False}
    volume = next(f for f in deep["fields"] if f["key"] == "volume")
    assert volume["type"] == "float @ 0<.."
    # A spread through a dispatcher cannot be inlined; it is named, not dropped.
    assert deep["unresolved_spreads"][0]["type"] == "minecraft:entity[[type]]"


def test_mcdoc_ambiguous_and_dispatcher_lookups(mcdoc_fixture):
    amb = handlers.handle_spyglass_get_mcdoc_symbol("ColorDisplay")
    assert amb["success"] is False
    assert len(amb["did_you_mean"]) == 2

    disp = handlers.handle_spyglass_get_mcdoc_symbol("minecraft:entity")
    assert disp["kind"] == "dispatcher"
    assert disp["keys"] == ["block_display", "item_display"]
