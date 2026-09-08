"""
Swift Compiler Documentation API
=================================

Search the Swift compiler's in-repo documentation (`github.com/swiftlang/swift/tree/main/docs`):
SIL, ABI, type checker, runtime, optimizer passes, ownership, C++ interop, generics, etc.

Returns GitHub paths; pair with `fetch_github_file` to read a specific file.
"""

import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from ._github import resolve_revision
from ._utils import open_url, UA_APP, all_terms_match, clamp_limit, fetch_json, mark_untrusted, require_string

# Upper bound for full-text candidate files; set above the corpus size so the
# `truncated` hint to raise max_files stays actionable rather than a false ceiling.
MAX_TEXT_FILES = 500


REPO = "swiftlang/swift"
DOCS_PREFIX = "docs/"
BLOB_BASE = f"https://github.com/{REPO}/blob/main"
LANDING_URL = "https://www.swift.org/documentation/swift-compiler/"

CONTENT_MAX_BYTES = 1_048_576

# Compiler phases from swift.org's landing page, mapped to their lib/ dirs.
# Used by get_compiler_phase() / list_compiler_phases() for quick orientation.
COMPILER_PHASES = [
    {
        "name": "Parsing",
        "description": "Recursive-descent parser with integrated hand-coded lexer. Produces an AST with no semantic or type information.",
        "lib_path": "lib/Parse",
    },
    {
        "name": "Semantic Analysis",
        "description": "Transforms the parsed AST into a well-formed, fully type-checked form. Handles type inference and semantic validation.",
        "lib_path": "lib/Sema",
    },
    {
        "name": "Clang Importer",
        "description": "Imports Clang modules and maps C / Objective-C APIs into their corresponding Swift APIs.",
        "lib_path": "lib/ClangImporter",
    },
    {
        "name": "SIL Generation",
        "description": "Lowers the type-checked AST into 'raw' Swift Intermediate Language (SIL).",
        "lib_path": "lib/SILGen",
        "design_doc": f"{BLOB_BASE}/docs/SIL/SIL.md",
    },
    {
        "name": "SIL Guaranteed Transformations",
        "description": "Mandatory dataflow diagnostics that produce 'canonical' SIL — run regardless of optimization level.",
        "lib_path": "lib/SILOptimizer/Mandatory",
    },
    {
        "name": "SIL Optimizations",
        "description": "High-level Swift-specific optimizations: ARC, devirtualization, generic specialization, loop transforms.",
        "lib_path": "lib/SILOptimizer",
    },
    {
        "name": "LLVM IR Generation",
        "description": "Lowers SIL to LLVM IR. LLVM takes over for final optimization and machine-code generation.",
        "lib_path": "lib/IRGen",
    },
]


def _fetch_tree(ref="main") -> Optional[List[Dict]]:
    # Resolve docs/ first: the repository-wide recursive tree may be truncated
    # by GitHub before it reaches all documentation entries.
    root = fetch_json(f"https://api.github.com/repos/{REPO}/git/trees/{ref}", extra_headers={'Accept': 'application/vnd.github+json'})
    if not isinstance(root, dict):
        return None
    docs = next((e for e in root.get('tree', []) if e.get('path') == 'docs' and e.get('type') == 'tree'), None)
    if not docs:
        return None
    data = fetch_json(f"https://api.github.com/repos/{REPO}/git/trees/{docs['sha']}?recursive=1")
    if not isinstance(data, dict) or data.get('truncated'):
        return None
    return [dict(e, path=DOCS_PREFIX + e['path']) for e in data.get('tree', []) if 'path' in e]


def _fetch_content(path: str, ref="main") -> Optional[Dict]:
    raw_url = f"https://raw.githubusercontent.com/{REPO}/{ref}/{path}"
    try:
        req = urllib.request.Request(raw_url, headers={'User-Agent': UA_APP})
        with open_url(req, timeout=10) as response:
            data = response.read(CONTENT_MAX_BYTES + 1)
            partial = len(data) > CONTENT_MAX_BYTES
            prefix = data[:CONTENT_MAX_BYTES]
            # Drop an incomplete last line rather than inventing a shortened match.
            if partial:
                newline = prefix.rfind(b'\n')
                prefix = prefix[:newline + 1] if newline >= 0 else b''
            return {"text": prefix.decode('utf-8', errors='replace'),
                    "truncated": partial, "bytes_searched": len(prefix)}
    except Exception:
        return None


