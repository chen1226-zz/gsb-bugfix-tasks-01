import os
import tempfile
import unittest

from jobstore import JobStore


def fresh():
    return JobStore(os.path.join(tempfile.mkdtemp(), "jobs.db"))


class TestJobStore(unittest.TestCase):
    def test_add_and_claim_single_process(self):
        """既有断言：单进程下按 id 顺序领取。"""
        store = fresh()
        store.add(["a", "b", "c"])
        self.assertEqual(store.claim("w0"), 1)
        self.assertEqual(store.claim("w0"), 2)

    def test_claim_returns_none_when_empty(self):
        """既有断言：没有待办时返回 None。"""
        store = fresh()
        self.assertIsNone(store.claim("w0"))

    def test_stats_counts(self):
        """既有断言：统计正确。"""
        store = fresh()
        store.add(["a", "b", "c"])
        store.claim("w0")
        stats = store.stats()
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["claimed"], 1)
        self.assertEqual(stats["pending"], 2)


if __name__ == "__main__":
    unittest.main()
