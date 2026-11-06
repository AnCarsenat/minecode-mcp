---
name: minecraft-feature-workflow
description: Step-by-step method for implementing a new feature in a Minecraft Java datapack (custom item, mechanic, timer, boss, crafting recipe, loot, advancement, dimension) so it is correct for the target version and verified before handing it over. Use when the user asks to add, build, make or implement something in a datapack or mcfunction project.
---

# Implementing a datapack feature

Goal: a feature that loads, runs, and is correct **for the target version**,
proven by tools rather than asserted. Work in this order; each step feeds the
next.

## 1. Pin the target

- `minecraft_start_session(workspace_path)` → target version, pack format,
  declared range, overlays, breaking changes that apply.
- No `pack.mcmeta`? Ask which version. For a new pack, create one with
  `version_to_pack_format(version)` (see *pack.mcmeta* below).
- A range (`supported_formats` / `min_format`–`max_format`) means the syntax
  must hold at **both ends**, or be split with overlays. Check both.

## 2. Turn the request into game mechanics

Minecraft has no events API. Translate the request into what the game offers,
and tell the user when the request needs a workaround:

| need | usual mechanism |
| --- | --- |
| run every tick | `#minecraft:tick` → one dispatcher function; keep per-tick work tiny |
| run once at load | `#minecraft:load` → create objectives, init storage, `schedule` loops |
| every N ticks | `schedule function ns:loop 20t` re-scheduling itself, or a scoreboard counter |
| player did X (ate, crafted, killed, used item, entered area) | advancement with a trigger criterion + `rewards.function`, then `advancement revoke` to re-arm |
| count a statistic | scoreboard objective with a criterion (`minecraft.used:minecraft.carrot_on_a_stick`, `deathCount`, …) |
| per-entity state | scoreboard on the entity, entity `Tags`, or `custom_data` on items |
| global state | `#name objective` fake-player scores, or `data … storage ns:state` |
| reusable condition | predicate file → `execute if predicate` |
| parameterised function | macros (`$` lines + `function ns:f {…}` / `with storage`) — 1.20.2+ |
| custom item | vanilla item + components (`custom_data`, `custom_name`, `item_model` from 1.21.2, …) — 1.20.5+; NBT before |
| right-click detection | `consumable` component (1.21.2+) or `carrot_on_a_stick` + `used` stat; check the version |
| custom crafting | recipe JSON (`result.id` from 1.20.5) |
| custom drops | loot table override or item modifier |

Name everything under the pack's own namespace. Never edit `minecraft:` files
you do not mean to override; tags in `minecraft:tags/function/` are the
exception (that is how load/tick hook in).

## 3. Look up every version-sensitive shape before writing it

- `get_technical_changes(to_version=target, topic=…)` for items, text,
  loot, recipes, predicates, advancements, attributes.
- Commands: `get_command_usage(version, command)`.
- Ids: `spyglass_get_registries(version, registry, search)`; block states:
  `spyglass_get_block_states`.
- JSON / component fields: `spyglass_search_mcdoc_symbols` →
  `spyglass_get_mcdoc_symbol`.
- Copy the shape of a real vanilla file: `misode_get_presets` →
  `misode_get_preset_data(version, generator_type, preset_id)`.

## 4. Write

Layout (1.21+ singular folders; before 1.21 plural — see the
`minecraft-version-differences` skill):

```text
pack.mcmeta
data/<ns>/function/load.mcfunction
data/<ns>/function/tick.mcfunction
data/<ns>/function/<feature>/....mcfunction
data/<ns>/advancement/  predicate/  loot_table/  recipe/  item_modifier/
data/minecraft/tags/function/load.json   {"values": ["<ns>:load"]}
data/minecraft/tags/function/tick.json   {"values": ["<ns>:tick"]}
```

Conventions that prevent bugs:

- Namespace every id (`minecraft:stone`, `ns:thing`) — valid in every version.
- Prefix objectives and tags with the namespace (`ns.timer`, `ns.boss`); other packs share the scoreboard.
- `scoreboard objectives add` in load fails harmlessly when the objective already exists; do not "fix" that by removing and re-adding (it wipes the scores).
- Keep `tick` cheap: gate expensive work with `execute if entity …` or a scheduled loop.
- `@s` in an advancement reward function is the player; in `tick` it is the server (no entity) — use `execute as @a at @s run …`.
- Comments start with `#` at line start; no trailing comments after a command.
- Macro lines start with `$`; everything else in the file must parse without the macro.

## 5. Verify before saying it is done

1. `validate_command(command, version)` on each new command line (all of them for short files).
2. `check_version_syntax(content, version, kind)` on each file.
3. `check_pack_structure(path)` — folder names.
4. If the emulator tools exist:
   - `emulator_check(path, version)` — what the version refuses to load.
   - `emulator_run(path, version, ticks, commands=[…])` — does it run, what does it print, what is the world state after.
   - `emulator_test(path, tests=[…], checks=[…])` — assert the behaviour (e.g. `"20:"` + `score #ns ns.timer = 20`).
   - For a range: `emulator_matrix(path, declared=true, boundaries=true)`.
5. Fix and repeat until clean. Do not hand over a feature that has not passed step 1–3.

## 6. Hand over

Tell the user:
- what you built and which files changed;
- the target version it was verified against (and the range, if any);
- how to try it in game (`/reload`, the trigger command, `/function ns:…`);
- what you could not verify (gameplay the emulator does not model: AI,
  physics, redstone, real advancement triggers) and what might break
  (other packs editing the same `minecraft:` files, version upgrades).

## pack.mcmeta

```json
{ "pack": { "pack_format": <version_to_pack_format(target).data>, "description": "…" } }
```

- Range of versions: `"supported_formats": {"min_inclusive": A, "max_inclusive": B}`
  (1.20.2–1.21.8). From 1.21.9, `"min_format"`/`"max_format"` replace
  `supported_formats` (and `pack_format` becomes optional); a pack that must
  also load on older versions keeps the old fields alongside. Overlays
  (`"overlays": {"entries": [{"directory": "overlay_48", "formats": …}]}`, with
  `min_format`/`max_format` instead of `formats` from 1.21.9) carry
  per-version files. Confirm the exact fields with
  `get_technical_changes(to_version=target, topic="pack")`.
