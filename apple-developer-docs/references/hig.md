# Human Interface Guidelines

Search and fetch Apple's HIG. Search walks the DocC JSON topic tree; `fetch_hig`
resolves a topic and returns `fetch_documentation` output for its page.

## search_hig(query: str, platform: str | None = None, limit: int = 25) -> Dict

Search HIG topics by title + abstract in a depth-two index. `platform` only
annotates the request; it does not filter HIG content. Results include
`platform_filter_applied: False`, `partial`, `failed_pages`, `truncated`, and
`search_scope`. Incomplete indexes are not cached as complete results.

**Returns:**
```python
{
    "query": str,
    "platform": str | None,
    "total_matches": int,
    "returned": int,
    "results": [
        {
            "title": str,         # "Buttons"
            "slug": str,          # "buttons"
            "category": str,      # "Foundations", "Patterns", "Components", ...
            "url": str,
            "abstract": str
        }
    ]
}
```

**Errors:** `fetch_failed`.

---

## fetch_hig(topic: str, section=None, start_line=None, end_line=None, max_lines=200, format='markdown') -> Dict

Fetch a HIG topic by slug or title. Markdown by default; `format='json'` returns the structured DocC fields.

**Parameters:**
- `topic`: `'buttons'` (slug) or `'Dark Mode'` (title substring).
- `section`: exact heading title (`'Help buttons'`) or the full heading path
  from the page title (`'Buttons > Platform considerations > macOS'`). An
  ambiguous or missing title returns `candidates` with each heading's `path`.
- `start_line`, `end_line`: inclusive lines, relative to `section` when one is
  given, capped by `max_lines` (1..1000).
  Selectors only apply when given; without them the whole page is returned.
- `format`: `'markdown'` (default) or `'json'`.

**Fast path:** when the input looks like a slug (alphanumeric + dashes), the
function tries the page directly (~1 fetch). Falls back to the full topic-index
walk on title-substring lookups.

**Returns:** Same shape as [`fetch_documentation`](apple-docs.md) for the chosen
format. Markdown keeps tables, image alt text, and the page's change log.

**Errors:** `empty_topic`, `invalid_topic`, `invalid_selection`, `topic_not_found`, `ambiguous_topic` (with `candidates` list), `section_not_found` / `ambiguous_section` (with `candidates`), `line_out_of_range`, plus `fetch_documentation`'s error variants.

**Example:**
```python
result = fetch_hig("buttons", section="Help buttons")
# or by title substring
result = fetch_hig("Dark Mode")
```
