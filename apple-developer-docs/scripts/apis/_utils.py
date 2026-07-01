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
    """True when every term appears in `text` (case-insensitive substring match).

    Both sides are lowercased, so callers may pass terms in any case.
    """
    lowered = text.lower()
    return all(term.lower() in lowered for term in terms)


def clamp_limit(value: int, cap: int = 200) -> int:
    """Clamp a user-supplied limit/count into the range [0, cap].

    Non-int values (None, str, float, …) fall back to `cap` rather than raising,
    so a caller passing e.g. `limit=None` to mean 'no limit' gets the maximum
    instead of a TypeError out of min()/max(). bool is treated as its int value.
    """
    if not isinstance(value, int):
        return cap
    return max(0, min(value, cap))


def require_string(value: Any, field: str) -> Optional[Dict]:
    """
    Return None when `value` is a string (caller continues normally).
    Return an `{error, message}` dict when it isn't, suitable for direct return.

    Catches the common chained-call mistake where a previous API returned an
    error dict and the caller piped `.get('url')` (=None) into the next call.
    """
    if value is None:
        return {
            "error": "invalid_input",
            "message": f"`{field}` is None — did a previous call return an error result?",
        }
    if not isinstance(value, str):
        return {
            "error": "invalid_input",
            "message": f"`{field}` must be a string; got {type(value).__name__}",
        }
    return None


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
