"""
Swift Repositories API
======================

Standalone implementation for searching and fetching from Apple's open-source
Swift repositories on GitHub. No API key required - uses web URLs.
"""

import difflib
import urllib.request
import urllib.parse
from typing import Dict, Optional

from ._utils import validate_fetch_url, open_url, read_bounded, UA_APP, mark_untrusted, require_string


from ._github import resolve_revision
from ._excerpts import select_text, validate_selection

MAX_FILE_BYTES = 1_000_000

EXTENSION_LANGUAGES = {
    'swift': 'swift', 'md': 'markdown', 'py': 'python',
    'cpp': 'cpp', 'cc': 'cpp', 'cxx': 'cpp', 'c': 'c',
    'h': 'header', 'hpp': 'header', 'json': 'json',
    'yaml': 'yaml', 'yml': 'yaml', 'sh': 'shell', 'txt': 'text',
}


class SwiftReposAPI:
    """Search and fetch from Apple's Swift open source repositories."""

    ALLOWED_ORGS = {'apple', 'swiftlang'}

    def _parse_github_url(self, url: str) -> Optional[Dict]:
        """Parse GitHub URL to extract org, repo, branch, and path."""
        parsed = urllib.parse.urlsplit(url)
        parts = parsed.path.strip('/').split('/')
        if parsed.hostname == 'github.com':
            if len(parts) < 5 or parts[2] != 'blob':
                return None
            org, repo, _, branch, *path = parts
        elif parsed.hostname == 'raw.githubusercontent.com':
            if len(parts) < 4:
                return None
            org, repo, branch, *path = parts
        else:
            return None
        if org not in self.ALLOWED_ORGS:
            return None
        return {'org': org, 'repo': repo, 'branch': branch, 'path': '/'.join(path)}

    def _convert_to_raw_url(self, url: str) -> Optional[str]:
        info = self._parse_github_url(url)
        if info:
            return f"https://raw.githubusercontent.com/{info['org']}/{info['repo']}/{info['branch']}/{info['path']}"
        return None

    def _detect_language(self, path: str) -> str:
        ext = path.rsplit('.', 1)[-1].lower() if '.' in path else ''
        return EXTENSION_LANGUAGES.get(ext, 'unknown')


_api = SwiftReposAPI()


def search_swift_repos_urls(query: str) -> Dict:
    """
    Search across all Apple and SwiftLang Swift repositories.

    Args:
        query: Search term (e.g., "async", "SPM", "property wrapper")

    Returns:
        Dictionary with search URLs for different scopes
    """
    err = require_string(query, 'query')
    if err: return err
    encoded_query = urllib.parse.quote(query)

    return {
        'query': query,
        'search_urls': {
            'github_search': f"https://github.com/search?q={encoded_query}+org:apple+org:swiftlang&type=code",
            'swift_code': f"https://github.com/search?q={encoded_query}+language:Swift+org:apple+org:swiftlang&type=code",
            'repositories': f"https://github.com/search?q={encoded_query}+org:apple+org:swiftlang&type=repositories",
            'issues': f"https://github.com/search?q={encoded_query}+org:apple+org:swiftlang&type=issues",
            'apple_org': f"https://github.com/search?q={encoded_query}+org:apple&type=code",
            'swiftlang_org': f"https://github.com/search?q={encoded_query}+org:swiftlang&type=code",
        },
        'note': "URLs only; open with an available browser/search tool. GitHub code search may require sign-in.",
        'tip': 'Start with "github_search" - it searches across code, comments, and documentation.'
    }


