# API Reference

Complete reference for all sandbox functions.

---

## Apple Documentation

### fetch_documentation(url: str) -> Dict

Fetch structured documentation from Apple Developer.

**Parameters:**
- `url`: Full URL starting with `https://developer.apple.com/documentation/`

**Returns:**
```python
{
    "title": str,
    "abstract": str,
    "declaration": str,      # Method signature
    "discussion": str,       # Detailed explanation
    "parameters": list,      # Parameter docs
    "returns": str,          # Return value doc
    "url": str,
    "json_url": str
}
```

**Example:**
```python
doc = fetch_documentation("https://developer.apple.com/documentation/swiftui/view")
result = {"title": doc["title"], "signature": doc.get("declaration")}
```

---

### search_apple_online_urls(query: str, platform: str = None) -> Dict

Generate search URLs for Apple documentation.

**Parameters:**
- `query`: Search term
- `platform`: Optional filter (`ios`, `macos`, `tvos`, `watchos`, `visionos`)

**Returns:**
```python
{
    "query": str,
    "platform": str | None,
    "apple_url": str,        # Direct Apple search URL
    "google_url": str,       # Google site:developer.apple.com
    "github_url": str        # GitHub Apple org search
}
```

---

### get_framework_info(framework: str) -> Dict

Get documentation URL for an Apple framework.

**Parameters:**
- `framework`: Framework name (e.g., `SwiftUI`, `UIKit`, `Foundation`)

**Returns:**
```python
{
    "name": str,
    "url": str,
    "note": str
}
```

---

## Swift Evolution

### search_proposals(feature: str) -> Dict

Search 500+ Swift Evolution proposals.

**Parameters:**
- `feature`: Feature name, Swift version, or concept (e.g., `async`, `Swift 6`, `actors`)

**Returns:**
```python
{
    "feature": str,
    "total_found": int,
    "proposals": [
        {
            "se_number": str,       # "SE-0413"
            "title": str,
            "status": str,          # "implemented", "accepted", "review", etc.
            "version": str,         # Swift version
            "summary": str,
            "github_url": str,
            "relevance_score": int
        }
    ],
    "available_versions": list[str],
    "deep_search": {             # Only present when fewer than 3 results
        "reason": str,
        "suggestion": str,
        "github_url": str
    }
}
```

**Example:**
```python
data = search_proposals("async")
implemented = [p for p in data["proposals"] if p["status"] == "implemented"]
result = {"count": len(implemented), "titles": [p["title"] for p in implemented[:5]]}
```

---

### get_proposal(se_number: str) -> Dict

Get details of a specific proposal.

**Parameters:**
- `se_number`: Proposal number (`SE-0413` or `0413`)

**Returns:**
```python
{
    "se_number": str,
    "title": str,
    "status": str,
    "version": str,
    "summary": str,
    "authors": list[str],
    "github_url": str,
    "raw_url": str,
    "swift_org_url": str
}
```

---

## Swift Repositories

### search_swift_repos_urls(query: str) -> Dict

Generate search URLs for Apple and SwiftLang GitHub repositories.

**Parameters:**
- `query`: Code or concept to search

**Returns:**
```python
{
    "query": str,
    "search_urls": {
        "github_search": str,   # All code across both orgs
        "swift_code": str,      # Swift-only code
        "repositories": str,    # Repository search
        "issues": str,          # Issues search
        "apple_org": str,       # Apple org only
        "swiftlang_org": str    # SwiftLang org only
    },
    "note": str,
    "tip": str
}
```

---

### fetch_github_file(url: str) -> Dict

Fetch source code from Apple/SwiftLang GitHub.

**Parameters:**
- `url`: GitHub file URL (must be from apple or swiftlang orgs)

**Returns:**
```python
{
    "content": str,
    "url": str,
    "raw_url": str,
    "language": str,
    "repo": str,
    "path": str,
    "size": int,
    "lines": int
}
```

---

## WWDC Notes

### search_wwdc_notes_urls(query: str) -> Dict

Generate search URLs for WWDC session notes.

**Parameters:**
- `query`: Topic to search

**Returns:**
```python
{
    "query": str,
    "search_urls": {
        "wwdcnotes": str,       # WWDCNotes search URL
        "apple_videos": str     # Apple developer videos search
    },
    "tip": str,                 # Context-specific tip (optional)
    "categories": list[str]     # Related session categories (optional)
}
```

---

### get_wwdc_session(session_id: str) -> Dict

Get WWDC session URLs.

**Parameters:**
- `session_id`: Format `wwdc2023-10154` or `wwdc2023/10154`

**Returns:**
```python
{
    "session_id": str,
    "urls": {
        "wwdcnotes": str,      # WWDCNotes session page
        "apple_video": str     # Apple developer video page
    }
}
```

---

## Human Interface Guidelines

### search_hig_urls(query: str, platform: str = None) -> Dict

Generate search URLs for Apple's Human Interface Guidelines.

**Parameters:**
- `query`: Design topic
- `platform`: Optional filter (`ios`, `macos`, etc.)

**Returns:**
```python
{
    "query": str,
    "platform": str | None,
    "base_url": str,
    "search_url": str,
    "direct_link": str,
    "platform_url": str,       # Only present when platform is specified
    "platform_search": str     # Only present when platform is specified
}
```

---

### list_hig_platforms() -> List[Dict]

List HIG platforms.

**Returns:** List of platform dictionaries:
```python
[
    {
        "platform": str,    # e.g., "ios"
        "name": str,        # e.g., "iOS", "macOS", "visionOS"
        "url": str          # HIG platform URL
    }
]
```
