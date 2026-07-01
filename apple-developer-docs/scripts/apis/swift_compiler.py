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

from ._utils import UA_APP, all_terms_match, clamp_limit, fetch_json, require_string

# Upper bound for full-text candidate files; set above the corpus size so the
# `truncated` hint to raise max_files stays actionable rather than a false ceiling.
MAX_TEXT_FILES = 500


REPO = "swiftlang/swift"
DOCS_PREFIX = "docs/"
TREE_API = f"https://api.github.com/repos/{REPO}/git/trees/main?recursive=1"
BLOB_BASE = f"https://github.com/{REPO}/blob/main"
LANDING_URL = "https://www.swift.org/documentation/swift-compiler/"

CONTENT_MAX_BYTES = 200_000

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


def _fetch_tree() -> Optional[List[Dict]]:
    data = fetch_json(TREE_API, extra_headers={'Accept': 'application/vnd.github+json'})
    if data is None:
        return None
    return [e for e in data.get('tree', []) if e.get('path', '').startswith(DOCS_PREFIX)]


def _fetch_content(path: str) -> Optional[str]:
    raw_url = f"https://raw.githubusercontent.com/{REPO}/main/{path}"
    try:
        req = urllib.request.Request(raw_url, headers={'User-Agent': UA_APP})
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read(CONTENT_MAX_BYTES).decode('utf-8', errors='replace')
    except Exception:
        return None


def _enrich_phase(phase: Dict) -> Dict:
    out = dict(phase)
    out["github_url"] = f"{BLOB_BASE}/{phase['lib_path']}"
    return out


def search_compiler_docs(query: str, limit: int = 25) -> Dict:
    """
    Search Swift compiler documentation files in `swiftlang/swift/docs/`.

    Matches keywords case-insensitively against the file path (directory + filename).
    Returns file entries you can fetch with `fetch_github_file`.

    Args:
        query: Space-separated keywords (e.g., "SIL optimization", "ownership", "ABI mangling").
        limit: Max results (default 25).

    Returns:
        {"query": str, "total_matches": int, "returned": int, "results": [file, ...]}
        Each file: {path, name, directory, github_url, raw_url}
    """
    err = require_string(query, 'query')
    if err: return err
    tree = _fetch_tree()
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
            "github_url": f"{BLOB_BASE}/{path}",
            "raw_url": f"https://raw.githubusercontent.com/{REPO}/main/{path}",
        })

    results.sort(key=lambda r: r["path"])

    return {
        "query": query,
        "total_matches": len(results),
        "returned": min(len(results), limit),
        "results": results[:limit],
    }


def search_compiler_docs_text(query: str, limit: int = 10, max_files: int = 60) -> Dict:
    """
    Full-text search inside the Swift compiler's `/docs` files.

    First narrows candidates by keyword match against file paths, then fetches
    up to `max_files` candidates and greps each for all query terms. Returns
    matched lines so callers can decide whether to read the whole file via
    `fetch_github_file`.

    Args:
        query: Space-separated keywords. All terms must appear in the same line.
        limit: Max line-level matches to return (default 10).
        max_files: Max files to grep into (default 60, capped at 500).

    Returns:
        {"query": str, "files_searched": int, "matches_returned": int,
         "candidate_files": int, "truncated": bool,
         "results": [{path, line_number, line, github_url}, ...]}

    Note: `matches_returned` is the count of returned hits, not a true total —
    the search stops at the first `limit` matches across the first `max_files`
    candidates. `truncated=True` means more candidate files existed than
    `max_files` allowed; raise the cap to scan more.
    """
    err = require_string(query, 'query')
    if err: return err
    terms = [t.lower() for t in query.split() if t]
    if not terms:
        return {"error": "empty_query", "message": "search_compiler_docs_text needs at least one keyword"}

    tree = _fetch_tree()
    if tree is None:
        return {
            "error": "fetch_failed",
            "message": "Could not fetch docs tree — check connectivity to api.github.com (or rate limit)",
        }

    blobs = [e.get('path', '') for e in tree if e.get('type') == 'blob']
    paths_with_term = [p for p in blobs if all(term in p.lower() for term in terms)]
    if not paths_with_term:
        paths_with_term = [p for p in blobs if any(term in p.lower() for term in terms)]
    if not paths_with_term:
        paths_with_term = blobs

    candidate_count = len(paths_with_term)
    max_files = clamp_limit(max_files, cap=MAX_TEXT_FILES)
    paths_with_term = paths_with_term[:max_files]
    truncated = candidate_count > len(paths_with_term)

    limit = clamp_limit(limit)
    results: List[Dict] = []
    files_searched = 0
    if limit > 0 and paths_with_term:
        # Fetch candidates concurrently so wall-clock is bounded by the slowest
        # single request, not the sum — a sparse/zero-match query that can't break
        # early would otherwise risk the sandbox timeout fetching files serially.
        with ThreadPoolExecutor(max_workers=8) as pool:
            contents = list(pool.map(_fetch_content, paths_with_term))
        for path, content in zip(paths_with_term, contents):
            if content is None:
                continue
            files_searched += 1
            for line_num, line in enumerate(content.splitlines(), start=1):
                if len(results) >= limit:
                    break
                if all_terms_match(line, terms):
                    results.append({
                        "path": path,
                        "line_number": line_num,
                        "line": line.strip()[:240],
                        "github_url": f"{BLOB_BASE}/{path}#L{line_num}",
                    })
            if len(results) >= limit:
                break

    return {
        "query": query,
        "files_searched": files_searched,
        "candidate_files": candidate_count,
        "truncated": truncated,
        "matches_returned": len(results),
        "results": results,
    }


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
