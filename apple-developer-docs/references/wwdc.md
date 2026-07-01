# WWDC Sessions

Search Apple's WWDC catalog and fetch community-written notes. Backed by the
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
    "content": str,       # raw markdown
    "source_url": str,    # raw.githubusercontent.com URL
    "permalink": str      # wwdcnotes.com URL
}
```

**Errors:**
- `invalid_session_id` — bad format.
- `year_not_indexed` — no notes folder for that year.
- `session_not_found` — folder exists but no file matches; includes `permalink`.
- `fetch_failed` — network / decode error.

**Example:**
```python
hits = search_wwdc_sessions("concurrency", year=2023, limit=3)
session = fetch_wwdc_session(hits["results"][0]["id"])
result = {"title": session["title"], "first_500": session["content"][:500]}
```
