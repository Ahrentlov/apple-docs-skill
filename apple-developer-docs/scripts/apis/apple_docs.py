"""
Apple Developer Documentation API
=================================

Standalone implementation for fetching Apple Developer documentation.
"""

import json
import socket
import urllib.request
import urllib.parse
import urllib.error
import time
from typing import Dict, Optional


class AppleDocsAPI:
    """Interface to Apple Developer documentation via JSON API."""

    def __init__(self):
        self.cache = {}
        self.cache_ttl = 3600
        self.base_url = "https://developer.apple.com/documentation/"

    def _fetch_json(self, url: str) -> Dict:
        """Fetch JSON with caching. Raises on any failure — callers should handle exceptions."""
        cache_key = f"{url}:{int(time.time() // self.cache_ttl)}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                'Accept': 'application/json'
            }
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
        self.cache[cache_key] = data
        if len(self.cache) > 100:
            self.cache = dict(list(self.cache.items())[-50:])
        return data

    def _extract_declaration(self, sections: list) -> str:
        """Extract declaration text from primaryContentSections."""
        tokens = [
            token.get("text", "")
            for section in sections if section.get("kind") == "declarations"
            for declaration in section.get("declarations", [])
            for token in declaration.get("tokens", [])
        ]
        return "".join(tokens)

    def _render_inline_item(self, item: Dict, references: Optional[Dict]) -> str:
        """Render a single inlineContent item to text."""
        kind = item.get("type")
        if kind == "text":
            return item.get("text", "")
        if kind == "codeVoice":
            code = item.get("code", "")
            return f"`{code}`" if code else ""
        if kind == "reference":
            ident = item.get("identifier", "")
            title = (references or {}).get(ident, {}).get("title", "")
            return f"`{title}`" if title else ident.rsplit("/", 1)[-1]
        if kind in ("emphasis", "strong"):
            return self._extract_inline_text(item.get("inlineContent", []), references)
        return ""

    def _extract_inline_text(self, items: list, references: Optional[Dict] = None) -> str:
        """Flatten an inlineContent list into readable text (text, codeVoice, reference, emphasis, strong)."""
        return "".join(self._render_inline_item(item, references) for item in items or [])

    def _render_content_block(self, block: Dict, references: Optional[Dict] = None) -> str:
        """Render a single content-section block: paragraph, code, list, aside, termList."""
        btype = block.get("type")
        if btype == "paragraph":
            return self._extract_inline_text(block.get("inlineContent", []), references)
        if btype == "codeListing":
            syntax = block.get("syntax", "") or ""
            code = "\n".join(block.get("code", []))
            return f"```{syntax}\n{code}\n```"
        if btype == "aside":
            style = (block.get("style") or "note").capitalize()
            body = self._content_blocks_to_text(block.get("content", []), references)
            return f"**{style}:** {body}" if body else ""
        if btype in ("unorderedList", "orderedList"):
            return self._render_list(block, references)
        if btype == "termList":
            return self._render_term_list(block, references)
        return ""

    def _render_list(self, block: Dict, references: Optional[Dict]) -> str:
        """Render an unordered or ordered list as markdown-style lines."""
        ordered = block.get("type") == "orderedList"
        lines = []
        for n, item in enumerate(block.get("items", []), 1):
            body = self._content_blocks_to_text(item.get("content", []), references)
            if not body:
                continue
            prefix = f"{n}." if ordered else "-"
            lines.append(f"{prefix} {body}")
        return "\n".join(lines)

    def _render_term_list(self, block: Dict, references: Optional[Dict]) -> str:
        """Render a termList as **term**: definition lines."""
        lines = []
        for item in block.get("items", []):
            term = self._extract_inline_text(item.get("term", {}).get("inlineContent", []), references)
            definition = self._content_blocks_to_text(item.get("definition", {}).get("content", []), references)
            if term or definition:
                lines.append(f"**{term}**: {definition}" if term else definition)
        return "\n".join(lines)

    def _content_blocks_to_text(self, blocks: list, references: Optional[Dict] = None) -> str:
        """Render a list of content blocks joined by blank lines."""
        rendered = (self._render_content_block(b, references) for b in blocks or [])
        return "\n\n".join(r for r in rendered if r)

    def _extract_content_by_heading(self, sections: list, references: Optional[Dict] = None) -> Dict[str, str]:
        """Group content-kind sections by heading, rendering full content (paragraphs + code + lists + asides)."""
        grouped: Dict[str, list] = {}
        for section in sections:
            if section.get("kind") != "content":
                continue
            current = None
            for item in section.get("content", []):
                if item.get("type") == "heading":
                    current = item.get("text", "")
                    continue
                if current is None:
                    continue
                grouped.setdefault(current, []).append(item)
        return {heading: self._content_blocks_to_text(blocks, references) for heading, blocks in grouped.items()}

    def _extract_parameters(self, sections: list, references: Optional[Dict] = None) -> list:
        """Extract parameter docs from parameters-kind sections."""
        return [
            {"name": p.get("name", ""), "description": self._content_blocks_to_text(p.get("content", []), references)}
            for section in sections if section.get("kind") == "parameters"
            for p in section.get("parameters", [])
        ]

    def _extract_possible_values(self, sections: list, references: Optional[Dict] = None) -> list:
        """Extract possible values from possibleValues-kind sections."""
        return [
            {"name": v.get("name", ""), "description": self._content_blocks_to_text(v.get("content", []), references)}
            for section in sections if section.get("kind") == "possibleValues"
            for v in section.get("values", [])
        ]

    def _resolve_ref(self, identifier: str, references: Optional[Dict]) -> Dict[str, str]:
        """Turn a doc:// identifier into {title, url} via the references map."""
        ref = (references or {}).get(identifier, {})
        url = ref.get("url", "")
        return {
            "title": ref.get("title", ""),
            "url": f"https://developer.apple.com{url}" if url else "",
        }

    def _extract_see_also(self, data: Dict) -> list:
        """Extract cross-referenced related topics from seeAlsoSections."""
        references = data.get("references", {})
        groups = []
        for section in data.get("seeAlsoSections", []):
            items = [self._resolve_ref(i, references) for i in section.get("identifiers", [])]
            items = [i for i in items if i["title"]]
            if items:
                groups.append({"title": section.get("title", ""), "items": items})
        return groups

    def _extract_relationships(self, data: Dict) -> list:
        """Extract conformsTo / inheritsFrom / inheritedBy relationships."""
        references = data.get("references", {})
        out = []
        for section in data.get("relationshipsSections", []):
            items = [self._resolve_ref(i, references) for i in section.get("identifiers", [])]
            items = [i for i in items if i["title"]]
            if items:
                out.append({
                    "title": section.get("title", ""),
                    "kind": section.get("type", ""),
                    "items": items,
                })
        return out

    def _extract_deprecation(self, data: Dict, references: Optional[Dict] = None) -> str:
        """Render top-level deprecationSummary as text."""
        return self._content_blocks_to_text(data.get("deprecationSummary") or [], references)

    def _extract_details(self, sections: list) -> Dict:
        """Extract metadata block (name, platforms, titleStyle, etc.) from details-kind section."""
        for section in sections:
            if section.get("kind") == "details":
                return section.get("details", {})
        return {}

    def _extract_mentions(self, sections: list, references: Optional[Dict]) -> list:
        """Extract cross-references from mentions-kind sections."""
        out = []
        for section in sections:
            if section.get("kind") != "mentions":
                continue
            for ident in section.get("mentions", []):
                item = self._resolve_ref(ident, references)
                if item["title"]:
                    out.append(item)
        return out

    def _extract_abstract(self, items: list) -> str:
        """Extract abstract text from abstract items."""
        return "".join(
            item.get("text", "") for item in items if item.get("type") == "text"
        )

    def _extract_symbols(self, data: Dict) -> list:
        """Extract child symbols from topicSections and references."""
        references = data.get("references", {})
        symbols = []
        for section in data.get("topicSections", []):
            group = section.get("title", "")
            for ref_id in section.get("identifiers", []):
                ref = references.get(ref_id, {})
                if ref.get("kind") != "symbol":
                    continue
                fragments = ref.get("fragments", [])
                declaration = "".join(f.get("text", "") for f in fragments)
                abstract_items = ref.get("abstract", [])
                abstract = "".join(
                    item.get("text", "") for item in abstract_items
                    if item.get("type") == "text"
                )
                symbols.append({
                    "name": ref.get("title", ""),
                    "declaration": declaration,
                    "abstract": abstract,
                    "group": group,
                    "role": ref.get("role", ""),
                    "url": f"https://developer.apple.com{ref.get('url', '')}",
                })
        return symbols

    def _parse_documentation_json(self, data: Dict) -> Dict:
        """Parse Apple's documentation JSON format."""
        sections = data.get("primaryContentSections", [])
        references = data.get("references", {})

        headings = self._extract_content_by_heading(sections, references)

        result = {
            "title": data.get("metadata", {}).get("title", "Unknown"),
            "abstract": self._extract_abstract(data.get("abstract", [])),
            "declaration": self._extract_declaration(sections),
            "discussion": headings.pop("Discussion", ""),
            "parameters": self._extract_parameters(sections, references),
            "returns": headings.pop("Return Value", ""),
        }

        optional_fields = {
            "deprecation": self._extract_deprecation(data, references),
            "possible_values": self._extract_possible_values(sections, references),
            "content_sections": headings,
            "see_also": self._extract_see_also(data),
            "relationships": self._extract_relationships(data),
            "mentions": self._extract_mentions(sections, references),
            "details": self._extract_details(sections),
            "symbols": self._extract_symbols(data),
        }
        for key, value in optional_fields.items():
            if value:
                result[key] = value

        return result


