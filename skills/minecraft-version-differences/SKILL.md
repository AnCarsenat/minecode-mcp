---
name: minecraft-version-differences
description: Per-version reference of Minecraft Java datapack differences — pack formats, folder names, commands and execute features by version, item NBT vs components, text component formats, attribute ids, pack.mcmeta fields — with the tool calls that confirm each one. Use when targeting a specific Minecraft version, porting a pack between versions, supporting a version range, or when unsure whether syntax is valid for a version.
---

# Version differences for datapacks

This is a **map, not the authority**. It tells you where the cliffs are; the
tools give the exact syntax. Before relying on an entry, confirm with
`get_technical_changes(from_version, to_version, topic)` (full changelog) or
the tool named beside it. For versions newer than this table, the tools are
the only source.

## Data pack formats

| version | format | | version | format |
| --- | --- | --- | --- | --- |
| 1.14–1.14.4 | 4 | | 1.20.5–1.20.6 | 41 |
| 1.15–1.16.1 | 5 | | 1.21–1.21.1 | 48 |
| 1.16.2–1.16.5 | 6 | | 1.21.2–1.21.3 | 57 |
| 1.17–1.17.1 | 7 | | 1.21.4 | 61 |
| 1.18–1.18.1 | 8 | | 1.21.5 | 71 |
| 1.18.2 | 9 | | 1.21.6 | 80 |
| 1.19–1.19.3 | 10 | | 1.21.7–1.21.8 | 81 |
| 1.19.4 | 12 | | 1.21.9–1.21.10 | 88 |
| 1.20–1.20.1 | 15 | | 1.21.11 | 94.1 |
| 1.20.2 | 18 | | 26.1–26.1.2 | 101.1 |
| 1.20.3–1.20.4 | 26 | | 26.2 | 107.1 |

Resource pack formats are numbered separately. Confirm with
`version_to_pack_format(version)` / `pack_format_to_version(n, kind)`.
From 1.21.11 formats have a minor part (`94.1`).

## The big cliffs

| version | change | consequence if ignored | confirm with |
| --- | --- | --- | --- |
| **1.20.2** | macros (`$` lines, `function … {args}` / `with`), `supported_formats`, overlays, `random` | none on newer; using them below 1.20.2 fails to parse | `get_technical_changes(to_version="1.20.2", topic="function")` |
| **1.20.5** | item NBT → **components** (`item[comp=…]`); recipe `result.item`→`result.id`; loot `set_nbt` removed; item predicates use `components`/`predicates`; attribute modifier fields lowercased, operations named (`add_value`, …); `execute if items`; inline predicates | braces NBT is a hard parse error; JSON files dropped | `topic="component"`, `spyglass_get_mcdoc_symbol` |
| **1.21** | registry folders **singular** (`function/`, `tags/function/`, `loot_table/`, …); enchantments are data-driven (`enchantment/`); attribute modifiers use namespaced `id` instead of UUID | plural folders ignored **silently** | `check_pack_structure`, `emulator_check` |
| **1.21.2** | attribute ids lose `generic.`/`player.`/… prefix; `food` split into `food` + `consumable`; `rotate` command | old ids unknown; food fields rejected | `spyglass_get_registries(registry="attribute")` |
| **1.21.4** | `custom_model_data` becomes an object (`{floats:[…], flags:[…], strings:[…], colors:[…]}`); item model definitions (`assets/<ns>/items/`) | integer value rejected | `topic="model"` |
| **1.21.5** | text components in commands are **SNBT**, not JSON strings; `clickEvent`→`click_event`, `hoverEvent`→`hover_event` (inner fields renamed, e.g. `show_text` uses `value`); strict types; `tooltip_display` replaces per-component `show_in_tooltip`; `enchantments` drops `levels` wrapper; `test` command | text silently wrong or parse error | `get_technical_changes(from_version="1.21.4", to_version="1.21.5", topic="text")` |
| **1.21.6** | dialogs (`dialog` command and registry), `waypoint`, `version` command | n/a below | `topic="dialog"` |
| **1.21.9** | `pack.mcmeta` gains `min_format`/`max_format` | range ignored by new clients if only old fields | `topic="pack"` |
| **26.x** | yearly numbering (26.1, 26.2, 26.3); new commands (`swing` 26.1, `unpublish` 26.2, `compute`, `posteffect` 26.3) | — | `list_technical_change_versions`, `get_technical_changes` |

