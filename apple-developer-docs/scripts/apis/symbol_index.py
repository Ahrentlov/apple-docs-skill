"""
Framework Symbol Index
======================

Search a framework's complete page list using Apple's navigator index
(`/tutorials/data/index/<framework>`), the same tree that drives the sidebar on
developer.apple.com. One fetch covers every page Apple lists for the framework,
so an empty result is meaningful within that index.
"""

import json
import re
import urllib.parse
from typing import Dict, List, Optional, Tuple

from ._utils import fetch_page, mark_untrusted


INDEX_BASE = "https://developer.apple.com/tutorials/data/index"

# Flattened indexes are memoized per framework for the process lifetime; failures are not cached.
_index_cache: Dict[str, List[Dict]] = {}


def _flatten(nodes: list) -> List[Dict]:
    """One entry per page path, keeping every place the page appears in the tree."""
    entries: Dict[str, Dict] = {}

    def walk(children: list, chain: List[str]) -> None:
        group = None
        for node in children:
            if not isinstance(node, dict):
                continue
            title, kind, path = node.get('title', ''), node.get('type', ''), node.get('path')
            if kind == 'groupMarker':
                group = title
                continue
            location = chain + ([group] if group else [])
            if path and not node.get('external'):
                entry = entries.setdefault(path, {
                    "title": title, "kind": kind, "url": f"https://developer.apple.com{path}",
                    "deprecated": bool(node.get('deprecated')), "beta": bool(node.get('beta')), "locations": [],
                })
                entry["locations"].append(" > ".join(location))
            walk(node.get('children') or [], location + [title])

    walk(nodes, [])
    return list(entries.values())


def _load_index(framework: str) -> Tuple[Optional[List[Dict]], Optional[Dict]]:
    if framework in _index_cache:
        return _index_cache[framework], None
    framework_url = f"https://developer.apple.com/documentation/{framework}"
    page, err = fetch_page(f"{INDEX_BASE}/{framework}", framework_url, 'application/json')
    if err:
        if err['error'] == 'not_found':
            err['message'] = f"Apple publishes no navigator index for '{framework}'"
        return None, err
    try:
        data = json.loads(page.body)
    except ValueError as exc:
        return None, {"error": "invalid_json", "message": str(exc), "url": framework_url}
    nodes = data.get('interfaceLanguages', {}).get('swift') if isinstance(data, dict) else None
    if not isinstance(nodes, list):
        return None, {"error": "invalid_schema", "message": "Expected a navigator index with a Swift tree", "url": framework_url}
    _index_cache[framework] = _flatten(nodes)
    return _index_cache[framework], None


def _rank(entry: Dict, query: str) -> int:
    """Exact title first (case-sensitive), then exact names ignoring case (title or
    URL name), then name prefixes, then other matches; Apple's order within each."""
    if entry['title'] == query:
        return 0
    needle = query.casefold()
    names = (entry['title'].casefold(), urllib.parse.unquote(entry['url'].rsplit('/', 1)[-1]).casefold())
    if needle in names:
        return 1
    return 2 if any(name.startswith(needle) for name in names) else 3


def search_symbols(framework: str, query: str = '', kind: Optional[str] = None, deprecated: Optional[bool] = None,
                   beta: Optional[bool] = None, limit: int = 20, offset: int = 0) -> Dict:
    """Search every page in a framework's navigator index.

    Args:
        framework: Framework slug, e.g. 'swiftui', 'uikit', 'foundation'.
        query: Space-separated terms; each must occur in the title (a
               declaration for members) or the URL's last path component.
               Empty matches everything, for filter-only listings.
        kind: Page kind such as 'struct', 'method', 'property', 'protocol',
              'article', or 'sampleCode' (case-insensitive).
        deprecated, beta: When set, keep only pages with that flag value.
        limit: 1..200 results per call; offset pages through the matches.
    """
    if not isinstance(framework, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', framework):
        return {'error': 'invalid_input', 'message': 'framework must be a framework slug, such as swiftui'}
    if not isinstance(query, str):
        return {'error': 'invalid_input', 'message': 'query must be a string'}
    if kind is not None and (not isinstance(kind, str) or not kind.strip()):
        return {'error': 'invalid_input', 'message': 'kind must be a nonempty string'}
    if any(flag is not None and not isinstance(flag, bool) for flag in (deprecated, beta)):
        return {'error': 'invalid_input', 'message': 'deprecated and beta must be True, False, or None'}
    if type(limit) is not int or not 1 <= limit <= 200 or type(offset) is not int or offset < 0:
        return {'error': 'invalid_input', 'message': 'limit must be 1..200 and offset a non-negative integer'}

    framework = framework.lower()
    entries, err = _load_index(framework)
    if err: return err

    needle = query.strip().casefold()
    terms = needle.split()
    matches = [
        e for e in entries
        if (kind is None or e['kind'].casefold() == kind.strip().casefold())
        and (deprecated is None or e['deprecated'] == deprecated)
        and (beta is None or e['beta'] == beta)
        and all(t in f"{e['title']} {urllib.parse.unquote(e['url'].rsplit('/', 1)[-1])}".casefold() for t in terms)
    ]
    if needle:
        matches.sort(key=lambda e: _rank(e, query.strip()))
    page = matches[offset:offset + limit]
    return mark_untrusted({
        'framework': framework, 'query': query, 'kind': kind, 'deprecated': deprecated, 'beta': beta,
        'results': page, 'returned': len(page), 'total_matches': len(matches), 'offset': offset,
        'next_offset': offset + limit if offset + limit < len(matches) else None,
        'indexed_pages': len(entries), 'index_url': f"{INDEX_BASE}/{framework}",
        'search_scope': "every page in Apple's navigator index for this framework (Swift); pages owned by other frameworks are excluded",
    }, 'developer.apple.com navigator index')
