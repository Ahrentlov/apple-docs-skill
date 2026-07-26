"""
Swift Repositories API
======================

Standalone implementation for searching and fetching from Apple's open-source
Swift repositories on GitHub. No API key required - uses web URLs.
"""

import urllib.request
import urllib.parse
import re
from typing import Dict, Optional

from ._utils import UA_APP, mark_untrusted, require_string


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

    GITHUB_URL_PATTERNS = [
        re.compile(r'github\.com/(apple|swiftlang)/([^/]+)/blob/([^/]+)/(.+)'),
        re.compile(r'raw\.githubusercontent\.com/(apple|swiftlang)/([^/]+)/([^/]+)/(.+)'),
    ]

    def _parse_github_url(self, url: str) -> Optional[Dict]:
        """Parse GitHub URL to extract org, repo, branch, and path."""
        for pattern in self.GITHUB_URL_PATTERNS:
            match = pattern.search(url)
            if match:
                org, repo, branch, path = match.groups()
                return {'org': org, 'repo': repo, 'branch': branch, 'path': path}
        return None

    def _convert_to_raw_url(self, url: str) -> Optional[str]:
        """Convert GitHub URL to raw content URL."""
        if 'raw.githubusercontent.com' in url:
            return url
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
        'note': "GitHub's search algorithm will automatically find relevant code, types, and discussions.",
        'tip': 'Start with "github_search" - it searches across code, comments, and documentation.'
    }


def fetch_github_file(url: str) -> Dict:
    """
    Fetch source code from a GitHub file (apple or swiftlang organizations only).

    Args:
        url: GitHub file URL (e.g., https://github.com/apple/swift/blob/main/stdlib/public/Concurrency/Task.swift)

    Returns:
        Dictionary with file content and metadata, or error
    """
    err = require_string(url, 'url')
    if err: return err
    # Security: Only allow Apple's official organizations via proper URL parsing
    parsed = urllib.parse.urlparse(url)
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

        with urllib.request.urlopen(req, timeout=15) as response:
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
            return mark_untrusted({
                "content": content,
                "url": url,
                "raw_url": raw_url,
                "language": _api._detect_language(repo_info['path']),
                "repo": repo,
                "path": repo_info['path'],
                "size": len(content),
                "lines": content.count('\n') + 1
            }, f"github.com/{repo}", wrap_field="content")

    except urllib.error.HTTPError as e:
        return {"error": "http_error", "status": e.code, "message": str(e.reason), "url": url}
    except urllib.error.URLError as e:
        return {"error": "network_error", "message": str(e.reason), "url": url}
    except Exception as e:
        return {"error": "fetch_failed", "message": str(e), "url": url}
