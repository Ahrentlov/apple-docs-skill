# Swift Compiler Internals

Search the Swift compiler's in-repo documentation (`github.com/swiftlang/swift/tree/main/docs`):
SIL, ABI, type checker, runtime, optimizer passes, ownership, generics, C++ interop.

## search_compiler_docs(query: str, limit: int = 25) -> Dict

Keyword search against file paths (directory + filename).

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

## search_compiler_docs_text(query: str, limit: int = 10, max_files: int = 60) -> Dict

Full-text search inside compiler docs. Path-prefilters candidates (ALL terms in
path → ANY term → all blobs), fetches up to `max_files` docs (capped at 200),
greps for ALL terms on the same line.

**Returns:**
```python
{
    "query": str,
    "files_searched": int,
    "candidate_files": int,        # how many path-matches existed before max_files truncation
    "truncated": bool,             # True when candidate_files > max_files
    "matches_returned": int,
    "results": [
        {
            "path": str,
            "line_number": int,
            "line": str,             # trimmed match (max 240 chars)
            "github_url": str        # link with #L<line> anchor
        }
    ]
}
```

`matches_returned` is the count of returned hits, not a true total — the search
stops at the first `limit` matches across the first `max_files` candidates.
When `truncated` is True, raise `max_files` (up to 200) to scan more.

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
