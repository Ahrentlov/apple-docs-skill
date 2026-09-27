"""
Apple Developer Documentation API
=================================

Standalone implementation for fetching Apple Developer documentation.
"""

import re
import json
import urllib.parse
from typing import Dict, Optional

from ._excerpts import select_section_lines, select_text, validate_section_selection
from ._utils import validate_fetch_url, fetch_page, mark_untrusted, require_string


class AppleDocsAPI:
    """Parser for Apple's DocC JSON (fetch_documentation format='json')."""

    def _extract_declaration(self, sections: list) -> str:
        """Extract declaration text from primaryContentSections."""
        return "\n".join("".join(t.get("text", "") for t in d.get("tokens", [])) for section in sections if section.get("kind") == "declarations" for d in section.get("declarations", []))

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
            title = self._extract_inline_text(item.get("overridingTitleInlineContent", []), references) or title
            ref = (references or {}).get(ident, {})
            url = ref.get("url", "")
            label = title or ident.rsplit("/", 1)[-1]
            return f"[{label}]({urllib.parse.urljoin('https://developer.apple.com', url)})" if url else label
        if kind in ("emphasis", "strong"):
            return self._extract_inline_text(item.get("inlineContent", []), references)
        return ""

    def _extract_inline_text(self, items: list, references: Optional[Dict] = None) -> str:
        """Flatten an inlineContent list into readable text (text, codeVoice, reference, emphasis, strong)."""
        return "".join(self._render_inline_item(item, references) for item in items or [])

    def _render_content_block(self, block: Dict, references: Optional[Dict] = None) -> str:
        """Render a single content-section block: paragraph, code, list, aside, termList."""
        btype = block.get("type")
        if btype == "heading":
            return "#" * min(max(block.get("level", 2), 1), 6) + " " + block.get("text", "")
        if btype == "table":
            rows = block.get("rows", [])
            return "\n".join(" | ".join(self._content_blocks_to_text(cell, references) for cell in row) for row in rows)
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
        if isinstance(block.get("content"), list):
            return self._content_blocks_to_text(block["content"], references)
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

    def _extract_content_outline(self, sections: list, references: Optional[Dict] = None) -> list:
        """Keep source order and heading ancestry, including repeated/empty headings."""
        outline = []
        for section in sections:
            if section.get("kind") != "content":
                continue
            stack = []
            current = None
            for item in section.get("content", []):
                if item.get("type") == "heading":
                    level = item.get("level", 2)
                    while stack and stack[-1][0] >= level:
                        stack.pop()
                    stack.append((level, item.get("text", "")))
                    current = {"heading": item.get("text", ""), "level": level,
                               "path": [title for _, title in stack], "blocks": []}
                    if item.get("anchor"):
                        current["anchor"] = item["anchor"]
                    outline.append(current)
                else:
                    if current is None:
                        current = {"heading": "Overview", "level": 0, "path": ["Overview"], "blocks": []}
                        outline.append(current)
                    current["blocks"].append(item)
        for entry in outline:
            entry["content"] = self._content_blocks_to_text(entry.pop("blocks"), references)
        return outline

    def _extract_content_by_heading(self, sections: list, references: Optional[Dict] = None) -> Dict[str, str]:
        return self._outline_to_sections(self._extract_content_outline(sections, references))

    def _outline_to_sections(self, outline: list) -> Dict[str, str]:
        """Convenience mapping; never merge identically named source sections."""
        grouped = {}
        for entry in outline:
            if not entry["content"]:
                continue
            base = " > ".join(entry["path"])
            key = base
            occurrence = 1
            while key in grouped:
                occurrence += 1
                key = f"{base} [{occurrence}]"
            grouped[key] = entry["content"]
        return grouped

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
            "url": urllib.parse.urljoin("https://developer.apple.com", url) if url else "",
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

    def _extract_abstract(self, items: list, references: Optional[Dict] = None) -> str:
        return self._extract_inline_text(items, references)

    def _extract_symbols(self, data: Dict) -> list:
        """Extract child symbols from topicSections and references."""
        references = data.get("references", {})
        symbols = []
        for section in data.get("topicSections", []):
            group = section.get("title", "")
            for ref_id in section.get("identifiers", []):
                ref = references.get(ref_id, {})
                # Symbols (members) have kind="symbol"; framework / index pages
                # link children with kind="article" — keep both so framework root
                # pages enumerate their topics.
                if ref.get("kind") not in ("symbol", "article"):
                    continue
                fragments = ref.get("fragments", [])
                declaration = "".join(f.get("text", "") for f in fragments)
                abstract = self._extract_inline_text(ref.get("abstract", []), references)
                symbols.append({
                    "name": ref.get("title", ""),
                    "kind": ref.get("kind"),
                    "declaration": declaration,
                    "abstract": abstract,
                    "group": group,
                    "role": ref.get("role", ""),
                    "url": urllib.parse.urljoin("https://developer.apple.com", ref.get("url", "")),
                })
        return symbols

    def _parse_documentation_json(self, data: Dict) -> Dict:
        """Parse Apple's documentation JSON format."""
        sections = data.get("primaryContentSections", [])
        references = data.get("references", {})

        outline = self._extract_content_outline(sections, references)
        headings = self._outline_to_sections(outline)

        result = {
            "title": data.get("metadata", {}).get("title", "Unknown"),
            "abstract": self._extract_abstract(data.get("abstract", []), references),
            "declaration": self._extract_declaration(sections),
            "discussion": headings.pop("Discussion", ""),
            "parameters": self._extract_parameters(sections, references),
            "returns": headings.pop("Return Value", ""),
        }

        optional_fields = {
            "availability": data.get("metadata", {}).get("platforms", []),
            "variants": data.get("variants", []),
            "deprecation": self._extract_deprecation(data, references),
            "possible_values": self._extract_possible_values(sections, references),
            "content_sections": headings,
            "content_outline": outline,
            "see_also": self._extract_see_also(data),
            "relationships": self._extract_relationships(data),
            "mentions": self._extract_mentions(sections, references),
            "details": self._extract_details(sections),
            "symbols": self._extract_symbols(data),
        }
        for key, value in optional_fields.items():
            if value:
                result[key] = value

        supported = {"text", "codeVoice", "reference", "emphasis", "strong", "paragraph", "heading", "codeListing", "aside", "unorderedList", "orderedList", "termList", "table"}
        unrendered = set()
        def inspect(value):
            if isinstance(value, list):
                for item in value:
                    inspect(item)
            elif isinstance(value, dict):
                kind = value.get("type")
                if kind and kind not in supported:
                    unrendered.add(kind)
                for item in value.values():
                    if isinstance(item, (dict, list)):
                        inspect(item)
        inspect(sections)
        if unrendered:
            result["unrendered_types"] = sorted(unrendered)
        return result


