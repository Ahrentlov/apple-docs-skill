"""
WWDC Notes API
==============

Search Apple's WWDC sessions and fetch community-written notes.

Backed by the `wwdcnotes/wwdcnotes` GitHub repo:
- `Sources/Sessions/sessions.json` — community-maintained session metadata.
- `Sources/WWDCNotes/WWDCNotes.docc/WWDC{YY}/WWDC{YY}-{number}-{slug}.md` — note content.
"""

import urllib.request
import re
from typing import Dict, List, Optional

from ._utils import open_url, read_bounded, UA_APP, all_terms_match, clamp_limit, fetch_json, mark_untrusted, require_string


SESSIONS_JSON_URL = "https://raw.githubusercontent.com/wwdcnotes/wwdcnotes/main/Sources/Sessions/sessions.json"
GITHUB_API_DIR = "https://api.github.com/repos/wwdcnotes/wwdcnotes/contents/Sources/WWDCNotes/WWDCNotes.docc"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/wwdcnotes/wwdcnotes/main/Sources/WWDCNotes/WWDCNotes.docc"


def _fetch_sessions() -> Optional[Dict]:
    return fetch_json(SESSIONS_JSON_URL)


def _parse_session_id(session_id: str) -> Optional[Dict]:
    """Normalize 'wwdc2023-10154' / 'wwdc2023/10154' → {'four_year', 'two_year', 'number'}."""
    match = re.fullmatch(r"wwdc(20[0-9]{2}|[0-9]{2})[-/]([0-9]{1,6})", session_id.strip().lower())
    if not match:
        return None
    year, number = match.groups()
    return {"four_year": year if len(year) == 4 else "20" + year, "two_year": year[-2:], "number": number}


def _fetch_year_dir(two_year: str) -> Optional[List[str]]:
    """List filenames in WWDC{YY}/ to resolve session number → exact .md filename."""
    entries = fetch_json(
        f"{GITHUB_API_DIR}/WWDC{two_year}",
        extra_headers={'Accept': 'application/vnd.github+json'},
    )
    if not isinstance(entries, list):
        return None
    return [e['name'] for e in entries if e.get('type') == 'file' and e.get('name', '').endswith('.md')]


def search_wwdc_sessions(query: str, year: Optional[int] = None, limit: int = 25) -> Dict:
    """
    Search WWDC sessions by title or description (across indexed WWDC years).

    Args:
        query: Space-separated keywords. All terms must match somewhere in
               title + description.
        year: Optional filter — full year (e.g., 2023) or 2-digit (e.g., 23).
        limit: Max results (default 25).

    Returns:
        {"query": str, "year": int|None, "total_matches": int, "returned": int,
         "results": [{id, title, year, code, description, permalink}, ...]}
    """
    err = require_string(query, 'query')
    if err: return err

    year_match: Optional[int] = None
    if year is not None:
        try:
            if isinstance(year, bool) or not re.fullmatch(r"[0-9]{2}|20[0-9]{2}", str(year)):
                raise ValueError("Use a two- or four-digit WWDC year")
            y = int(year)
        except (TypeError, ValueError):
            return {
                "error": "invalid_argument",
                "message": f"`year` must be an integer (e.g. 2023 or 23); got {year!r}",
            }
        year_match = y if y > 99 else 2000 + y

    sessions = _fetch_sessions()
    if not sessions:
        return {
            "error": "fetch_failed",
            "message": "Could not fetch the WWDC sessions index from wwdcnotes",
        }

    limit = clamp_limit(limit)
    terms = [t.lower() for t in query.split() if t]
    matches: List[Dict] = []
    for sid, entry in sessions.items():
        if year_match is not None and entry.get('year') != year_match:
            continue
        if terms:
            haystack = f"{entry.get('title', '')} {entry.get('description', '')}"
            if not all_terms_match(haystack, terms):
                continue
        matches.append({
            "id": sid,
            "title": entry.get('title', ''),
            "year": entry.get('year'),
            "code": entry.get('code', ''),
            "description": entry.get('description', ''),
            "permalink": entry.get('permalink', ''),
        })

    matches.sort(key=lambda m: (-(m['year'] or 0), m['code']))

    return mark_untrusted({
        "query": query,
        "truncated": len(matches) > limit,
        "search_scope": "community-maintained WWDC session index",
        "year": year,
        "total_matches": len(matches),
        "returned": min(len(matches), limit),
        "results": matches[:limit],
    }, "github.com/wwdcnotes/wwdcnotes session metadata")


def fetch_wwdc_session(session_id: str) -> Dict:
    """
    Fetch the community-written notes for a WWDC session.

    Args:
        session_id: e.g. 'wwdc2023-10154', 'wwdc23-10154', or 'wwdc2023/10154'.

    Returns (success):
        {id, title, year, code, content (markdown), source_url, permalink}

    Errors:
        {error: 'invalid_session_id', message}                      — bad format
        {error: 'session_not_found', message, permalink}            — folder exists but no file matches
        {error: 'fetch_failed', message, url}                       — network / decode error
    """
    err = require_string(session_id, 'session_id')
    if err: return err
    parts = _parse_session_id(session_id)
    if not parts:
        return {"error": "invalid_session_id", "message": "Use format wwdc2023-10154"}

    listing = _fetch_year_dir(parts["two_year"])
    if listing is None:
        return {
            "error": "fetch_failed",
            "message": f"Could not list WWDC {parts['four_year']} notes; the folder may be missing or GitHub unavailable/rate-limited",
        }

    prefix = f"WWDC{parts['two_year']}-{parts['number']}-"
    filename = next((f for f in listing if f.startswith(prefix)), None)
    if not filename:
        return {
            "error": "session_not_found",
            "message": f"No notes file matching {prefix}* in WWDC{parts['two_year']}/",
            "permalink": f"https://wwdcnotes.com/notes/wwdc{parts['four_year']}/{parts['number']}",
        }

    raw_url = f"{GITHUB_RAW_BASE}/WWDC{parts['two_year']}/{filename}"
    try:
        req = urllib.request.Request(raw_url, headers={'User-Agent': UA_APP})
        with open_url(req, timeout=15) as response:
            content = read_bounded(response, 500_000).decode('utf-8', errors='replace')
    except Exception as e:
        return {"error": "fetch_failed", "message": str(e), "url": raw_url}

    sessions = _fetch_sessions() or {}
    canonical_id = f"wwdc{parts['four_year']}-{parts['number']}"
    meta = sessions.get(canonical_id, {})

    return mark_untrusted({
        "id": canonical_id,
        "title": meta.get('title', ''),
        "year": meta.get('year', int(parts["four_year"])),
        "code": parts['number'],
        "content": content,
        "source_url": raw_url,
        "permalink": meta.get('permalink') or f"https://wwdcnotes.com/notes/wwdc{parts['four_year']}/{parts['number']}",
    }, "wwdcnotes.com (community-written notes)", wrap_field="content")


