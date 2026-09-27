"""
WWDC Sessions API
=================

Search WWDC sessions, fetch Apple's official transcripts, and fetch
community-written notes.

- Session metadata and notes come from the `wwdcnotes/wwdcnotes` GitHub repo:
  `Sources/Sessions/sessions.json` and
  `Sources/WWDCNotes/WWDCNotes.docc/WWDC{YY}/WWDC{YY}-{number}-{slug}.md`.
- Transcripts, chapters, and code samples come from Apple's session pages at
  `developer.apple.com/videos/play/wwdc{YYYY}/{number}/`.
"""

import urllib.request
import re
from html.parser import HTMLParser
from typing import Dict, List, Optional

from ._excerpts import select_section_lines, validate_section_selection
from ._utils import (open_url, read_bounded, UA_APP, all_terms_match, clamp_limit, fetch_json, fetch_page,
                     mark_untrusted, require_string)


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


class _SessionPageParser(HTMLParser):
    """Collect title, description, chapters, transcript paragraphs, and code samples from a session page."""

    _VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}

    def __init__(self):
        super().__init__()
        self.title, self.description = '', ''
        self.chapters: List[Dict] = []     # {start, title}
        self.paragraphs: List[Dict] = []   # {start, text}
        self.samples: List[Dict] = []      # {start, title, code}
        self._open: List[tuple] = []       # (tag, role) for each open element
        self._capture = None               # (field setter, depth of the element being captured)
        self._buffer: List[str] = []

    @staticmethod
    def _role(tag: str, attrs: Dict) -> Optional[str]:
        classes = (attrs.get('class') or '').split()
        if tag == 'li' and {'supplement', 'details'} <= set(classes):
            return 'details'
        if tag == 'section' and attrs.get('id') == 'transcript-content':
            return 'transcript'
        if tag == 'li' and 'chapter-item' in classes:
            return 'chapter'
        if tag == 'li' and 'sample-code-main-container' in classes:
            return 'sample'
        return None

    def _within(self, role: str) -> bool:
        return any(r == role for _, r in self._open)

    def _capture_into(self, setter) -> None:
        self._capture, self._buffer = (setter, len(self._open)), []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        role = self._role(tag, attrs)
        if tag not in self._VOID:
            self._open.append((tag, role))
        if tag == 'span' and attrs.get('data-start') and self.paragraphs and self.paragraphs[-1]['start'] is None \
                and self._within('transcript'):
            self.paragraphs[-1]['start'] = float(attrs['data-start'])
        if self._capture:
            if tag == 'br':
                self._buffer.append('\n')
            return
        if role == 'chapter':
            self.chapters.append({"start": float(attrs.get('data-start-time') or 0), "title": ''})
        elif role == 'sample':
            self.samples.append({"start": None, "title": '', "code": ''})
        elif tag == 'h1' and self._within('details') and not self.title:
            self._capture_into(lambda text: setattr(self, 'title', text))
        elif tag == 'p' and self._within('details') and self.title and not self.description:
            self._capture_into(lambda text: setattr(self, 'description', text))
        elif tag == 'a' and self._within('chapter'):
            self._capture_into(lambda text: self.chapters[-1].update(title=text))
        elif tag == 'a' and self._within('sample'):
            self.samples[-1]['start'] = float(attrs.get('data-start-time') or 0)
            self._capture_into(lambda text: self.samples[-1].update(title=text))
        elif tag == 'pre' and self._within('sample'):
            self._capture_into(lambda text: self.samples[-1].update(code=text))
        elif tag == 'p' and self._within('transcript'):
            self.paragraphs.append({"start": None, "text": ''})
            self._capture_into(lambda text: self.paragraphs[-1].update(text=text))

    def handle_endtag(self, tag):
        # Close the nearest matching element (and any unclosed children inside it).
        for i in range(len(self._open) - 1, -1, -1):
            if self._open[i][0] == tag:
                del self._open[i:]
                break
        if self._capture and len(self._open) < self._capture[1]:
            setter, _ = self._capture
            raw = ''.join(self._buffer)
            # Code keeps its layout; prose is whitespace-normalized.
            setter(raw.strip('\n') if tag == 'pre' else re.sub(r'\s+', ' ', raw).strip())
            self._capture = None

    def handle_data(self, data):
        if self._capture:
            self._buffer.append(data)


def _timestamp(seconds: float) -> str:
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    return f"{hours}:{rest // 60:02d}:{rest % 60:02d}" if hours else f"{rest // 60}:{rest % 60:02d}"


