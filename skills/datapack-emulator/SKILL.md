---
name: datapack-emulator
description: How to run, test and check a Minecraft Java datapack without the game using Datapack Emulator — through MineCode's emulator_* MCP tools, the datapack_emulator.agent Python API, or datapack-emulator-cli --json — and how to read its results. Use after writing or changing datapack code, to reproduce a bug, to assert behaviour with tests, or to check a pack across a range of versions.
---

# Datapack Emulator

The emulator loads a pack the way a server of a chosen version would, runs
`#minecraft:load` and `#minecraft:tick`, and reports what happened: errors,
chat, functions that did not load, folders the version ignored, the final
scores/storage/entities, the call graph and an estimated cost. Seconds per
run, no Minecraft install. It closes the loop **write → run → read → fix**.

## Three ways in, same JSON

| you have | call |
| --- | --- |
| MineCode MCP tools | `emulator_check`, `emulator_run`, `emulator_test`, `emulator_matrix`, `emulator_explain`, `emulator_server_profile` |
| Python | `from datapack_emulator import agent` → `agent.check/run/test/matrix/explain/server_profile` |
| a shell | `datapack-emulator-cli --quiet run|test|matrix PACK --version V --json` |

`PACK` is the folder that holds `pack.mcmeta` (or several, in load order).
Always pass the version the pack targets.

## Which one when

| goal | call | read |
| --- | --- | --- |
| will it load? (cheap, first) | `check(path, version)` | `load_blockers` FIRST (fatal: the world/pack will not load), then `ok`, `results[].problems[]` (`severity`, `code`, `resource`, `line`, `message`) |
| what exactly does a real server refuse? | `check(path, version, real_server=true, user_accepted_minecraft_eula=true)` | `results[].server` (`started`, `problems`, `log`) — only with the user's explicit EULA consent |
| does it run, what does it do? | `run(path, version, ticks=40, commands=[…])` | `summary`, `ignored_folders`, `failed_functions`, error `records`, `chat`, `world.scores`, `commands[].output` |
| does it do the *right* thing? | `test(path, tests=[…], checks=[…])` | `ok`, `results[].status`/`reason` |
| does it work across the range? | `matrix(path, declared=true, boundaries=true)` | `results[]` per version: `status`, `unknown_commands`, `failed_functions` |
| is this one line valid in V? | `explain(command, version)` | `exists`, `missing_features[].since` |

## Reading results

- Severities, worst first: **fatal** (the world or the pack will not load
  at all — fix these before anything else), error, warning, info.

- Read `summary` first. Then `ok`.
- `run.ok` is **false** for the silent failures the real game only warns
  about: a function that does not parse (`failed_functions`), a tag that
  does not load (`failed_tags`), a resource kind sitting in folders this
  version ignores (`ignored_folders` — `functions/` on 1.21+), a called
  function that does not exist (`call_graph.missing_functions`), any
  error-level record.
- Record `source`: `game` = what Minecraft would print (real problem);
  `emulator` = a limit of the emulation (a command it does not model) — not a
  bug in the pack; `app` = context.
- `call_graph.never_called`: functions nothing reaches — usually a missing
  tag entry or typo in a `function` call.
- `profile` comes from a cost model **measured on a real server**, but in
  warm loops: a lower bound and a ranking (what is dearest, how a change
  moves it), not real milliseconds — a line run once per tick can cost
  10–50× more on a real server. For real numbers: `emulator_server_profile`.
- Lists are capped (`max_records`); `truncated: true` and `*_total` say so.

## Real timings (`emulator_server_profile`)

When the user reports lag, or asks what their pack really costs:

1. ask them to run `/perf start` in game (singleplayer works) or on the server
   console, and wait 10 seconds — the server writes
   `debug/profiling/<date>-<world>-<version>.zip`;
2. `emulator_server_profile()` finds the newest report in the game folders
   (or pass `report=` / `search_dir=`), and returns `mspt` (the whole tick),
   `datapack_ms_per_tick`, and per function `ms_per_tick` with its dearest
   `lines[]` (`us_each`, `runs_per_tick`; lines from 1.20.3);
3. with `path=` the pack is emulated too: `compared.functions[]` has the
   estimate and `ratio` per function — a function whose ratio is far above
   the others does something the model misses.

Fix the dearest function first; check the fix with a new `/perf` report.

## Asking the world (`run` → `commands`)

Commands run after the ticks, as if typed in the server console (as the
server, at 0 0 0 — use `execute as @p at @s run …` for player context):

```json
["scoreboard players get #game ns.timer",
 "data get storage ns:state",
 "execute if entity @e[tag=ns.boss]",
 "function ns:debug/dump"]
```

Each answer has `success`, `value` and its own `output` records.

## Writing tests

A test is `"TICK:COMMAND"` (runs after that tick's functions; tick 0 is the
first, after load) or an object
`{"command", "at_tick", "expect", "expect_value", "checks"}`. The command
may be empty (`"20:"`) when only checks matter. Check lines — spaces around
`=`/`!=` are required:

```text
score HOLDER OBJECTIVE = RANGE    score #game ns.timer = 20     score @p ns.pts != 0
storage ID [PATH] = SNBT          storage ns:state phase = 2b
entity SELECTOR [PATH] = SNBT     entity @e[type=pig,limit=1] Tags = ["ns.marked"]
SELECTOR = RANGE                  @e[type=zombie,tag=ns.boss] = 1
block X Y Z = BLOCK               block 0 64 0 = minecraft:chest[facing=north]
if CONDITION / unless CONDITION   if entity @a[tag=ns.winner]
```

`expect` = text the command output must contain; `expect_value` = range the
command's result must be in (`5`, `1..`, `..3`, `1..4`).

Pattern — pin a behaviour, then refactor safely:

```json
{"path": "my_pack", "version": "1.21.4",
 "tests": [{"command": "", "at_tick": 19, "checks": ["score #t ns.timer = 20"]},
           {"command": "function ns:reset", "at_tick": 20, "checks": ["score #t ns.timer = 0"]}]}
```

## Typical loops

**Bug report "pack does nothing"** → `run` → `ignored_folders` /
`failed_functions` / `never_called` → fix → `run` again until `ok`.

**New feature** → write → `check` → `run` with `commands` that show the new
state → encode the expected behaviour as a `test` → hand over with the test.

**Version port** → `matrix(from_version=old, to_version=new, boundaries=true)`
→ for each failing version, `get_technical_changes` for the cliff → fix or
overlay → `matrix` again.

## Limits — say them to the user

Modelled: scoreboards, selectors, `execute` (all subcommands of the
version), macros, schedules, storage, entity NBT, tags, inventories, placed
blocks and containers, teams, bossbars, predicates, loot tables, item
modifiers, advancements (tick/location triggers), health/attributes/effects.

Not modelled: chunks, physics, movement, mob AI, redstone, block updates,
worldgen, gameplay-triggered advancements (killing, crafting, using items),
real players. A pack can pass here and still fail in game for those; a
`game`-source error here fails in game too.

With a `client.jar` (`vanilla="auto"` uses an installed one,
`download=true` fetches it from Mojang once) ids, tags, loot tables and JSON
fields are checked against that version's real files. Without one, logic is
still emulated; id checks are skipped.

## Install

`pip install datapack-emulator` (pure standard library). MineCode depends on
it; if the `emulator_*` tools report it missing, install it into the same
Python as the `minecode` server. Full contract: the emulator's
`docs/agents.md`.
