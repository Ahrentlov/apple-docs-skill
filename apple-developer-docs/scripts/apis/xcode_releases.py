"""
Xcode Release Notes API
========================

Index of Apple's Xcode release notes. Pair with `fetch_documentation(url)` to
read a specific release-notes page — this module provides discovery only.
"""

from typing import Dict, List, Optional

from ._utils import fetch_json


INDEX_URL = "https://developer.apple.com/tutorials/data/documentation/xcode-release-notes.json"
DEVELOPER_BASE = "https://developer.apple.com"


def _fetch_index() -> Optional[Dict]:
    return fetch_json(INDEX_URL)


def _flatten_releases(data: Dict) -> List[Dict]:
    references = data.get('references', {})
    out: List[Dict] = []
    for section in data.get('topicSections', []):
        major = section.get('title', '')
        for ident in section.get('identifiers', []):
            ref = references.get(ident, {})
            url_path = ref.get('url') or ''
            out.append({
                "version": ref.get('title', ''),
                "major": major,
                "url": f"{DEVELOPER_BASE}{url_path}" if url_path else "",
            })
    return out


def list_xcode_release_notes(major: Optional[str] = None) -> Dict:
    """
    List every Xcode release-notes page Apple publishes.

    Args:
        major: Optional filter — substring matched against the major-version
               heading, e.g. '15', '16', '26'.

    Returns:
        {"count": int, "releases": [{version, major, url}, ...]}
        Pass `url` to `fetch_documentation` to read the actual notes.
    """
    data = _fetch_index()
    if not data:
        return {
            "error": "fetch_failed",
            "message": "Could not fetch the Xcode release-notes index from developer.apple.com",
        }
    releases = _flatten_releases(data)
    if major:
        needle = major.lower()
        releases = [r for r in releases if needle in r['major'].lower()]
    return {"count": len(releases), "releases": releases}


def get_xcode_release_notes_url(version: str) -> Dict:
    """
    Resolve a version string (e.g. '15.4', '16.3', '26.5 RC') to the matching
    release-notes URL. Pass that URL to `fetch_documentation` to read the notes.

    Args:
        version: Substring matched case-insensitively against the page title.

    Returns:
        {version, major, url} on a unique match, or {error, candidates} when
        ambiguous, or {error, available_count} when no match.
    """
    data = _fetch_index()
    if not data:
        return {
            "error": "fetch_failed",
            "message": "Could not fetch the Xcode release-notes index from developer.apple.com",
        }
    needle = (version or '').lower().strip()
    if not needle:
        return {"error": "empty_version", "message": "Pass a version like '15.4' or '16.3'"}
    releases = _flatten_releases(data)
    matches = [r for r in releases if needle in r['version'].lower()]
    if not matches:
        return {
            "error": "version_not_found",
            "message": f"No release notes match '{version}'",
            "available_count": len(releases),
        }
    if len(matches) > 1:
        return {
            "error": "ambiguous_version",
            "candidates": [{"version": m['version'], "url": m['url']} for m in matches[:10]],
        }
    return matches[0]
