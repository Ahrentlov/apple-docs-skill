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
import time
import urllib.request
from typing import Dict, List, Optional


ARCHIVE_BASE = "https://developer.apple.com/library/archive"
LIBRARY_JSON_URL = f"{ARCHIVE_BASE}/navigation/library.json"

COLUMNS = {
    "name": 0, "id": 1, "type": 2, "date": 3, "updateSize": 4,
    "topic": 5, "framework": 6, "release": 7, "subtopic": 8,
    "url": 9, "sortOrder": 10, "displayDate": 11, "platform": 12,
}


TOPIC_TARGETS = {"Resource Types": "type", "Technologies": "framework", "Topics": "topic"}
_TRAILING_COMMA_RE = re.compile(r',(\s*[}\]])')


class ArchiveAPI:
    def __init__(self):
        self.cache: Optional[Dict] = None
        self.maps: Optional[Dict[str, Dict[int, str]]] = None
        self.cache_time = 0.0
        self.cache_ttl = 3600

    def _fetch_library(self) -> Optional[Dict]:
        if self.cache and (time.time() - self.cache_time) < self.cache_ttl:
            return self.cache
        try:
            req = urllib.request.Request(
                LIBRARY_JSON_URL,
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                raw = response.read().decode('utf-8')
            # library.json uses JS-style trailing commas (evalJSON-compatible).
            data = json.loads(_TRAILING_COMMA_RE.sub(r'\1', raw))
            self.cache = data
            self.maps = self._build_maps(data)
            self.cache_time = time.time()
            return data
        except Exception:
            return None

    def _build_maps(self, data: Dict) -> Dict[str, Dict[int, str]]:
        maps: Dict[str, Dict[int, str]] = {"topic": {}, "framework": {}, "type": {}, "subtopic": {}}
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
                label = html.unescape(entry.get('name', ''))
                maps[target][key] = label
                if target == 'topic':
                    maps['subtopic'][key] = label
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

    def _doc_to_dict(self, row: List, maps: Dict[str, Dict]) -> Dict:
        def col(name):
            return row[COLUMNS[name]]
        return {
            "name": html.unescape(col("name") or ""),
            "id": col("id"),
            "resource_type": maps["type"].get(col("type"), ""),
            "topic": maps["topic"].get(col("topic"), ""),
            "framework": maps["framework"].get(col("framework"), ""),
            "platform": col("platform") or "",
            "date": col("displayDate") or col("date") or "",
            "url": self._resolve_url(col("url")),
        }


_api = ArchiveAPI()


def _matches(text: str, terms: List[str]) -> bool:
    t = text.lower()
    return all(term in t for term in terms)


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
    if not data or _api.maps is None:
        return {
            "error": "Failed to fetch library.json",
            "suggestion": "Check connectivity to developer.apple.com"
        }

    limit = max(0, limit)
    maps = _api.maps
    terms = [t.lower() for t in (query or "").split() if t]

    platform_lc = platform.lower() if platform else None
    framework_lc = framework.lower() if framework else None
    rt_lc = resource_type.lower() if resource_type else None
    topic_lc = topic.lower() if topic else None

    name_col = COLUMNS["name"]
    type_col = COLUMNS["type"]
    topic_col = COLUMNS["topic"]
    framework_col = COLUMNS["framework"]
    platform_col = COLUMNS["platform"]
    date_col = COLUMNS["date"]

    matches: List[tuple] = []
    for row in data.get('documents', []):
        if terms:
            raw_name = html.unescape(row[name_col] or "").lower()
            if not _matches(raw_name, terms):
                continue
        if platform_lc and platform_lc not in (row[platform_col] or "").lower():
            continue
        if framework_lc and framework_lc not in maps["framework"].get(row[framework_col], "").lower():
            continue
        if rt_lc and rt_lc not in maps["type"].get(row[type_col], "").lower():
            continue
        if topic_lc and topic_lc not in maps["topic"].get(row[topic_col], "").lower():
            continue

        matches.append((row[date_col] or "", row))

    matches.sort(key=lambda pair: pair[0], reverse=True)

    results = [_api._doc_to_dict(row, maps) for _, row in matches[:limit]]

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
    if _api._fetch_library() is None or _api.maps is None:
        return None
    return sorted({v for v in _api.maps[bucket].values() if v})


def list_archive_frameworks() -> Dict:
    """List all framework/technology names available as filters in the archive."""
    names = _list_archive_names("framework")
    if names is None:
        return {"error": "Failed to fetch library.json"}
    return {"count": len(names), "frameworks": names}


def list_archive_topics() -> Dict:
    """List all topic categories available as filters in the archive."""
    names = _list_archive_names("topic")
    if names is None:
        return {"error": "Failed to fetch library.json"}
    return {"count": len(names), "topics": names}


def list_archive_resource_types() -> Dict:
    """List all resource-type filters in the archive (Technical Notes, Sample Code, etc.)."""
    names = _list_archive_names("type")
    if names is None:
        return {"error": "Failed to fetch library.json"}
    return {"count": len(names), "resource_types": names}
