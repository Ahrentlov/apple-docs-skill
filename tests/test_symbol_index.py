"""Tests for search_symbols over Apple's framework navigator index."""
import json
import unittest
import urllib.error

from support import LIVE, LIVE_REASON, fail_with, route

from apis import symbol_index
from apis import search_symbols

INDEX = "https://developer.apple.com/tutorials/data/index/demo"
TREE = {"interfaceLanguages": {"swift": [{"title": "Demo", "type": "module", "path": "/documentation/demo", "children": [
    {"title": "Essentials", "type": "groupMarker"},
    {"title": "Guide", "type": "article", "path": "/documentation/demo/guide"},
    {"title": "Other framework page", "type": "article", "path": "/documentation/other/page", "external": True},
    {"title": "Views", "type": "groupMarker"},
    {"title": "Widget", "type": "struct", "path": "/documentation/demo/widget", "children": [
        {"title": "Modifiers", "type": "groupMarker"},
        {"title": "func opacity(Double) -> Widget", "type": "method", "path": "/documentation/demo/widget/opacity(_:)"},
        {"title": "func widgetStyle(Style) -> Widget", "type": "method", "path": "/documentation/demo/widget/widgetstyle(_:)",
         "deprecated": True},
    ]},
    {"title": "WidgetGroup", "type": "struct", "path": "/documentation/demo/widgetgroup", "beta": True},
    {"title": "Also listed here", "type": "groupMarker"},
    {"title": "func opacity(Double) -> Widget", "type": "method", "path": "/documentation/demo/widget/opacity(_:)"},
    {"title": "OldWidget", "type": "class", "path": "/documentation/demo/oldwidget", "deprecated": True},
]}]}}


class SymbolIndexTests(unittest.TestCase):
    def setUp(self):
        symbol_index._index_cache.clear()

    def search(self, *args, **kwargs):
        with route({INDEX: json.dumps(TREE).encode()}):
            return search_symbols("demo", *args, **kwargs)

    def titles(self, result):
        return [r["title"] for r in result["results"]]

    def test_flattening(self):
        r = self.search(limit=200)
        self.assertEqual(r["indexed_pages"], 7)  # module + 6 pages; group markers and external pages excluded
        opacity = next(e for e in r["results"] if e["title"].startswith("func opacity"))
        self.assertEqual(opacity["locations"], ["Demo > Views > Widget > Modifiers", "Demo > Also listed here"])
        self.assertEqual(opacity["url"], "https://developer.apple.com/documentation/demo/widget/opacity(_:)")
        self.assertNotIn("Other framework page", self.titles(r))

    def test_query_terms_match_title_or_last_path_component(self):
        self.assertEqual(self.titles(self.search("widgetstyle")), ["func widgetStyle(Style) -> Widget"])
        self.assertEqual(self.titles(self.search("opacity double")), ["func opacity(Double) -> Widget"])
        self.assertEqual(self.search("nothing-like-this")["total_matches"], 0)

    def test_case_sensitive_exact_title_wins(self):
        tree = {"interfaceLanguages": {"swift": [
            {"title": "var widget: Widget", "type": "property", "path": "/documentation/demo/thing/widget"},
            {"title": "Widget", "type": "struct", "path": "/documentation/demo/widget"}]}}
        with route({INDEX: json.dumps(tree).encode()}):
            self.assertEqual([r["title"] for r in search_symbols("demo", "Widget")["results"]], ["Widget", "var widget: Widget"])
            symbol_index._index_cache.clear()
        with route({INDEX: json.dumps(tree).encode()}):
            self.assertEqual([r["title"] for r in search_symbols("demo", "widget")["results"]], ["var widget: Widget", "Widget"])

    def test_exact_then_prefix_then_other(self):
        self.assertEqual(self.titles(self.search("widget", kind="struct")), ["Widget", "WidgetGroup"])
        ranked = self.titles(self.search("widget"))
        self.assertEqual(ranked[0], "Widget")  # exact name
        # Name prefixes (by title or last path component) next, in Apple's order.
        self.assertEqual(ranked[1:3], ["func widgetStyle(Style) -> Widget", "WidgetGroup"])

    def test_filters(self):
        self.assertEqual(self.titles(self.search(deprecated=True)), ["func widgetStyle(Style) -> Widget", "OldWidget"])
        self.assertEqual(self.titles(self.search(beta=True)), ["WidgetGroup"])
        self.assertEqual(self.titles(self.search(kind="CLASS")), ["OldWidget"])
        self.assertEqual(self.search(kind="struct", deprecated=False)["total_matches"], 2)

    def test_pagination(self):
        first = self.search(limit=4)
        second = self.search(limit=4, offset=first["next_offset"])
        self.assertEqual(first["next_offset"], 4)
        self.assertIsNone(second["next_offset"])
        self.assertEqual(len(first["results"]) + len(second["results"]), first["total_matches"])

    def test_index_is_cached_but_failures_are_not(self):
        seen = []
        with route({INDEX: json.dumps(TREE).encode()}, requests=seen):
            search_symbols("demo", "a")
            search_symbols("DEMO", "b")
        self.assertEqual(seen, [INDEX])
        symbol_index._index_cache.clear()
        with route({INDEX: b"not json"}):
            self.assertEqual(search_symbols("demo")["error"], "invalid_json")
        with route({INDEX: json.dumps(TREE).encode()}):
            self.assertNotIn("error", search_symbols("demo"))

    def test_errors(self):
        with fail_with(urllib.error.HTTPError(INDEX, 404, "x", {}, None)):
            r = search_symbols("demo")
        self.assertEqual(r["error"], "not_found")
        self.assertIn("navigator index", r["message"])
        with route({INDEX: json.dumps({"interfaceLanguages": {}}).encode()}):
            self.assertEqual(search_symbols("demo")["error"], "invalid_schema")

    def test_invalid_input_never_fetches(self):
        cases = [((None,), {}), (("a/b",), {}), (("demo", 3), {}), (("demo",), {"kind": ""}), (("demo",), {"kind": 1}),
                 (("demo",), {"deprecated": "yes"}), (("demo",), {"beta": 1}), (("demo",), {"limit": 0}),
                 (("demo",), {"limit": 201}), (("demo",), {"offset": -1}), (("demo",), {"limit": True})]
        for args, kwargs in cases:
            with self.subTest(args=args, kwargs=kwargs), fail_with(AssertionError("network used")):
                self.assertEqual(search_symbols(*args, **kwargs)["error"], "invalid_input")


@unittest.skipUnless(LIVE, LIVE_REASON)
class LiveSymbolIndexTests(unittest.TestCase):
    def test_swiftui(self):
        r = search_symbols("swiftui", "NavigationStack")
        self.assertEqual(r["results"][0]["title"], "NavigationStack")
        self.assertGreater(r["indexed_pages"], 5000)
        deprecated = search_symbols("swiftui", deprecated=True, limit=200)
        self.assertGreater(deprecated["total_matches"], 50)
        self.assertTrue(all(e["deprecated"] for e in deprecated["results"]))
        self.assertGreater(search_symbols("swiftui", kind="sampleCode")["total_matches"], 5)

    def test_large_frameworks_and_missing(self):
        for framework in ("foundation", "uikit"):
            with self.subTest(framework=framework):
                self.assertGreater(search_symbols(framework, "URL")["total_matches"], 0)
        self.assertEqual(search_symbols("not-a-framework-xyz")["error"], "not_found")
