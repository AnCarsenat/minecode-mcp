# What changed

Implementation of the review in [IMPROVEMENTS.md](IMPROVEMENTS.md). That file holds the reasoning; this one holds the summary.

Tool count went 19 → 30, but the count is not the point — the point is that the two root causes of version-wrong output are fixed.

---

## The two root causes

### 1. The assistant preprompt was dead code

`server.py` loaded `assistant_preprompt.txt` into `server.default_preprompt` and defined `get_preprompt_messages()`. **Nothing called either.** Every piece of guidance in that file — "get the pack_format first", "target the right version", "the wiki only has the latest version" — never reached the model.

MCP servers cannot inject a system prompt; there is no such mechanism in the protocol. The server now uses all three channels that do exist:

- **Prompt** `minecraft_datapack_session` — user-invoked, appears as a slash command
- **Resources** `minecode://preprompt` and `minecode://migrations` — client-attachable
- **Tool** `minecraft_start_session` — **the one that matters.** Agents call tools autonomously; they do not autonomously invoke prompts.

`minecraft_start_session` reads `pack.mcmeta`, resolves the target version, and returns the applicable breaking changes plus the workflow to follow.

### 2. The version-drift fix was already written and never wired up

`misode.py` contained `list_changelog_releases()`, `list_changelogs()`, `get_changelog()`, and `parse_changelog()` — hitting [misode/technical-changes](https://github.com/misode/technical-changes), the community-maintained per-version technical changelog. Exactly the record of "items became components", "text component format changed".

**None of the four was registered as a tool.** Not in `TOOLS`, not in the dispatcher, not in the README. The best answer to the version problem was sitting in the repo, unreachable.

Now exposed as `get_technical_changes(from_version, to_version, topic)`.

Fixing this surfaced a bug in the range logic: most changelog entries are snapshots (`24w14a`, `1.21.2-pre1`) whose IDs cannot be ordered against release numbers. Comparing them directly placed every snapshot below version 1.0, and the function returned **zero results for every query**. Now filtered by the containing release directory instead. Verified: `1.20.4 → 1.20.5` returns 40 entries across 7 snapshots, correctly including the components rewrite.

---

## New tools (11)

| Tool | Why |
|------|-----|
| `minecraft_start_session` | The delivery channel for methodology + version detection |
| `get_technical_changes` | The version-drift fix |
| `check_version_syntax` | Scan output against known migrations before saving |
| `check_pack_structure` | Catches the silent 1.21 folder-rename failure |
| `detect_pack_version` | Reads `pack.mcmeta`; the preprompt asked for this with no tool to do it |
| `pack_format_to_version` | Reverse lookup, derived from live Spyglass data |
| `version_to_pack_format` | Forward lookup for writing `pack.mcmeta` |
| `list_technical_change_versions` | Changelog coverage |
| `get_command_usage` | Brigadier trees rendered as readable syntax |
| `validate_command` | Parse a command against the real grammar |
| `cache_status` | Cache maintenance |

`spyglass_get_mcdoc_symbols` (unfiltered megabyte dump) was replaced by `spyglass_search_mcdoc_symbols` + `spyglass_get_mcdoc_symbol` (path search, then one pruned definition).

`get_wiki_page` and `get_wiki_page_content` merged into one tool with a `full` flag — two tools taking identical input and differing only in verbosity is a decision the agent can get wrong.

`get_wiki_command_info` renamed to `get_wiki_command_explanation`. The old name implied authority over command syntax, competing with `spyglass_get_commands` and losing.

---

## Version knowledge: how it's structured

You asked whether a big hand-written skillset covering every version would work. It wouldn't — it'd be stale on day one, impossible to keep current against Minecraft's snapshot cadence, and too large for context. So the knowledge is split:

**Curated layer** — `minecode/knowledge/migrations.json`, 16 entries. Only the migrations where a model's training data actively fights the correct answer. Concrete before/after code pairs, not prose (models pattern-match on code shape far better than on paragraphs). Each entry carries regex detection rules and a `verify_with` field naming the tool that confirms it. Offline and instant.

**Live layer** — `get_technical_changes` queries misode/technical-changes, which is exhaustive and maintained by people tracking every snapshot.

The curated layer is deliberately small and explicitly not an authority. `check_syntax` returns a `caveat` field stating that a clean result means "no known trap matched", not "this is valid".

Covered: item NBT → components (1.20.5), folder singularization (1.21), `set_nbt` → `set_components`, recipe `result.item` → `result.id`, attribute prefix removal (1.21.2), attribute modifier field renames, enchantments component reshape (1.21.5), `custom_model_data` object (1.21.4), text component strictness (1.21.5), item predicate components, `supported_formats`, enchantment datapack registry, food/consumable split (1.21.2), loot table `type`, function macros, namespace requirements.

---

## Correctness and robustness

**Error shape.** Failures returned a bare `f"Error: {e}"` string while successes returned JSON. An agent parsing the output hit `JSONDecodeError` and typically abandoned the tool. All responses are JSON now, with `success`, `tool`, `error`, and `error_type`.

**Version resolution.** Ten tools took a free-form `version` string with no validation. `"1.21"` when Spyglass wanted `"1.21.1"` produced an opaque `404 Client Error`. Every version-taking tool now resolves through `packmeta.resolve_version` — accepts `latest`, exact IDs, and partials, and returns `did_you_mean` candidates on a miss. Agents recover from suggestions; they do not recover from 404s.

**Dispatch.** The 19-branch `if/elif` chain is replaced by a `HANDLERS` dict with an import-time assertion that `{t.name for t in TOOLS} == set(HANDLERS)`. This is the guard that would have caught the orphaned changelog functions. Backed by tests that also check every schema parameter is accepted by its handler's signature.

**Blocking event loop.** `call_tool` was `async` but every handler called `requests.get()` synchronously, stalling the whole server on a slow upstream. Now wrapped in `asyncio.to_thread`.

**Caching.** There was none — an agent refetched the same multi-megabyte registry five or six times per session, slowly enough that agents time out and abandon the tool. Disk cache added: version-pinned data cached permanently (immutable by nature), wiki 24h, Mojira 1h. `MINECODE_NO_CACHE=1` and `MINECODE_CACHE_DIR` to override.

**Silent scraper failure.** When mojira.dev's HTML changed, `table.find()` returned `None` and the scraper returned `[]` — reported as "no bugs found", a confident wrong answer. Now raises `ScraperStructureError`. An empty `tbody` (genuine no-results) still returns `[]`.

**Bare `except:`** at `minecraftwiki.py:252` caught `KeyboardInterrupt` and `SystemExit`, making the server unkillable mid-request. Now `except Exception` with logging.

**Missing timeout** on Spyglass `_make_request` (the wiki already had one — see the retraction in IMPROVEMENTS.md §4.4).

**`get_latest_release` / `get_latest_snapshot`** were called in `spyglass.py`'s `__main__` block but never defined — a guaranteed `NameError`. Implemented.

**Wiki warnings.** All six wiki tools now lead their description with `LATEST VERSION ONLY` and name the version-exact alternative, and every wiki response carries a `version_warning` field. Descriptions get skimmed; payload fields get read. A test enforces the warning's presence.

---

## Upstream finding

**Spyglass `/vanilla-mcdoc/symbols` returns HTTP 502** while the rest of the API is healthy — confirmed with curl during this work. `spyglass_get_mcdoc_symbols` has been calling a dead endpoint, which is likely a real part of why the Spyglass approach felt unreliable.

Not fixable from here, but it now degrades usefully: the handler returns `upstream_outage: true` plus named alternatives (`misode_get_preset_data` for real vanilla JSON, `get_technical_changes` for field changes) and an explicit instruction *not* to fall back on remembered field names — which is exactly the failure this server exists to prevent.

---

## Packaging and publishing

**`mcp>=1.25.0` was unsafe.** mcp 2.0.0 removed the low-level decorator API this server is built on; installing it raises `AttributeError` at import. Now pinned `>=1.25.0,<2`. Migrating to the 2.x `MCPServer` API is separate future work.

**Trusted Publishing.** `publish.yml` rewritten to use OIDC — no `PYPI_API_TOKEN` secret to create, paste, rotate, or leak. The workflow verifies the tag matches `pyproject.toml`, runs tests, builds, checks metadata, and **verifies the preprompt/config/migration files are actually inside the wheel** before publishing. That last check matters: those are data files, and if hatch drops them the server still starts but silently loses its version knowledge — invisible in an editable install, broken for every pip user. Setup walkthrough is in the README.

**`.mcp.json`** used `${command:python.interpreterPath}`, a VS Code variable. Any other client tried to execute a program by that literal name. Now a portable config; the VS Code-specific one stays in `.vscode/`.

**Placeholder author email** `antoine.carsenat@example.com` removed.

**Security check:** `pip_token.txt` was never committed (`git log --all --full-history` returns nothing) and is in `.gitignore:30`. No action needed.

---

## Bugs found by self-review and live testing

Everything above was written first, then reviewed adversarially and tested against a real Minecraft install (Prism, 26.2 Fabric) with a real 4128-command datapack. Five defects surfaced, all now fixed with regression tests.

**`validate_command` rejected valid `execute` chains.** The biggest one. Spyglass serializes Brigadier's two redirect forms differently:

- `execute at <targets>` carries `"redirect": ["execute"]` — an explicit path
- `execute run` carries **nothing** — a bare `{"type": "literal"}` with no children, no executable flag, no redirect field

Handling only the first form broke every `execute run ...`. Then a fix that treated *all* childless nodes as root redirects broke every `execute at ... run ...` instead — 66% of the test pack. Both forms are now handled explicitly.

**`validate_command` needed backtracking.** In `/tp @s ~ ~ ~`, the token `@s` matches both `<destination>` and `<targets>`. Committing to the first match left `~ ~ ~` unparseable. Real Brigadier tries the alternatives; the validator now does too, with step and depth budgets so pathological input can't hang it.

Measured on the real pack: **4128 commands, 0 false positives, 9.1s.** Verified in the other direction too — 13/13 deliberately malformed commands still rejected. A validator that accepts everything is worse than none.

**`get_logs` filtering did nothing.** It read `result["content"]`, a key the log reader never returns — every launcher puts content in a `logs` list, one entry per instance. The filter silently no-opped for all of them. Found by running it against the live Prism install, which surfaced two instances (`26.2 Fabric`, `1.8.9`). Now filters per-instance: 400 lines → 45 error lines.

**`pack.mcmeta` `min_format`/`max_format` was ignored.** The real datapack declares `"min_format": 88, "max_format": 102` — a flat form alongside the `supported_formats` object the parser already handled. Ignoring it reported a multi-version pack as single-version, so the agent would write syntax valid only at the low end of a range it didn't know existed. Now read, with an inverted-range guard.

**Cache couldn't distinguish a cached `None` from a miss.** `get()` returned `None` for both, so an upstream returning JSON `null` would refetch forever while appearing to work. Now uses a `MISS` sentinel.

**`_truncate()` returned every list twice** — once under `items`, once under the renamed key — doubling the payload of every registry and preset response.

---

## Tests

219 offline + 14 network. None previously existed.

- **219 offline** (0.4s) — registry consistency, schema wellformedness, handler signature matching, version comparison, migration detection, Brigadier rendering/validation/redirects/backtracking, pack.mcmeta forms, cache semantics, log filtering
- **14 network-marked**, excluded by default — shape assertions against live APIs, run nightly

The false-positive tests carry as much weight as the detection tests: a checker that flags correct modern syntax trains the agent to ignore it, which is worse than no checker. There are explicit tests that correct 1.21.4 component syntax produces zero issues, and that 1.20.4-era NBT is *not* flagged when the target is 1.20.4.

CI runs offline tests on 3.10/3.11/3.12 per push; live tests nightly only, since they hit volunteer-run services.

---

## Verified working

Against live APIs during implementation:

```
detect_pack_version(example/crystal_dimension)  -> pack_format 94 -> 1.21.11
get_command_usage("1.21.4", "give")             -> /give <targets> <item> [<count>]
version_to_pack_format("1.21.4")                -> data 61, resource 46
get_technical_changes("1.20.4" -> "1.20.5")     -> 40 entries / 7 snapshots
validate_command(legacy NBT give, "1.21.4")     -> parses, flagged by migration table
resolve_version("banana")                       -> did_you_mean [...]
```

Against a real Prism install (26.2 Fabric) and a real 4128-command datapack:

```
get_logs(filter="errors")            -> 2 instances found, 400 lines -> 45 error lines
minecraft_start_session(real pack)   -> format range 88-102, multi_version, warned
check_pack_structure(real pack)      -> 714 files, 0 structure issues
validate_command x 4128 real commands-> 0 false positives, 9.1s
check_version_syntax x all JSON      -> 0 issues (pack is correctly modern)
13 deliberately-malformed commands   -> 13 rejected
```

The `validate_command` result is worth noting: legacy NBT *parses* cleanly against the Brigadier tree, because the item argument is a single token. Grammar validation alone cannot catch it. The curated migration layer does. That's why both run.

---

## Not done

- **mcp 2.x support** — needs a rewrite against the new `MCPServer` API. Pinned `<2` for now.
- **Full JSON schema validation** (`validate_datapack_file`) — needs an mcdoc type-checker, and the mcdoc endpoint is currently 502-ing anyway. `misode_get_preset_data` is the practical substitute.
- **Mods and plugins** — the README claims "datapacks, mods, plugins" but every tool is datapack/resource-pack only. Either narrow the pitch or add Fabric/NeoForge/Paper support; narrowing is the better call until the datapack story is airtight.
- **Argument sub-grammars** in `validate_command` — parsers like `minecraft:item_stack` accept any single token. Catches structural errors, not malformed component blocks.
