---
name: minecraft-recurring-issues
description: Catalogue of the mistakes that recur in Minecraft Java datapacks and in AI-written datapack code — silent load failures, outdated syntax, context and selector bugs, scoreboard pitfalls, performance traps — each with the symptom, the cause, the fix and the tool that catches it. Use as a checklist when writing or reviewing datapack code, and when a bug looks familiar.
---

# Recurring datapack issues

Each entry: **symptom → cause → fix → tool that catches it.** Read the whole
list once before reviewing a pack; most bugs are one of these.

## Silent load failures (no error, nothing happens)

1. **Folder spelling vs version.** 1.21+ reads `function/`, `tags/function/`,
   `advancement/`, `loot_table/`, `recipe/`, `predicate/`, `item_modifier/`,
   `structure/`, `tags/block|item|entity_type|fluid|game_event/`; older versions
   read the plural forms. The wrong spelling is ignored without a log line.
   → rename, or ship both via overlays for multi-version packs.
   → `check_pack_structure`, `emulator_check` (`ignored-folder`), `emulator_run` (`ignored_folders`).
2. **Load/tick tag in the wrong place.** Must be `data/minecraft/tags/function/load.json`
   (plural `functions` before 1.21) with `{"values": ["ns:load"]}`.
   → `emulator_run`: an `emulator` note says `#minecraft:tick is empty`.
3. **Nested pack folder.** `datapacks/Pack/Pack/pack.mcmeta` — the world sees
   no pack. → put `pack.mcmeta` directly in `datapacks/<Pack>/`.
4. **Invalid resource names.** Uppercase, spaces, accents in a path → the file
   is skipped. → lowercase `a-z 0-9 _ - . /` only.
5. **Pack not enabled** after adding it to a running world → `/reload`, check
   `/datapack list`.

## Whole file dropped by one bad line

6. **One unparsable line drops the entire function**, and the game only warns.
   Callers then call nothing. → `validate_command` each line; `emulator_check`
   lists `function-not-loaded` with the line.
7. **Item NBT braces on 1.20.5+**: `give @s stick{display:{Name:'…'}}` →
   `give @s stick[custom_name="…"]` (components; shape per version — look it up).
   → `check_version_syntax`.
8. **Text components**: 1.21.5+ commands take SNBT, not a JSON string;
   `clickEvent`/`hoverEvent` became `click_event`/`hover_event` with renamed
   inner fields; booleans must be booleans. → `get_technical_changes(topic="text")`.
9. **Attribute ids** lost `generic.`/`player.`/… in 1.21.2. → `spyglass_get_registries(registry="attribute")`.
10. **Commands that do not exist yet** in the target: `item` (1.17), `place`
    (1.19), `damage`/`ride`/`execute on|summon` (1.19.4), `return` (1.20),
    `random`, macros (1.20.2), `tick`, `execute if function`, `return run`
    (1.20.3), `transfer`, `execute if items` (1.20.5), `rotate` (1.21.2),
    `dialog` (1.21.6). `replaceitem` is gone from 1.17. → `validate_command`, `emulator_explain`/`emulator_check`.
11. **Comments**: only whole-line `#`; `say hi # note` says the comment.
12. **Encoding**: BOM at file start, smart quotes from copy-paste, CRLF in
    macro lines. → save UTF-8 without BOM.

## The world will not load (fatal)