_api = AppleDocsAPI()


def fetch_documentation(url: str) -> Dict:
    """Fetch and parse documentation from Apple Developer website.

    On failure, returns a dict with an ``error`` key identifying the cause:
      * ``invalid_url`` — URL doesn't start with developer.apple.com/documentation/
      * ``not_found``  — page doesn't exist (HTTP 404)
      * ``http_error`` — other HTTP status (includes ``status`` field)
      * ``timeout``    — request exceeded 10s
      * ``network_error`` — DNS/connection/reset/SSL failure (includes ``reason`` field)
      * ``invalid_json`` — response wasn't valid JSON
    """
    if not url.startswith("https://developer.apple.com/documentation/"):
        return {"error": "invalid_url", "message": "URL must be from developer.apple.com/documentation/", "url": url}

    path = url.split("/documentation/", 1)[1].rstrip('/')
    json_url = f"https://developer.apple.com/tutorials/data/documentation/{path}.json"

    try:
        data = _api._fetch_json(json_url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"error": "not_found", "message": f"No documentation at {url}", "url": url}
        return {"error": "http_error", "status": e.code, "message": f"HTTP {e.code}: {e.reason}", "url": url}
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return {"error": "timeout", "message": "Request exceeded 10s", "url": url}
        return {"error": "network_error", "reason": type(reason).__name__, "message": str(reason), "url": url}
    except json.JSONDecodeError as e:
        return {"error": "invalid_json", "message": str(e), "url": url}

    parsed = _api._parse_documentation_json(data)
    parsed["url"] = url
    parsed["json_url"] = json_url
    return parsed


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
