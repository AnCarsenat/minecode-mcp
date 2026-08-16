"""
Mojira.dev Scraper for Minecraft Bug Tracker
"""

import logging
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

from .. import cache

logger = logging.getLogger("minecode.mojira")

BASE_URL = "https://mojira.dev/"
USER_AGENT = "MineCode/1.0 (+https://github.com/AnCarsenat/minecode-mcp)"


class ScraperStructureError(RuntimeError):
    """
    Raised when the scraped page no longer has the structure we expect.

    Distinct from "no results" on purpose: an HTML-shape change must surface as
    an error the caller can see, not as an empty result set that reads like a
    genuine answer.
    """

# Available filter options
PROJECTS = ["MC", "MCPE", "MCL", "REALMS", "WEB", "BDS"]

STATUSES = ["Open", "Reopened", "Postponed", "In Progress", "Resolved", "Closed"]

CONFIRMATIONS = ["Unconfirmed", "Plausible", "Community Consensus", "Confirmed"]

RESOLUTIONS = [
    "Awaiting Response", "Cannot Reproduce", "Done", "Duplicate", 
    "Fixed", "Incomplete", "Invalid", "Unresolved", "Won't Fix", "Works As Intended"
]

PRIORITIES = ["Low", "Normal", "Important", "Very Important"]

SORT_OPTIONS = ["Created", "Updated", "Resolved", "Priority", "Votes", "Comments", "Duplicates"]


@dataclass
class Issue:
    """Represents a Mojira issue"""
    key: str
    url: str
    summary: str
    status: str
    reporter: str
    assignee: Optional[str]
    created: str


def search(
    query: str = None,
    project: str = None,
    status: str = None,
    confirmation: str = None,
    resolution: str = None,
    priority: str = None,
    sort: str = None,
    page: int = 1
) -> list[Issue]:
    """
    Search Mojira for issues matching the given criteria.
    
    Args:
        query: Search text (minimum 3 characters)
        project: Filter by project (MC, MCPE, MCL, REALMS, WEB, BDS)
        status: Filter by status (Open, Reopened, Postponed, In Progress, Resolved, Closed)
        confirmation: Filter by confirmation status
        resolution: Filter by resolution (Fixed, Done, Duplicate, etc.)
        priority: Filter by priority (Low, Normal, Important, Very Important)
        sort: Sort by field (Created, Updated, Resolved, Priority, Votes, Comments, Duplicates)
        page: Page number (default 1)
    
    Returns:
        List of Issue objects
    """
    # Build query parameters
    params = {}
    
    if query and len(query) >= 3:
        params["search"] = query
    if project and project in PROJECTS:
        params["project"] = project
    if status and status in STATUSES:
        params["status"] = status
    if confirmation and confirmation in CONFIRMATIONS:
        params["confirmation"] = confirmation
    if resolution and resolution in RESOLUTIONS:
        params["resolution"] = resolution
    if priority and priority in PRIORITIES:
        params["priority"] = priority
    if sort and sort in SORT_OPTIONS:
        params["sort"] = sort
    if page > 1:
        params["page"] = page
    
    # Build URL
    url = BASE_URL
    if params:
        url += "?" + urlencode(params)
    
    # Make request (cached briefly -- issue status does change)
    def fetch():
        response = requests.get(url, timeout=10,
                                headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        return response.text

    html = cache.cached_fetch(f"mojira:{url}", cache.TTL_MOJIRA, fetch)

    # Parse HTML
    soup = BeautifulSoup(html, "html.parser")

    # Find issue table
    issues = []
    table = soup.find("table", class_="issue-table")

    if not table:
        # This scraper depends on mojira.dev's markup. When that markup
        # changes, returning [] would report "no bugs found" -- a confident
        # wrong answer that reads as a real result. Raise instead, so the
        # failure is visible as a failure.
        raise ScraperStructureError(
            "Could not find the issue table on mojira.dev. The site's HTML has "
            "probably changed and this scraper needs updating. Do NOT interpret "
            "this as 'no matching issues'."
        )

    tbody = table.find("tbody")
    if not tbody:
        # An empty tbody is a legitimate no-results response.
        return issues
    
    # Parse each row
    for row in tbody.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 6:
            continue
        
        # Extract key and URL
        key_link = cells[0].find("a", class_="issue-table-key")
        if not key_link:
            continue
        
        key = key_link.get_text(strip=True)
        issue_url = BASE_URL.rstrip("/") + key_link.get("href", "")
        
        # Extract summary
        summary_div = cells[1].find("div", class_="issue-table-summary")
        summary = summary_div.get_text(strip=True) if summary_div else ""
        
        # Extract status
        status_badge = cells[2].find("div", class_="status-badge")
        status = status_badge.get_text(strip=True) if status_badge else ""
        
        # Extract reporter
        reporter_link = cells[3].find("a", class_="issue-table-user")
        reporter = reporter_link.get_text(strip=True) if reporter_link else ""
        
        # Extract assignee
        assignee_link = cells[4].find("a", class_="issue-table-user")
        assignee = assignee_link.get_text(strip=True) if assignee_link else None
        if assignee == "":
            assignee = None
        
        # Extract created date
        time_elem = cells[5].find("time")
        created = time_elem.get("datetime", "") if time_elem else ""
        
        issues.append(Issue(
            key=key,
            url=issue_url,
            summary=summary,
            status=status,
            reporter=reporter,
            assignee=assignee,
            created=created
        ))
    
    return issues


def search_to_dict(issues: list[Issue]) -> list[dict]:
    """Convert list of Issues to list of dictionaries"""
    return [
        {
            "key": issue.key,
            "url": issue.url,
            "summary": issue.summary,
            "status": issue.status,
            "reporter": issue.reporter,
            "assignee": issue.assignee,
            "created": issue.created
        }
        for issue in issues
    ]


if __name__ == "__main__":    
    results = search(
        query="creeper",
        status="Resolved",
        resolution="Fixed"
    )