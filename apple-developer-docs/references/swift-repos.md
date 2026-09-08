# Swift Repositories

## search_swift_repos_urls(query: str) -> Dict

Generate GitHub search URLs scoped to Apple/SwiftLang orgs (URLs only).

**Returns:** `{query, search_urls: {github_search, swift_code, ...}}`.

---

## fetch_github_file(url: str, start_line=None, end_line=None, section=None, ref=None, max_lines=200) -> Dict

Fetch a source file from a GitHub URL. **Restricted to `apple/` and `swiftlang/` orgs**; 1 MB byte cap.

**Parameters:**
- `url`: GitHub blob URL (e.g. `https://github.com/apple/swift/blob/main/stdlib/public/Concurrency/Task.swift`) or raw URL.

**Returns (success):**
```python
{
    "content": str,        # file text wrapped in external-content markers
    "url": str,
    "raw_url": str,
    "language": str,       # detected from extension
    "repo": str,           # "org/repo"
    "path": str,
    "size": int,           # bytes
    "lines": int,          # original text lines, excluding wrapper markers
    "truncated": False,    # complete fetch; does not describe caller-selected excerpts
}
```

**Errors:**
- `invalid_url` — host not on github.com / raw.githubusercontent.com, or org not in `{apple, swiftlang}`.
- `file_too_large` — exceeds 1 MB cap.
- `http_error` — HTTP status (status field included).
- `network_error`, `fetch_failed`.

**Example: read a bounded passage and retain its coverage.** Choose the range
from headings or search hits, then read enough surrounding text to support your
claim. Fetch success only describes the downloaded file; `excerpt_partial`
describes the selection you actually return to the agent.

```python
result = fetch_github_file(
    "https://github.com/swiftlang/swift/blob/main/docs/SIL/Ownership.md",
    start_line=80, end_line=120, ref="main")
```

The first window may only contain an introduction or contents list. Follow up
with the relevant section's line range before explaining details. For keyword
search previews, preserve total matches and how many you return; clipped lines
may omit essential qualifications. If the host truncates displayed output,
read smaller windows or its saved tool-output file. Logs should state these
actual selections rather than describing filtered JSON as the full source.

URLs must use HTTPS. Both initial requests and redirects are checked. Query
parameters and fragments do not change the fetched raw file. Blob URLs use a
single path segment for the branch/ref. For refs containing slashes, use a URL
with a placeholder single-segment ref (such as `main`) and pass the actual
branch in `ref=`. The URL supplies the repository and path.


### Selectors and revisions

With no selectors, returns the complete file as before. For a bounded read, use
1-based inclusive `start_line` / `end_line`, or `section` (not both). Section
names match Markdown ATX/setext headings or RST underline headings, ignoring case.
Use `Parent > Child` for repeated titles. Ambiguous/missing sections return
`ambiguous_section` / `section_not_found` with up to 50 candidate paths and ranges.
This is a lightweight heading reader, not a full Markdown/RST parser.

`max_lines` defaults to 200, range 1..1000, and only limits selected reads.
Selections return `citation_url`, `total_lines`, `start_line`, `end_line`,
`returned_lines`, `selection_end_line`, `selection_truncated`, `excerpt_partial`,
and `next_start_line`. Continue with `start_line=next_start_line` and the same
`selection_end_line`; retain the pinned URL when available. Source downloads still
have the 1 MB cap; selection does not bypass it. Out-of-file starts (including
empty files) return `line_out_of_range`; oversized ends clamp to the file end.

Optional `ref` accepts a branch, tag, or commit and resolves it to a full SHA
before fetching. Results include `ref`, `resolved_ref`, and `commit_url`; URLs
and citations use the resolved SHA. Without `ref`, the URL's revision is used
without an extra resolution request. Invalid selectors return `invalid_selection`;
invalid/missing/inaccessible refs return `invalid_ref` / `revision_fetch_failed`.
Revision HTTP errors include `status` and available retry/rate-limit headers;
network failures include `reason`.

## compare_github_file(url, base_ref, head_ref, context_lines=3, max_diff_lines=400)

Compare the same repository path at two revisions in Apple/SwiftLang repositories.
Both refs resolve to commits before reading either snapshot. Returns `status`
(`unchanged`, `modified`, `added`, `deleted`), `changed`, `repo`, `path`, original
refs, `base_commit`, `head_commit`, immutable `base_url` / `head_url`, and `diff`
wrapped as external content. This is a direct endpoint comparison, not a
merge-base comparison; renames are not inferred.

`context_lines` accepts 0..20; `max_diff_lines` accepts 1..2000 (default 400).
The diff also has a 200,000-character cap. Check `truncated` and
`diff_lines_returned`; clipping preserves whole diff lines, so a single huge
line can leave only headers. Newline-only changes are retained. Each source
must fit the 1 MB download cap. NUL-containing binary files return
`unsupported_text`. A missing file at one valid revision means added/deleted;
both missing returns `file_not_found`. Other fetch failures report `side` and
stop the comparison. Empty-file additions/deletions can have an empty diff;
use `status` and `changed` as well as diff text.

```python
result = compare_github_file(
    "https://github.com/swiftlang/swift/blob/main/docs/README.md",
    base_ref="swift-6.0-RELEASE", head_ref="swift-6.1-RELEASE",
    max_diff_lines=100)
```
