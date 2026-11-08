"""
Minecraft.wiki API Client for Minecraft wiki pages
Uses the MediaWiki API: https://www.mediawiki.org/wiki/API:Main_page

IMPORTANT LIMITATION -- read before using anything here.

minecraft.wiki documents the LATEST version of the game only. It carries no
per-version history for command syntax, JSON schemas, NBT structure, or item
IDs. Every function in this module therefore returns latest-version content,
regardless of what version the caller is working on.

That is the single largest source of wrong output in this project: an agent
asks the wiki for /give syntax, gets the current component syntax back, and
writes it into a 1.20.4 pack where it is a parse error.

Use this module for CONCEPTUAL questions ("how does a raid work", "what
triggers a piglin barter"). For anything version-sensitive, use spyglass
(authoritative, version-exact) or misode (vanilla presets per version).

Every public function's result is wrapped with a version warning by the server
layer -- see WIKI_VERSION_WARNING.
"""

import logging
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import re

from .. import cache

logger = logging.getLogger("minecode.wiki")

BASE_URL = "https://minecraft.wiki"
API_URL = "https://minecraft.wiki/api.php"
PAGE_URL = "https://minecraft.wiki/w/"

USER_AGENT = "MineCode/1.0 (+https://github.com/AnCarsenat/minecode-mcp)"

# Attached to every wiki tool response. Descriptions get skimmed; payload
# fields get read, so the warning travels with the data rather than sitting
# only in the tool schema.
WIKI_VERSION_WARNING = (
    "minecraft.wiki documents the LATEST Minecraft version only. It has no "
    "per-version history. If your target version is not the current release, "
    "treat all syntax, JSON schemas, NBT structure, and IDs in this result as "
    "POSSIBLY WRONG until confirmed against a version-exact source: "
    "spyglass_get_commands / spyglass_get_registries / spyglass_get_mcdoc_symbol "
    "for syntax and schemas, misode_get_preset_data for vanilla examples, and "
    "get_technical_changes to see what moved between versions. "
    "This content is reliable for CONCEPTS and game mechanics, not for syntax."
)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class SearchResult:
    """Represents a wiki search result"""
    title: str
    url: str
    snippet: str = ""


@dataclass
class PageInfo:
    """Represents basic page information"""
    pageid: int
    title: str
    url: str


@dataclass
class PageContent:
    """Represents parsed page content"""
    title: str
    pageid: int
    url: str
    extract: str  # Plain text of the page body, capped at MAX_PAGE_CHARS
    sections: List[Dict[str, Any]]
    categories: List[str]
    # Header/value rows of the page's infobox (blocks, items, mobs), e.g.
    # {"Blast resistance": "0", "Hardness": "0"}. Empty when there is none.
    infobox: Dict[str, str] = field(default_factory=dict)
    truncated: bool = False
    full_length: int = 0  # length of the body text before the cap
    redirected_from: Optional[str] = None
    # Anything the agent should know about how complete this result is.
    notes: List[str] = field(default_factory=list)


@dataclass
class CommandInfo:
    """Represents a Minecraft command"""
    name: str
    url: str


# ============================================================================
# API Functions
# ============================================================================

