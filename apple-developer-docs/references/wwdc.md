# WWDC Sessions

Search a community-maintained WWDC catalog, read Apple's official transcripts,
and fetch community-written notes. The catalog and notes come from the
`wwdcnotes/wwdcnotes` GitHub repo: `Sources/Sessions/sessions.json` (metadata)
and `Sources/WWDCNotes/WWDCNotes.docc/WWDC{YY}/WWDC{YY}-{number}-{slug}.md`
(notes). Transcripts come from Apple's session pages at
`https://developer.apple.com/videos/play/wwdc{YYYY}/{number}/`.

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

## fetch_wwdc_transcript(session_id, section=None, start_line=None, end_line=None, max_lines=200) -> Dict

Fetch Apple's transcript for a session, with its chapters and code samples, as
Markdown. Prefer this over community notes when quoting what Apple said.

**Parameters:**
- `session_id`: `wwdc2025-256`, `wwdc25-256`, or `wwdc2025/256`.
- `section`: a chapter title (`'Framework foundations'`), a code-sample title
  (`'Toolbar spacer'`), `'Transcript'`, or `'Code'`. Includes nested headings.
- `start_line`, `end_line`, `max_lines`: as in `fetch_documentation`; relative
  to `section` when given.

**Returns (success):**
```python
{
    "id": str,             # canonical wwdc{4-year}-{number}
    "title": str,
    "description": str,
    "url": str,            # session page; append ?time=<seconds> to cite a moment
    "chapters": [{"title": str, "start": "6:59", "url": str}],
    "code_samples": int,
    "content": str,        # Markdown wrapped in external-content markers
    # with a selector: section, total_lines, start_line, end_line, returned_lines,
    # selection_truncated, excerpt_partial, next_start_line, line_basis
}
```

`content` layout: `# Title`, the description, `## Transcript` with one
`### <chapter>` per chapter, paragraphs prefixed with `[m:ss]`, then `## Code`
with one `### <sample title>` and fenced code block per sample.

**Errors:** `invalid_session_id`; `session_not_found` (Apple has no page for
that session; older sessions have been removed from the site);
`transcript_unavailable`; `invalid_selection`, `section_not_found`,
`ambiguous_section`, `line_out_of_range`; and fetch errors.

```python
result = fetch_wwdc_transcript("wwdc2025-256", section="Framework foundations", max_lines=40)
```

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
notes actually read and verify API semantics against Apple documentation or the
session's transcript.
