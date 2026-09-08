# Xcode Release Notes

Index of Apple's Xcode release-notes pages. Use these helpers to discover the
right URL, then pass it to `fetch_documentation` to read the actual notes.

## list_xcode_release_notes(major: str | None = None) -> Dict

List every release-notes page Apple publishes.

**Parameters:**
- `major`: Optional numeric-boundary substring filter against the major-version heading (`'15'`, `'16'`, `'26'`).

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
- `version`: case-insensitive substring of the page title with numeric boundaries (`15.4` does not match `15.40`) — `'15.4'`, `'16.3'`, `'26.5 RC'`.

**Returns:** `{version, major, url}` on unique match.

**Errors:**
- `empty_version`
- `version_not_found` (with `available_count`)
- `ambiguous_version` (with `candidates` list)
- `fetch_failed`

**Example:**
```python
release = get_xcode_release_notes_url("15.4")
if 'error' in release:
    result = release
else:
    notes = fetch_documentation(release['url'])
    if 'error' in notes:
        result = notes
    else:
        result = {'title': notes['title'], 'url': notes['url'],
                  'sections': notes.get('content_outline', []),
                  'discussion': notes['discussion'],
                  'unrendered_types': notes.get('unrendered_types', [])}
```

Use each outline entry’s `path` to retain parent categories such as General or
Devices when several headings say “Resolved Issues”. Empty parent headings are
kept in source order; the issue text lives in their child entries.
