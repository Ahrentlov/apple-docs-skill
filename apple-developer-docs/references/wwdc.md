# WWDC Sessions

Search a community-maintained WWDC catalog and fetch community-written notes. Backed by the
`wwdcnotes/wwdcnotes` GitHub repo: `Sources/Sessions/sessions.json` (metadata)
and `Sources/WWDCNotes/WWDCNotes.docc/WWDC{YY}/WWDC{YY}-{number}-{slug}.md`
(notes).

## search_wwdc_sessions(query: str, year: int | None = None, limit: int = 25) -> Dict

Search ~3000 sessions by title + description.

**Parameters:**
- `query`: Space-separated keywords. All terms must match in title + description.
- `year`: Optional — full year (`2023`) or 2-digit (`23`).
- `limit`: Max results.

**Returns:**
```python
{
    "query": str,
    "year": int | None,
    "total_matches": int,
    "returned": int,
    "results": [
        {
            "id": str,            # "wwdc2023-10154"
            "title": str,
            "year": int,
            "code": str,          # session number
            "description": str,
            "permalink": str
        }
    ]
}
```

Sorted newest year first, then by session code.

**Errors:** `fetch_failed`, `invalid_argument` (non-int `year`).

---

## fetch_wwdc_session(session_id: str) -> Dict

Fetch the community-written notes (markdown) for a session.

**Parameters:**
- `session_id`: `wwdc2023-10154`, `wwdc23-10154`, or `wwdc2023/10154`.

**Returns (success):**
```python
{
    "id": str,            # canonical wwdc{4-year}-{number}
    "title": str,
    "year": int,
    "code": str,
    "content": str,       # markdown wrapped in external-content markers
    "source_url": str,    # raw.githubusercontent.com URL
    "permalink": str      # wwdcnotes.com URL
}
```

**Errors:**
- `invalid_session_id` — bad format.
- `session_not_found` — folder exists but no file matches; includes `permalink`.
- `fetch_failed` — index/listing unavailable, network/decode failure, or notes exceed 500,000 bytes. A missing year folder and a network failure are not reliably distinguishable.

**Example:**
```python
hits = search_wwdc_sessions("concurrency", year=2023, limit=3)
if 'error' in hits or not hits['results']:
    result = hits
else:
    session = fetch_wwdc_session(hits['results'][0]['id'])
    if 'error' in session:
        result = session
    else:
        result = {'title': session['title'], 'source_url': session['source_url'],
                  'community_notes_excerpt': session['content'][:1500]}
```

Search output includes `truncated`, `search_scope`, and `content_notice`. Session
metadata and notes are community-maintained, with incomplete coverage; cite the
notes actually read and verify API semantics against Apple documentation.
