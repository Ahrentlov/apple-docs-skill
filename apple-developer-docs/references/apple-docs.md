# Apple Documentation

## fetch_documentation(url: str) -> Dict

Fetch structured documentation from Apple Developer.

**Parameters:**
- `url`: A URL under either `https://developer.apple.com/documentation/` or `https://developer.apple.com/design/human-interface-guidelines/` (same DocC schema).

**Returns (always present):**
```python
{
    "title": str,
    "abstract": str,
    "declaration": str,      # method signature
    "discussion": str,       # rendered Discussion body
    "parameters": [{"name": str, "description": str}],
    "returns": str,          # rendered Return Value body
    "url": str,
    "json_url": str,
}
```

**Optional (present only when the page has them):**
```python
{
    "deprecation": str,                 # deprecation notice
    "possible_values": [{"name": str, "description": str}],   # enum-like property-list keys
    "content_sections": {"Heading": str},                      # non-Discussion / Return-Value headings
    "see_also": [{"title": str, "items": [{"title": str, "url": str}]}],
    "relationships": [{"title": str, "kind": str, "items": [{"title": str, "url": str}]}],
    "mentions": [{"title": str, "url": str}],
    "details": {...},                   # property-list metadata
    "symbols": [{"name": str, "declaration": str, "abstract": str, "group": str, "role": str, "url": str}],
}
```

**Errors:**
- `invalid_url` — URL does not match an accepted prefix.
- `not_found` — HTTP 404.
- `http_error` — other HTTP status (`status` field included).
- `timeout` — request exceeded 10s.
- `network_error` — DNS / connection / SSL failure.
- `invalid_json` — response was not valid JSON.

Discussion and other rendered fields produce markdown-style text (fenced code blocks, `- item` bullets, `**Note:**` / `**Important:**` aside prefixes, `` `title` `` for cross-references).

**Examples:**
```python
doc = fetch_documentation("https://developer.apple.com/documentation/swiftui/view")
result = {"title": doc["title"], "signature": doc.get("declaration")}

# enum-like property-list key
doc = fetch_documentation("https://developer.apple.com/documentation/bundleresources/app-privacy-configuration/nsprivacycollecteddatatypes/nsprivacycollecteddatatype")
result = [v["name"] for v in doc.get("possible_values", [])]

# deprecation + related APIs
doc = fetch_documentation("https://developer.apple.com/documentation/uikit/uialertview")
result = {"deprecated": doc.get("deprecation"), "see_also": doc.get("see_also")}

# HIG (same schema)
doc = fetch_documentation("https://developer.apple.com/design/human-interface-guidelines/buttons")
result = doc["abstract"]
```

---

## search_apple_online_urls(query: str, platform: str = None) -> Dict

Generate search URLs for Apple documentation (returns URLs only — does not fetch).

**Returns:**
```python
{
    "query": str,
    "platform": str | None,
    "apple_url": str,        # direct Apple search URL
    "google_url": str,       # Google site:developer.apple.com
    "github_url": str        # GitHub Apple org search
}
```

---

## get_framework_info(framework: str) -> Dict

Get documentation URL for a framework name (e.g. `SwiftUI`, `UIKit`, `Foundation`).

**Returns:** `{name, url, note}`.
