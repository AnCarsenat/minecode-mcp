"""
Brigadier command tree rendering and validation.

Spyglass serves the game's own command tree, which is authoritative and
version-exact. The problem is its shape: deeply nested
{"type": "argument", "parser": "minecraft:item_stack", "children": {...}}
nodes. An agent handed that raw tree has to mentally compile it into a syntax
string, and that compilation step is exactly where version errors creep back
in -- the model falls back on remembered syntax rather than reading the tree.

So this module does the compilation server-side:

  render_usage()    -> "/give <targets> <item> [<count>]" plus argument notes
  validate()        -> does this command actually parse against this version?

Both operate on the tree Spyglass returns. Neither hardcodes any Minecraft
syntax, so both stay correct as the game changes.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Maximum distinct usage lines to emit for one command. /execute alone expands
# to thousands of paths; past a few dozen the output stops being useful to a
# reader and starts being a context sink.
MAX_USAGE_LINES = 60
MAX_DEPTH = 24


# ---------------------------------------------------------------------------
# Human-readable parser descriptions
# ---------------------------------------------------------------------------

_PARSER_NOTES = {
    "brigadier:bool": "true or false",
    "brigadier:double": "decimal number",
    "brigadier:float": "decimal number",
    "brigadier:integer": "whole number",
    "brigadier:long": "whole number",
    "brigadier:string": "text",
    "minecraft:angle": "angle in degrees, optionally relative (~)",
    "minecraft:block_pos": "block position: x y z, with ~ relative or ^ local",
    "minecraft:block_predicate": "block ID, block tag (#), or block state pattern",
    "minecraft:block_state": "block ID with optional [state=value] and {nbt}",
    "minecraft:color": "colour name (e.g. red, aqua, reset)",
    "minecraft:column_pos": "column position: x z",
    "minecraft:component": "text component (JSON or SNBT)",
    "minecraft:dimension": "dimension ID (e.g. minecraft:overworld)",
    "minecraft:entity": "entity selector, player name, or UUID",
    "minecraft:entity_anchor": "eyes or feet",
    "minecraft:float_range": "numeric range (e.g. 1..5, ..5, 3..)",
    "minecraft:function": "function ID or #function tag",
    "minecraft:game_profile": "player name, UUID, or selector",
    "minecraft:int_range": "integer range (e.g. 1..5)",
    "minecraft:item_predicate": "item ID, item tag (#), or component pattern",
    "minecraft:item_slot": "slot name (e.g. weapon.mainhand, container.0)",
    "minecraft:item_stack": "item ID with optional [components]",
    "minecraft:message": "free text, consumes the rest of the line",
    "minecraft:nbt_compound_tag": "SNBT compound, e.g. {key:value}",
    "minecraft:nbt_path": "NBT path, e.g. Inventory[0].id",
    "minecraft:nbt_tag": "any SNBT value",
    "minecraft:objective": "scoreboard objective name",
    "minecraft:objective_criteria": "scoreboard criterion",
    "minecraft:operation": "scoreboard operation (=, +=, -=, *=, /=, %=, <, >, ><)",
    "minecraft:particle": "particle ID with optional parameters",
    "minecraft:resource": "namespaced ID from a registry",
    "minecraft:resource_key": "namespaced ID from a registry",
    "minecraft:resource_location": "namespaced ID (namespace:path)",
    "minecraft:resource_or_tag": "namespaced ID or #tag",
    "minecraft:rotation": "rotation: yaw pitch",
    "minecraft:score_holder": "score holder: selector, name, or *",
    "minecraft:scoreboard_slot": "display slot (e.g. sidebar, list, below_name)",
    "minecraft:style": "text style object",
    "minecraft:swizzle": "any combination of x, y, z",
    "minecraft:team": "team name",
    "minecraft:time": "duration with optional unit (t, s, d)",
    "minecraft:uuid": "UUID",
    "minecraft:vec2": "2D position: x z",
    "minecraft:vec3": "3D position: x y z, with ~ relative or ^ local",
}

# Parsers that swallow every remaining token.
_GREEDY_PARSERS = {"minecraft:message"}


def describe_parser(parser: str, properties: Optional[Dict] = None) -> str:
    """Return a human-readable description of an argument parser."""
    base = _PARSER_NOTES.get(parser)
    if base is None:
        # Unknown parser: degrade to the raw ID rather than inventing a
        # description. A wrong description is worse than none.
        base = parser

    if not properties:
        return base

    extras = []
    if "min" in properties or "max" in properties:
        lo = properties.get("min", "")
        hi = properties.get("max", "")
        extras.append(f"range {lo}..{hi}")
    if properties.get("type"):
        extras.append(f"type: {properties['type']}")
    if properties.get("amount"):
        extras.append(f"amount: {properties['amount']}")
    if properties.get("registry"):
        extras.append(f"registry: {properties['registry']}")

    return f"{base} ({', '.join(extras)})" if extras else base


# ---------------------------------------------------------------------------
# Usage rendering
# ---------------------------------------------------------------------------

def _node_label(name: str, node: Dict[str, Any]) -> str:
    if node.get("type") == "literal":
        return name
    return f"<{name}>"


def render_usage(command_name: str, node: Dict[str, Any],
                 max_lines: int = MAX_USAGE_LINES) -> Dict[str, Any]:
    """
    Walk a command node and emit concrete usage lines.

    Returns usage strings, per-argument notes, and a truncation flag so the
    caller can tell a complete rendering from a partial one. Silent truncation
    would read as "these are all the forms", which is worse than saying so.
    """
    usages: List[str] = []
    arguments: Dict[str, str] = {}
    truncated = False
    redirects: List[str] = []

    def walk(n: Dict[str, Any], parts: List[str], depth: int) -> None:
        nonlocal truncated

        if len(usages) >= max_lines:
            truncated = True
            return
        if depth > MAX_DEPTH:
            truncated = True
            return

        if n.get("executable"):
            usages.append("/" + " ".join(parts))

        redirect = n.get("redirect")
        if redirect:
            target = redirect[0] if isinstance(redirect, list) else redirect
            redirects.append(target)
            usages.append("/" + " ".join(parts) + f" -> continues as /{target} ...")
            return

        children = n.get("children") or {}
        for child_name, child in children.items():
            if not isinstance(child, dict):
                continue
            if child.get("type") == "argument":
                parser = child.get("parser", "")
                if child_name not in arguments:
                    arguments[child_name] = describe_parser(
                        parser, child.get("properties"))
            walk(child, parts + [_node_label(child_name, child)], depth + 1)
            if len(usages) >= max_lines:
                truncated = True
                return

    walk(node, [command_name], 0)

    # Preserve order while removing duplicates -- different tree paths often
    # collapse to the same rendered string.
    seen = set()
    unique = []
    for u in usages:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    return {
        "command": command_name,
        "usage": unique,
        "arguments": arguments,
        "redirects": sorted(set(redirects)),
        "truncated": truncated,
        "note": (
            f"Rendering stopped at {max_lines} usage lines; this command has more "
            "forms than shown. Narrow the query or read the raw tree."
            if truncated else None
        ),
    }


# ---------------------------------------------------------------------------
# Command validation
# ---------------------------------------------------------------------------

def tokenize(command: str) -> Tuple[List[str], int, Optional[str]]:
    """
    Split a command into tokens, keeping quoted strings, bracketed component
    blocks, and braced NBT together.

    Minecraft commands nest [] and {} inside single arguments
    (`diamond_sword[enchantments={...}]`), so a plain whitespace split would
    shred them into meaningless pieces.

    Returns (tokens, final_bracket_depth, unterminated_quote_char). A non-zero
    depth or a non-None quote char means the input was malformed -- reported
    rather than silently tolerated, since an unclosed bracket is one of the
    most common hand-written command errors.
    """
    tokens: List[str] = []
    current: List[str] = []
    depth = 0
    in_string: Optional[str] = None
    escaped = False

    for ch in command:
        if escaped:
            current.append(ch)
            escaped = False
            continue

        if in_string:
            current.append(ch)
            if ch == "\\":
                escaped = True
            elif ch == in_string:
                in_string = None
            continue

        if ch in ('"', "'"):
            in_string = ch
            current.append(ch)
        elif ch in "[{(":
            depth += 1
            current.append(ch)
        elif ch in "]})":
            depth -= 1
            current.append(ch)
        elif ch.isspace() and depth == 0:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(ch)

    if current:
        tokens.append("".join(current))

    return tokens, depth, in_string


def _consume_argument(parser: str, properties: Optional[Dict],
                      tokens: List[str], index: int) -> Tuple[int, Optional[str]]:
    """
    Return (tokens_consumed, error) for one argument node.

    This is an approximation. Full Brigadier argument parsing needs a
    sub-grammar per parser type; here we validate what is cheaply checkable
    (numbers, booleans, coordinate arity) and otherwise accept a single token.
    The result is a validator with no false positives on well-formed input,
    which is the property that matters -- a validator that cries wolf gets
    ignored.
    """
    if index >= len(tokens):
        return 0, "missing"

    token = tokens[index]
    properties = properties or {}

    if parser in _GREEDY_PARSERS:
        return len(tokens) - index, None

    if parser == "brigadier:string" and properties.get("type") == "greedy":
        return len(tokens) - index, None

    if parser in ("brigadier:integer", "brigadier:long"):
        if not re.fullmatch(r"[+-]?\d+", token):
            return 1, f"expected a whole number, got '{token}'"
        value = int(token)
        if "min" in properties and value < properties["min"]:
            return 1, f"{value} is below the minimum {properties['min']}"
        if "max" in properties and value > properties["max"]:
            return 1, f"{value} is above the maximum {properties['max']}"
        return 1, None

    if parser in ("brigadier:double", "brigadier:float"):
        if not re.fullmatch(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?", token):
            return 1, f"expected a number, got '{token}'"
        return 1, None

    if parser == "brigadier:bool":
        if token not in ("true", "false"):
            return 1, f"expected true or false, got '{token}'"
        return 1, None

    if parser in ("minecraft:block_pos", "minecraft:vec3"):
        return min(3, len(tokens) - index), None

    if parser in ("minecraft:column_pos", "minecraft:vec2", "minecraft:rotation"):
        return min(2, len(tokens) - index), None

    if parser == "minecraft:swizzle":
        if not re.fullmatch(r"[xyz]{1,3}", token) or len(set(token)) != len(token):
            return 1, f"expected a combination of x, y, z, got '{token}'"
        return 1, None

    return 1, None


def validate(command: str, root: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse `command` against the command tree `root`.

    Returns a verdict plus, on failure, the token that failed and what was
    valid there. "What was valid there" is the part that lets an agent
    self-correct instead of guessing again.
    """
    original = command
    command = command.strip()
    if command.startswith("/"):
        command = command[1:]

    if not command:
        return {"valid": False, "command": original, "error": "empty command"}

    tokens, depth, in_string = tokenize(command)

    if depth != 0:
        return {
            "valid": False,
            "command": original,
            "error": f"unbalanced brackets or braces (depth {depth:+d} at end of input)",
            "hint": "Every [ { ( must be closed. Component and NBT blocks are a common place to drop one.",
        }
    if in_string:
        return {
            "valid": False,
            "command": original,
            "error": f"unterminated {in_string} string",
        }

    return _walk(tokens, root, root, original, [], 0)


