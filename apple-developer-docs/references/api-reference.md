# API Reference

Complete reference for all sandbox functions.

---

## Apple Documentation

### fetch_documentation(url: str) -> Dict

Fetch structured documentation from Apple Developer.

**Parameters:**
- `url`: Full URL starting with `https://developer.apple.com/documentation/`

**Returns:**

Always present:
```python
{
    "title": str,
    "abstract": str,
    "declaration": str,      # Method signature
    "discussion": str,       # Rendered Discussion body — paragraphs, code blocks, lists, asides
    "parameters": [{"name": str, "description": str}],
    "returns": str,          # Rendered Return Value body
    "url": str,
    "json_url": str,
}
```

Optional (present only when the page has them):
```python
{
    "deprecation": str,                 # Deprecation notice (use other API instead, etc.)
    "possible_values": [                # Enum-like property-list keys
        {"name": str, "description": str}
    ],
    "content_sections": {                # Any non-Discussion/Return-Value headings (Overview, etc.)
        "Heading": str
    },
    "see_also": [                        # Related topic groups
        {"title": str, "items": [{"title": str, "url": str}]}
    ],
    "relationships": [                   # Conforms-to / Inherits-from / Inherited-by
        {"title": str, "kind": str, "items": [{"title": str, "url": str}]}
    ],
    "mentions": [                        # Cross-references to this symbol
        {"title": str, "url": str}
    ],
    "details": {                         # Property-list key metadata (name, platforms, titleStyle)
        ...
    },
    "symbols": [                         # Framework/type index pages
        {"name": str, "declaration": str, "abstract": str,
         "group": str, "role": str, "url": str}
    ],
}
```

Discussion and other rendered fields produce markdown-style text: fenced code blocks (```lang ... ```), `- item` bullets, `**Note:**` / `**Important:**` aside prefixes, and `` `title` `` for cross-references.