43. **A world registry file the version rejects.** Worldgen, dimension,
    dimension type, enchantment, damage type, variants… are loaded all or
    nothing when the world starts: one bad element and the server stops with
    "Failed to load datapacks, can't proceed with server load" — for every
    pack. Typical after a version upgrade: a newly required field
    (`dimension_type.has_ender_dragon_fight` in 26.2, `noise_router` fields),
    a removed feature type (`minecraft:random_patch` in 26.2).
    → `emulator_check` → `load_blockers`; `real_server=true` for the server's
    exact verdict (needs the user's EULA consent).

## JSON resources ignored

13. **Recipe `result`**: `"item"` → `"id"` (1.20.5); bare-string result invalid. → `misode_get_preset_data(generator_type="recipe")`.
14. **Loot `set_nbt`** removed (1.20.5) → `set_components` / `set_custom_data`.
15. **Item predicates** `"nbt"` → `"components"` / `"predicates"` (1.20.5).
16. **Missing required fields** (e.g. `criteria` on advancements, `pools[].rolls`
    on loot tables) → file dropped. → compare with `misode_get_preset_data`.
17. **Copying vanilla JSON from another version.** Always fetch the preset for
    *the target* version: `misode_get_preset_data(version=target, …)`.

## Context and selectors

18. **`@s` in tick / schedule / load** is the server: matches no entity. Use
    `execute as @a at @s run function ns:per_player`.
19. **Position is separate from executor**: `execute as @a run …` changes who
    `@s` is but still runs at the old position (world spawn from tick). Add
    `at @s` for relative coordinates (`~ ~ ~`, `distance=`, `@p`). Each
    subcommand applies in order, so `as @e[type=zombie] at @s as @p` ends with
    `@s` = the player nearest each zombie.
20. **`@p` from the server** picks the player nearest world spawn, not "the player".
21. **Unfiltered `@e`** iterates items, arrows, XP orbs, markers; slow and wrong.
    Add `type=` and a namespaced `tag=`.
22. **`limit=1` without `sort`** is "arbitrary", not "nearest" (selector `@e` sorts arbitrarily by default).
23. **`execute if entity` vs `as`**: `if` tests once; `as` forks per entity — a
    `run function` after `as @e` runs N times.

## Scoreboards and state

24. **Unset score ≠ 0**: `if score @s x matches 0` fails for a player with no
    score. Initialise (`scoreboard players add @s x 0`) or test `unless score … matches 1..`.
25. **Integer-only, 32-bit**; `/=` floors; overflow wraps. Scale by 100 or 1000
    for decimals; `execute store result … scale 0.01` to convert.
26. **Objective name collisions** with other packs → prefix (`ns.timer`).
27. **Removing and re-adding objectives in load** wipes every score on `/reload`.
28. **Trigger objectives** must be `scoreboard players enable @a ns.trig` again
    after each use.

## Re-arming

29. **Advancement-triggered functions fire once** unless the reward function
    runs `advancement revoke @s only ns:adv`.
30. **`schedule function`** replaces a pending schedule of the same function by
    default; use `append` for several, and re-schedule inside a loop function.
31. **Tags as flags** must be removed when done (`tag @s remove ns.busy`).

## Performance

32. **Heavy work in `#tick`** — gate with a cheap `execute if`, or move to a
    20t scheduled loop. → `emulator_server_profile` on a `/perf start` report
    (real); `emulator_run` → `profile.functions`, `dearest_lines` (estimate).
    Measured on 26.2: an `nbt=` selector costs ~1.4 µs per entity it checks,
    `data … entity` ~3 µs, scoreboard and storage under 1 µs.
33. **Recursion without a depth limit** (raycasts) → hits `maxCommandChainLength`
    and stops silently. → `emulator_run` → `call_graph.recursion`.
34. **`@e[…,distance=..N]` without `type`** scans every entity in loaded chunks.

## Multi-version packs

35. **Single `pack_format` only** → "made for a different version" warning
    elsewhere. Add `supported_formats` (1.20.2–1.21.8) / `min_format`+`max_format`
    (1.21.9+, which drops `supported_formats`; keep both for a range spanning it).
36. **Overlay ranges overlapping or leaving gaps** → some versions get both or
    neither file. → `emulator_matrix(declared=true, boundaries=true)`.
37. **Testing only the newest version** of a range — always check both ends.

## AI-specific traps

38. Writing from memory instead of calling `get_command_usage` /
    `spyglass_get_mcdoc_symbol`. Recall is pre-1.20.5-biased.
39. Using the wiki (`get_wiki_page`) for syntax of an older target.
40. Declaring "done" without running `validate_command` and, where available,
    the emulator.
41. Inventing ids (`minecraft:ruby`) — check with `spyglass_get_registries(search=…)`.
42. Assuming the latest version when `pack.mcmeta` was not found — ask.
