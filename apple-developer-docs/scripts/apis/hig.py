"""
Human Interface Guidelines API
==============================

Search and fetch Apple's Human Interface Guidelines. Backed by the same DocC
JSON schema Apple uses for `/documentation/` — `fetch_documentation` does the
heavy lifting; this module adds discovery and a topic index.
"""

import urllib.parse
from typing import Dict, List, Optional

from ._utils import all_terms_match, fetch_json
from .apple_docs import fetch_documentation


PLATFORMS = ["ios", "macos", "tvos", "watchos", "visionos"]
PLATFORM_NAMES = {
    "ios": "iOS", "macos": "macOS", "tvos": "tvOS",
    "watchos": "watchOS", "visionos": "visionOS",
}

BASE_URL = "https://developer.apple.com/design/human-interface-guidelines"
DOCC_BASE = "https://developer.apple.com/tutorials/data/design/human-interface-guidelines"

# Top-level HIG categories — Apple keeps these stable; cheaper than discovering them.
ROOT_CATEGORIES = ("getting-started", "foundations", "patterns", "components", "inputs", "technologies")

def _fetch_node(slug: str) -> Optional[Dict]:
    return fetch_json(f"{DOCC_BASE}/{slug}.json")


def _iter_child_refs(data: Dict):
    """Yield (slug, title, url, abstract) for every topic referenced by `data`."""
    references = data.get('references', {})
    for section in data.get('topicSections', []):
        for ident in section.get('identifiers', []):
            ref = references.get(ident, {})
            url_path = ref.get('url') or ''
            title = ref.get('title') or ''
            if not url_path or not title:
                continue
            slug = url_path.rsplit('/', 1)[-1]
            yield slug, title, f"https://developer.apple.com{url_path}", _flatten_abstract(ref.get('abstract', []))


def _build_topic_index() -> List[Dict]:
    """
    BFS to depth 2 across the HIG tree (root → category → sub-page → topic).
    Collects every reachable page so callers can search both container titles
    ('Menus and actions') and leaf titles ('Buttons').
    """
    topics: List[Dict] = []
    seen_slugs: set = set()
    for category in ROOT_CATEGORIES:
        root_data = _fetch_node(category)
        if not root_data:
            continue
        category_title = root_data.get('metadata', {}).get('title', category)
        for slug, title, url, abstract in _iter_child_refs(root_data):
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            topics.append({
                "title": title, "slug": slug, "category": category_title,
                "url": url, "abstract": abstract,
            })
            child_data = _fetch_node(slug)
            if not child_data:
                continue
            for c_slug, c_title, c_url, c_abstract in _iter_child_refs(child_data):
                if c_slug in seen_slugs:
                    continue
                seen_slugs.add(c_slug)
                topics.append({
                    "title": c_title, "slug": c_slug, "category": category_title,
                    "url": c_url, "abstract": c_abstract,
                })
    return topics


def _flatten_abstract(items: list) -> str:
    return "".join(item.get('text', '') for item in items if item.get('type') == 'text').strip()


def search_hig(query: str, platform: Optional[str] = None, limit: int = 25) -> Dict:
    """
    Search Human Interface Guidelines topics by title and abstract.

    Args:
        query: Space-separated keywords (e.g., 'navigation', 'dark mode',
               'accessibility'). All terms must match somewhere in title +
               abstract.
        platform: Optional — currently used only to annotate the search; HIG
                  topics are mostly cross-platform.
        limit: Max results (default 25).

    Returns:
        {"query": str, "platform": str|None, "total_matches": int, "returned": int,
         "results": [{title, slug, category, url, abstract}, ...]}
    """
    topics = _build_topic_index()
    if not topics:
        return {
            "error": "fetch_failed",
            "message": "Could not build HIG topic index — check connectivity to developer.apple.com",
        }

    limit = max(0, limit)
    terms = [t.lower() for t in (query or "").split() if t]

    matches: List[Dict] = []
    for topic in topics:
        haystack = f"{topic['title']} {topic['abstract']}"
        if terms and not all_terms_match(haystack, terms):
            continue
        matches.append(topic)

    return {
        "query": query,
        "platform": platform,
        "total_matches": len(matches),
        "returned": min(len(matches), limit),
        "results": matches[:limit],
    }


def fetch_hig(topic: str) -> Dict:
    """
    Fetch the full content of a HIG topic by slug or title.

    Args:
        topic: Either a slug ('buttons', 'dark-mode') or a title substring
               ('Buttons', 'Dark Mode'). Resolved against the topic index.

    Returns:
        Same shape as `fetch_documentation` — title, abstract, declaration,
        discussion, parameters, returns, content_sections, etc.
        Or {error, candidates} when ambiguous, {error, message} when missing.
    """
    needle = (topic or '').lower().strip()
    if not needle:
        return {"error": "empty_topic", "message": "Pass a HIG topic slug or title"}

    # Fast path: when the input looks like a slug, try the URL directly
    # (~1 fetch instead of the ~36-fetch index walk).
    if needle.replace('-', '').replace('_', '').isalnum() and ' ' not in needle:
        slug = needle.replace('_', '-')
        direct = fetch_documentation(f"https://developer.apple.com/design/human-interface-guidelines/{slug}")
        if not direct.get('error'):
            return direct
        if direct.get('error') not in ('not_found',):
            return direct

    topics = _build_topic_index()
    if not topics:
        return {
            "error": "fetch_failed",
            "message": "Could not build HIG topic index — check connectivity to developer.apple.com",
        }

    matches = [t for t in topics if needle == t['slug'].lower() or needle == t['title'].lower()]
    if not matches:
        matches = [t for t in topics if needle in t['slug'].lower() or needle in t['title'].lower()]

    if not matches:
        return {"error": "topic_not_found", "message": f"No HIG topic matching '{topic}'"}
    if len(matches) > 1:
        return {
            "error": "ambiguous_topic",
            "candidates": [{"title": m['title'], "slug": m['slug'], "category": m['category']} for m in matches[:10]],
        }
    return fetch_documentation(matches[0]['url'])


# --- legacy URL-only helpers, retained for backwards compatibility ---

def search_hig_urls(query: str, platform: Optional[str] = None) -> Dict:
    """
    Generate search URLs for HIG. Prefer `search_hig` for structured results;
    this remains for callers that just want a search link.
    """
    encoded_query = urllib.parse.quote(query)
    results = {
        "query": query,
        "platform": platform,
        "base_url": BASE_URL,
        "search_url": f"https://www.google.com/search?q=site:developer.apple.com/design/human-interface-guidelines+{encoded_query}",
        "direct_link": BASE_URL,
    }
    if platform and platform.lower() in PLATFORMS:
        platform_lower = platform.lower()
        results["platform_url"] = f"{BASE_URL}/platforms/{platform_lower}"
        results["platform_search"] = (
            f"https://www.google.com/search?q=site:developer.apple.com/design/human-interface-guidelines+{platform_lower}+{encoded_query}"
        )
    return results


def list_hig_platforms() -> List[Dict]:
    """List all supported Apple platforms with HIG links."""
    return [
        {
            "platform": platform,
            "name": PLATFORM_NAMES.get(platform, platform),
            "url": f"{BASE_URL}/platforms/{platform}"
        }
        for platform in PLATFORMS
    ]
