"""
Human Interface Guidelines API
==============================

Search and fetch Apple's Human Interface Guidelines. Backed by the same DocC
JSON schema Apple uses for `/documentation/` — `fetch_documentation` does the
heavy lifting; this module adds discovery and a topic index.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from ._utils import all_terms_match, clamp_limit, fetch_json, require_string
from .apple_docs import fetch_documentation


DOCC_BASE = "https://developer.apple.com/tutorials/data/design/human-interface-guidelines"

# Top-level HIG categories — Apple keeps these stable; cheaper than discovering them.
ROOT_CATEGORIES = ("getting-started", "foundations", "patterns", "components", "inputs", "technologies")

# Built index is memoized for the process lifetime so search_hig + fetch_hig in
# one script don't each pay the full ~40-fetch walk.
_topic_index_cache: Optional[List[Dict]] = None

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

    Each BFS level is fetched concurrently so the ~40-page walk stays well under
    the sandbox timeout. The result is memoized for the process lifetime.
    """
    global _topic_index_cache
    if _topic_index_cache is not None:
        return _topic_index_cache

    topics: List[Dict] = []
    seen_slugs: set = set()

    with ThreadPoolExecutor(max_workers=8) as pool:
        # Level 1: fetch all root categories at once.
        root_data_by_category = dict(zip(ROOT_CATEGORIES, pool.map(_fetch_node, ROOT_CATEGORIES)))

        # Record each category's direct children, queueing their slugs to expand.
        children_to_expand: List[tuple] = []  # (slug, category_title)
        for category, root_data in root_data_by_category.items():
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
                children_to_expand.append((slug, category_title))

        # Level 2: fetch every discovered child page at once.
        child_slugs = [slug for slug, _ in children_to_expand]
        child_data_list = list(pool.map(_fetch_node, child_slugs))
        for (_, category_title), child_data in zip(children_to_expand, child_data_list):
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

    if topics:  # only cache a real index, so a transient failure can retry
        _topic_index_cache = topics
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
    err = require_string(query, 'query')
    if err: return err
    topics = _build_topic_index()
    if not topics:
        return {
            "error": "fetch_failed",
            "message": "Could not build HIG topic index — check connectivity to developer.apple.com",
        }

    limit = clamp_limit(limit)
    terms = [t.lower() for t in query.split() if t]

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
    err = require_string(topic, 'topic')
    if err: return err
    needle = topic.lower().strip()
    if not needle:
        return {"error": "empty_topic", "message": "Pass a HIG topic slug or title"}
    if len(needle) > 200 or '/' in needle or '\x00' in needle:
        return {"error": "invalid_topic", "message": "Topic must be a single slug or title (no slashes, ≤200 chars)"}

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


