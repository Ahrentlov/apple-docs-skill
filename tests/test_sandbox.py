"""Tests for the sandbox supervisor: results, validation, deadlines, and resource limits."""
import sys
import threading
import time
import unittest

import support  # noqa: F401  (adds the scripts directory to sys.path)

from sandbox import SandboxExecutor


def run(code, timeout=5, handlers=None):
    return SandboxExecutor(timeout=timeout, api_handlers=handlers or {}).execute(code)


class SandboxTests(unittest.TestCase):
    def test_result_and_api_bridge(self):
        r = run("result = double(21)", handlers={"double": lambda x: x * 2})
        self.assertTrue(r.success)
        self.assertEqual((r.result, r.api_calls_made), (42, 1))

    def test_validation_rejects_imports_before_running(self):
        r = run("import os\nresult = os.getcwd()")
        self.assertEqual(r.error_type, "ValidationError")

    def test_deadline_stops_busy_code(self):
        started = time.monotonic()
        r = run("x = 0\nwhile True:\n    x += 1", timeout=2)
        self.assertEqual(r.error_type, "TimeoutError")
        self.assertLess(time.monotonic() - started, 5)

    def test_deadline_stops_a_blocked_api_call(self):
        # The handler never returns and the code never writes again: only the supervisor can end this.
        never = threading.Event()
        started = time.monotonic()
        r = run("result = hang()", timeout=2, handlers={"hang": never.wait})
        self.assertEqual(r.error_type, "TimeoutError")
        self.assertLess(time.monotonic() - started, 5)

    def test_errors_always_carry_a_message(self):
        r = run("raise ValueError()")
        self.assertEqual((r.error_type, r.error), ("ValueError", "ValueError"))

    @unittest.skipUnless(sys.platform.startswith("linux"), "only Linux lets the sandbox lower RLIMIT_AS")
    def test_memory_limit_on_linux(self):
        r = run('big = "x" * (400 * 1024 * 1024)\nresult = len(big)')
        self.assertEqual(r.error_type, "MemoryError")

    @unittest.skipUnless(sys.platform == "darwin", "documents the macOS limitation")
    def test_memory_is_unbounded_on_macos(self):
        # If this starts failing, macOS began honoring RLIMIT_AS: update sandbox.md and security.md.
        r = run('big = "x" * (100 * 1024 * 1024)\nresult = len(big)')
        self.assertTrue(r.success)
