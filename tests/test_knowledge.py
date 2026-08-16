"""
Offline tests for the version knowledge base and Brigadier handling.

The false-positive tests matter as much as the detection tests: a checker that
flags correct modern syntax trains the agent to ignore it, which is worse than
having no checker.
"""

import json
import re
from pathlib import Path

import pytest

from minecode import brigadier, knowledge

MIGRATIONS_FILE = Path(knowledge.__file__).parent / "migrations.json"


# ---------------------------------------------------------------------------
# Migration table integrity
# ---------------------------------------------------------------------------

def test_migrations_file_is_valid_json():
    data = json.loads(MIGRATIONS_FILE.read_text(encoding="utf-8"))
    assert data["migrations"], "migration table is empty"


@pytest.mark.parametrize("migration", knowledge.all_migrations(),
                         ids=lambda m: m["id"])
def test_migration_has_required_fields(migration):
    for field in ("id", "title", "changed_in", "explanation", "verify_with"):
        assert migration.get(field), f"{migration.get('id')} is missing '{field}'"

    # verify_with is what stops the table being treated as an authority. Every
    # entry must name a tool that can confirm it.
    assert "(" in migration["verify_with"], (
        f"{migration['id']}: verify_with should name a concrete tool call"
    )


@pytest.mark.parametrize("migration", knowledge.all_migrations(),
                         ids=lambda m: m["id"])
def test_migration_detect_patterns_compile(migration):
    for rule in migration.get("detect", []):
        assert "pattern" in rule and "message" in rule
        re.compile(rule["pattern"])  # raises on a bad pattern
        assert rule.get("kind") in ("command", "json", "path", "any", None)


def test_migration_ids_are_unique():
    ids = [m["id"] for m in knowledge.all_migrations()]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Version comparison
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("a,b,expected", [
    ("1.21.4", "1.20.5", True),
    ("1.20.4", "1.20.5", False),
    ("1.21", "1.21", True),
    ("1.21.2", "1.21", True),
    ("1.20", "1.21", False),
    ("1.9", "1.10", False),      # not a string comparison
    ("1.100", "1.99", True),
])
def test_version_gte(a, b, expected):
    assert knowledge.version_gte(a, b) is expected


def test_changes_between_is_bounded_by_from_version():
    """A change already present in from_version must not be reported again."""
    everything = knowledge.changes_between(None, "1.21.4")
    narrow = knowledge.changes_between("1.21", "1.21.4")

    assert len(narrow) < len(everything)
    ids = {m["id"] for m in narrow}
    assert "item-nbt-to-components" not in ids, (
        "1.20.5 change reported for a range starting at 1.21"
    )


def test_changes_applicable_to_modern_version_include_components():
    ids = {m["id"] for m in knowledge.applicable_to("1.21.4")}
    assert "item-nbt-to-components" in ids
    assert "datapack-folders-singularized" in ids


def test_changes_not_applicable_to_old_version():
    ids = {m["id"] for m in knowledge.applicable_to("1.19.4")}
    assert "item-nbt-to-components" not in ids
    assert "datapack-folders-singularized" not in ids


# ---------------------------------------------------------------------------
# Syntax detection -- true positives
# ---------------------------------------------------------------------------

def test_detects_legacy_item_nbt():
    result = knowledge.check_syntax(
        '/give @s diamond_sword{Enchantments:[{id:"minecraft:sharpness",lvl:5}]} 1',
        "1.21.4", kind="command")
    assert "item-nbt-to-components" in {i["migration_id"] for i in result["issues"]}


def test_detects_prefixed_attribute():
    result = knowledge.check_syntax(
        "/attribute @s minecraft:generic.max_health base set 40",
        "1.21.4", kind="command")
    assert "attribute-name-prefixes-dropped" in {i["migration_id"] for i in result["issues"]}


def test_detects_set_nbt_loot_function():
    result = knowledge.check_syntax(
        '{"function": "minecraft:set_nbt", "tag": "{}"}', "1.21.4", kind="json")
    assert "loot-set-nbt-to-set-components" in {i["migration_id"] for i in result["issues"]}


def test_detects_recipe_result_item_key():
    result = knowledge.check_syntax(
        '{"result": {"item": "minecraft:diamond_sword", "count": 1}}',
        "1.21.4", kind="json")
    assert "recipe-result-object" in {i["migration_id"] for i in result["issues"]}


