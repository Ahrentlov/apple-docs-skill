# Documentation Archive (legacy)

Apple's legacy documentation archive at `developer.apple.com/library/archive/`:
~5200 Technical Notes, Technical Q&As, Sample Code projects, Guides, Release
Notes, and Articles — most removed from the modern docs site but still
canonical for pre-SwiftUI / pre-UIKit-era topics.

## search_archive(query, platform=None, framework=None, resource_type=None, topic=None, limit=25) -> Dict

Keyword search over titles, with optional facet filters.

**Parameters:**
- `query`: Space-separated keywords (case-insensitive; all terms must match the title).
- `platform`: Substring filter — `iOS`, `macOS`, `tvOS`, `watchOS`, `Safari`, `Xcode Developer Tools`, etc.
- `framework`: Framework / technology name (`UIKit`, `CoreData`, `AVFoundation`). Use `list_archive_frameworks()`.
- `resource_type`: `Technical Notes`, `Technical Q&As`, `Sample Code`, `Guides`, `Release Notes`, `Articles`, `Getting Started`, `Xcode Tasks`.
- `topic`: Topic category (`Networking`, `Graphics & Animation`). Use `list_archive_topics()`.
- `limit`: Max results (default 25).

**Returns:** `{query, filters, total_matches, returned, results}` where `filters` echoes the `(platform, framework, resource_type, topic)` you passed.
```python
{
    "query": str,
    "filters": {"platform": str|None, "framework": str|None, "resource_type": str|None, "topic": str|None},
    "total_matches": int,
    "returned": int,
    "results": [
        {
            "name": str,           # title
            "id": str,             # Apple's UID, e.g. "DTS40009554"
            "resource_type": str,
            "topic": str,
            "framework": str,
            "platform": str,       # pipe-delimited if multiple, e.g. "iOS|macOS"
            "date": str,           # YYYY-MM-DD
            "url": str             # absolute URL on developer.apple.com/library/archive/
        }
    ]
}
```

Sorted newest first.

**Errors:** `fetch_failed`.

---

## list_archive_frameworks() -> Dict
```python
{"count": int, "frameworks": [str, ...]}   # e.g. "UIKit", "CoreData", "QuickTime"
```

## list_archive_topics() -> Dict
```python
{"count": int, "topics": [str, ...]}       # e.g. "Audio", "Networking", "Graphics & Animation"
```

## list_archive_resource_types() -> Dict
```python
{"count": int, "resource_types": [str, ...]}   # 8 types
```