**Example:**
```python
doc = fetch_documentation("https://developer.apple.com/documentation/swiftui/view")
result = {"title": doc["title"], "signature": doc.get("declaration")}

# Enum-like property-list key with many possible values
doc = fetch_documentation("https://developer.apple.com/documentation/bundleresources/app-privacy-configuration/nsprivacycollecteddatatypes/nsprivacycollecteddatatype")
result = [v["name"] for v in doc.get("possible_values", [])]

# Find related APIs and check for deprecation
doc = fetch_documentation("https://developer.apple.com/documentation/uikit/uialertview")
result = {"deprecated": doc.get("deprecation"), "see_also": doc.get("see_also")}
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

---

## Documentation Archive

Search Apple's legacy documentation archive at `developer.apple.com/library/archive/`:
~5200 Technical Notes, Technical Q&As, Sample Code projects, Guides, Release Notes,
and Articles — most removed from the modern docs site but still canonical for
pre-SwiftUI/UIKit-era topics.

### search_archive(query: str, platform: str = None, framework: str = None, resource_type: str = None, topic: str = None, limit: int = 25) -> Dict

Keyword search across archived document titles, with optional facet filters.

**Parameters:**
- `query`: Space-separated keywords (matched case-insensitively against the title; all terms must match)
- `platform`: Platform substring filter — `"iOS"`, `"macOS"`, `"tvOS"`, `"watchOS"`, `"Safari"`, `"Xcode Developer Tools"`, etc. Many docs list multiple platforms.
- `framework`: Framework/technology name, e.g. `"CoreData"`, `"UIKit"`, `"AVFoundation"`. Use `list_archive_frameworks()` for the full set.
- `resource_type`: `"Technical Notes"`, `"Technical Q&As"`, `"Sample Code"`, `"Guides"`, `"Release Notes"`, `"Articles"`, `"Getting Started"`, `"Xcode Tasks"` (substring match).
- `topic`: Topic category, e.g. `"Networking"`, `"Graphics & Animation"`. Use `list_archive_topics()`.
- `limit`: Max results (default 25).

**Returns:**
```python
{
    "query": str,
    "filters": {"platform": str|None, "framework": str|None, "resource_type": str|None, "topic": str|None},
    "total_matches": int,
    "returned": int,
    "results": [
        {
            "name": str,           # Document title
            "id": str,             # Apple's doc UID, e.g. "DTS40009554"
            "resource_type": str,
            "topic": str,
            "framework": str,
            "platform": str,       # Pipe-delimited when multiple, e.g. "iOS|macOS"
            "date": str,           # YYYY-MM-DD
            "url": str             # Absolute URL on developer.apple.com/library/archive/
        }
    ]
}
```

Results are sorted newest first.

---

### list_archive_frameworks() -> Dict

```python
{"count": int, "frameworks": [str, ...]}   # e.g. "UIKit", "CoreData", "QuickTime"
```

### list_archive_topics() -> Dict

```python
{"count": int, "topics": [str, ...]}       # e.g. "Audio", "Networking", "Graphics & Animation"
```

### list_archive_resource_types() -> Dict

```python
{"count": int, "resource_types": [str, ...]}   # 8 types
```

---

## Swift Compiler Internals

Search the Swift compiler's in-repo documentation (`github.com/swiftlang/swift/tree/main/docs`).
Covers SIL, ABI, type checker, runtime, optimizer passes, ownership, generics, and C++ interop.

### search_compiler_docs(query: str, limit: int = 25) -> Dict

Keyword search against file paths in `swiftlang/swift/docs`. Pair the returned
`raw_url` with `fetch_github_file()` to read a doc's contents.

**Parameters:**
- `query`: Space-separated keywords matched against the file path (directory + filename). All terms must match.
- `limit`: Max results (default 25).

**Returns:**
```python
{
    "query": str,
    "total_matches": int,
    "returned": int,
    "results": [
        {
            "path": str,          # e.g. "docs/SIL/Ownership.md"
            "name": str,          # e.g. "Ownership.md"
            "directory": str,     # e.g. "docs/SIL"
            "github_url": str,    # Web URL
            "raw_url": str        # Fetch with fetch_github_file()
        }
    ]
}
```

---

### list_compiler_phases() -> Dict

List the Swift compiler pipeline phases, each with its `lib/` directory.

**Returns:**
```python
{
    "landing_url": str,     # swift.org/documentation/swift-compiler/
    "phases": [
        {
            "name": str,              # e.g. "SIL Generation"
            "description": str,
            "lib_path": str,          # e.g. "lib/SILGen"
            "github_url": str,        # Link into swiftlang/swift
            "design_doc": str         # Only on phases with a dedicated design doc
        }
    ]
}
```

---

### get_compiler_phase(name: str) -> Dict

Get a single phase by case-insensitive substring match against its name or lib path
(e.g. `"SIL Generation"`, `"Sema"`, `"IRGen"`).

**Returns:** The phase dict (see above) on a unique match, or an error dict with
`"available"` / `"candidates"` when unknown or ambiguous.

---

### search_compiler_docs_text(query: str, limit: int = 10, max_files: int = 30) -> Dict

Full-text search inside compiler doc files. Path-prefilters candidates by any
keyword in the query, fetches up to `max_files` docs, then greps for all
terms on the same line.

**Returns:**
```python
{
    "query": str,
    "files_searched": int,
    "total_matches": int,
    "results": [
        {
            "path": str,             # e.g. "docs/SIL/Ownership.md"
            "line_number": int,
            "line": str,             # Trimmed match (max 240 chars)
            "github_url": str        # Link with #L<line_number> anchor
        }
    ]
}
```

---

## WWDC Sessions

Search ~3000 WWDC sessions and fetch community-written notes. Backed by the
`wwdcnotes/wwdcnotes` GitHub repo.

### search_wwdc_sessions(query: str, year: int | None = None, limit: int = 25) -> Dict

Search WWDC sessions by title + description.

**Parameters:**
- `query`: Space-separated keywords. All terms must match somewhere in title + description.
- `year`: Optional filter — full year (`2023`) or 2-digit (`23`).
- `limit`: Max results (default 25).

**Returns:**
```python
{
    "query": str,
    "year": int | None,
    "total_matches": int,
    "returned": int,
    "results": [
        {
            "id": str,            # e.g. "wwdc2023-10154"
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

---

### fetch_wwdc_session(session_id: str) -> Dict

Fetch community-written notes for a WWDC session.

**Parameters:**
- `session_id`: `'wwdc2023-10154'`, `'wwdc23-10154'`, or `'wwdc2023/10154'`.

**Returns (success):**
```python
{
    "id": str,            # canonical wwdc{4-digit-year}-{number}
    "title": str,
    "year": int,
    "code": str,
    "content": str,       # raw markdown notes
    "source_url": str,    # raw.githubusercontent.com URL
    "permalink": str      # wwdcnotes.com URL
}
```

**Errors:** `invalid_session_id`, `year_not_indexed`, `session_not_found`, `fetch_failed`.

---

## Human Interface Guidelines

### search_hig(query: str, platform: str | None = None, limit: int = 25) -> Dict

Search HIG topics by title and abstract.

**Returns:**
```python
{
    "query": str,
    "platform": str | None,
    "total_matches": int,
    "returned": int,
    "results": [
        {
            "title": str,         # e.g. "Buttons"
            "slug": str,          # e.g. "buttons"
            "category": str,      # "Foundations", "Patterns", etc.
            "url": str,
            "abstract": str
        }
    ]
}
```

---

### fetch_hig(topic: str) -> Dict

Fetch the full content of a HIG topic by slug (`'buttons'`) or title
(`'Dark Mode'`). Returns the same shape as `fetch_documentation` (title,
abstract, declaration, discussion, parameters, content_sections, etc.).

Errors: `topic_not_found`, `ambiguous_topic` (with `candidates` list).

---

## Xcode Release Notes

### list_xcode_release_notes(major: str | None = None) -> Dict

List every Xcode release-notes page Apple publishes.

**Parameters:**
- `major`: Optional substring filter against the major-version heading (e.g. `'15'`, `'16'`, `'26'`).

**Returns:**
```python
{
    "count": int,
    "releases": [
        {
            "version": str,       # e.g. "Xcode 15.4 Release Notes"
            "major": str,         # e.g. "Xcode 15"
            "url": str            # pass to fetch_documentation()
        }
    ]
}
```

---

### get_xcode_release_notes_url(version: str) -> Dict

Resolve a version string (e.g. `'15.4'`, `'16.3'`, `'26.5 RC'`) to a single
release-notes URL. Substring-matched against page titles.

**Returns:** `{version, major, url}` on unique match, `{error: 'ambiguous_version', candidates: [...]}` when multiple match, `{error: 'version_not_found', available_count: N}` when missing.
