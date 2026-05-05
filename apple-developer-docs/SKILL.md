---
name: apple-developer-docs
description: "Execute Python code to query and filter Apple developer documentation (SwiftUI, UIKit, all frameworks), Apple's legacy Documentation Archive (Tech Notes, Sample Code, Guides), Swift Evolution proposals, Swift Forums discussions, WWDC session notes (with searchable content), Human Interface Guidelines (with searchable content), Apple/SwiftLang GitHub source code, Swift compiler internals (with full-text search), and Xcode release notes. TRIGGER when: user asks about Apple API docs, archived/legacy Apple docs, Swift proposals (SE-xxxx), Swift Forums, WWDC sessions and notes, HIG topics, Swift source code, Swift compiler internals (SIL, IRGen, Sema, ABI), or Xcode release notes. Examples: look up SwiftUI View, find async proposals, what changed in Swift 6, fetch the actual notes for WWDC2023-10154, search HIG for buttons, find archived Core Data sample code, grep compiler docs for 'reborrow', what's new in Xcode 15.4. Do NOT trigger for general Swift programming questions without documentation lookup."
license: MIT
allowed-tools: "Bash(python3:*)"
metadata:
  author: Patrick Ahrentløv
  version: 1.4.0
---

# Apple Developer Docs

Query Apple developer documentation efficiently via sandboxed Python execution. Write code that fetches and filters data directly, significantly reducing token usage.

## Execution

CRITICAL: Always assign your final output to a variable named `result`.

```bash
python3 {{SKILL_PATH}}/scripts/run.py "your_code_here"
```

Output is JSON with `success`, `result`, `stdout`, `error`, and `execution_time_ms` fields.

## Available APIs

### Apple Documentation
- `fetch_documentation(url)` - Fetch and parse any Apple Developer doc page (works for `/documentation/` AND `/design/human-interface-guidelines/` URLs — same DocC schema)
- `search_apple_online_urls(query, platform=None)` - Generate search URLs
- `get_framework_info(framework)` - Get framework documentation URL

### Swift Evolution & Forums
- `search_proposals(feature)` - Search proposals by keyword, version, or status
- `get_proposal(se_number)` - Get details of a specific proposal (SE-0413, 413, etc.)
- `search_swift_forums_urls(query, category=None)` - Search Swift Forums (URLs only)
- `search_swift_forums(query, category=None)` - Search Swift Forums (topics, posts, blurbs)

### Swift Repositories
- `search_swift_repos_urls(query)` - Search Apple/SwiftLang GitHub repos
- `fetch_github_file(url)` - Fetch source from GitHub (apple/swiftlang orgs only, 1 MB cap)

### WWDC Sessions
- `search_wwdc_sessions(query, year=None, limit=25)` - Search ~3000 sessions by title + description
- `fetch_wwdc_session(session_id)` - Fetch the actual community-written notes (markdown). Format: `wwdc2023-10154`.
- `search_wwdc_notes_urls(query)` / `get_wwdc_session(id)` - Legacy URL-only helpers

### Human Interface Guidelines
- `search_hig(query, platform=None, limit=25)` - Search HIG topics by title + abstract
- `fetch_hig(topic)` - Fetch full HIG topic content by slug ('buttons') or title ('Dark Mode')
- `search_hig_urls(query, platform=None)` / `list_hig_platforms()` - Legacy URL-only helpers

### Documentation Archive (legacy)
- `search_archive(query, platform=None, framework=None, resource_type=None, topic=None, limit=25)` - Search ~5200 archived docs (Tech Notes, Tech Q&As, Sample Code, Guides, Release Notes)
- `list_archive_frameworks()` / `list_archive_topics()` / `list_archive_resource_types()` - List filter values

### Swift Compiler Internals
- `search_compiler_docs(query, limit=25)` - Path-search `swiftlang/swift/docs` files
- `search_compiler_docs_text(query, limit=10, max_files=30)` - Full-text grep inside compiler docs (returns matched lines with file path + line number)
- `list_compiler_phases()` - List the compiler pipeline phases (Parse → Sema → SILGen → IRGen)
- `get_compiler_phase(name)` - Get a specific phase (e.g. 'Parsing', 'IRGen', 'Sema')

### Xcode Release Notes
- `list_xcode_release_notes(major=None)` - List every Xcode release-notes page (optionally filter by major version)
- `get_xcode_release_notes_url(version)` - Resolve a version like '15.4' to its release-notes URL. Pass to `fetch_documentation`.

For full API signatures and return types, consult `references/api-reference.md`.

### Available Builtins
- Data types: `list`, `dict`, `set`, `tuple`, `str`, `int`, `float`, `bool`, `bytes`
- Iteration: `len`, `range`, `enumerate`, `zip`, `map`, `filter`, `reversed`, `sorted`, `iter`, `next`
- Aggregation: `min`, `max`, `sum`, `any`, `all`
- Math: `abs`, `round`, `pow`
- Type checking: `isinstance`, `type`
- Output: `print`, `repr`

No `import` statements allowed. All API functions are pre-loaded.

## Examples

### Search and filter Swift Evolution proposals

```bash
python3 {{SKILL_PATH}}/scripts/run.py "
proposals = search_proposals('async')
swift6 = [p for p in proposals.get('proposals', []) if p.get('version', '').startswith('6')]
result = {'swift6_async': swift6[:5], 'count': len(swift6)}
"
```

### Fetch documentation and extract fields

```bash
python3 {{SKILL_PATH}}/scripts/run.py "
doc = fetch_documentation('https://developer.apple.com/documentation/swiftui/view')
result = {
    'title': doc.get('title'),
    'declaration': doc.get('declaration'),
    'abstract': doc.get('abstract')
}
"
```

### Combine multiple sources

```bash
python3 {{SKILL_PATH}}/scripts/run.py "
proposals = search_proposals('Observation')
wwdc = search_wwdc_notes_urls('observation framework')
result = {
    'proposals': [p['title'] for p in proposals.get('proposals', [])[:3]],
    'wwdc_search': wwdc.get('search_urls', {})
}
"
```

## Tips

1. **Always assign to `result`** - This is how data is returned
2. **Filter before returning** - Reduce data to only what's needed
3. **Check for errors** - API responses may contain an `'error'` key
4. **Use `print()` for debugging** - Output appears in the `stdout` field

## Troubleshooting

**Error: "No 'result' variable set"**
Cause: Code ran but never assigned to `result`.
Fix: Add `result = ...` with your output data.

**Error: "Import statements are not allowed"**
Cause: Code contains `import`. The sandbox forbids all imports.
Fix: Remove imports. All API functions and safe builtins are pre-loaded.

**Error: "Execution timed out"**
Cause: Code took too long (default 10s limit).
Fix: Simplify logic or filter data earlier. Use `--timeout 30` for large fetches.

**Error: "Failed to fetch" from `fetch_documentation`**
Cause: Invalid Apple Developer URL or network issue.
Fix: Ensure URL starts with `https://developer.apple.com/documentation/`.

For security model details, see `references/security.md`.