## Commands and execute features by first version

From the emulator's version data (1.14 baseline: everything else predates it):

| since | added | removed |
| --- | --- | --- |
| 1.15 | `spectate`, `execute if predicate`, `execute store … storage`, `schedule clear` | |
| 1.16 | `attribute`, `locatebiome` | |
| 1.17 | `item`, `perf` | `replaceitem` |
| 1.18 | `jfr` | |
| 1.18.2 | `placefeature` | |
| 1.19 | `place` | `locatebiome`, `placefeature` (→ `locate biome`, `place feature`) |
| 1.19.3 | `fillbiome`, `execute if biome`; `#load` runs before `#tick` on the first tick | |
| 1.19.4 | `damage`, `ride`, `execute on`, `execute summon`, `execute if dimension`, `execute if loaded` | |
| 1.20 | `return <value>` | |
| 1.20.2 | `random`, `function … with`, macros | |
| 1.20.3 | `tick`, `execute if function`, `return run`, `return fail` | |
| 1.20.5 | `transfer`, `execute if items` | |
| 1.21.2 | `rotate` | |
| 1.21.5 | `test` | |
| 1.21.6 | `dialog`, `version`, `waypoint` | |
| 1.21.9 | `fetchprofile` | |
| 1.21.11 | `stopwatch`, `execute if stopwatch` | |
| 26.1 | `swing` | |
| 26.2 | `unpublish` | |
| 26.3 | `compute`, `posteffect`, `execute if slots` | |

Confirm one with `get_command_usage(version, command)` or `validate_command`.

## Same intent, different syntax

| intent | before | after |
| --- | --- | --- |
| named item | `give @s stick{display:{Name:'{"text":"Wand"}'}}` (≤1.20.4) | `give @s stick[custom_name={"text":"Wand"}]` (1.20.5+; SNBT text from 1.21.5) |
| enchant | `{Enchantments:[{id:"sharpness",lvl:5}]}` (≤1.20.4) | `[enchantments={levels:{"minecraft:sharpness":5}}]` (1.20.5–1.21.4) → `[enchantments={"minecraft:sharpness":5}]` (1.21.5+) |
| custom tag on item | `{MyTag:1b}` | `[custom_data={MyTag:1b}]` |
| model | `{CustomModelData:3}` → `[custom_model_data=3]` (1.20.5–1.21.3) | `[custom_model_data={floats:[3f]}]` (1.21.4+) |
| hide tooltip part | `HideFlags` (≤1.20.4) → `show_in_tooltip:false` (1.20.5–1.21.4) | `tooltip_display={hidden_components:[…]}` (1.21.5+) |
| max health | `generic.max_health` (1.16–1.21.1) | `max_health` (1.21.2+) |
| click a link | `"clickEvent":{"action":"open_url","value":"…"}` | `click_event:{action:"open_url",url:"…"}` (1.21.5+) |
| function folder | `data/ns/functions/` (≤1.20.6) | `data/ns/function/` (1.21+) |
| tick tag | `data/minecraft/tags/functions/tick.json` | `data/minecraft/tags/function/tick.json` (1.21+) |
| version range | — | `supported_formats` (1.20.2+), `min_format`/`max_format` (1.21.9+) |

Shapes in the right-hand column are the common form; fields inside
components keep changing — fetch the mcdoc (`spyglass_get_mcdoc_symbol`) or a
vanilla preset (`misode_get_preset_data`) for the exact target.

## Supporting a range

1. `detect_pack_version` → declared range.
2. Find every cliff inside the range with
   `get_technical_changes(from_version=min, to_version=max)`.
3. For each cliff either use syntax valid on both sides, or put the newer
   form in an overlay (`overlays.entries[].directory`, with `formats` /
   `min_format`+`max_format` covering the newer versions) and keep the older
   form in the base.
4. Folder rename: the base pack keeps `functions/`; an overlay for format ≥ 48
   holds `function/` copies (or the reverse).
5. Verify: `emulator_matrix(path, declared=true, boundaries=true)` runs the
   first release of every pack format in the range.