_api = AppleDocsAPI()


DOC_FORMATS = ('markdown', 'json')

# (page prefix, Markdown base, JSON base or None, whether the bare prefix is itself a page).
# Apple serves /documentation pages as <page>.md but HIG and tutorial Markdown only under
# tutorials/data. The HIG root is a page; /documentation and /tutorials have no Markdown root.
# Tutorial JSON uses a different schema than DocC reference pages, so tutorials are Markdown-only.
_DOC_SOURCES = (
    ("https://developer.apple.com/documentation/",
     "https://developer.apple.com/documentation",
     "https://developer.apple.com/tutorials/data/documentation", False),
    ("https://developer.apple.com/design/human-interface-guidelines/",
     "https://developer.apple.com/tutorials/data/design/human-interface-guidelines",
     "https://developer.apple.com/tutorials/data/design/human-interface-guidelines", True),
    ("https://developer.apple.com/tutorials/",
     "https://developer.apple.com/tutorials/data/tutorials",
     None, False),
)


def validate_documentation_request(section, start_line, end_line, max_lines, format) -> Optional[Dict]:
    """Validate fetch_documentation's selector and format arguments before any network work."""
    if format not in DOC_FORMATS:
        return {"error": "invalid_input", "message": "format must be 'markdown' or 'json'"}
    return validate_section_selection(section, start_line, end_line, max_lines)


