---
name: minecode-mcp
description: How to use the MineCode MCP server's tools for Minecraft Java datapack and resource pack work — which tool answers which question, the order to call them in, and which sources to trust for which version. Use whenever the minecode MCP tools are available and the task touches a datapack, mcfunction, pack.mcmeta, loot table, predicate, recipe, advancement, item components or text components.
---

# Using the MineCode MCP server

MineCode exists because **your memory of Minecraft syntax is probably wrong
for the target version**. Datapack syntax broke in 1.20.5 (item components),
1.21 (folder names), 1.21.2 (attribute ids), 1.21.4 (custom_model_data),
1.21.5 (text components as SNBT, `click_event`/`hover_event`) and keeps moving.
Wrong syntax feels exactly as certain as right syntax. The tools are the
authority; recall is a hypothesis to check.

## The one rule

**Know the target version before writing anything.** Every other tool takes
it. Get it from `minecraft_start_session` (or `detect_pack_version`). If there
is no `pack.mcmeta`, ask the user — never assume the latest release.

## Call order

```text
minecraft_start_session(workspace_path)        # version + breaking changes that apply
  └─ get_technical_changes(to_version, topic)  # before writing any JSON / components / text
       └─ look up, don't recall:
            get_command_usage(version, command)        # command grammar
            spyglass_get_registries(version, registry, search)   # does this id exist?
            spyglass_get_block_states(version, block_id)
            spyglass_search_mcdoc_symbols(query) → spyglass_get_mcdoc_symbol(symbol)  # JSON/NBT fields
            misode_get_presets → misode_get_preset_data  # real vanilla file to copy the shape of
       └─ verify before saving:
            validate_command(command, version)         # every command line
            check_version_syntax(content, version, kind)   # every command and JSON file
            check_pack_structure(path)                 # folder names (1.21+)
       └─ run it (if the emulator tools are present):
            emulator_check / emulator_run / emulator_test / emulator_matrix
```

## Which tool answers which question

| question | tool | notes |
| --- | --- | --- |
| What version is this pack? | `minecraft_start_session`, `detect_pack_version` | reads `pack.mcmeta`, reports format range and overlays |
| pack_format ↔ version | `pack_format_to_version`, `version_to_pack_format` | data and resource formats are numbered separately: pass `kind` |
| What changed between X and Y? | `get_technical_changes` | curated traps first, then the full changelog. The changelog wins on disagreement |
| Exact syntax of a command | `get_command_usage` | from the game's Brigadier grammar, per version |
| Is this command valid? | `validate_command` | failing token + what was expected |
| Does this id exist? | `spyglass_get_registries` | always pass `search`; registries have thousands of entries |
| Which fields does this JSON/NBT/component take? | `spyglass_search_mcdoc_symbols` → `spyglass_get_mcdoc_symbol` | mcdoc is the authority on shapes |
| Show me a real one | `misode_get_preset_data` | a vanilla file of that exact version — correct by construction |
| Known trap in my text? | `check_version_syntax` | pre-filter over a curated table; clean ≠ valid |
| Folder layout right? | `check_pack_structure` | the 1.21 rename fails **silently** |
| How does a mechanic work? | `search_wiki`, `get_wiki_page` | **latest version only** — never for syntax/ids on older targets |
| Is it a Mojang bug? | `search_mojira` | filters by project, not version; read each issue's affected versions |
| What did the game log? | `get_logs(filter="errors")` | default launcher, Prism, TLauncher |
| Does it actually work? | `emulator_*` | see the `datapack-emulator` skill |
| What does it really cost / why the lag? | `emulator_server_profile` | reads a `/perf start` report from the user's game or server |

## Source reliability

1. `spyglass_*`, `get_command_usage`, `validate_command` — version-exact, authoritative.
2. `misode_*` — real vanilla data per version; best shape reference.
3. `get_technical_changes` — what changed; check before any version-sensitive file.
4. `emulator_*` — what a server of that version would do with the whole pack (a model, not the game; see its limits).
5. Wiki tools — current release only. Fine for concepts, wrong for old-version syntax.

## Version strings

Tools accept `"1.21.4"`, `"latest"`, or a line such as `"1.21"` (resolves to
the newest 1.21.x for Spyglass). Responses report what the version resolved
to — read it, and say so if it differs from what you meant.

## Response shape

Every tool returns JSON with `success`. On `success: false` read `error` and
any `hint` / `expected_schema` and retry with corrected arguments; do not fall
back to recall. Lists are capped and say `truncated: true` with the full
`count` — narrow with `search` rather than assuming the list is complete.

## Guides from the server

`get_minecode_guide(topic)` returns any of these skills as text (for clients
without skill support). Topics: `minecode-mcp`, `minecraft-feature-workflow`,
`minecraft-diagnose`, `minecraft-recurring-issues`,
`minecraft-version-differences`, `datapack-emulator`.

## Anti-patterns

- Writing `give @s diamond_sword{...}` because it "looks right" — braces NBT is a parse error from 1.20.5.
- Using the wiki for an older target's syntax.
- Treating a clean `check_version_syntax` as proof of validity — follow with `validate_command` and, for whole packs, the emulator.
- Calling `spyglass_get_registries` without `search` and drowning in ids.
- Guessing the version because `pack.mcmeta` was not found — ask.