def _enrich_phase(phase: Dict) -> Dict:
    out = dict(phase)
    out["github_url"] = f"{BLOB_BASE}/{phase['lib_path']}"
    return out


def search_compiler_docs(query: str, limit: int = 25, ref: str = "main") -> Dict:
    """
    Search Swift compiler documentation files in `swiftlang/swift/docs/`.

    Matches keywords case-insensitively against the file path (directory + filename).
    Returns file entries you can fetch with `fetch_github_file`.

    Args:
        query: Space-separated keywords (e.g., "SIL optimization", "ownership", "ABI mangling").
        limit: Max results (default 25).
        ref: Branch, tag, or commit; resolved once before tree and content reads.

    Returns:
        {"query": str, "total_matches": int, "returned": int, "results": [file, ...]}
        Each file: {path, name, directory, github_url, raw_url}
    """
    err = require_string(query, 'query')
    if err: return err
    revision = resolve_revision(REPO, ref)
    if 'error' in revision: return revision
    ref = revision['resolved_ref']
    tree = _fetch_tree(ref)
    if tree is None:
        return {
            "error": "fetch_failed",
            "message": "Could not fetch docs tree — check connectivity to api.github.com (or rate limit)",
        }

    limit = clamp_limit(limit)
    terms = [t.lower() for t in query.split() if t]
    results: List[Dict] = []
    for entry in tree:
        if entry.get('type') != 'blob':
            continue
        path = entry.get('path', '')
        if terms and not all_terms_match(path, terms):
            continue
        name = path.rsplit('/', 1)[-1]
        directory = path.rsplit('/', 1)[0] if '/' in path else ''
        results.append({
            "path": path,
            "name": name,
            "directory": directory,
            "github_url": f"https://github.com/{REPO}/blob/{ref}/{path}",
            "raw_url": f"https://raw.githubusercontent.com/{REPO}/{ref}/{path}",
        })

    results.sort(key=lambda r: r["path"])

    return mark_untrusted({
        **revision, "query": query,
        "truncated": len(results) > limit,
        "total_matches": len(results),
        "returned": min(len(results), limit),
        "results": results[:limit],
    }, "github.com/swiftlang/swift docs")