def _make_request(params: dict) -> dict:
    """Make a request to the MediaWiki API, via the disk cache."""
    params["format"] = "json"
    key = f"wiki:{sorted(params.items())}"

    def fetch():
        response = requests.get(API_URL, params=params, timeout=15,
                                headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        return response.json()

    # Wiki content changes, so this is a TTL cache rather than immutable.
    return cache.cached_fetch(key, cache.TTL_WIKI, fetch)


def search(query: str, limit: int = 10) -> List[SearchResult]:
    """
    Search the Minecraft Wiki using OpenSearch protocol.
    
    Args:
        query: Search query string
        limit: Maximum number of results (default 10, max 100)
    
    Returns:
        List of SearchResult objects with title and URL
    """
    params = {
        "action": "opensearch",
        "search": query,
        "limit": min(limit, 100),
        "namespace": 0  # Main namespace only
    }
    
    data = _make_request(params)
    
    # OpenSearch returns: [query, [titles], [descriptions], [urls]]
    results = []
    if len(data) >= 4:
        titles = data[1]
        descriptions = data[2]
        urls = data[3]
        
        for i, title in enumerate(titles):
            results.append(SearchResult(
                title=title,
                url=urls[i] if i < len(urls) else f"{PAGE_URL}{title.replace(' ', '_')}",
                snippet=descriptions[i] if i < len(descriptions) else ""
            ))
    
    return results


def search_fulltext(query: str, limit: int = 10) -> List[SearchResult]:
    """
    Full-text search with snippets showing matches.
    
    Args:
        query: Search query string
        limit: Maximum number of results
    
    Returns:
        List of SearchResult objects with snippets
    """
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": min(limit, 50),
        "srprop": "snippet|titlesnippet"
    }
    
    data = _make_request(params)
    
    results = []
    for item in data.get("query", {}).get("search", []):
        # Clean HTML from snippet
        snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))
        results.append(SearchResult(
            title=item["title"],
            url=f"{PAGE_URL}{item['title'].replace(' ', '_')}",
            snippet=snippet
        ))
    
    return results


def get_page_extract(title: str, sentences: int = 5) -> Optional[str]:
    """
    Get a plain text extract/summary of a page.
    
    Args:
        title: Page title
        sentences: Number of sentences to extract
    
    Returns:
        Plain text summary or None if page not found
    """
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts",
        "exintro": True,  # Only intro section
        "explaintext": True,  # Plain text, no HTML
        "exsentences": sentences
    }
    
    data = _make_request(params)
    pages = data.get("query", {}).get("pages", {})
    
    for page_id, page in pages.items():
        if page_id != "-1":
            return page.get("extract", "")
    
    return None


# Cap on the body text of a full page. Block pages run to 30-60k characters of
# text (sound tables, data values, history); returning all of it crowds out
# the agent's work. Truncation is always reported, never silent.
MAX_PAGE_CHARS = 12000

# Page furniture that is not content: edit links, navigation boxes, the
# infobox's raw history JSON, citation markers.
_NOISE_SELECTORS = (
    "script", "style", ".mw-editsection", ".navbox", ".history-json",
    "sup.reference", ".mw-cite-backlink",
    # Hidden calculator inputs: "1" + "0.05" read as "10.05" otherwise.
    '[style*="display:none"]', '[style*="display: none"]',
)


def _decompose_all(elements) -> None:
    """
    Decompose a precomputed list of elements.

    The list can hold an element AND its descendants (an infobox and the
    tables nested in it). Decomposing the parent destroys the children too,
    and bs4 clears a destroyed tag's attributes, so touching one afterwards
    raises AttributeError. That is how every page with a nested infobox --
    "Redstone Repeater", "Hopper", "Creeper" -- failed with
    "'NoneType' object has no attribute 'get'". Skip what is already gone.
    """
    for el in elements:
        if getattr(el, "decomposed", False):
            continue
        el.decompose()


def _clean_text(text: str) -> str:
    text = text.replace("\u200b", "").replace("\u200c", "").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


_BLOCK_TAGS = (
    "p", "div", "li", "dd", "dt", "tr", "table", "pre", "ul", "ol", "dl",
    "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "figure", "figcaption",
)


def _soup_text(soup: BeautifulSoup) -> str:
    """
    Text with line breaks only at block elements and table cells.

    get_text(separator="\\n") put every link and bold word on its own line,
    which tripled the line count of a page and split sentences apart.
    """
    for row in soup.find_all("tr"):
        for s in list(row.find_all(string=True, recursive=False)):
            if not s.strip():
                s.extract()
    for cell in soup.find_all(["td", "th"]):
        # Source newlines inside a cell would split "Hardness | 0" apart.
        for s in list(cell.find_all(string=True)):
            if "\n" in s:
                s.replace_with(s.replace("\n", " "))
        cell.append(" | ")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for tag in soup.find_all(_BLOCK_TAGS):
        tag.insert_before("\n")
        tag.append("\n")
    text = soup.get_text()
    text = re.sub(r"[ \t]*\|[ \t]*(?=\n|$)", "", text)  # trailing cell separators
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text


