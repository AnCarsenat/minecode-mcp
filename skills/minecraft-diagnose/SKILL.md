---
name: minecraft-diagnose
description: Systematic diagnosis of a Minecraft Java datapack that does nothing, errors, behaves wrongly, lags, or broke after a version upgrade. Use when the user reports that a datapack, function, recipe, loot table, advancement or command "doesn't work", "does nothing", shows an error, or stopped working on a new version.
---

# Diagnosing a datapack problem

Work from evidence to cause. Do not rewrite code before you know which of
the classes below the problem is in.

## 0. Pin the version

`minecraft_start_session(workspace_path)`. Ask which version the user
actually **plays** on — it is often not the one `pack.mcmeta` claims, and
that mismatch is itself a frequent cause.

## 1. Classify the symptom

| symptom | most likely class | first move |
| --- | --- | --- |
| nothing happens, no error anywhere | not loaded (folders, tags, namespace, pack disabled) | `check_pack_structure`, `emulator_run` → `ignored_folders`, `failed_functions` |
| "Unknown or incomplete command" / function missing from `/function` tab-complete | function failed to parse (whole file dropped) | `get_logs(filter="errors")`, `emulator_check`, `validate_command` per line |
| works on old version, broken on new | syntax migration | `get_technical_changes(from_version=old, to_version=new)` |
| JSON file (recipe, loot, advancement, predicate) ignored | schema error → file dropped on load | logs, `emulator_check`, compare with `misode_get_preset_data` |
| runs but wrong result | logic: selector, context (`@s`, position), execution order, score math | `emulator_run` with `commands=[…]` to inspect state; `emulator_test` to pin it |
| runs once then stops | re-arming: advancement not revoked, schedule not re-scheduled, tag not removed | read the trigger path |
| lag | per-tick work, `@e` without filters, `nbt=` scans, entity NBT reads, unbounded recursion | ask for a `/perf start` report → `emulator_server_profile` (real ms per function and line); `emulator_run` → `profile`, `call_graph.recursion` |
| "pack made for a different version" | pack_format / range mismatch | `detect_pack_version`, `version_to_pack_format` |

## 2. Gather evidence

1. **Logs**: `get_logs(filter="errors")`. Look for `Failed to load function`,
   `Couldn't load tag`, `Couldn't parse element`, `Failed to parse`. The line
   number after `Whilst parsing command on line N` is the culprit; the whole
   function file is dropped, and every function calling it then fails silently.
2. **Clean logs but nothing happens** → the content was never read. Run
   `check_pack_structure`. On 1.21+ `functions/`, `tags/functions/`,
   `loot_tables/`, `advancements/` … are ignored without a word (and before
   1.21 the singular ones are). This is the #1 cause.
3. **Static check**: `emulator_check(path, version)` lists every function and
   tag that will not load, unknown ids, bad SNBT, missing referenced
   functions, broken loot tables and predicates — per version.
4. **Run it**: `emulator_run(path, version, ticks=40, commands=[…])`. Read
   `summary`, then `ignored_folders`, `failed_functions`, `failed_tags`,
   records with `level: error`, `call_graph.missing_functions` /
   `never_called`. Use `commands` to ask the world:
   `scoreboard players get #x ns.obj`, `data get storage ns:state`,
   `execute if entity @e[tag=ns.boss]`.
5. **Single lines**: `validate_command(line, version)` gives the failing
   token and what was expected; `get_command_usage` gives the grammar.
6. **Known bug?** `search_mojira(query)` before a long session; check each
   issue's affected versions.

## 3. Common root causes, by class

**Not loaded**
- Folder spelling wrong for the version (1.21 rename) — incl. `tags/function(s)`.
- `#minecraft:load` / `#minecraft:tick` tag file missing, misspelled, or in the wrong namespace (`data/minecraft/tags/function/tick.json`).
- `pack.mcmeta` invalid JSON, or the pack is a folder inside a folder (`datapacks/MyPack/MyPack/pack.mcmeta`).
- Pack disabled: `/datapack list` shows it under *available*, not *enabled*.
- Uppercase letters or spaces in a file or folder name: ids are `[a-z0-9_.-/]` only — the file is skipped.

**Parse failure (whole file dropped)**
- Item NBT in braces on 1.20.5+ → components in brackets.
- JSON-string text components where 1.21.5+ wants SNBT; `clickEvent` → `click_event`, `hoverEvent` → `hover_event`.
- `generic.` attribute ids on 1.21.2+.
- A command that does not exist in this version (`item` < 1.17, `return` < 1.20, `execute if function` < 1.20.3, `rotate` < 1.21.2).
- Macro line (`$…`) without `$`, or a `$(var)` in a non-`$` line.
- Trailing comment after a command, smart quotes, a BOM at file start.

**Logic**
- Wrong execution context: `tick` runs as the server — `@s` matches nothing; use `execute as @a at @s`.
- `@p`/`@s` in a scheduled function: schedules run as the server at world spawn.
- Score never initialised (unset ≠ 0 for `if score … matches`).
- Advancement fired once and never revoked.
- Load runs after/before tick depending on version (load first from 1.19.3).
- Integer math: scoreboards are 32-bit ints, `/=` truncates toward −∞, no floats — scale with `execute store … scale`.
- `@e` selectors include items, projectiles, markers and players — add `type=` and tags.

## 4. Fix, then prove it

1. Fix the cause, not the symptom. Explain the cause to the user first.
2. Re-run the same evidence: `emulator_check`, `emulator_run`; turn the bug
   into an `emulator_test` that failed before and passes now.
3. If the user upgraded versions, run `emulator_matrix(path, declared=true,
   boundaries=true)` so the fix does not break the other end of the range.
4. Say what changed and what you could not verify (things the emulator does
   not model: physics, AI, redstone, gameplay advancement triggers).

## When the emulator and the game disagree

The emulator is a model. A `game`-source error from it is real; an
`emulator`-source note marks something it does not simulate. If the user
sees behaviour in game that the emulator does not reproduce, trust the game,
and check `search_mojira` and the emulator's limits before blaming the pack.
