# Swift Compiler Internals

Search the Swift compiler's in-repo documentation (`github.com/swiftlang/swift/tree/main/docs`):
SIL, ABI, type checker, runtime, optimizer passes, ownership, generics, C++ interop.

## search_compiler_docs(query: str, limit: int = 25, ref: str = "main") -> Dict

Keyword search against file paths (directory + filename).

Both compiler searches accept `ref`: a branch, tag, or commit, default `main`.
The ref is resolved once to a full commit SHA before the tree and file reads,
so each search uses one immutable snapshot. Results return `ref`, `resolved_ref`,
and `commit_url`; result URLs use that SHA. For a particular installed toolchain,
pass its matching release tag, such as `ref="swift-6.0-RELEASE"`.
Invalid refs return `invalid_ref`; missing, inaccessible, or rate-limited
revisions return `revision_fetch_failed`. Static compiler phase links below
remain on `main`.

**Returns:**
```python
{
    "query": str,
    "total_matches": int,
    "returned": int,
    "results": [
        {
            "path": str,          # "docs/SIL/Ownership.md"
            "name": str,          # "Ownership.md"
            "directory": str,     # "docs/SIL"
            "github_url": str,
            "raw_url": str        # pass to fetch_github_file()
        }
    ]
}
```

**Errors:** `fetch_failed`.

---

## search_compiler_docs_text(query: str, limit: int = 10, max_files: int = 60, ref: str = "main") -> Dict

Full-text search inside `.md`, `.rst`, and `.txt` compiler docs. Matching paths
are prioritized but do not exclude other files. Fetches batches of up to eight,
within `max_files` (default 60, capped at 500), matching ALL terms on the same line.
The docs subtree is fetched separately so repository-wide tree truncation cannot
silently drop documentation.

**Returns:**
```python
{
    "query": str,
    "files_searched": int,          # successfully fetched and examined files
    "files_attempted": int,
    "searched_paths": list[str],     # successfully examined files, including partial prefixes
    "path_priority_matches": int,   # candidate paths containing at least one query term
    "failed_files": list[str],      # failed fetches, not partially searched files
    "truncated_files": [{"path": str, "bytes_searched": int}],
    "content_max_bytes": int,        # 1,048,576 bytes per file
    "max_files": int,                # effective file budget
    "match_limit_reached": bool,
    "candidate_files": int,        # number of text files in the docs subtree
    "truncated": bool,             # True for unsearched files, failed/partial fetches, or omitted hits
    "matches_returned": int,
    "results": [
        {
            "path": str,
            "line_number": int,
            "line": str,             # trimmed match (max 240 chars)
            "line_truncated": bool,
            "github_url": str        # link with #L<line> anchor
        }
    ]
}
```

`searched_paths` identifies the examined files; failed files are excluded.
`path_priority_matches` counts candidate paths containing at least one query
term, independently of body matches and the file budget. Use these fields for
path-specific scope claims rather than inferring them from a zero-hit result.

`matches_returned` counts returned hits, not all matches. `truncated` also covers
failed fetches, partially read files, and omitted hits, not just the file budget. Raise
`max_files` up to 500 and/or `limit` up to 200 where useful, and inspect
`failed_files` and `truncated_files`; raising the file budget does not repair a
failed fetch or expand the per-file byte budget. Files up to 1 MiB are searched
fully. For larger files, complete lines in the first 1 MiB remain searchable;
the unfinished last line is omitted to preserve accurate excerpts. Partial files
always make `truncated` true, even with zero matches. Read the original file to
inspect an unsearched tail. The first match
batch may be enough for discovery, but cannot establish absence from the corpus.

**Errors:** `empty_query`, `fetch_failed`.

---

## list_compiler_phases() -> Dict

List the compiler pipeline phases (Parse → Sema → SILGen → IRGen).

**Returns:**
```python
{
    "landing_url": str,
    "phases": [
        {
            "name": str,              # "SIL Generation"
            "description": str,
            "lib_path": str,          # "lib/SILGen"
            "github_url": str,
            "design_doc": str         # only when a phase has one
        }
    ]
}
```

---

## get_compiler_phase(name: str) -> Dict

Get a single phase by name or lib path (case-insensitive substring match).

**Returns:** The phase dict on a unique match; `{error: 'ambiguous_phase' | 'phase_not_found', candidates | available}` otherwise.

Phase descriptions are a bundled overview, not a fresh fetch of the landing page.
Use the linked source for current details. Repository URLs use `main`; they do
not necessarily describe the user's installed compiler release.
