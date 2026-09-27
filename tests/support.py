"""Shared helpers for the test suite: import path, fake network, and content unwrapping."""
import email.message
import os
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apple-developer-docs" / "scripts"))

from apis import _utils  # noqa: E402

LIVE = os.environ.get("APPLE_DOCS_LIVE") == "1"
LIVE_REASON = "set APPLE_DOCS_LIVE=1 to query developer.apple.com"

DOCS = "https://developer.apple.com/documentation/"
HIG = "https://developer.apple.com/design/human-interface-guidelines/"
BEGIN = "<<<BEGIN EXTERNAL CONTENT"
END = "<<<END EXTERNAL CONTENT>>>"


def unwrap(content):
    lines = content.split("\n")
    assert lines[0].startswith(BEGIN) and lines[-1] == END, "content is not wrapped in boundary markers"
    return "\n".join(lines[1:-1])


class FakeResponse:
    def __init__(self, body, content_type, url):
        self.body, self.url = body, url
        self.headers = email.message.Message()
        self.headers["Content-Type"] = content_type

    def read(self, n=-1):
        return self.body if n < 0 else self.body[:n]

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _guess_type(url):
    if url.endswith(".md"):
        return "text/markdown; charset=utf-8"
    return "text/html; charset=utf-8" if "/videos/" in url else "application/json"


def serve(body, content_type=None, requests=None, final_url=None):
    """Answer every request with `body`, optionally recording requests or simulating a redirect."""
    def open_url(req, timeout=15):
        if requests is not None:
            requests.append((req, timeout))
        return FakeResponse(body, content_type or _guess_type(req.full_url), final_url or req.full_url)
    return mock.patch.object(_utils, "open_url", open_url)


def route(responses, requests=None):
    """Answer by exact URL: `responses` maps URL -> bytes or an exception to raise."""
    def open_url(req, timeout=15):
        if requests is not None:
            requests.append(req.full_url)
        answer = responses[req.full_url]
        if isinstance(answer, BaseException):
            raise answer
        return FakeResponse(answer, _guess_type(req.full_url), req.full_url)
    return mock.patch.object(_utils, "open_url", open_url)


def fail_with(exc):
    def open_url(req, timeout=15):
        raise exc
    return mock.patch.object(_utils, "open_url", open_url)
