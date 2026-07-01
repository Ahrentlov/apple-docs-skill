# Swift Repositories

## search_swift_repos_urls(query: str) -> Dict

Generate GitHub search URLs scoped to Apple/SwiftLang orgs (URLs only).

**Returns:** `{query, search_urls: {github_search, swift_code, ...}}`.

---

## fetch_github_file(url: str) -> Dict

Fetch a source file from a GitHub URL. **Restricted to `apple/` and `swiftlang/` orgs**; 1 MB byte cap.

**Parameters:**
- `url`: GitHub blob URL (e.g. `https://github.com/apple/swift/blob/main/stdlib/public/Concurrency/Task.swift`) or raw URL.

**Returns (success):**
```python
{
    "content": str,        # file text
    "url": str,
    "raw_url": str,
    "language": str,       # detected from extension
    "repo": str,           # "org/repo"
    "path": str,
    "size": int,           # bytes
    "lines": int
}
```

**Errors:**
- `invalid_url` — host not on github.com / raw.githubusercontent.com, or org not in `{apple, swiftlang}`.
- `file_too_large` — exceeds 1 MB cap.
- `http_error` — HTTP status (status field included).
- `network_error`, `fetch_failed`.

**Example:**
```python
file = fetch_github_file("https://github.com/swiftlang/swift/blob/main/docs/SIL/Ownership.md")
result = {"size": file.get("size"), "lines": file.get("lines"), "head": file.get("content", "")[:300]}
```