def _extract_infobox(soup: BeautifulSoup) -> Dict[str, str]:
    """Header/value rows of every infobox on the page."""
    rows: Dict[str, str] = {}
    for box in soup.select(".infobox"):
        for tr in box.select("tr"):
            th, td = tr.find("th"), tr.find("td")
            if th is None or td is None:
                continue
            for sup in th.select("sup"):  # "[BE only]" edition markers
                sup.extract()
            key = _clean_text(th.get_text(" ", strip=True))
            value = _clean_text(td.get_text(" ", strip=True))
            if key and key not in rows:
                rows[key] = value
    return rows


def html_to_page_text(html: str):
    """
    Turn a parsed wiki page into (text, infobox, notes).

    Never raises: a step that fails is skipped and reported in `notes`, so a
    page whose markup changes upstream still yields partial content.
    """
    notes: List[str] = []
    if not html:
        return "", {}, ["the wiki returned no page HTML"]
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:  # pragma: no cover - html.parser is lenient
        logger.warning("HTML parse failed: %s", e)
        text = _clean_text(re.sub(r"<[^>]+>", "\n", html))
        return text, {}, [f"HTML could not be parsed ({e}); tags were stripped instead"]

    infobox: Dict[str, str] = {}
    try:
        infobox = _extract_infobox(soup)
    except Exception as e:
        logger.warning("Infobox extraction failed: %s", e)
        notes.append(f"infobox could not be read ({e}); it is omitted")

    try:
        _decompose_all(soup.select(", ".join(_NOISE_SELECTORS)))
        _decompose_all(soup.select(".infobox"))
    except Exception as e:
        logger.warning("Page cleanup failed: %s", e)
        notes.append(f"page cleanup failed ({e}); text may include navigation")

    try:
        text = _soup_text(soup)
    except Exception as e:
        logger.warning("Text extraction failed: %s", e)
        text = re.sub(r"<[^>]+>", "\n", html)
        notes.append(f"text extraction failed ({e}); tags were stripped instead")
    return _clean_text(text), infobox, notes