def _resolve_redirect(node: Dict[str, Any],
                      root: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Return the node parsing continues at, or None if this is not a redirect.

    Spyglass serializes the two Brigadier redirect forms differently, and both
    appear constantly in real datapacks:

      * Chaining subcommands carry an explicit path, e.g.
        `execute at <targets>` has `"redirect": ["execute"]` -- parsing resumes
        at /execute so `at ... as ... if ... run` can chain.

      * Root redirects carry NOTHING. `execute run` and `return run` arrive as
        bare `{"type": "literal"}` with no children, no executable flag, and no
        redirect field. A node that can never match anything is not something
        Brigadier would contain, so a childless non-executable node means
        "parse the rest as a fresh command from root".

    Getting this wrong is expensive in both directions: treating every
    childless node as a root redirect broke `execute at ... run ...` (66% of a
    real 4128-command pack), while handling neither form broke every
    `execute run ...`.
    """
    redirect = node.get("redirect")
    if redirect:
        target = root
        for step in (redirect if isinstance(redirect, list) else [redirect]):
            children = target.get("children") or {}
            nxt = children.get(step)
            if not isinstance(nxt, dict):
                return root  # unknown target; root is the safe fallback
            target = nxt
        return target

    if not node.get("children") and not node.get("executable"):
        return root

    return None


# Guards against pathological input. Real commands sit far below both.
_MAX_REDIRECT_DEPTH = 12
_MAX_PARSE_STEPS = 20000


class _Failure:
    """Deepest failure seen while backtracking -- the best error to report."""

    __slots__ = ("index", "token", "children", "path", "arg_errors")

    def __init__(self):
        self.index = -1
        self.token = None
        self.children = {}
        self.path = []
        self.arg_errors = []

    def record(self, index, token, children, path, arg_errors):
        # Deepest match is the most informative: it is where the command
        # actually stopped making sense, not where the first guess failed.
        if index > self.index:
            self.index = index
            self.token = token
            self.children = children
            self.path = list(path)
            self.arg_errors = arg_errors


def _walk(tokens: List[str], node: Dict[str, Any], root: Dict[str, Any],
          original: str, path: List[str], depth: int) -> Dict[str, Any]:
    """
    Parse `tokens` against `node` with BACKTRACKING.

    Backtracking is required, not a refinement. Command nodes overlap: in
    `/tp @s ~ ~ ~`, the token `@s` matches both `<destination>` (an entity) and
    `<targets>`. Committing to the first match and never reconsidering leaves
    `~ ~ ~` unparseable, and real Brigadier resolves this by trying the
    alternatives. Greedy first-match reported valid commands as broken.
    """
    failure = _Failure()
    steps = [0]

    def attempt(node: Dict[str, Any], index: int, path: List[str],
                redirects: int) -> bool:
        steps[0] += 1
        if steps[0] > _MAX_PARSE_STEPS or redirects > _MAX_REDIRECT_DEPTH:
            return False

        if index >= len(tokens):
            if node.get("executable"):
                failure.record(index, None, {}, path, [])
                return True
            failure.record(index, None, node.get("children") or {}, path, [])
            return False

        children = node.get("children") or {}
        token = tokens[index]
        arg_errors: List[str] = []

        # Literals bind tighter than arguments, as in Brigadier itself.
        literal = children.get(token)
        if isinstance(literal, dict) and literal.get("type") == "literal":
            if attempt(literal, index + 1, path + [token], redirects):
                return True

        for name, child in children.items():
            if not isinstance(child, dict) or child.get("type") != "argument":
                continue
            consumed, err = _consume_argument(
                child.get("parser", ""), child.get("properties"), tokens, index)
            if err == "missing":
                arg_errors.append(f"<{name}>: missing")
                continue
            if err:
                arg_errors.append(f"<{name}>: {err}")
                continue

            # Multi-token parsers (vec3, block_pos) may legitimately match
            # fewer tokens than their maximum, so try shorter widths too.
            widths = sorted({max(1, consumed), 1}, reverse=True)
            for width in widths:
                if index + width > len(tokens):
                    continue
                if attempt(child, index + width, path + [f"<{name}>"], redirects):
                    return True

        target = _resolve_redirect(node, root)
        if target is not None and target is not node:
            if attempt(target, index, path, redirects + 1):
                return True

        failure.record(index, token, children, path, arg_errors)
        return False

    if attempt(node, 0, path, depth):
        return {
            "valid": True,
            "command": original,
            "parsed_path": " ".join(failure.path) if failure.path else "",
            "tokens": len(tokens),
        }

    if steps[0] > _MAX_PARSE_STEPS:
        return {
            "valid": True,
            "partial": True,
            "command": original,
            "note": ("Parse budget exhausted; the command was too ambiguous to "
                     "verify. Treat this as unverified, not as valid."),
        }

    if failure.token is None:
        return {
            "valid": False,
            "command": original,
            "error": "command is incomplete",
            "parsed_path": " ".join(failure.path),
            "expected_here": _describe_expected(failure.children),
        }

    return {
        "valid": False,
        "command": original,
        "error": f"unexpected token '{failure.token}' at position {failure.index + 1}",
        "parsed_path": " ".join(failure.path) or "(start)",
        "expected_here": _describe_expected(failure.children),
        "argument_errors": failure.arg_errors or None,
    }


def _describe_expected(children: Dict[str, Any]) -> List[str]:
    """List what could legally appear at this point in the tree."""
    out = []
    for name, child in (children or {}).items():
        if not isinstance(child, dict):
            continue
        if child.get("type") == "literal":
            out.append(name)
        else:
            parser = child.get("parser", "")
            out.append(f"<{name}> ({describe_parser(parser, child.get('properties'))})")
    return sorted(out)[:40]