def _transcript_markdown(page: _SessionPageParser) -> str:
    """Render the session as Markdown: chapter and code-sample titles become '###' headings
    (so section selection matches them exactly), each followed by its [m:ss] start time."""
    lines = [f"# {page.title}", ""]
    if page.description:
        lines += [page.description, ""]
    lines += ["## Transcript", ""]
    chapters = sorted((c for c in page.chapters if c['title']), key=lambda c: c['start'])
    next_chapter = 0
    for paragraph in page.paragraphs:
        start = paragraph['start'] or 0.0
        while next_chapter < len(chapters) and chapters[next_chapter]['start'] <= start:
            chapter = chapters[next_chapter]
            lines += [f"### {chapter['title']}", "", f"[{_timestamp(chapter['start'])}] Chapter start", ""]
            next_chapter += 1
        lines += [f"[{_timestamp(start)}] {paragraph['text']}", ""]
    if page.samples:
        lines += ["## Code", ""]
        for sample in page.samples:
            lines += [f"### {sample['title']}", ""]
            if sample['start'] is not None:
                lines += [f"[{_timestamp(sample['start'])}] Shown in the session", ""]
            lines += ["```", sample['code'], "```", ""]
    return "\n".join(lines).rstrip() + "\n"


def fetch_wwdc_transcript(session_id: str, section=None, start_line=None, end_line=None, max_lines=200) -> Dict:
    """
    Fetch Apple's official transcript for a WWDC session, with chapters and code samples.

    Args:
        session_id: e.g. 'wwdc2025-256', 'wwdc25-256', or 'wwdc2025/256'.
        section: A chapter title (e.g. 'Framework foundations'), 'Transcript',
                 'Code', or a code-sample title; includes nested headings.
        start_line, end_line: Inclusive lines (relative to `section` when
                              given), capped by max_lines (1..1000).

    Returns (success):
        {id, title, description, url, chapters: [{title, start, url}],
         code_samples: int, content (Markdown)} plus excerpt metadata when a
         selector is given. Transcript paragraphs start with [m:ss]; append
         `?time=<seconds>` to `url` to cite a moment.

    Errors: invalid_session_id, session_not_found, transcript_unavailable,
    invalid_selection, section_not_found, ambiguous_section, line_out_of_range,
    plus fetch errors (http_error, timeout, network_error, fetch_failed).
    """
    err = require_string(session_id, 'session_id')
    if err: return err
    err = validate_section_selection(section, start_line, end_line, max_lines)
    if err: return err
    parts = _parse_session_id(session_id)
    if not parts:
        return {"error": "invalid_session_id", "message": "Use format wwdc2025-256"}

    canonical_id = f"wwdc{parts['four_year']}-{parts['number']}"
    url = f"https://developer.apple.com/videos/play/wwdc{parts['four_year']}/{parts['number']}/"
    fetched, err = fetch_page(url, url, 'text/html')
    if err and err['error'] != 'not_found':
        return err
    # Apple redirects unknown sessions to the year's video list instead of returning 404.
    if err or fetched.final_url.rstrip('/') != url.rstrip('/'):
        return {"error": "session_not_found", "message": f"Apple has no session page for {canonical_id}", "url": url}

    page = _SessionPageParser()
    page.feed(fetched.body.decode('utf-8', errors='replace'))
    page.close()
    if not any(p['text'] for p in page.paragraphs):
        return {"error": "transcript_unavailable", "message": f"The session page for {canonical_id} has no transcript", "url": url}

    content = _transcript_markdown(page)
    result = {
        "id": canonical_id, "title": page.title, "description": page.description, "url": url,
        "chapters": [{"title": c['title'], "start": _timestamp(c['start']), "url": f"{url}?time={int(c['start'])}"}
                     for c in page.chapters if c['title']],
        "code_samples": len(page.samples),
    }
    if section is None and start_line is None and end_line is None:
        result["content"] = content
        return mark_untrusted(result, "developer.apple.com WWDC session page", wrap_field="content")
    selection = select_section_lines(content, section, start_line, end_line, max_lines)
    if 'error' in selection:
        return dict(selection, url=url)
    result.update(selection)
    result["line_basis"] = "Markdown lines within the selected section" if section is not None else "Markdown lines of the rendered transcript"
    return mark_untrusted(result, "developer.apple.com WWDC session page", wrap_field="content")