def get_page_content(title: str) -> Optional[PageContent]:
    """
    Get full parsed content of a page including sections and categories.

    Follows redirects. Returns None only when the page does not exist; a page
    that exists but parses badly comes back partial, with `notes` saying why.
    """
    params = {
        "action": "parse",
        "page": title,
        "prop": "text|sections|categories",
        "disabletoc": True,
        "redirects": True,
    }

    try:
        data = _make_request(params)
    except requests.exceptions.HTTPError:
        return None
    # Validate response
    if not data or not isinstance(data, dict):
        return None
    if "error" in data:
        return None

    parse = data.get("parse")
    if not isinstance(parse, dict):
        return None

    text_field = parse.get("text")
    if isinstance(text_field, dict):
        html = text_field.get("*", "")
    else:  # formatversion=2 returns the HTML as a plain string
        html = text_field or ""

    text, infobox, notes = html_to_page_text(html)

    full_length = len(text)
    truncated = full_length > MAX_PAGE_CHARS
    if truncated:
        cut = text.rfind("\n", 0, MAX_PAGE_CHARS)
        text = text[: cut if cut > MAX_PAGE_CHARS // 2 else MAX_PAGE_CHARS]
        notes.append(
            f"text truncated to {len(text)} of {full_length} characters; "
            "the infobox and the section list cover the whole page. Read the "
            "rest at the page URL, or use search_wiki for a specific topic."
        )

    def _plain(s: str) -> str:  # section titles can carry <i>, <span>
        return re.sub(r"<[^>]+>", "", s or "")

    sections = [
        {"index": s.get("index"), "level": int(s.get("level") or 0),
         "name": _plain(s.get("line", ""))}
        for s in parse.get("sections") or [] if isinstance(s, dict)
    ]
    categories = [
        cat.get("*", "") for cat in parse.get("categories") or []
        if isinstance(cat, dict)
    ]
    if any("disambiguation" in c.lower() for c in categories):
        notes.append(
            "this is a disambiguation page: it lists other pages. Fetch the "
            "specific one you need."
        )

    redirects = parse.get("redirects") or []
    redirected_from = redirects[0].get("from") if redirects and isinstance(redirects[0], dict) else None

    real_title = parse.get("title") or title
    if not text and not infobox:
        notes.append("no readable text was found on this page")

    return PageContent(
        title=real_title,
        pageid=parse.get("pageid", 0),
        url=f"{PAGE_URL}{real_title.replace(' ', '_')}",
        extract=text,
        sections=sections,
        categories=categories,
        infobox=infobox,
        truncated=truncated,
        full_length=full_length,
        redirected_from=redirected_from,
        notes=notes,
    )


def get_page_sections(title: str) -> List[Dict[str, Any]]:
    """
    Get the section structure of a page.
    
    Args:
        title: Page title
    
    Returns:
        List of section dictionaries with index, level, and name
    """
    params = {
        "action": "parse",
        "page": title,
        "prop": "sections"
    }
    
    try:
        data = _make_request(params)
    except Exception as e:
        # A bare `except:` here previously swallowed KeyboardInterrupt and
        # SystemExit along with real errors, making the server unkillable
        # mid-request.
        logger.warning("Failed to fetch sections for %r: %s", title, e)
        return []

    return [
        {"index": s["index"], "level": int(s["level"]), "name": s["line"]}
        for s in data.get("parse", {}).get("sections", [])
    ]


def get_category_members(category: str, limit: int = 50) -> List[PageInfo]:
    """
    Get all pages in a category.
    
    Args:
        category: Category name (with or without "Category:" prefix)
        limit: Maximum number of results
    
    Returns:
        List of PageInfo objects
    """
    if not category.startswith("Category:"):
        category = f"Category:{category}"
    
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category,
        "cmlimit": min(limit, 500),
        "cmtype": "page"  # Only pages, not subcategories
    }
    
    data = _make_request(params)
    
    return [
        PageInfo(
            pageid=item["pageid"],
            title=item["title"],
            url=f"{PAGE_URL}{item['title'].replace(' ', '_')}"
        )
        for item in data.get("query", {}).get("categorymembers", [])
    ]


def get_commands(limit: int = 100) -> List[CommandInfo]:
    """
    Get list of all Minecraft commands from the wiki.
    
    Args:
        limit: Maximum number of commands to return
    
    Returns:
        List of CommandInfo objects
    """
    pages = get_category_members("Commands", limit=limit)
    
    commands = []
    for page in pages:
        # Filter to only actual command pages
        if page.title.startswith("Commands/"):
            cmd_name = page.title.replace("Commands/", "")
            commands.append(CommandInfo(
                name=cmd_name,
                url=page.url
            ))
    
    return commands


def get_command_info(command: str) -> Optional[str]:
    """
    Get information about a specific command.
    
    Args:
        command: Command name (e.g., "execute", "give")
    
    Returns:
        Plain text description of the command
    """
    # Try with Commands/ prefix first
    extract = get_page_extract(f"Commands/{command}", sentences=10)
    if extract:
        return extract
    
    # Try without prefix
    return get_page_extract(command, sentences=10)


def get_version_info(version: str) -> Optional[str]:
    """
    Get information about a specific Minecraft version.
    
    Args:
        version: Version string (e.g., "1.20.1", "Java Edition 1.20")
    
    Returns:
        Plain text description of the version
    """
    # Try different page name formats
    candidates = [
        f"Java Edition {version}",
        version,
        f"Bedrock Edition {version}"
    ]
    
    for title in candidates:
        extract = get_page_extract(title, sentences=10)
        if extract:
            return extract
    
    return None