def _resolve_page(url: str):
    """Return ((canonical URL, Markdown URL, JSON URL), None) or (None, error dict)."""
    try:
        validate_fetch_url(url)
        parsed = urllib.parse.urlsplit(url)
    except ValueError as exc:
        return None, {"error": "invalid_url", "message": str(exc), "url": url}
    language = urllib.parse.parse_qs(parsed.query).get("language", ["swift"])[0]
    if language != "swift":
        return None, {"error": "unsupported_language", "message": "Only the default Swift DocC representation is supported; open the page for other languages", "url": url}
    # Fragments, queries, and trailing slashes are not part of the page identity.
    clean_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip('/'), '', ''))
    for prefix, md_base, json_base, root_is_page in _DOC_SOURCES:
        if (clean_url + '/').startswith(prefix):
            path = clean_url[len(prefix):]
            if path or root_is_page:
                suffix = f"/{path}" if path else ""
                return (clean_url, f"{md_base}{suffix}.md", f"{json_base}{suffix}.json" if json_base else None), None
    return None, {
        "error": "invalid_url",
        "message": "URL must be a page under developer.apple.com/documentation/, /design/human-interface-guidelines, or /tutorials/",
        "url": url,
    }


def _markdown_documentation(md_url: str, clean_url: str, section, start_line, end_line, max_lines) -> Dict:
    """Fetch Apple's Markdown rendering, split off its metadata comment, and optionally select an excerpt."""
    page, err = fetch_page(md_url, clean_url, 'text/markdown')
    if err: return err
    if page.content_type != 'text/markdown':
        return {"error": "invalid_schema", "message": f"Expected text/markdown, got {page.content_type}", "url": clean_url}
    text = page.body.decode('utf-8', errors='replace')
    metadata = {}
    match = re.match(r'\s*<!--(.*?)-->\s*', text, re.S)
    if match:
        try:
            metadata = json.loads(match[1])
        except ValueError:
            pass
        if not isinstance(metadata, dict):
            metadata = {}
        text = text[match.end():]
    title = metadata.get('title')
    result = {"title": title if isinstance(title, str) else '', "url": clean_url, "markdown_url": md_url, "metadata": metadata}
    if section is None and start_line is None and end_line is None:
        result['content'] = text
        return mark_untrusted(result, "developer.apple.com", wrap_field='content')
    selection = select_section_lines(text, section, start_line, end_line, max_lines)
    if 'error' in selection:
        return dict(selection, url=clean_url)
    result.update(selection)
    result.update({'citation_url': clean_url,
                   'line_basis': 'Markdown lines within the selected section' if section is not None else 'Markdown lines after the metadata comment'})
    return mark_untrusted(result, "developer.apple.com", wrap_field='content')


