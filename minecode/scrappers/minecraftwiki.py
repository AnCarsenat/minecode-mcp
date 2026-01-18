"""
Minecraft.wiki API Client for Minecraft wiki pages
Uses the MediaWiki API: https://www.mediawiki.org/wiki/API:Main_page
"""

import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import re

BASE_URL = "https://minecraft.wiki"
API_URL = "https://minecraft.wiki/api.php"
PAGE_URL = "https://minecraft.wiki/w/"


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
    extract: str  # Plain text summary
    sections: List[Dict[str, Any]]
    categories: List[str]


@dataclass
class CommandInfo:
    """Represents a Minecraft command"""
    name: str
    url: str


# ============================================================================
# API Functions
# ============================================================================

def _make_request(params: dict) -> dict:
    """Make a request to the MediaWiki API"""
    params["format"] = "json"
    response = requests.get(API_URL, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


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


def get_page_content(title: str) -> Optional[PageContent]:
    """
    Get full parsed content of a page including sections and categories.
    
    Args:
        title: Page title
    
    Returns:
        PageContent object or None if page not found
    """
    params = {
        "action": "parse",
        "page": title,
        "prop": "text|sections|categories",
        "disabletoc": True
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
    
    parse = data.get("parse", {})
    
    # Extract plain text from HTML
    html = ""
    if isinstance(parse, dict):
        html = parse.get("text", {}).get("*", "") if parse.get("text") else ""
    soup = BeautifulSoup(html, "html.parser")
    
    # Remove unwanted elements
    for elem in soup.find_all(["script", "style", "table", "div"]):
        if elem.get("class") and "infobox" in " ".join(elem.get("class", [])):
            elem.decompose()
    
    # Get text content
    text = soup.get_text(separator="\n", strip=True)
    # Clean up excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Extract sections
    sections = [
        {"index": s["index"], "level": s["level"], "name": s["line"]}
        for s in parse.get("sections", [])
    ]
    
    # Extract categories
    categories = [
        cat["*"] for cat in parse.get("categories", [])
    ]
    
    return PageContent(
        title=parse.get("title", title),
        pageid=parse.get("pageid", 0),
        url=f"{PAGE_URL}{title.replace(' ', '_')}",
        extract=text[:5000],  # Limit size
        sections=sections,
        categories=categories
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
    except:
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
        "categories": content.categories
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