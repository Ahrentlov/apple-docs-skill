"""Live test for search_compiler_docs_text defaults (uses a few GitHub API requests)."""
import unittest

from support import LIVE, LIVE_REASON

from apis import search_compiler_docs_text


@unittest.skipUnless(LIVE, LIVE_REASON)
class LiveCompilerTextTests(unittest.TestCase):
    def test_default_budget_covers_the_docs_corpus(self):
        # "reborrow" lives in docs/SIL, beyond the first 60 candidates; the default must still reach it.
        r = search_compiler_docs_text("reborrow")
        self.assertNotIn("error", r, r.get("message"))
        self.assertGreaterEqual(r["max_files"], r["candidate_files"])
        self.assertTrue(any(m["path"].startswith("docs/SIL/") for m in r["results"]))
