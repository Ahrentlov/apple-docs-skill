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


class SwiftReposAPI:
    """Search and fetch from Apple's Swift open source repositories."""

    ALLOWED_ORGS = {'apple', 'swiftlang'}

    GITHUB_URL_PATTERNS = [
        re.compile(r'github\.com/(apple|swiftlang)/([^/]+)/blob/([^/]+)/(.+)'),
        re.compile(r'raw\.githubusercontent\.com/(apple|swiftlang)/([^/]+)/([^/]+)/(.+)'),
    ]

    def __init__(self):
        self.cache = {}

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
        """Detect programming language from file extension."""
        ext_map = {
            '.swift': 'swift', '.md': 'markdown', '.py': 'python',
            '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.c': 'c',
            '.h': 'header', '.hpp': 'header', '.json': 'json',
            '.yaml': 'yaml', '.yml': 'yaml', '.sh': 'shell', '.txt': 'text'
        }
        for ext, lang in ext_map.items():
            if path.endswith(ext):
                return lang
        return 'unknown'


_api = SwiftReposAPI()


def search_swift_repos(query: str) -> Dict:
    """
    Search across all Apple and SwiftLang Swift repositories.

    Args:
        query: Search term (e.g., "async", "SPM", "property wrapper")

    Returns:
        Dictionary with search URLs for different scopes
    """
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
    # Security: Only allow Apple's official organizations
    allowed_domains = [
        f"{domain}/{org}/"
        for domain in ('github.com', 'raw.githubusercontent.com')
        for org in _api.ALLOWED_ORGS
    ]
    if not any(domain in url for domain in allowed_domains):
        return {
            "error": "Invalid URL",
            "message": "URL must be from github.com/apple/ or github.com/swiftlang/ organizations",
            "suggestion": "Example: https://github.com/apple/swift/blob/main/stdlib/public/Concurrency/Task.swift"
        }

    try:
        repo_info = _api._parse_github_url(url)
        if not repo_info:
            return {
                "error": "Invalid GitHub URL format",
                "message": "Could not parse repository and file information from URL",
                "url": url
            }

        raw_url = _api._convert_to_raw_url(url)
        if not raw_url:
            return {
                "error": "Invalid GitHub URL format",
                "message": "Could not convert URL to raw content URL",
                "url": url
            }

        # Check cache
        if raw_url in _api.cache:
            return _api.cache[raw_url]

        req = urllib.request.Request(
            raw_url,
            headers={
                'User-Agent': 'AppleDeveloperDocs/1.0',
                'Accept': 'text/plain, */*'
            }
        )

        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status != 200:
                return {"error": f"HTTP {response.status}", "message": "Failed to fetch file", "url": url}

            content = response.read().decode('utf-8')
            result = {
                "content": content,
                "url": url,
                "raw_url": raw_url,
                "language": _api._detect_language(repo_info['path']),
                "repo": f"{repo_info['org']}/{repo_info['repo']}",
                "path": repo_info['path'],
                "size": len(content),
                "lines": content.count('\n') + 1
            }

            _api.cache[raw_url] = result
            if len(_api.cache) > 50:
                _api.cache = dict(list(_api.cache.items())[-25:])

            return result

    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "message": str(e.reason), "url": url}
    except urllib.error.URLError as e:
        return {"error": "Network error", "message": str(e.reason), "url": url}
    except Exception as e:
        return {"error": "Fetch failed", "message": str(e), "url": url}
