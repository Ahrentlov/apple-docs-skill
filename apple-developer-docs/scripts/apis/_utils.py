"""
Shared helpers for the API modules.
"""

import json
import urllib.request
from typing import Any, Callable, Dict, List, Optional


# Apple's developer.apple.com serves different content to non-browser UAs; spoof.
UA_APPLE_BROWSER = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
# Honest app identifier for GitHub / swift.org / wwdcnotes fetches.
UA_APP = 'AppleDeveloperDocs/1.0'


def all_terms_match(text: str, terms: List[str]) -> bool:
    """True when every term appears in `text` (case-insensitive substring match)."""
    lowered = text.lower()
    return all(term in lowered for term in terms)


def fetch_json(
    url: str,
    *,
    ua: str = UA_APP,
    timeout: int = 15,
    extra_headers: Optional[Dict[str, str]] = None,
    decoder: Callable[[str], Any] = json.loads,
) -> Optional[Any]:
    """
    Plain JSON fetch — no cache, returns None on any failure.

    `decoder` defaults to `json.loads`; pass a custom callable when the payload
    needs preprocessing (e.g. archive.py's library.json has trailing commas).

    For modules with stricter error semantics (typed exceptions, security
    checks, size guards), keep their own urllib invocations rather than going
    through this helper.
    """
    headers = {'User-Agent': ua}
    if extra_headers:
        headers.update(extra_headers)
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return decoder(response.read().decode('utf-8'))
    except Exception:
        return None
