import unittest

from cache import TTLCache


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


class TestTTLCache(unittest.TestCase):
    def test_hit_before_expiry(self):
        """既有断言：TTL 内可读。"""
        clock = Clock()
        c = TTLCache(capacity=4, ttl=10, clock=clock)
        c.put("a", 1)
        clock.advance(1)
        self.assertEqual(c.get("a"), 1)

    def test_expired_after_ttl(self):
        """既有断言：超过 TTL 后读不到（单线程）。"""
        clock = Clock()
        c = TTLCache(capacity=4, ttl=1, clock=clock)
        c.put("a", 1)
        clock.advance(2)
        self.assertIsNone(c.get("a"))

    def test_lru_eviction_and_callback_outside_lock(self):
        """既有断言：超容量按 LRU 淘汰，回调在锁外调用。"""
        evicted = []
        clock = Clock()
        c = TTLCache(capacity=2, ttl=100, clock=clock, on_evict=lambda k, v: evicted.append(k))
        c.put("a", 1)
        c.put("b", 2)
        c.put("c", 3)
        self.assertEqual(evicted, ["a"])
        self.assertEqual(c.stats()["size"], 2)

    def test_stats_counts_hits_and_misses(self):
        """既有断言：命中/未命中统计。"""
        clock = Clock()
        c = TTLCache(capacity=4, ttl=10, clock=clock)
        c.put("a", 1)
        c.get("a")
        c.get("missing")
        s = c.stats()
        self.assertEqual((s["hits"], s["misses"]), (1, 1))


if __name__ == "__main__":
    unittest.main()
