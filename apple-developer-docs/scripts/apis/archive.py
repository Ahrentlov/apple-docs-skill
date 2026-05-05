"""
Apple Documentation Archive API
================================

Search Apple's legacy documentation archive (https://developer.apple.com/library/archive/).
~5200 archived documents: Technical Notes, Technical Q&As, Sample Code, Guides,
Release Notes, Articles, and Getting Started material.

Backed by the same `library.json` the archive's navigation page loads client-side.
"""

import html
import json
import re
from typing import Dict, List, Optional

from ._utils import UA_APPLE_BROWSER, all_terms_match, fetch_json


ARCHIVE_BASE = "https://developer.apple.com/library/archive"
LIBRARY_JSON_URL = f"{ARCHIVE_BASE}/navigation/library.json"

COLUMNS = {
    "name": 0, "id": 1, "type": 2, "date": 3, "updateSize": 4,
    "topic": 5, "framework": 6, "release": 7, "subtopic": 8,
    "url": 9, "sortOrder": 10, "displayDate": 11, "platform": 12,
}


TOPIC_TARGETS = {"Resource Types": "type", "Technologies": "framework", "Topics": "topic"}
_TRAILING_COMMA_RE = re.compile(r',(\s*[}\]])')


def _decode_library_json(text: str) -> Dict:
    # library.json uses JS-style trailing commas (evalJSON-compatible).
    return json.loads(_TRAILING_COMMA_RE.sub(r'\1', text))


class ArchiveAPI:
    def _fetch_library(self) -> Optional[Dict]:
        return fetch_json(
            LIBRARY_JSON_URL,
            ua=UA_APPLE_BROWSER,
            decoder=_decode_library_json,
        )

    def _build_maps(self, data: Dict) -> Dict[str, Dict[int, str]]:
        maps: Dict[str, Dict[int, str]] = {"topic": {}, "framework": {}, "type": {}}
        for topic in data.get('topics', []):
            target = TOPIC_TARGETS.get(topic.get('name', ''))
            if not target:
                continue
            for entry in topic.get('contents', []):
                raw_key = entry.get('key')
                if raw_key is None:
                    continue
                # contents keys are strings; document rows store ints.
                try:
                    key = int(raw_key)
                except (TypeError, ValueError):
                    key = raw_key
                maps[target][key] = html.unescape(entry.get('name', ''))
        return maps

    def _resolve_url(self, relative: str) -> str:
        if not relative:
            return ""
        if relative.startswith('http'):
            return relative
        # library.json paths are relative to /library/archive/navigation/
        if relative.startswith('../'):
            return f"{ARCHIVE_BASE}/{relative[3:]}"
        return f"{ARCHIVE_BASE}/navigation/{relative}"

    def _doc_to_dict(self, row: List, maps: Dict[str, Dict], name: str) -> Dict:
        def col(key):
            return row[COLUMNS[key]]
        return {
            "name": name,
            "id": col("id"),
            "resource_type": maps["type"].get(col("type"), ""),
            "topic": maps["topic"].get(col("topic"), ""),
            "framework": maps["framework"].get(col("framework"), ""),
            "platform": col("platform") or "",
            "date": col("displayDate") or col("date") or "",
            "url": self._resolve_url(col("url")),
        }


_api = ArchiveAPI()


def search_archive(
    query: str,
    platform: Optional[str] = None,
    framework: Optional[str] = None,
    resource_type: Optional[str] = None,
    topic: Optional[str] = None,
    limit: int = 25,
) -> Dict:
    """
    Search Apple's Documentation Archive (~5200 legacy docs).

    Args:
        query: Space-separated keywords matched against the document title (case-insensitive).
        platform: Optional filter: 'iOS', 'macOS', 'tvOS', 'watchOS', 'Safari', 'Xcode Developer Tools', etc.
                  Matches when the platform string contains this value.
        framework: Optional framework/technology name (e.g., 'UIKit', 'Core Data', 'WebKit').
        resource_type: Optional type filter: 'Technical Note', 'Technical Q&A', 'Sample Code',
                       'Guide', 'Release Notes', 'Article', 'Getting Started', 'Xcode Tasks'.
        topic: Optional topic category (e.g., 'Audio', 'Networking', 'Graphics & Animation').
        limit: Max results to return (default 25).

    Returns:
        {"query": str, "total_matches": int, "returned": int, "results": [doc, ...]}
        Each doc: {name, id, resource_type, topic, framework, platform, date, url}
    """
    data = _api._fetch_library()
    if not data:
        return {
            "error": "fetch_failed",
            "message": "Could not fetch library.json — check connectivity to developer.apple.com",
        }

    limit = max(0, limit)
    maps = _api._build_maps(data)
    name_col = COLUMNS["name"]
    doc_names = [html.unescape(row[name_col] or "") for row in data.get('documents', [])]
    terms = [t.lower() for t in (query or "").split() if t]

    platform_lc = platform.lower() if platform else None
    framework_lc = framework.lower() if framework else None
    rt_lc = resource_type.lower() if resource_type else None
    topic_lc = topic.lower() if topic else None

    type_col = COLUMNS["type"]
    topic_col = COLUMNS["topic"]
    framework_col = COLUMNS["framework"]
    platform_col = COLUMNS["platform"]
    date_col = COLUMNS["date"]

    matches: List[tuple] = []
    for idx, row in enumerate(data.get('documents', [])):
        if terms and not all_terms_match(doc_names[idx], terms):
            continue
        if platform_lc and platform_lc not in (row[platform_col] or "").lower():
            continue
        if framework_lc and framework_lc not in maps["framework"].get(row[framework_col], "").lower():
            continue
        if rt_lc and rt_lc not in maps["type"].get(row[type_col], "").lower():
            continue
        if topic_lc and topic_lc not in maps["topic"].get(row[topic_col], "").lower():
            continue

        matches.append((row[date_col] or "", idx, row))

    matches.sort(key=lambda triple: triple[0], reverse=True)

    results = [_api._doc_to_dict(row, maps, doc_names[idx]) for _, idx, row in matches[:limit]]

    return {
        "query": query,
        "filters": {
            "platform": platform, "framework": framework,
            "resource_type": resource_type, "topic": topic,
        },
        "total_matches": len(matches),
        "returned": len(results),
        "results": results,
    }


def _list_archive_names(bucket: str) -> Optional[List[str]]:
    data = _api._fetch_library()
    if data is None:
        return None
    maps = _api._build_maps(data)
    return sorted({v for v in maps[bucket].values() if v})


def list_archive_frameworks() -> Dict:
    """List all framework/technology names available as filters in the archive."""
    names = _list_archive_names("framework")
    if names is None:
        return {"error": "fetch_failed", "message": "Could not fetch library.json"}
    return {"count": len(names), "frameworks": names}


def list_archive_topics() -> Dict:
    """List all topic categories available as filters in the archive."""
    names = _list_archive_names("topic")
    if names is None:
        return {"error": "fetch_failed", "message": "Could not fetch library.json"}
    return {"count": len(names), "topics": names}


def list_archive_resource_types() -> Dict:
    """List all resource-type filters in the archive (Technical Notes, Sample Code, etc.)."""
    names = _list_archive_names("type")
    if names is None:
        return {"error": "fetch_failed", "message": "Could not fetch library.json"}
    return {"count": len(names), "resource_types": names}
