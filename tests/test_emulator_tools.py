"""The emulator_* tools (offline: no client jar is fetched)."""

import json

import pytest

pytest.importorskip("datapack_emulator.agent")

from minecode import emulator  # noqa: E402


@pytest.fixture
def pack(tmp_path):
    root = tmp_path / "pack"
    files = {
        "pack.mcmeta": {"pack": {"pack_format": 61, "description": "t"}},
        "data/t/function/load.mcfunction": "scoreboard objectives add t.n dummy\nscoreboard players set #c t.n 0\n",
        "data/t/function/tick.mcfunction": "scoreboard players add #c t.n 1\n",
        "data/minecraft/tags/function/load.json": {"values": ["t:load"]},
        "data/minecraft/tags/function/tick.json": {"values": ["t:tick"]},
    }
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(content) if isinstance(content, dict) else content)
    return root


@pytest.fixture(autouse=True)
def no_jars(tmp_path, monkeypatch):
    from datapack_emulator import agent
    from datapack_emulator.emulator.vanilla import VanillaLibrary
    from datapack_emulator.settings import PATHS

    monkeypatch.setattr(PATHS, "CACHE", tmp_path / ".cache")
    monkeypatch.setattr(agent, "default_library",
                        lambda: VanillaLibrary(tmp_path / "jars", search_dirs=[]))


def test_run_returns_world_and_console_answers(pack):
    r = emulator.handle_emulator_run(str(pack), "1.21.4", ticks=5,
                                     commands=["scoreboard players get #c t.n"])
    assert r["success"] and r["ok"], r["summary"]
    assert r["world"]["scores"]["#c"]["t.n"] == 5
    assert r["commands"][0]["value"] == 5
    json.dumps(r)


def test_test_passes_and_fails(pack):
    good = emulator.handle_emulator_test(["4:"], str(pack), "1.21.4", checks=["score #c t.n = 5"])
    assert good["success"] and good["ok"], good
    bad = emulator.handle_emulator_test(["4:"], str(pack), "1.21.4", checks=["score #c t.n = 9"])
    assert bad["success"] and not bad["ok"]


def test_check_and_matrix_and_explain(pack):
    assert emulator.handle_emulator_check(str(pack), "1.21.4")["ok"]
    m = emulator.handle_emulator_matrix(str(pack), versions=["1.21", "1.21.4"], ticks=2)
    assert m["success"] and [row["version"] for row in m["results"]] == ["1.21", "1.21.4"]
    e = emulator.handle_emulator_explain("execute if function t:x run say hi", "1.20.2")
    assert e["success"] and e["ok"] is False


def test_bad_input_is_a_failure_not_an_exception(tmp_path):
    r = emulator.handle_emulator_run(str(tmp_path / "missing"))
    assert r["success"] is False and "no such" in r["error"]
    r = emulator.handle_emulator_test([], str(tmp_path))
    assert r["success"] is False


def test_missing_emulator_degrades_to_an_install_hint(monkeypatch):
    def unavailable():
        raise emulator._Unavailable("No module named 'datapack_emulator'")

    monkeypatch.setattr(emulator, "_agent", unavailable)
    r = emulator.handle_emulator_run(".")
    assert r["success"] is False and "pip install datapack-emulator" in r["hint"]
