# Xcode Release Notes

Index of Apple's Xcode release-notes pages. Use these helpers to discover the
right URL, then pass it to `fetch_documentation` to read the actual notes.

## list_xcode_release_notes(major: str | None = None) -> Dict

List every release-notes page Apple publishes.

**Parameters:**
- `major`: Optional substring filter against the major-version heading (`'15'`, `'16'`, `'26'`).

**Returns:**
```python
{
    "count": int,
    "releases": [
        {
            "version": str,       # "Xcode 15.4 Release Notes"
            "major": str,         # "Xcode 15"
            "url": str            # pass to fetch_documentation()
        }
    ]
}
```

**Errors:** `fetch_failed`.

---

## get_xcode_release_notes_url(version: str) -> Dict

Resolve a version string to a single release-notes URL.

**Parameters:**
- `version`: substring of the page title — `'15.4'`, `'16.3'`, `'26.5 RC'`.

**Returns:** `{version, major, url}` on unique match.

**Errors:**
- `empty_version`
- `version_not_found` (with `available_count`)
- `ambiguous_version` (with `candidates` list)
- `fetch_failed`

**Example:**
```python
url = get_xcode_release_notes_url("15.4")["url"]
notes = fetch_documentation(url)
result = {"title": notes["title"], "head": notes.get("discussion", "")[:600]}
```
