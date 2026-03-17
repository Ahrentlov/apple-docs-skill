"""
Apple Developer Documentation API
=================================

Standalone implementation for fetching Apple Developer documentation.
"""

import json
import urllib.request
import urllib.parse
import time
from typing import Dict, Optional


class AppleDocsAPI:
    """Interface to Apple Developer documentation via JSON API."""

    def __init__(self):
        self.cache = {}
        self.cache_ttl = 3600
        self.base_url = "https://developer.apple.com/documentation/"

    def _fetch_json(self, url: str) -> Optional[Dict]:
        """Fetch JSON with caching."""
        cache_key = f"{url}:{int(time.time() // self.cache_ttl)}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                    'Accept': 'application/json'
                }
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read())
                    self.cache[cache_key] = data
                    if len(self.cache) > 100:
                        self.cache = dict(list(self.cache.items())[-50:])
                    return data
        except Exception:
            pass
        return None

    def _extract_declaration(self, sections: list) -> str:
        """Extract declaration text from primaryContentSections."""
        tokens = [
            token.get("text", "")
            for section in sections if section.get("kind") == "declarations"
            for declaration in section.get("declarations", [])
            for token in declaration.get("tokens", [])
        ]
        return "".join(tokens)

    def _extract_discussion(self, sections: list) -> str:
        """Extract discussion text from primaryContentSections."""
        paragraphs = [
            content.get("inlineContent", [{}])[0].get("text", "")
            for section in sections if section.get("kind") == "content"
            for content in section.get("content", [])
            if content.get("type") == "paragraph" and content.get("inlineContent")
        ]
        return "".join(paragraphs)

    def _extract_abstract(self, items: list) -> str:
        """Extract abstract text from abstract items."""
        return "".join(
            item.get("text", "") for item in items if item.get("type") == "text"
        )

    def _parse_documentation_json(self, data: Dict) -> Dict:
        """Parse Apple's documentation JSON format."""
        sections = data.get("primaryContentSections", [])

        return {
            "title": data.get("metadata", {}).get("title", "Unknown"),
            "abstract": self._extract_abstract(data.get("abstract", [])),
            "declaration": self._extract_declaration(sections),
            "discussion": self._extract_discussion(sections),
            "parameters": [],
            "returns": ""
        }


_api = AppleDocsAPI()


def fetch_documentation(url: str) -> Dict:
    """Fetch and parse documentation from Apple Developer website."""
    if not url.startswith("https://developer.apple.com/documentation/"):
        return {"error": "Invalid URL", "message": "URL must be from developer.apple.com/documentation/"}

    try:
        path = url.split("/documentation/", 1)[1].rstrip('/')
        json_url = f"https://developer.apple.com/tutorials/data/documentation/{path}.json"
        data = _api._fetch_json(json_url)

        if not data:
            json_url = f"https://developer.apple.com/documentation/{path}/data.json"
            data = _api._fetch_json(json_url)

        if not data:
            return {"error": "Failed to fetch", "url": url}

        parsed = _api._parse_documentation_json(data)
        parsed["url"] = url
        parsed["json_url"] = json_url
        return parsed

    except Exception as e:
        return {"error": str(e), "url": url}


def search_apple_online_urls(query: str, platform: Optional[str] = None) -> Dict:
    """Generate search URLs for Apple documentation."""
    encoded_query = urllib.parse.quote(query)
    result = {
        "query": query,
        "platform": platform,
        "apple_url": f"https://developer.apple.com/documentation/technologies?filter={encoded_query}",
        "google_url": f"https://www.google.com/search?q=site:developer.apple.com+{encoded_query}",
        "github_url": f"https://github.com/search?q={encoded_query}+language:swift&type=code"
    }
    if platform:
        result["apple_url"] += f"+{platform}"
    return result


def get_framework_info(framework: str) -> Dict:
    """Get documentation URL for a framework."""
    framework_path = framework.lower().replace(" ", "").replace("-", "")
    return {
        "name": framework,
        "url": f"https://developer.apple.com/documentation/{framework_path}",
        "note": "Direct link to framework documentation"
    }
