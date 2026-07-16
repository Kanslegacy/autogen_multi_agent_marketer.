"""
tools.py
--------
The one external tool in this system: a free web search using DuckDuckGo
(no API key required). This plays the role that Serper/Google Search
played in the reference architecture -- it's what the Web Search Agent
calls when the Router decides live/current information is needed.
"""

from typing import List, Dict

try:
    from duckduckgo_search import DDGS
except ImportError:  # package was renamed to `ddgs` in some environments
    from ddgs import DDGS


def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web for current marketing information, trends, competitor
    activity, or facts that may not be in the model's training data.

    Args:
        query: the search query.
        max_results: how many results to pull back.

    Returns:
        A formatted string of results (title, snippet, source URL) that
        the calling agent can read and summarize. Also used to populate
        the "Sources" panel in the Streamlit UI.
    """
    try:
        with DDGS() as ddgs:
            results: List[Dict] = list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        return f"WEB_SEARCH_ERROR: {e}"

    if not results:
        return "No web results found for that query."

    lines = []
    for r in results:
        title = r.get("title", "Untitled")
        body = r.get("body", "")
        href = r.get("href", "")
        lines.append(f"- {title}\n  {body}\n  Source: {href}")
    return "\n".join(lines)


def parse_sources_from_search_output(search_output: str) -> List[Dict[str, str]]:
    """Pulls (title, url) pairs out of web_search()'s formatted string so
    the UI can render them as clickable source links."""
    sources = []
    lines = search_output.splitlines()
    current_title = None
    for line in lines:
        line = line.strip()
        if line.startswith("- "):
            current_title = line[2:].strip()
        elif line.startswith("Source:"):
            url = line.replace("Source:", "").strip()
            sources.append({"title": current_title or url, "url": url})
    return sources
