"""Tests for search_swift_forums response handling."""
import json
import unittest
from unittest import mock

from support import fail_with

from apis import swift_evolution
from apis import search_swift_forums


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def read(self, n=-1):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def discourse(payload):
    body = json.dumps(payload).encode()
    return mock.patch.object(swift_evolution, "open_url", lambda req, timeout=15: FakeResponse(body))


class ForumsTests(unittest.TestCase):
    def test_blank_query_rejected_before_fetch(self):
        for query in ("", "   ", "\n"):
            with self.subTest(query=query), fail_with(AssertionError("network used")):
                self.assertEqual(search_swift_forums(query)["error"], "invalid_input")

    def test_null_sections_are_empty_results(self):
        with discourse({"grouped_search_result": None, "topics": None, "posts": None}):
            r = search_swift_forums("typed throws")
        self.assertEqual((r["returned_topics"], r["returned_posts"], r["more_available"]), (0, 0, False))

    def test_upstream_errors_are_not_empty_success(self):
        with discourse({"errors": ["You supplied invalid parameters to the request: q"]}):
            r = search_swift_forums("a")
        self.assertEqual(r["error"], "upstream_rejected")
        self.assertIn("invalid parameters", r["message"])

    def test_null_fields_and_missing_ids(self):
        payload = {"topics": [{"title": "T", "created_at": None, "last_posted_at": None}, None],
                   "posts": [{"topic_id": 7, "created_at": None, "post_number": 2}],
                   "grouped_search_result": {"more_posts": True}}
        with discourse(payload):
            r = search_swift_forums("x")
        self.assertEqual(r["topics"][0]["created_at"], "")
        self.assertEqual(r["posts"][0]["post_url"], "https://forums.swift.org/t/7/2")
        self.assertTrue(r["more_available"])

    def test_non_object_payload(self):
        with discourse([1, 2]):
            self.assertEqual(search_swift_forums("x")["error"], "invalid_schema")
