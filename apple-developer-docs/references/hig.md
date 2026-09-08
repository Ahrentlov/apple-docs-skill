# Human Interface Guidelines

Search and fetch Apple's HIG. Same DocC JSON schema as `/documentation/`, so
`fetch_hig` returns the same shape as `fetch_documentation`.

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

## fetch_hig(topic: str) -> Dict

Fetch the full content of a HIG topic by slug or title.

**Parameters:**
- `topic`: `'buttons'` (slug) or `'Dark Mode'` (title substring).

**Fast path:** when the input looks like a slug (alphanumeric + dashes), the
function tries the URL directly (~1 fetch). Falls back to the full topic-index
walk on title-substring lookups.

**Returns:** Same shape as `fetch_documentation` — `title, abstract, declaration, discussion, content_sections, ...`. HIG pages don't have programmatic symbols, so optional fields like `relationships`, `see_also`, `mentions`, and `symbols` are typically absent.

**Errors:** `empty_topic`, `topic_not_found`, `ambiguous_topic` (with `candidates` list), plus `fetch_documentation`'s error variants.

**Example:**
```python
result = fetch_hig("buttons")
# or by title substring
result = fetch_hig("Dark Mode")
```
