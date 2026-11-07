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


def test_matrix_runs_exact_versions_as_given(pack):
    # 1.21 and 1.21.1 share a pack format; boundaries must not drop one of them
    m = emulator.handle_emulator_matrix(str(pack), versions=["1.21", "1.21.1"], ticks=1)
    assert m["success"] and [row["version"] for row in m["results"]] == ["1.21", "1.21.1"]


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
    assert r["success"] is False and "pip install -U minecode-mcp" in r["hint"]


def _report(tmp_path, name="2026-11-06_21_34_37-world-26_2.zip"):
    import zipfile
    from pathlib import Path

    folder = tmp_path / "debug" / "profiling"
    folder.mkdir(parents=True)
    report = folder / name
    text = (Path(__file__).parent / "data" / "profiling-26.2.txt").read_text()
    with zipfile.ZipFile(report, "w") as archive:
        archive.writestr("server/profiling.txt", text)
    return report


def test_server_profile_reads_a_report(tmp_path):
    report = _report(tmp_path)
    r = emulator.handle_emulator_server_profile(str(report))
    if not r["success"] and "too old" in r.get("error", ""):
        pytest.skip("datapack-emulator < 0.3.0")
    assert r["success"] and r["measured"] and r["report"] == str(report)
    assert r["functions"][0]["function"] == "probe:sb"


def test_server_profile_finds_the_newest_report(tmp_path, monkeypatch):
    _report(tmp_path)
    monkeypatch.setattr(emulator, "_game_dirs", lambda: [tmp_path])
    r = emulator.handle_emulator_server_profile()
    if not r["success"] and "too old" in r.get("error", ""):
        pytest.skip("datapack-emulator < 0.3.0")
    assert r["success"] and r["report"].endswith(".zip")


def test_server_profile_without_a_report_says_how_to_make_one(tmp_path, monkeypatch):
    monkeypatch.setattr(emulator, "_game_dirs", lambda: [tmp_path])
    r = emulator.handle_emulator_server_profile()
    assert r["success"] is False and "/perf start" in r["hint"]


def test_find_perf_reports_ignores_stray_zips_and_missing_folders(tmp_path, monkeypatch):
    (tmp_path / "my-pack-v1.zip").write_bytes(b"not a report")  # a workspace release zip
    monkeypatch.setattr(emulator, "_game_dirs", lambda: [tmp_path, tmp_path / "missing"])
    assert emulator.find_perf_reports() == []
    report = _report(tmp_path)
    assert emulator.find_perf_reports() == [report.resolve()]
    # a folder the user points at explicitly may hold the zips directly
    assert (tmp_path / "my-pack-v1.zip").resolve() in emulator.find_perf_reports(str(tmp_path))


def test_check_puts_load_blockers_first(tmp_path):
    root = tmp_path / "fatal"
    (root / "data/t/worldgen/biome").mkdir(parents=True)
    (root / "pack.mcmeta").write_text('{"pack": {"pack_format": 61, "description": ""}}')
    (root / "data/t/worldgen/biome/bad.json").write_text("{not json")
    r = emulator.handle_emulator_check(str(root), "1.21.4")
    if "load_blockers" not in r:
        pytest.skip("datapack-emulator without fatal problems")
    assert r["success"] and r["ok"] is False and r["load_blockers"]
    assert r["first"].startswith("FATAL")


def test_real_server_needs_the_users_eula_consent(tmp_path):
    r = emulator.handle_emulator_check(str(tmp_path), "26.2", real_server=True)
    assert r["success"] is False and "EULA" in r["error"]
    assert "Ask the user" in r["hint"]
