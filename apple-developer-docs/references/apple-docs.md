# Apple Documentation

## fetch_documentation(url: str, section=None, start_line=None, end_line=None, max_lines=200, format='markdown') -> Dict

Fetch documentation from Apple Developer.

**Parameters:**
- `url`: A page under `https://developer.apple.com/documentation/`, `https://developer.apple.com/design/human-interface-guidelines`, or `https://developer.apple.com/tutorials/` (step-by-step tutorials, Markdown only; see [Tutorials](#tutorials)).
- `format`: `'markdown'` (default) returns Apple's own Markdown rendering of
  the page. `'json'` parses the DocC JSON into structured fields (the pre-1.9
  behavior). Use `'json'` when you need `symbols`, `relationships`,
  `see_also`, or per-field access to `declaration` / `parameters`.

**Markdown returns (default, no selectors):**
```python
{
    "title": str,
    "url": str,              # human-facing page; cite this
    "markdown_url": str,     # .md source actually fetched
    "metadata": dict,        # Apple's metadata comment: title, role, framework,
                             # documentType, availability ["iOS: 13.0.0 -", ...], symbol {kind, preciseIdentifier}
    "content": str,          # full Markdown, wrapped in untrusted-content markers
}
```

The Markdown keeps tables, image alt text, Topics, Relationships, and HIG
change logs. Declarations appear as fenced code blocks after the abstract.
Links are site-relative (`/documentation/SwiftUI/Text`); prefix
`https://developer.apple.com` to fetch them.

**JSON returns (`format='json'`, no selectors):**
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

**Optional JSON fields (present only when the page has them):**
```python
{
    "availability": list[dict],          # platform introducedAt/deprecatedAt/unavailable/beta metadata
    "variants": list[dict],              # available language/page variants
    "unrendered_types": list[str],       # content types not fully rendered; consult original
    "deprecation": str,                 # deprecation notice
    "possible_values": [{"name": str, "description": str}],   # enum-like property-list keys
    "content_sections": {"Parent > Heading": str},             # convenience mapping; duplicate paths get [2], [3], ...
    "content_outline": [{"heading": str, "level": int, "path": list[str], "content": str}], # source order; optional anchor
    "see_also": [{"title": str, "items": [{"title": str, "url": str}]}],
    "relationships": [{"title": str, "kind": str, "items": [{"title": str, "url": str}]}],
    "mentions": [{"title": str, "url": str}],
    "details": {...},                   # property-list metadata
    "symbols": [{"name": str, "declaration": str, "abstract": str, "group": str, "role": str, "kind": str, "url": str}],
}
```

**Errors:**
- `invalid_input` — URL is not a string, or `format` is not `'markdown'` / `'json'`.
- `unsupported_language` — non-Swift language query; open the original page.
- `unsupported_format`: `format='json'` for a tutorial page.
- `invalid_schema` — response is not a DocC document (JSON) or not `text/markdown` (Markdown).
- `fetch_failed` — response-size limit or other fetch failure.
- `invalid_url` — URL is not a page under an accepted prefix (the bare `/documentation` root is not a page; the HIG root is).
- `not_found` — HTTP 404.
- `http_error` — other HTTP status (`status` field included).
- `timeout` — request exceeded 10s.
- `network_error` — DNS / connection / SSL failure.
- `invalid_json` — response was not valid JSON (JSON).
- `invalid_selection`, `section_not_found`, `ambiguous_section`, `line_out_of_range`: see [Bounded documentation passages](#bounded-documentation-passages).

In the JSON format, discussion and other rendered fields produce markdown-style text (fenced code blocks, `- item` bullets, `**Note:**` / `**Important:**` aside prefixes, `` `title` `` for cross-references).

**Example:**
```python
doc = fetch_documentation("https://developer.apple.com/documentation/swiftui/view", format="json")
if 'error' in doc:
    result = doc
else:
    result = {"title": doc['title'], "url": doc['url'],
              "declaration": doc['declaration'], "availability": doc.get('availability', []),
              "deprecation": doc.get('deprecation'), "discussion_excerpt": doc['discussion'][:1500],
              "other_sections": list(doc.get('content_sections', {})),
              "unrendered_types": doc.get('unrendered_types', [])}
```

The default Swift representation is fetched. Query parameters and fragments are
removed from the canonical output URL; a non-Swift `language` is rejected rather
than silently returning Swift declarations. Non-Discussion headings remain in
`content_sections`, including text before the first heading under `Overview`.
In the JSON format, `content_outline` is the authoritative ordered representation: it keeps empty and
repeated headings, their ancestor paths, optional source anchors, and Discussion /
Return Value entries. Each entry contains its own body, not its descendants.
Heading scope resets at each content-kind section. Use paths when attributing
release-note issues; a child named “Resolved Issues” alone is ambiguous.

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
    "github_url": str        # GitHub Swift code search (not org-scoped)
}
```

---

## get_framework_info(framework: str) -> Dict

Get documentation URL for a framework name (e.g. `SwiftUI`, `UIKit`, `Foundation`).

**Returns:** `{name, url, note}`.


## Discovery workflow

When the URL is known, fetch it directly. For an unknown member, fetch the
framework or parent type page and follow its Topics links (or the `symbols`
URLs with `format='json'`). Filter
those symbols locally by name/abstract. `get_framework_info` only constructs a
likely framework URL; fetching it verifies that the page exists.

If that does not find the page, use an available browser/search tool with a
query scoped to `developer.apple.com/documentation`, or open the generated
search links. Do not treat link generation as a completed search. If no search
tool is available, report the discovery limit and any verified parent page.
Legacy `/library/archive/` HTML is not supported by this parser; open archive
result links with a browser tool.


## Bounded documentation passages

Pass `section="Overview"` or a qualified heading. Matching ignores case and
includes descendant sections. Repeated matches return `ambiguous_section` with
candidate paths; missing headings return `section_not_found`.

Heading paths differ by format. In Markdown they are the full path from the
page title, e.g. `"Xcode 16.4 Release Notes > Overview > General > Resolved Issues"`. In JSON they
start below it, e.g. `"Overview > General > Resolved Issues"`, and candidates
carry source anchors that become `citation_url` fragments.

Optional `start_line` and `end_line` select 1-based inclusive lines,
relative to the selected section when one is supplied. Without a section,
Markdown lines count from after the metadata comment; JSON lines count the
rendered outline. `max_lines` defaults to 200 (1..1000).
With no section or line selector, the full response is returned.
Selected responses contain wrapped `content`, title, source URLs (plus
`metadata` for Markdown, `availability` for JSON), `citation_url`, `line_basis`,
`total_lines`, `start_line`, `end_line`, `returned_lines`, `selection_end_line`,
`selection_truncated`, `excerpt_partial`, and `next_start_line`.
Retain these fields when reporting excerpts. Continue with the same section and
`start_line=next_start_line`; raise `max_lines` only as needed. Structured
fields such as declarations and parameters are available in the full JSON
response.

```python
result = fetch_documentation(
    "https://developer.apple.com/documentation/swiftui/navigationstack",
    section="Overview", max_lines=40)
```

## search_symbols(framework, query='', kind=None, deprecated=None, beta=None, limit=20, offset=0)

Searches a framework's navigator index: the tree behind the sidebar on
developer.apple.com, fetched once (`/tutorials/data/index/<framework>`) and
cached for the process. It lists every page Apple publishes for the framework,
so an empty result means the framework lists no such page. Pages the tree links
from other frameworks are excluded.

**Parameters:**
- `framework`: slug such as `swiftui`, `uikit`, `foundation`, `appkit`.
- `query`: space-separated terms; each must occur in the title or the URL's
  last path component. Member titles are declarations (`func opacity(Double) -> some View`).
  Empty matches everything, for filter-only listings.
- `kind`: `struct`, `class`, `protocol`, `enum`, `method`, `property`, `init`,
  `case`, `macro`, `article`, `sampleCode`, ... (case-insensitive).
- `deprecated`, `beta`: `True`/`False` keep only pages with that flag.
- `limit` 1..200 per call; follow `next_offset` for the rest.

**Returns:**
```python
{
    "framework": str, "query": str, "kind": str | None, "deprecated": bool | None, "beta": bool | None,
    "total_matches": int, "returned": int, "offset": int, "next_offset": int | None,
    "indexed_pages": int, "index_url": str, "search_scope": str,
    "results": [{"title": str, "kind": str, "url": str, "deprecated": bool, "beta": bool,
                 "locations": [str]}],   # every sidebar path the page appears under
}
```

Exact title or name matches rank first, then prefixes, then other matches in
Apple's order. Fetch a result's `url` for declarations and availability before
explaining behavior. **Errors:** `invalid_input`, `not_found` (Apple publishes
no index for that slug), `invalid_json`, `invalid_schema`, and fetch errors.

```python
result = search_symbols("swiftui", "NavigationStack")
deprecated = search_symbols("swiftui", kind="struct", deprecated=True, limit=50)
```

## check_availability(url, platform=None, version=None)

Reads platform availability from the page's DocC metadata (`format='json'`
under the hood; the Markdown metadata drops deprecation messages and flags).

**Returns:** `{title, url, platforms: [{name, introduced, deprecated,
deprecation_message, beta, unavailable}]}`. Versions are Apple's strings
(`"13.0"`); `introduced` is `None` when Apple lists the platform without one.

With `platform` (`'iOS'`, `'macOS'`, `'Mac Catalyst'`, `'visionOS'`, ...;
case and spaces ignored) the result adds `platform`, `version`,
`platform_availability`, and `status`:

| status | meaning |
|---|---|
| `available` | listed, not deprecated (at `version`, or in the latest documented release) |
| `deprecated` | still usable, deprecated at or before `version` (or at all, without `version`) |
| `not_yet_available` | `version` precedes the introduced version |
| `unavailable` | Apple marks it unavailable on that platform |
| `not_listed` | Apple lists no availability for that platform |
| `introduction_unknown` | listed without an introduced version, so `version` cannot be compared |

`version` (`'17'`, `'17.4'`, `'17.4.1'`) requires `platform`.
**Errors:** `invalid_input` plus `fetch_documentation`'s errors.

```python
result = check_availability("https://developer.apple.com/documentation/swiftui/view/glasseffect(_:in:)",
                            platform="iOS", version="17.4")   # status: not_yet_available
```

## Tutorials

`list_tutorials(course)` lists a course's tutorials in order from its overview:
`develop-in-swift`, `swiftui`, `app-dev-training`, `swiftui-concepts`,
`sample-apps`. Each entry has `volume`, `chapter`, `title`, `kind`, `url`,
`abstract`, and `markdown`.

Step-by-step tutorials (`kind: 'project'`, `markdown: True`) are read with
`fetch_documentation(url, ...)`; their sections are headed
`Section N: <title>` with `### Step N` children, so select a section by its full title. Articles and course overviews have
no Markdown rendering; open them in a browser. Tutorials do not support
`format='json'` (`unsupported_format`). **Errors:** `invalid_input`,
`not_found`, `invalid_json`, `invalid_schema`, and fetch errors.

```python
course = list_tutorials("develop-in-swift")
first = next(t for t in course['tutorials'] if t['markdown'])
result = fetch_documentation(first['url'], start_line=1, max_lines=60)
```