def test_detects_plural_datapack_folders():
    result = knowledge.check_paths(
        ["data/mypack/advancements/root.json", "data/mypack/tags/items/tool.json"],
        "1.21")
    assert result["issue_count"] == 2


# ---------------------------------------------------------------------------
# Syntax detection -- false positives
# ---------------------------------------------------------------------------

def test_no_false_positive_on_modern_component_syntax():
    result = knowledge.check_syntax(
        '/give @s diamond_sword[enchantments={"minecraft:sharpness":5}] 1',
        "1.21.4", kind="command")
    assert result["issue_count"] == 0, result["issues"]


def test_no_false_positive_on_modern_recipe():
    result = knowledge.check_syntax(
        '{"type":"minecraft:crafting_shaped","result":{"id":"minecraft:diamond_sword","count":1}}',
        "1.21.4", kind="json")
    assert result["issue_count"] == 0, result["issues"]


def test_no_false_positive_on_singular_folders():
    result = knowledge.check_paths(
        ["data/mypack/advancement/root.json", "data/mypack/tags/item/tool.json"],
        "1.21")
    assert result["issue_count"] == 0, result["issues"]


def test_legacy_syntax_is_not_flagged_on_legacy_version():
    """Old NBT is correct on 1.20.4 and must not be reported there."""
    result = knowledge.check_syntax(
        '/give @s diamond_sword{Enchantments:[{id:"minecraft:sharpness",lvl:5}]} 1',
        "1.20.4", kind="command")
    assert "item-nbt-to-components" not in {i["migration_id"] for i in result["issues"]}


def test_clean_result_states_it_is_not_a_guarantee():
    """A clean scan must not read as proof of validity."""
    result = knowledge.check_syntax("/say hello", "1.21.4", kind="command")
    assert result["issue_count"] == 0
    assert "does NOT mean" in result["caveat"]


# ---------------------------------------------------------------------------
# Brigadier
# ---------------------------------------------------------------------------

TREE = {
    "type": "root",
    "children": {
        "give": {"type": "literal", "children": {
            "targets": {"type": "argument", "parser": "minecraft:entity", "children": {
                "item": {"type": "argument", "parser": "minecraft:item_stack",
                         "executable": True, "children": {
                             "count": {"type": "argument", "parser": "brigadier:integer",
                                       "properties": {"min": 1}, "executable": True}}}}}}},
        "kill": {"type": "literal", "executable": True},
    },
}


def test_tokenize_keeps_components_together():
    tokens, depth, quote = brigadier.tokenize(
        '/give @s diamond_sword[enchantments={"minecraft:sharpness":5}] 1')
    assert depth == 0 and quote is None
    assert 'diamond_sword[enchantments={"minecraft:sharpness":5}]' in tokens


def test_tokenize_reports_unbalanced_brackets():
    _, depth, _ = brigadier.tokenize("/give @s diamond_sword[enchantments={ 1")
    assert depth != 0


def test_render_usage_produces_readable_lines():
    rendered = brigadier.render_usage("give", TREE["children"]["give"])
    assert "/give <targets> <item>" in rendered["usage"]
    assert "/give <targets> <item> <count>" in rendered["usage"]
    assert "targets" in rendered["arguments"]


@pytest.mark.parametrize("command", [
    "/give @s diamond_sword",
    "/give @s diamond_sword 5",
    'give @s diamond_sword[enchantments={"a":1}] 1',
    "/kill",
])
def test_valid_commands_parse(command):
    assert brigadier.validate(command, TREE)["valid"] is True


@pytest.mark.parametrize("command,fragment", [
    ("/give", "incomplete"),
    ("/give @s diamond_sword abc", "unexpected token"),
    ("/nonexistent @s", "unexpected token"),
    ("/give @s sword[unclosed 1", "unbalanced"),
])
def test_invalid_commands_are_rejected(command, fragment):
    result = brigadier.validate(command, TREE)
    assert result["valid"] is False
    assert fragment in result["error"]


def test_invalid_command_reports_what_was_expected():
    """The recovery hint is the point -- an agent cannot self-correct without it."""
    result = brigadier.validate("/give", TREE)
    assert result["expected_here"], "no recovery information offered"


def test_integer_range_is_enforced():
    result = brigadier.validate("/give @s diamond_sword 0", TREE)
    assert result["valid"] is False