def get_block_info(block: str) -> Optional[PageContent]:
    """
    Get information about a specific block.
    
    Args:
        block: Block name (e.g., "Stone", "Diamond Ore")
    
    Returns:    
        PageContent object with block information
    """
    return get_page_content(block)


def get_item_info(item: str) -> Optional[PageContent]:
    """
    Get information about a specific item.
    
    Args:
        item: Item name (e.g., "Diamond Sword", "Ender Pearl")
    
    Returns:
        PageContent object with item information
    """
    return get_page_content(item)


def get_mob_info(mob: str) -> Optional[PageContent]:
    """
    Get information about a specific mob/entity.
    
    Args:
        mob: Mob name (e.g., "Creeper", "Enderman")
    
    Returns:
        PageContent object with mob information
    """
    return get_page_content(mob)


def get_random_pages(count: int = 5) -> List[PageInfo]:
    """
    Get random wiki pages.
    
    Args:
        count: Number of random pages to get
    
    Returns:
        List of PageInfo objects
    """
    params = {
        "action": "query",
        "list": "random",
        "rnnamespace": 0,  # Main namespace
        "rnlimit": min(count, 20)
    }
    
    data = _make_request(params)
    
    return [
        PageInfo(
            pageid=item["id"],
            title=item["title"],
            url=f"{PAGE_URL}{item['title'].replace(' ', '_')}"
        )
        for item in data.get("query", {}).get("random", [])
    ]


# ============================================================================
# Conversion Functions
# ============================================================================

def search_to_dict(results: List[SearchResult]) -> List[dict]:
    """Convert SearchResult list to dict list"""
    return [
        {"title": r.title, "url": r.url, "snippet": r.snippet}
        for r in results
    ]


def page_info_to_dict(pages: List[PageInfo]) -> List[dict]:
    """Convert PageInfo list to dict list"""
    return [
        {"pageid": p.pageid, "title": p.title, "url": p.url}
        for p in pages
    ]


def page_content_to_dict(content: Optional[PageContent]) -> Optional[dict]:
    """Convert PageContent to dict"""
    if not content:
        return None
    return {
        "title": content.title,
        "pageid": content.pageid,
        "url": content.url,
        "extract": content.extract,
        "sections": content.sections,
        "categories": content.categories,
        "infobox": content.infobox,
        "truncated": content.truncated,
        "full_length": content.full_length,
        "redirected_from": content.redirected_from,
        "notes": content.notes,
    }


def commands_to_dict(commands: List[CommandInfo]) -> List[dict]:
    """Convert CommandInfo list to dict list"""
    return [
        {"name": c.name, "url": c.url}
        for c in commands
    ]


# ============================================================================
# Main / Testing
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Minecraft Wiki API Client Tests")
    print("=" * 60)
    
    # Test 1: Search
    print("\n🔍 Test 1: Search for 'creeper'")
    results = search("creeper", limit=5)
    for r in results:
        print(f"  - {r.title}: {r.url}")
    
    # Test 2: Full-text search
    print("\n🔍 Test 2: Full-text search for 'explosion damage'")
    results = search_fulltext("explosion damage", limit=3)
    for r in results:
        print(f"  - {r.title}")
        print(f"    Snippet: {r.snippet[:100]}...")
    
    # Test 3: Get page extract
    print("\n📄 Test 3: Get extract for 'Creeper'")
    extract = get_page_extract("Creeper", sentences=3)
    if extract:
        print(f"  {extract[:300]}...")
    
    # Test 4: Get commands
    print("\n⌨️ Test 4: Get Minecraft commands")
    commands = get_commands(limit=10)
    for cmd in commands[:10]:
        print(f"  - /{cmd.name}")
    
    # Test 5: Get category members
    print("\n📁 Test 5: Get blocks category (first 5)")
    blocks = get_category_members("Blocks", limit=5)
    for b in blocks:
        print(f"  - {b.title}")
    
    # Test 6: Get version info
    print("\n🎮 Test 6: Get version info for '1.20'")
    version = get_version_info("1.20")
    if version:
        print(f"  {version[:200]}...")
    
    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)