def fetch_github_file(url: str, start_line=None, end_line=None, section=None, ref=None, max_lines=200) -> Dict:
    """
    Fetch source code from a GitHub file (apple or swiftlang organizations only).

    Args:
        start_line, end_line: Inclusive source lines; mutually exclusive with section.
        section: Exact Markdown/RST title or a qualified Parent > Child path.
        ref: Optional branch/tag/commit override, resolved to an immutable SHA.
        max_lines: Selected passage limit (1..1000); does not clip full-file reads.
        url: GitHub file URL (e.g., https://github.com/apple/swift/blob/main/stdlib/public/Concurrency/Task.swift)

    Returns:
        Dictionary with file content and metadata, or error
    """
    err = require_string(url, 'url')
    if err: return err
    err = validate_selection(start_line, end_line, section, max_lines)
    if err: return err
    revision = {}
    # Security: Only allow Apple's official organizations via proper URL parsing
    try:
        validate_fetch_url(url)
        parsed = urllib.parse.urlparse(url)
    except ValueError as exc:
        return {"error": "invalid_url", "message": str(exc), "url": url}
    if parsed.hostname not in ('github.com', 'raw.githubusercontent.com'):
        return {
            "error": "invalid_url",
            "message": "URL must be from github.com or raw.githubusercontent.com (e.g. https://github.com/apple/swift/blob/main/stdlib/public/Concurrency/Task.swift)",
        }
    path_parts = parsed.path.strip('/').split('/')
    if not path_parts or path_parts[0] not in _api.ALLOWED_ORGS:
        return {
            "error": "invalid_url",
            "message": "URL must be from github.com/apple/ or github.com/swiftlang/ organizations (e.g. https://github.com/apple/swift/blob/main/stdlib/public/Concurrency/Task.swift)",
        }

    try:
        repo_info = _api._parse_github_url(url)
        if not repo_info:
            return {
                "error": "invalid_url",
                "message": "Could not parse repository and file information from URL",
                "url": url,
            }

        if ref is not None:
            revision = resolve_revision(f"{repo_info['org']}/{repo_info['repo']}", ref)
            if 'error' in revision: return revision
            url = f"https://github.com/{repo_info['org']}/{repo_info['repo']}/blob/{revision['resolved_ref']}/{repo_info['path']}"
        raw_url = _api._convert_to_raw_url(url)
        if not raw_url:
            return {
                "error": "invalid_url",
                "message": "Could not convert URL to raw content URL",
                "url": url,
            }

        req = urllib.request.Request(
            raw_url,
            headers={
                'User-Agent': UA_APP,
                'Accept': 'text/plain, */*'
            }
        )

        with open_url(req, timeout=15) as response:
            content_length = int(response.headers.get('Content-Length') or 0)
            if content_length > MAX_FILE_BYTES:
                return {
                    "error": "file_too_large",
                    "message": f"File is {content_length} bytes; limit is {MAX_FILE_BYTES}",
                    "url": url,
                }
            raw_bytes = response.read(MAX_FILE_BYTES + 1)
            if len(raw_bytes) > MAX_FILE_BYTES:
                return {
                    "error": "file_too_large",
                    "message": f"File exceeds {MAX_FILE_BYTES}-byte limit",
                    "url": url,
                }
            content = raw_bytes.decode('utf-8', errors='replace')
            repo = f"{repo_info['org']}/{repo_info['repo']}"
            result = {
                "content": content,
                "url": url,
                "raw_url": raw_url,
                "language": _api._detect_language(repo_info['path']),
                "repo": repo,
                "path": repo_info['path'],
                "size": len(raw_bytes),
                "lines": len(content.splitlines()),
                "truncated": False,  # oversized downloads fail; caller excerpts may still be partial
            }
            result.update(revision)
            if section is not None or start_line is not None or end_line is not None:
                selection = select_text(content, start_line, end_line, section, max_lines,
                                        rst=repo_info['path'].endswith('.rst'))
                if 'error' in selection: return dict(selection, url=url)
                result.update(selection)
                canonical = f"https://github.com/{repo}/blob/{revision.get('resolved_ref', repo_info['branch'])}/{repo_info['path']}"
                result['citation_url'] = f"{canonical}#L{selection['start_line']}-L{selection['end_line']}"
            return mark_untrusted(result, f"github.com/{repo}", wrap_field="content")

    except urllib.error.HTTPError as e:
        return {"error": "http_error", "status": e.code, "message": str(e.reason), "url": url}
    except urllib.error.URLError as e:
        return {"error": "network_error", "message": str(e.reason), "url": url}
    except Exception as e:
        return {"error": "fetch_failed", "message": str(e), "url": url}


def compare_github_file(url: str, base_ref: str, head_ref: str, context_lines=3, max_diff_lines=400) -> Dict:
    """Compare the same text file at two resolved commits (not a merge-base diff)."""
    if type(context_lines) is not int or not 0 <= context_lines <= 20:
        return {'error': 'invalid_input', 'message': 'context_lines must be 0..20'}
    if type(max_diff_lines) is not int or not 1 <= max_diff_lines <= 2000:
        return {'error': 'invalid_input', 'message': 'max_diff_lines must be 1..2000'}
    err = require_string(url, 'url')
    if err: return err
    try:
        validate_fetch_url(url)
        info = _api._parse_github_url(url)
    except ValueError as exc:
        return {'error': 'invalid_url', 'message': str(exc)}
    if not info: return {'error': 'invalid_url', 'message': 'Expected an Apple/SwiftLang file URL'}
    repo = f"{info['org']}/{info['repo']}"
    snapshots, revisions, urls = [], [], []
    for side, ref in (('base', base_ref), ('head', head_ref)):
        revision = resolve_revision(repo, ref)
        if 'error' in revision: return dict(revision, side=side)
        pinned = f"https://github.com/{repo}/blob/{revision['resolved_ref']}/{info['path']}"
        fetched = fetch_github_file(pinned)
        if fetched.get('error') == 'http_error' and fetched.get('status') == 404:
            content = None
        elif 'error' in fetched:
            return dict(fetched, side=side)
        else:
            content = fetched['content'].split('\n', 1)[1].rsplit('\n', 1)[0]
            if '\x00' in content:
                return {'error': 'unsupported_text', 'side': side, 'message': 'Binary files are not supported'}
        snapshots.append(content)
        revisions.append(revision)
        urls.append(pinned)
    if snapshots == [None, None]: return {'error': 'file_not_found', 'base_url': urls[0], 'head_url': urls[1]}
    before, after = snapshots
    status = 'added' if before is None else 'deleted' if after is None else 'unchanged' if before == after else 'modified'
    pieces, size, line_count, truncated = [], 0, 0, False
    for line in difflib.unified_diff((before or '').splitlines(keepends=True), (after or '').splitlines(keepends=True),
                                     fromfile=urls[0], tofile=urls[1], n=context_lines):
        if not line.endswith('\n'): line += '\n\\ No newline at end of file\n'
        count = len(line.splitlines())
        if line_count + count > max_diff_lines or size + len(line) > 200000:
            truncated = True
            break
        pieces.append(line)
        size += len(line)
        line_count += count
    return mark_untrusted({'repo': repo, 'path': info['path'], 'status': status, 'changed': before != after,
        'base_ref': base_ref, 'head_ref': head_ref, 'base_commit': revisions[0]['resolved_ref'],
        'head_commit': revisions[1]['resolved_ref'], 'base_url': urls[0], 'head_url': urls[1],
        'diff': ''.join(pieces), 'diff_lines_returned': line_count,
        'truncated': truncated, 'max_diff_lines': max_diff_lines, 'max_diff_chars': 200000},
        f'github.com/{repo}', wrap_field='diff')
