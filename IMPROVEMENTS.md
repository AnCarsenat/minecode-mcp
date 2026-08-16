# MineCode MCP — Improvement Plan

Review date: 2026-08-16 · Reviewed at commit `0de0808` · Version `0.1.9`

> **Status: implemented.** Everything in this document has been applied except
> where noted below. See `CHANGES.md` for what shipped. This file is kept as
> the reasoning record — the *why* behind each change.
>
> **Two corrections to the original review, found during implementation:**
>
> 1. **§4.4 was wrong.** `minecraftwiki._make_request` already passed
>    `timeout=15`. The sub-agent that reported a missing timeout was mistaken;
>    verification against the file disproved it. No timeout bug existed. All
>    three HTTP scrapers already had timeouts.
> 2. **A worse problem was found instead.** Spyglass's
>    `/vanilla-mcdoc/symbols` endpoint returns **HTTP 502** while the rest of
>    the API is healthy — confirmed directly with curl. `spyglass_get_mcdoc_symbols`
>    has therefore been calling a dead endpoint. This is likely a significant
>    part of why "the Spyglass approach doesn't work very well." Handled with a
>    graceful degradation path that names working alternatives (§1.2).
> 3. **`mcp>=1.25.0` was unsafe.** mcp 2.0.0 removed the low-level decorator
>    API (`@server.list_tools`, `@server.call_tool`) this server is built on;
>    installing it raises `AttributeError` at import. Now pinned `<2`.

This document covers three things you asked about:

1. Tools that confuse agents, and tools that are missing
2. The version-drift problem (components vs. JSON, text component changes, etc.)
3. PyPI publishing — why it hurts and how to fix it with GitHub Actions

---

## Part 0 — Two bugs that undercut everything else

Before any new features, fix these. They are the reason the current approach "doesn't work very well."

### 0.1 The assistant pre-prompt is dead code

`minecode/server.py:37-92` loads `assistant_preprompt.txt` into `server.default_preprompt` and defines
`server.get_preprompt_messages()`. **Nothing ever calls it.** Grep confirms zero call sites.

This matters a lot. MCP servers **cannot** inject a system prompt into the client. There is no such
mechanism in the protocol. So the README feature "🧠 Assistant Pre-prompts — configurable system
prompts for better AI accuracy" currently does nothing at all. Every piece of guidance you wrote in
that file — "get the pack_format first", "target the right versions", "the wiki only has the latest
version" — never reaches the model.

**The protocol does give you two legitimate delivery channels, and you implement neither:**

| Channel | Handler | Behavior |
|---|---|---|
| **Prompts** | `@server.list_prompts()` / `@server.get_prompt()` | User-invoked. Appears in Claude Desktop as a slash command / in Copilot's prompt picker. |
| **Resources** | `@server.list_resources()` / `@server.read_resource()` | Client can attach as context. |

Implement both. Minimal version:

```python
from mcp.types import Prompt, PromptMessage, GetPromptResult, Resource

@server.list_prompts()
async def list_prompts():
    return [
        Prompt(
            name="datapack_session",
            description="Load MineCode's datapack development methodology and version-safety rules.",
            arguments=[],
        )
    ]

@server.get_prompt()
async def get_prompt(name: str, arguments: dict | None = None) -> GetPromptResult:
    if name != "datapack_session":
        raise ValueError(f"Unknown prompt: {name}")
    return GetPromptResult(
        description="MineCode datapack session bootstrap",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=server.default_preprompt),
            )
        ],
    )
```

**Additionally**, add a third and far more reliable channel: a tool. Agents call tools
autonomously; they do not autonomously invoke prompts.

```python
Tool(
    name="minecraft_start_session",
    description=(
        "CALL THIS FIRST before writing or editing any Minecraft datapack, resource pack, "
        "mod, or plugin file. Returns the target Minecraft version detected from the "
        "workspace pack.mcmeta, the correct syntax conventions for that version, and the "
        "list of breaking changes you must account for. Skipping this step causes "
        "version-mismatched output."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "workspace_path": {"type": "string", "description": "Absolute path to the datapack root"},
        },
        "required": [],
    },
)
```

That single tool is worth more than the other 19 combined, because it is the only one an agent
will reliably reach for unprompted.

### 0.2 Errors return the wrong shape

`server.py:946-947`:

```python
except Exception as e:
    return [TextContent(type="text", text=f"Error: {str(e)}")]
```

Every successful call returns JSON. Every failure returns a bare string. An agent that parses your
output gets a `JSONDecodeError` and typically gives up on the tool entirely rather than retrying.
Return `json.dumps({"success": False, "error": str(e), "tool": name})` and set `isError=True` on
the result. This is a five-line fix with an outsized effect on tool reliability.

---

## Part 1 — Tools that confuse agents

### 1.1 The wiki tools are actively harmful (highest severity)

`search_wiki`, `get_wiki_page`, `get_wiki_page_content`, `get_wiki_commands`,
`get_wiki_command_info`, `get_wiki_category` — six of your nineteen tools — all hit
`minecraft.wiki`, which documents **only the latest version**. Their descriptions contain no
version warning whatsoever.

The failure mode is exact and predictable: the agent asks for `/give` syntax, the wiki returns
1.21.x component syntax, the agent writes component syntax into a 1.20.4 datapack, and the pack
breaks. The agent has no way to know it was given latest-version data, because you never told it.

There is a second, subtler problem. `get_wiki_command_info` and `spyglass_get_commands` both claim
to answer "what is the syntax for command X". They disagree. Spyglass is version-accurate and
authoritative (it is Brigadier's own tree); the wiki is prose about the latest version. When two
tools answer the same question and one is wrong, the agent picks arbitrarily.

**Fixes, in order of preference:**

**(a) Rewrite every wiki tool description to lead with the limitation.** Example:

```
"⚠️ LATEST VERSION ONLY. minecraft.wiki does not document historical versions. Use this ONLY
for conceptual explanation ('how does a raid work?'), NEVER for syntax, IDs, NBT structure, or
JSON schema. For anything version-sensitive use spyglass_get_commands or misode_get_preset_data
with an explicit version. If your target version is not the current release, treat all syntax
in this result as WRONG until verified against Spyglass."
```

**(b) Inject a runtime warning into every wiki response payload.** Descriptions get skimmed;
payload fields get read. Add to every wiki handler's return dict:

```python
"version_warning": (
    f"Content reflects Minecraft {latest_release} only. "
    f"Your target version may differ — verify syntax with spyglass_get_commands."
),
```

**(c) Demote `get_wiki_command_info`.** Rename to `get_wiki_command_explanation` and rewrite its
description to say it returns prose, not syntax, and that `spyglass_get_commands` is the
authoritative source. Naming two tools "command info" and "commands" guarantees confusion.

**(d) Merge `get_wiki_page` and `get_wiki_page_content`.** Two tools, same input, differing only in
verbosity. Make it one tool with a `full: boolean` parameter. Every redundant tool costs the agent
a decision and adds a chance of a wrong choice.

### 1.2 `spyglass_get_mcdoc_symbols` is a context bomb

`server.py:415-419` — zero parameters, zero filtering. It fetches the **entire** vanilla mcdoc
symbol table from `/vanilla-mcdoc/symbols` and dumps it. That response is on the order of
megabytes. It will either blow the agent's context window or be truncated into garbage.

There is a second problem: the description says "useful for understanding NBT/datapack data
structures" without saying what mcdoc *is* or when to prefer it over `spyglass_get_registries`.
An agent cannot choose a tool it does not understand.

**Fix:** add required filtering, and never return the whole table.

```python
Tool(
    name="spyglass_get_mcdoc_symbols",
    description=(
        "Look up the exact field-level schema of a Minecraft data structure (NBT, item "
        "components, text components, predicates) as defined in mcdoc — the machine-readable "
        "type definitions used by the Spyglass language server. This is the authoritative "
        "answer to 'what fields does X accept and what are their types'. "
        "Requires a symbol path, e.g. 'java::world::item::ItemStack', "
        "'java::data::loot::LootTable', 'java::util::text::Text'. "
        "Use spyglass_search_mcdoc_symbols first if you do not know the path."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Fully-qualified mcdoc symbol path"},
            "depth": {"type": "integer", "description": "How many levels of nested types to expand (default 2, max 4)"},
        },
        "required": ["symbol"],
    },
)
```

Add a companion `spyglass_search_mcdoc_symbols(query, limit)` that returns matching symbol paths
only — no bodies. Fetch the full table once, cache it, serve filtered slices. Never ship the
whole thing across the wire.

### 1.3 `version` is a free-form string with no validation

Ten tools take `"version": {"type": "string", "description": "Minecraft version"}`. Nothing
validates it. Agents will confidently pass `"1.21"` when Spyglass wants `"1.21.1"`, or `"latest"`,
or `"1.20"`, and get an opaque HTTP 404 that surfaces as `Error: 404 Client Error`.

**Fixes:**

- Normalize server-side. Fetch the version list once, cache it, fuzzy-match the input. `"1.21"` →
  `"1.21"` if it exists, else nearest `1.21.x`. Return `{"resolved_version": "1.21.1",
  "requested_version": "1.21"}` so the agent sees what happened.
- On a miss, return the nearest valid candidates instead of a 404:
  `{"success": false, "error": "Unknown version '1.21'", "did_you_mean": ["1.21.1", "1.21.3"]}`.
  Agents recover from this; they do not recover from `404 Client Error`.
- Put concrete valid examples in every description: `"e.g. '1.21.4', '1.20.4', '25w14a'"`. Vague
  descriptions produce vague inputs.

### 1.4 Every request is uncached

Confirmed across all five scrapers: no `lru_cache`, no memoization, no HTTP caching, nothing. An
agent doing real work calls `spyglass_get_registries("1.21.4", "item")` five or six times in one
session, refetching an identical multi-megabyte payload each time.

This is slow enough that agents time out and abandon the tool — which looks to you like "the tool
doesn't work" rather than "the tool is slow." It also hammers Spyglass, misode's GitHub raw
endpoints, and minecraft.wiki, all of which are volunteer-funded and will eventually rate-limit
you.

**Fix:** disk cache keyed by URL, in `platformdirs.user_cache_dir("minecode-mcp")`. Version-pinned
data (Spyglass, misode) is immutable for released versions — cache it forever. Wiki and Mojira
change; give those a 24h and 1h TTL respectively. Ship a `clear_cache` maintenance path.

### 1.5 Mojira is unversioned and fragile

`mojira.py` scrapes HTML from `mojira.dev` with BeautifulSoup. When the markup changes, `table.find()`
returns `None`, the scraper returns `[]`, and the agent is told "no bugs found" — which reads as a
positive result. Silent wrong answers are worse than errors.

Also: it filters by *project* (MC / MCPE / …), never by Minecraft version. "Search Mojira for
elytra bugs" returns issues from 2016 alongside current ones, with no signal about which apply.

**Fixes:** add a structural sanity check (if the results table is absent, raise rather than return
`[]`); add an `affected_version` filter if the site supports it; state in the description that
results span all versions and the agent must check `affects_version` on each issue.

### 1.6 Minor confusions

| Issue | Location | Fix |
|---|---|---|
| `misode_get_generators` returns generator *URLs* for humans, but its description doesn't say the agent should hand them to the user rather than fetch them | `server.py:281-295` | Say "returns web UI links intended to be shown to the human user, not fetched" |
| `misode_get_loot_tables` / `misode_get_recipes` overlap heavily with `misode_get_presets` | `server.py:340-385` | Keep them (they're better ergonomics) but cross-reference in descriptions |
| `get_logs` doesn't say it reads from the **local machine** | `server.py:420-446` | Say so — agents on remote/containerized setups will call it and get confusing empties |
| `get_logs` has no error filtering | `minecraft_logs.py` | Add `filter: "errors" \| "warnings" \| "all"` and a `since_timestamp` — dumping 1000 raw lines wastes most of the context on JVM boilerplate |
| MultiMC, ATLauncher, Modrinth App, CurseForge, Fabric/Quilt server logs unsupported | `minecraft_logs.py:62-109` | Add paths; MultiMC and Modrinth App are widely used |

---

## Part 2 — The version problem (the one you actually care about)

### 2.1 You already built the fix and never wired it up

`minecode/scrappers/misode.py` contains, at lines 328-417:

- `list_changelog_releases()` — every release with a technical changelog
- `list_changelogs(release)` — every version in a release
- `get_changelog(release, version_id)` — the markdown body
- `parse_changelog(content)` — already parses it into structured data

These hit `misode/technical-changes`, which is a community-maintained, per-version technical
changelog. It is precisely the record of "items moved to components", "text component JSON
changed", "`minecraft:` prefix now required here", "this field was renamed".

**None of these four functions is exposed as an MCP tool.** They are not in `TOOLS`, not in the
`call_tool` dispatcher, not in the README. The single best answer to your problem is already sitting
in your repo, unreachable.

**This is the highest-value change in this entire document.** Ship these tools:

```python
Tool(
    name="get_technical_changes",
    description=(
        "CRITICAL FOR VERSION CORRECTNESS. Returns the technical changelog — every breaking "
        "change to datapack/resource pack format — between two Minecraft versions. Covers "
        "renamed fields, moved registries, changed JSON schemas, and format migrations such "
        "as the NBT-to-components change for items (1.20.5) and the text component format "
        "changes. "
        "CALL THIS whenever your knowledge of Minecraft syntax may predate the target version, "
        "and ALWAYS before writing item NBT, text components, loot tables, or predicates. "
        "Your training data is older than the current game; this tool is how you correct for that."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "from_version": {"type": "string", "description": "Starting version, e.g. '1.20.4'"},
            "to_version": {"type": "string", "description": "Target version, e.g. '1.21.4'"},
            "topic": {
                "type": "string",
                "description": "Optional filter, e.g. 'components', 'text', 'loot', 'recipe', 'predicate'",
            },
        },
        "required": ["to_version"],
    },
)
```

Implementation: enumerate versions between the two, fetch each changelog, parse, concatenate,
filter by topic. Cache aggressively — released changelogs never change.

Also expose `list_technical_change_versions()` so the agent can discover coverage.

### 2.2 A hand-written skillset is the wrong shape — and unnecessary

You floated writing a big document covering every version's changes. Don't. Three reasons:

1. **misode/technical-changes already is that document**, maintained by people who track every
   snapshot. You will never keep pace manually.
2. **A static document goes stale the day it's written.** Every new snapshot adds drift you must
   chase.
3. **Size.** All versions' changes is far too large to inject as context. It has to be queryable,
   not preloaded — which means a tool, which is what 2.1 gives you.

Where a hand-written layer *does* earn its keep is narrow and specific: the handful of migrations
that agents get wrong constantly, written as **before/after code pairs**. Not prose. Not an
exhaustive list. Perhaps eight to twelve entries:

```json
{
  "id": "item-nbt-to-components",
  "changed_in": "1.20.5",
  "affects": ["give", "item", "loot_table", "recipe", "container_contents"],
  "before": "/give @s diamond_sword{Enchantments:[{id:\"minecraft:sharpness\",lvl:5}]} 1",
  "after":  "/give @s diamond_sword[enchantments={levels:{\"minecraft:sharpness\":5}}] 1",
  "note": "NBT braces {} became component brackets []. The old syntax is a hard parse error in 1.20.5+, not a warning.",
  "detect": "\\{[A-Za-z]+:",
  "authority": "spyglass_get_mcdoc_symbols('java::world::item::ItemStack')"
}
```

Concrete pairs beat prose descriptions for LLM correction by a wide margin — the model pattern-matches
on the shape of the code rather than reasoning about a paragraph. Ship these as
`minecode/knowledge/migrations.json` and expose:

```python
Tool(
    name="check_version_syntax",
    description=(
        "Check a snippet of Minecraft command, JSON, or NBT against known breaking changes for "
        "a target version. Returns any deprecated or removed syntax found, with the correct "
        "replacement. Run this on every command or JSON file you write before saving it."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "content": {"type": "string"},
            "version": {"type": "string"},
            "kind": {"type": "string", "enum": ["command", "json", "nbt", "mcfunction"]},
        },
        "required": ["content", "version"],
    },
)
```

Start with these known-bad migrations, roughly in order of how often agents get them wrong:

| Change | Version | What agents write instead |
|---|---|---|
| Item NBT → components | 1.20.5 | `{Enchantments:[...]}` instead of `[enchantments={...}]` |
| Text component JSON stricter / SNBT in commands | 1.21.5 | Old lenient JSON forms |
| `/give` count position | 1.20.5 | Count before components |
| `minecraft:` namespace now required in more places | various | Bare IDs |
| Loot table `entries[].functions` schema | 1.20.5 | Old `set_nbt` instead of `set_components` |
| `predicate` item matching | 1.20.5 | `nbt` field instead of `components` / `predicates` |
| `/execute store` result types | various | Wrong scale/type args |
| Attribute IDs renamed (`generic.max_health` → `max_health`) | 1.21.2 | Old `generic.` prefix |
| Recipe `result` now an object with `count` | 1.20.5 | Bare string result |
| `pack.mcmeta` `supported_formats` | 1.20.2 | Single int `pack_format` only |

Verify each against `misode/technical-changes` before shipping — do not trust this table or any
LLM-generated version of it. It is a starting list, not a source.

### 2.3 Why Spyglass alone hasn't solved it

Spyglass is the right data source. Three things stop it from working:

1. **The agent doesn't know it should call it.** Nothing tells the model that its training data is
   stale. Absent that signal, a model that "knows" `/give` syntax simply writes it. The preprompt
   that would have said so is dead code (§0.1). Fix the delivery channel and rewrite the
   descriptions to state the reason explicitly — "your training data predates this version" is a
   sentence models act on.

2. **Spyglass returns raw Brigadier trees.** `spyglass_get_commands("1.21.4", "give")` returns a
   deeply nested `{"type": "argument", "parser": "minecraft:item_stack", "children": {...}}`
   structure. Correct, but the agent must mentally compile it into a syntax string, and that
   compilation is exactly where errors creep back in. **Render it.** Walk the tree server-side and
   emit human-readable usage lines, the way the game's own `/help` does:

   ```
   /give <targets> <item>[<components>] [<count>]
     <targets>  : entity selector
     <item>     : item_stack — namespaced item ID, optional [component=value,...]
     <count>    : integer 1..99
   ```

   Return both `usage` (rendered) and `tree` (raw). The agent will use `usage`, and the correctness
   comes from Spyglass either way. This is likely the second-highest-value change in this document.

3. **No feedback loop.** The agent writes a command and never learns whether it parses. §2.4 fixes
   that.

### 2.4 The missing tool: validation

Right now nothing verifies the agent's output. It writes, it saves, the user runs the pack, it
breaks, and the agent finds out through `get_logs` — if at all. That loop is far too slow, and it
runs at the user's expense.

A validation tool changes the economics entirely, because the agent can self-correct before the
user ever sees the output. Two levels:

**Level 1 — command syntax check against the Brigadier tree (pure Python, no dependencies):**

```python
Tool(
    name="validate_command",
    description=(
        "Parse a Minecraft command against the official Brigadier grammar for a specific version. "
        "Returns whether it parses, and if not, the exact character position and reason. "
        "Run this on EVERY command you write before saving it to an .mcfunction file."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "version": {"type": "string"},
        },
        "required": ["command", "version"],
    },
)
```

You already have the tree from `spyglass_get_commands`. Walking it to validate a literal/argument
sequence is a few hundred lines. It won't catch everything (argument parsers like `item_stack`
need their own sub-grammars) but it catches the structural errors that make up most failures.

**Level 2 — JSON schema validation against mcdoc:**

```python
Tool(
    name="validate_datapack_file",
    description=(
        "Validate a datapack JSON file (loot table, recipe, advancement, predicate, worldgen, "
        "item modifier) against the schema for a specific Minecraft version. Returns per-field "
        "errors. Run this on every JSON file you write."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The JSON content"},
            "file_type": {"type": "string", "description": "e.g. 'loot_table', 'recipe', 'advancement'"},
            "version": {"type": "string"},
        },
        "required": ["content", "file_type", "version"],
    },
)
```

Cheaper alternative if full mcdoc validation is too much work: fetch the closest vanilla preset via
`misode_get_preset_data` and structurally diff the agent's output against it — unknown keys, missing
required keys, type mismatches. Rough, but it catches the common failures at a fraction of the cost.

Consider also shelling out to `spyglass` CLI (`npx @spyglassmc/cli`) if it's installed, and
degrading gracefully when it isn't. That gives you real validation for free, at the price of an
optional Node dependency.

### 2.5 Workspace awareness

The preprompt instructs the agent to "get the pack_format (generally in /pack.mcmeta)" — but you
give it no tool to do that, so it must guess or use a generic file reader that may not be present.

```python
Tool(
    name="detect_pack_version",
    description=(
        "Read pack.mcmeta from the workspace and return the target Minecraft version(s), "
        "pack_format, supported_formats range, and pack type (data or resource). "
        "CALL THIS FIRST in any Minecraft project — every other tool needs the version."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to pack.mcmeta or the pack root. Defaults to CWD search."},
        },
        "required": [],
    },
)
```

Plus the reverse mapping, which agents get wrong constantly and which is trivially lookup-able:

```python
Tool(name="pack_format_to_version", ...)   # 61 -> ["1.21.4"]
Tool(name="version_to_pack_format", ...)   # "1.21.4" -> {"data": 61, "resource": 46}
```

Both derive from `spyglass_get_versions`, which already carries `data_pack_version` and
`resource_pack_version` (`spyglass.py:63-64`). You have the data; you just don't expose the lookup.

### 2.6 Priority order for Part 2

1. Expose the changelog tools (§2.1) — the data exists, the work is wiring
2. Fix preprompt delivery (§0.1) — nothing else lands without it
3. Render Brigadier trees as usage strings (§2.3.2)
4. `detect_pack_version` + pack_format mapping (§2.5)
5. `validate_command` (§2.4 level 1)
6. `check_version_syntax` with a small migration table (§2.2)
7. Wiki version warnings (§1.1)
8. `validate_datapack_file` (§2.4 level 2)

Items 1–4 are a weekend. They will do more for correctness than the other fifteen tools combined.

---

## Part 3 — PyPI publishing

### 3.1 What you have now

`.github/workflows/publish.yml` already builds and publishes on a `v*.*.*` tag push using
`TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}`. The structure is correct. The pain is that it
depends on a long-lived API token you must create, paste, and eventually rotate — and if you never
added the secret, the workflow fails at the last step with an auth error, which is likely what
you're hitting.

### 3.2 Use Trusted Publishing instead — no token at all

PyPI supports OIDC-based Trusted Publishing. GitHub Actions proves its identity to PyPI directly.
No secret to create, paste, rotate, or leak. This is strictly better and is the current
recommended approach.

**Step 1 — configure on PyPI (one time, in a browser):**

1. Log in at https://pypi.org
2. Go to your project → **Manage** → **Publishing** (or, for a brand-new project, the
   "Publishing" section under your account → "Pending publishers")
3. **Add a new pending publisher** with exactly these values:

   | Field | Value |
   |---|---|
   | PyPI Project Name | `minecode-mcp` |
   | Owner | `AnCarsenat` |
   | Repository name | `minecode-mcp` |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

   The workflow filename and environment name must match the workflow file exactly. This is the
   most common place people get it wrong.

**Step 2 — create the GitHub environment (one time):**

Repo → **Settings** → **Environments** → **New environment** → name it `pypi`.
Optionally add yourself as a required reviewer, which makes every publish require a manual
click — a good safety net when a tag push would otherwise publish immediately.

**Step 3 — replace `.github/workflows/publish.yml`:**

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - 'v*.*.*'
  workflow_dispatch: {}

jobs:
  build:
    name: Build distributions
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install build tooling
        run: python -m pip install --upgrade pip build

      - name: Verify tag matches pyproject version
        if: startsWith(github.ref, 'refs/tags/')
        run: |
          TAG="${GITHUB_REF#refs/tags/v}"
          PKG=$(python -c "import tomllib,pathlib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['version'])")
          if [ "$TAG" != "$PKG" ]; then
            echo "::error::Tag v$TAG does not match pyproject.toml version $PKG"
            exit 1
          fi

      - name: Build
        run: python -m build

      - name: Check metadata
        run: |
          python -m pip install twine
          python -m twine check dist/*

      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  publish:
    name: Publish to PyPI
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url: https://pypi.org/p/minecode-mcp
    permissions:
      id-token: write        # REQUIRED for trusted publishing
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/

      - name: Publish
        uses: pypa/gh-action-pypi-publish@release/v1
```

Note `permissions: id-token: write` — without it OIDC fails and you get an opaque 403. It must be
on the `publish` job, not at the workflow root.

**Step 4 — release:**

```bash
# bump version in pyproject.toml, e.g. 0.1.9 -> 0.2.0
git add pyproject.toml
git commit -m "Release 0.2.0"
git tag v0.2.0
git push origin main --tags
```

The workflow fires on the tag. If you added a required reviewer to the `pypi` environment, approve
it in the Actions tab. Done — no token anywhere.

### 3.3 Add TestPyPI first

Set up a second pending publisher on https://test.pypi.org identically, plus a `testpypi` GitHub
environment, and a job that runs on every push to `main`:

```yaml
  publish-test:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment:
      name: testpypi
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with: { name: dist, path: dist/ }
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          repository-url: https://test.pypi.org/legacy/
          skip-existing: true
```

This catches packaging errors before they reach real PyPI, where a version number is burned
permanently — you cannot re-upload `0.2.0` after a bad publish, only bump to `0.2.1`.

### 3.4 Retire `scripts/release.ps1`

Once Actions handles publishing, the PowerShell script is a liability: it's Windows-only, it wants
your token in `pip_token.txt` (which is one `.gitignore` slip from being committed), and it lets
you publish from a dirty working tree. Keep it for local *builds* if you like; strip the publish
path.

**Checked during this review: `pip_token.txt` was never committed** — `git log --all --full-history --
pip_token.txt` returns nothing, and it is listed in `.gitignore:30`. No action needed. Re-run that
command if you ever suspect otherwise; a token pushed to a public repo must be revoked on PyPI, and
rewriting history does not undo the exposure.

### 3.5 Packaging issues to fix while you're in there

| Issue | Location | Fix |
|---|---|---|
| Author email is a placeholder | `pyproject.toml:11` — `antoine.carsenat@example.com` | Real address, or drop the field |
| `example/` ships in the sdist but not the wheel | `pyproject.toml` sdist include | Fine, but decide deliberately — 20+ JSON files add weight for no runtime benefit |
| `preprompts/` and `config/` may not be included in the wheel | hatch wheel config | `packages = ["minecode"]` includes non-Python files under it, but **verify**: `python -m build && unzip -l dist/*.whl \| grep -E 'preprompt\|config'`. If missing, the preprompt silently fails for every pip-installed user — and you'd never see it locally |
| No lower bound on `mcp` beyond `>=1.25.0` | `pyproject.toml:26` | Consider `mcp>=1.25.0,<2` — MCP's API is still moving |
| No `CHANGELOG.md` | — | The README's "Changelog Highlights" has no versions or dates; make it a real file |

### 3.6 A note on `.mcp.json`

`.mcp.json:5` uses `"command": "${command:python.interpreterPath}"`. That is a **VS Code variable
substitution** — it only resolves inside VS Code. Any other MCP client tries to execute a program
literally named `${command:python.interpreterPath}` and fails with a confusing error. Either move
that file to `.vscode/` (where the convention is understood) or use a plain `python` / `minecode`
command at the repo root.

---

## Part 4 — Everything else

### 4.1 There are no tests

Zero test files. Every scraper depends on an external service whose response shape can change
without notice — and three of them (`mojira`, and parts of `minecraftwiki`) parse HTML, which
changes constantly. You will find out about breakage from a user bug report.

Minimum viable:

- `tests/test_schemas.py` — every `Tool` in `TOOLS` has a name, a description over N characters,
  a valid JSON Schema, and a matching branch in `call_tool`. Pure unit test, no network. This
  catches the "I added a tool and forgot the dispatcher" class of bug, which is exactly how the
  changelog functions ended up orphaned.
- `tests/test_live.py` — marked `@pytest.mark.network`, one call per scraper, asserting shape not
  content. Run nightly on a schedule, not on every PR.
- A GitHub Action that runs the offline tests on every push.

### 4.2 Structural notes on `server.py`

980 lines: tool schemas, handlers, and dispatch all in one file. The `call_tool` dispatcher is a
19-branch `if/elif` chain that must be kept manually in sync with `TOOLS` — and already isn't, in
the sense that four working scraper functions have no tool at all.

Replace the chain with a registry:

```python
HANDLERS = {
    "search_wiki": handle_search_wiki,
    "get_wiki_page": handle_get_wiki_page,
    # ...
}

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handler = HANDLERS.get(name)
    if handler is None:
        return _err(f"Unknown tool: {name}", name)
    try:
        result = await asyncio.to_thread(handler, **arguments)
        return [TextContent(type="text", text=json.dumps(result))]
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return [TextContent(type="text", text=json.dumps(
            {"success": False, "tool": name, "error": str(e)}))]
```

Then assert `set(HANDLERS) == {t.name for t in TOOLS}` at import time. That single assertion would
have caught the orphaned changelog functions.

### 4.3 Every handler blocks the event loop

`call_tool` is `async`, but every handler calls `requests.get()` synchronously. On a slow
minecraft.wiki response the entire server stalls — it cannot even respond to a ping. The
`asyncio.to_thread` wrapper above fixes it for free. Migrating to `httpx` with a shared async
client would be cleaner, but `to_thread` is a one-line change and solves the actual problem.

### 4.4 ~~No timeout on wiki requests~~ — RETRACTED, this was wrong

The original review claimed `minecraftwiki._make_request` had no `timeout`. **That was incorrect.**
Line 62 already read `requests.get(API_URL, params=params, timeout=15)`. All three HTTP scrapers
had timeouts already (wiki 15s, misode 10s, mojira 10s).

The claim came from a sub-agent's file summary and did not survive checking it against the actual
file. Recorded here rather than deleted, because the lesson generalises: a confident secondhand
report about a specific line is worth one `grep` before acting on it.

What *was* wrong nearby: Spyglass's `_make_request` had **no** timeout. That one is real and is now
fixed (`timeout=30` — higher than the others because registry payloads are large).

### 4.5 Bare `except:` swallows everything

`minecraftwiki.py:252` uses a bare `except:`, which catches `KeyboardInterrupt` and `SystemExit`
along with real errors. Use `except Exception:` and log it.

### 4.6 Coverage gaps versus the README's stated scope

The README says the server targets "datapacks, mods, plugins" but every tool is datapack-only.
Nothing addresses mods or plugins at all. Either narrow the pitch to datapacks and resource packs
(honest, and the tools are genuinely good there), or add:

- Fabric / NeoForge / Forge API version lookup and mappings (Yarn ↔ Mojmap ↔ Intermediary)
- `build.gradle` / `fabric.mod.json` / `mods.toml` scaffolding awareness
- Bukkit / Paper / Spigot API version and event lookup
- `plugin.yml` / `paper-plugin.yml` schema

That is a large amount of work for a different audience. Narrowing the pitch is the better call
until the datapack story is airtight.

### 4.7 Documentation

- The README's Development section repeats the "CI publishes on tag push" note **twice** (lines 148
  and 159). Trim.
- Point 133 references `scripts/release.ps1` before it's introduced.
- No `CONTRIBUTING.md`, despite the README asking for issues and stars.
- The Example Prompts section is good — extend it once the version tools land, since those prompts
  are how users discover the version-awareness features that are the point of the project.

---

## Suggested order of work

**This week — small, high-return:**

1. `timeout=10` in `minecraftwiki._make_request` (§4.4) — one line, prevents a hung server
2. Return JSON on error, not a bare string (§0.2)
3. `HANDLERS` dict + the `set(HANDLERS) == {t.name for t in TOOLS}` assertion (§4.2)
4. `asyncio.to_thread` around handlers (§4.3)
5. Confirm `pip_token.txt` was never committed (§3.4)

**Next — the version problem:**

6. Expose the four changelog functions as tools (§2.1)
7. Prompts + resources + `minecraft_start_session` so the preprompt actually reaches the model (§0.1)
8. `detect_pack_version` and pack_format ↔ version mapping (§2.5)
9. Render Brigadier trees as usage strings (§2.3.2)
10. Version warnings on all six wiki tools (§1.1)

**Then — publishing:**

11. Trusted Publishing (§3.2) + TestPyPI (§3.3)
12. Verify the wheel actually contains `preprompts/` and `config/` (§3.5)

**Then — validation, the long game:**

13. `validate_command` against the Brigadier tree (§2.4)
14. Disk cache for all scrapers (§1.4)
15. `check_version_syntax` with the migration table (§2.2)
16. Filtered mcdoc symbols, retire the unfiltered dump (§1.2)
17. Tests (§4.1)

---

## The one-paragraph summary

The project's data sources are well chosen — Spyglass and misode are exactly right for
version-accurate Minecraft data, and you were correct to reach for them. Two things stop that from
translating into correct output. First, the guidance telling the agent to *use* them is loaded into
a variable that nothing reads, so the model never learns its training data is stale and simply
writes the syntax it already "knows". Second, the tool that most directly fixes version drift —
misode's technical changelog — is fully implemented in `misode.py` and was never registered as a
tool. Fix those two and the version problem largely resolves without any hand-written skillset. For
PyPI, switch to Trusted Publishing and the token disappears from the process entirely.