def _json_documentation(json_url: str, clean_url: str, section, start_line, end_line, max_lines) -> Dict:
    """Fetch and parse the DocC JSON, optionally selecting from its rendered outline."""
    page, err = fetch_page(json_url, clean_url, 'application/json')
    if err: return err
    try:
        data = json.loads(page.body)
    except ValueError as e:  # JSONDecodeError, or UnicodeDecodeError for non-UTF-8 bytes
        return {"error": "invalid_json", "message": str(e), "url": clean_url}

    if not isinstance(data, dict) or not isinstance(data.get("metadata"), dict):
        return {"error": "invalid_schema", "message": "Expected a DocC document with metadata", "url": clean_url}
    parsed = _api._parse_documentation_json(data)
    parsed["url"] = clean_url
    parsed["json_url"] = json_url
    if section is not None or start_line is not None or end_line is not None:
        outline = parsed.get('content_outline', [])
        selected_outline = outline
        citation = clean_url
        if section is not None:
            needle = section.strip().casefold()
            matches = [i for i, entry in enumerate(outline) if needle in
                       (entry['heading'].casefold(), ' > '.join(entry['path']).casefold())]
            if len(matches) != 1:
                candidates = [outline[i] for i in matches] if matches else outline
                return {'error': 'ambiguous_section' if matches else 'section_not_found', 'url': clean_url,
                        'candidates': [{k: e[k] for k in ('heading', 'path', 'anchor') if k in e} for e in candidates[:50]],
                        'candidates_truncated': len(candidates) > 50}
            start = matches[0]
            finish = next((i for i in range(start + 1, len(outline)) if outline[i]['level'] <= outline[start]['level']), len(outline))
            selected_outline = outline[start:finish]
            if outline[start].get('anchor'):
                citation += '#' + urllib.parse.quote(outline[start]['anchor'], safe='-._~')
        rendered = '\n\n'.join((entry['heading'] + '\n' + entry['content']).strip() for entry in selected_outline)
        selection = select_text(rendered, start_line, end_line, max_lines=max_lines)
        if 'error' in selection: return dict(selection, url=clean_url)
        parsed = {k: parsed[k] for k in ('title', 'url', 'json_url', 'availability', 'unrendered_types') if k in parsed}
        parsed.update(selection)
        parsed.update({'citation_url': citation, 'section': section, 'line_basis': 'rendered selected content; not source line numbers',
                       'excerpt_partial': True})
        return mark_untrusted(parsed, 'developer.apple.com', wrap_field='content')
    return mark_untrusted(parsed, "developer.apple.com")


def fetch_documentation(url: str, section=None, start_line=None, end_line=None, max_lines=200, format='markdown') -> Dict:
    """Fetch documentation from the Apple Developer website.

    Accepts pages under `developer.apple.com/documentation/`,
    `developer.apple.com/design/human-interface-guidelines` (including its root),
    and `developer.apple.com/tutorials/` (step-by-step tutorials; Markdown only).

    format='markdown' (default) returns Apple's Markdown rendering of the page
    in `content`, with the page's metadata comment parsed into `metadata`.
    format='json' parses the DocC JSON into structured fields (declaration,
    parameters, content_outline, symbols, ...).

    Optional section selects a heading and its descendants. Line bounds are
    relative to that selection (or the whole page), capped by max_lines (1..1000).
    Without selectors, returns the full document.

    On failure, returns a dict with an ``error`` key identifying the cause:
      * ``invalid_input``: `url` was not a string, or `format` is unknown
      * ``invalid_selection``: bad section / line / max_lines arguments
      * ``invalid_url``: URL isn't a page under an accepted developer.apple.com prefix
      * ``unsupported_language``: a non-Swift ``language`` query
      * ``unsupported_format``: format='json' for a tutorial page
      * ``not_found``: page doesn't exist (HTTP 404)
      * ``http_error``: other HTTP status (includes ``status`` field)
      * ``timeout``: request exceeded 10s
      * ``network_error``: DNS/connection/reset/SSL failure (includes ``reason`` field)
      * ``fetch_failed``: response-size limit or other fetch failure
      * ``invalid_json``: response wasn't valid JSON (format='json')
      * ``invalid_schema``: not a DocC document (JSON) or not text/markdown (Markdown)
      * ``section_not_found`` / ``ambiguous_section`` / ``line_out_of_range``: selection failed
    """
    err = require_string(url, 'url') or validate_documentation_request(section, start_line, end_line, max_lines, format)
    if err: return err
    urls, err = _resolve_page(url)
    if err: return err
    clean_url, md_url, json_url = urls
    if format == 'markdown':
        return _markdown_documentation(md_url, clean_url, section, start_line, end_line, max_lines)
    if json_url is None:
        return {"error": "unsupported_format", "message": "Tutorial pages are available as Markdown only", "url": clean_url}
    return _json_documentation(json_url, clean_url, section, start_line, end_line, max_lines)


