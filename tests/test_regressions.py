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