def search_compiler_docs_text(query: str, limit: int = 10, max_files: int = 60, ref: str = "main") -> Dict:
    """
    Full-text search inside the Swift compiler's `/docs` files.

    Prioritizes candidates by keyword match against file paths without excluding
    the rest of the docs corpus, then fetches up to `max_files` text files. Returns
    matched lines so callers can decide whether to read the whole file via
    `fetch_github_file`.

    Args:
        query: Space-separated keywords. All terms must appear in the same line.
        limit: Max line-level matches to return (default 10).
        max_files: Max files to grep into (default 60, capped at 500).
        ref: Branch, tag, or commit; resolved once before tree and content reads.

    Returns:
        {"query": str, "files_searched": int, "matches_returned": int,
         "candidate_files": int, "truncated": bool,
         "results": [{path, line_number, line, github_url}, ...]}

    Note: `matches_returned` is the count of returned hits, not a true total —
    the search stops after enough hits within the file budget. `truncated=True`
    also covers failed/partially read files and omitted matches. Check truncated_files, failed_files
    and match_limit_reached before interpreting coverage.
    """
    err = require_string(query, 'query')
    if err: return err
    terms = [t.lower() for t in query.split() if t]
    if not terms:
        return {"error": "empty_query", "message": "search_compiler_docs_text needs at least one keyword"}

    revision = resolve_revision(REPO, ref)
    if 'error' in revision: return revision
    ref = revision['resolved_ref']
    tree = _fetch_tree(ref)
    if tree is None:
        return {
            "error": "fetch_failed",
            "message": "Could not fetch docs tree — check connectivity to api.github.com (or rate limit)",
        }

    blobs = sorted(e.get('path', '') for e in tree if e.get('type') == 'blob' and e.get('path', '').endswith(('.md', '.rst', '.txt')))
    # Path hits are prioritized, never used to exclude the rest of the corpus.
    blobs.sort(key=lambda p: -sum(term in p.lower() for term in terms))
    candidate_count = len(blobs)
    path_priority_matches = sum(any(term in path.lower() for term in terms) for path in blobs)
    max_files = clamp_limit(max_files, cap=MAX_TEXT_FILES)
    paths = blobs[:max_files]
    limit = clamp_limit(limit)
    results = []
    failures = []
    partial_files = []
    files_searched = 0
    searched_paths = []
    attempted = 0
    match_limit_reached = False
    if limit:
        with ThreadPoolExecutor(max_workers=8) as pool:
            for start in range(0, len(paths), 8):
                batch = paths[start:start + 8]
                contents = list(pool.map(lambda path: _fetch_content(path, ref), batch))
                attempted += len(batch)
                for path, content in zip(batch, contents):
                    if content is None:
                        failures.append(path)
                        continue
                    files_searched += 1
                    searched_paths.append(path)
                    if content["truncated"]:
                        partial_files.append({"path": path, "bytes_searched": content["bytes_searched"]})
                    for line_num, line in enumerate(content["text"].splitlines(), start=1):
                        if all_terms_match(line, terms):
                            if len(results) >= limit:
                                match_limit_reached = True
                                continue
                            results.append({"path": path, "line_number": line_num,
                                            "line": line.strip()[:240], "line_truncated": len(line.strip()) > 240,
                                            "github_url": f"https://github.com/{REPO}/blob/{ref}/{path}#L{line_num}"})
                if len(results) >= limit:
                    match_limit_reached = match_limit_reached or attempted < len(paths)
                    break
    incomplete = bool(failures or partial_files) or attempted < candidate_count or match_limit_reached
    return mark_untrusted({
        **revision, "query": query, "files_searched": files_searched, "files_attempted": attempted,
        "searched_paths": searched_paths, "path_priority_matches": path_priority_matches,
        "failed_files": failures, "truncated_files": partial_files,
        "content_max_bytes": CONTENT_MAX_BYTES, "max_files": max_files,
        "candidate_files": candidate_count,
        "truncated": incomplete, "match_limit_reached": match_limit_reached,
        "search_scope": "all query terms on the same line; paths prioritize scan order",
        "matches_returned": len(results), "results": results,
    }, "github.com/swiftlang/swift docs")


def list_compiler_phases() -> Dict:
    """
    List the Swift compiler's pipeline phases (from swift.org's architecture overview).

    Returns:
        {"landing_url": str, "phases": [{name, description, lib_path, github_url}, ...]}
    """
    return {
        "landing_url": LANDING_URL,
        "phases": [_enrich_phase(p) for p in COMPILER_PHASES],
    }


def get_compiler_phase(name: str) -> Dict:
    """
    Get a single compiler phase by name (case-insensitive substring match).

    Args:
        name: Phase name (e.g., 'SIL', 'Parsing', 'IRGen', 'Sema').

    Returns:
        The phase dict, or an error dict with available names.
    """
    err = require_string(name, 'name')
    if err: return err
    needle = name.lower().strip()
    if not needle:
        return {"error": "empty_name", "message": "Pass a phase name like 'IRGen' or 'Sema'"}
    matches = [p for p in COMPILER_PHASES if needle in p["name"].lower() or needle in p["lib_path"].lower()]
    if not matches:
        return {
            "error": "phase_not_found",
            "message": f"No compiler phase matching '{name}'",
            "available": [p["name"] for p in COMPILER_PHASES],
        }
    if len(matches) > 1:
        return {
            "error": "ambiguous_phase",
            "message": f"'{name}' matches multiple phases — pass a more specific name",
            "candidates": [p["name"] for p in matches],
        }
    return _enrich_phase(matches[0])