def _version_tuple(version: str) -> tuple:
    parts = [int(p) for p in version.split('.')]
    return tuple(parts + [0] * (3 - len(parts)))


def _platform_key(name: str) -> str:
    return name.casefold().replace(' ', '')


def check_availability(url: str, platform: Optional[str] = None, version: Optional[str] = None) -> Dict:
    """Report a page's platform availability from Apple's DocC metadata.

    Without `platform`, returns every listed platform. With `platform`
    (e.g. 'iOS', 'macOS', 'Mac Catalyst', 'visionOS'), adds a `status` for it:
    'available', 'deprecated' (still usable, deprecated at or before the
    version), 'unavailable', 'not_yet_available' (version precedes
    introduction), 'not_listed' (Apple lists no availability for that platform),
    or 'introduction_unknown' (listed without an introduced version).
    `version` ('17', '17.4', '17.4.1') requires `platform`; without it the
    status describes the latest release Apple documents.
    """
    err = require_string(url, 'url')
    if err: return err
    if platform is not None and (not isinstance(platform, str) or not platform.strip()):
        return {"error": "invalid_input", "message": "platform must be a nonempty string"}
    if version is not None:
        if platform is None:
            return {"error": "invalid_input", "message": "version requires platform"}
        if not isinstance(version, str) or not re.fullmatch(r'[0-9]+(\.[0-9]+){0,2}', version.strip()):
            return {"error": "invalid_input", "message": "version must look like '17', '17.4', or '17.4.1'"}
        version = version.strip()

    doc = fetch_documentation(url, format='json')
    if 'error' in doc:
        return doc
    platforms = [{
        "name": p.get('name', ''),
        "introduced": p.get('introducedAt'),
        "deprecated": p.get('deprecatedAt'),
        "deprecation_message": p.get('message'),
        "beta": bool(p.get('beta')),
        "unavailable": bool(p.get('unavailable')),
    } for p in doc.get('availability', []) if isinstance(p, dict)]
    result = {"title": doc.get('title', ''), "url": doc['url'], "platforms": platforms}
    if platform is None:
        return mark_untrusted(result, "developer.apple.com")

    listed = next((p for p in platforms if _platform_key(p['name']) == _platform_key(platform)), None)
    if listed is None:
        status = 'not_listed'
    elif listed['unavailable']:
        status = 'unavailable'
    elif version is not None and listed['introduced'] is None:
        status = 'introduction_unknown'
    elif version is not None and _version_tuple(version) < _version_tuple(listed['introduced']):
        status = 'not_yet_available'
    elif listed['deprecated'] and (version is None or _version_tuple(version) >= _version_tuple(listed['deprecated'])):
        status = 'deprecated'
    else:
        status = 'available'
    result.update({"platform": platform, "version": version, "status": status, "platform_availability": listed})
    return mark_untrusted(result, "developer.apple.com")


def search_apple_online_urls(query: str, platform: Optional[str] = None) -> Dict:
    """Generate search URLs for Apple documentation."""
    err = require_string(query, 'query')
    if err: return err
    encoded_query = urllib.parse.quote(query)
    result = {
        "query": query,
        "platform": platform,
        "apple_url": f"https://developer.apple.com/documentation/technologies?filter={encoded_query}",
        "google_url": f"https://www.google.com/search?q=site:developer.apple.com+{encoded_query}",
        "github_url": f"https://github.com/search?q={encoded_query}+language:swift&type=code"
    }
    if platform:
        result["apple_url"] += "+" + urllib.parse.quote(str(platform), safe="")
    return result


def get_framework_info(framework: str) -> Dict:
    """Get documentation URL for a framework."""
    err = require_string(framework, 'framework')
    if err: return err
    framework_path = framework.lower().replace(" ", "").replace("-", "")
    return {
        "name": framework,
        "url": f"https://developer.apple.com/documentation/{framework_path}",
        "note": "Direct link to framework documentation"
    }
