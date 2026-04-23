"""
Swift Compiler Documentation API
=================================

Search the Swift compiler's in-repo documentation (`github.com/swiftlang/swift/tree/main/docs`):
SIL, ABI, type checker, runtime, optimizer passes, ownership, C++ interop, generics, etc.

Returns GitHub paths; pair with `fetch_github_file` to read a specific file.
"""

import json
import time
import urllib.request
from typing import Dict, List, Optional


REPO = "swiftlang/swift"
DOCS_PREFIX = "docs/"
TREE_API = f"https://api.github.com/repos/{REPO}/git/trees/main?recursive=1"
BLOB_BASE = f"https://github.com/{REPO}/blob/main"
LANDING_URL = "https://www.swift.org/documentation/swift-compiler/"

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


class CompilerDocsAPI:
    def __init__(self):
        self.tree_cache: Optional[List[Dict]] = None
        self.tree_cache_time = 0.0
        self.cache_ttl = 3600

    def _fetch_tree(self) -> Optional[List[Dict]]:
        if self.tree_cache and (time.time() - self.tree_cache_time) < self.cache_ttl:
            return self.tree_cache
        try:
            req = urllib.request.Request(
                TREE_API,
                headers={
                    'User-Agent': 'AppleDeveloperDocs/1.0',
                    'Accept': 'application/vnd.github+json',
                }
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
            tree = [e for e in data.get('tree', []) if e.get('path', '').startswith(DOCS_PREFIX)]
            self.tree_cache = tree
            self.tree_cache_time = time.time()
            return tree
        except Exception:
            return None


_api = CompilerDocsAPI()


def _file_matches(path: str, terms: List[str]) -> bool:
    p = path.lower()
    return all(term in p for term in terms)


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
    tree = _api._fetch_tree()
    if tree is None:
        return {
            "error": "Failed to fetch docs tree from GitHub",
            "suggestion": "Check connectivity to api.github.com or try again (rate-limited?)"
        }

    limit = max(0, limit)
    terms = [t.lower() for t in (query or "").split() if t]
    results: List[Dict] = []
    for entry in tree:
        if entry.get('type') != 'blob':
            continue
        path = entry.get('path', '')
        if terms and not _file_matches(path, terms):
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


def list_compiler_phases() -> Dict:
    """
    List the Swift compiler's pipeline phases (from swift.org's architecture overview).

    Returns:
        {"landing_url": str, "phases": [{name, description, lib_path, github_url}, ...]}
    """
    phases = []
    for p in COMPILER_PHASES:
        entry = dict(p)
        entry["github_url"] = f"{BLOB_BASE}/{p['lib_path']}"
        phases.append(entry)
    return {"landing_url": LANDING_URL, "phases": phases}


def get_compiler_phase(name: str) -> Dict:
    """
    Get a single compiler phase by name (case-insensitive substring match).

    Args:
        name: Phase name (e.g., 'SIL', 'Parsing', 'IRGen', 'Sema').

    Returns:
        The phase dict, or an error dict with available names.
    """
    needle = (name or '').lower()
    matches = [p for p in COMPILER_PHASES if needle in p["name"].lower() or needle in p["lib_path"].lower()]
    if not matches:
        return {
            "error": f"No compiler phase matching '{name}'",
            "available": [p["name"] for p in COMPILER_PHASES],
        }
    if len(matches) > 1:
        return {
            "error": f"Ambiguous phase '{name}'",
            "candidates": [p["name"] for p in matches],
        }
    p = dict(matches[0])
    p["github_url"] = f"{BLOB_BASE}/{p['lib_path']}"
    return p
