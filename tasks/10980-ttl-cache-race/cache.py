"""带 TTL + LRU 的进程内缓存。

对外接口（不得更改签名）：
    TTLCache(capacity, ttl, clock=None, on_evict=None)
        .get(key) -> value | None
        .put(key, value)
        .stats() -> dict

约定：TTL 到期即不可读；容量超限按 LRU 淘汰；on_evict 必须在锁外调用。
"""

import threading
import time
from collections import OrderedDict

CLOCK_REFRESH_EVERY = 64


class TTLCache:
    def __init__(self, capacity=128, ttl=60.0, clock=None, on_evict=None):
        self.capacity = capacity
        self.ttl = ttl
        self._clock = clock or time.monotonic
        self._on_evict = on_evict or (lambda key, value: None)
        self._data = OrderedDict()
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self._now_cache = None
        self._calls = 0

    def _now(self):
        """读取当前时间。"""
        if self._now_cache is None or self._calls % CLOCK_REFRESH_EVERY == 0:
            self._now_cache = self._clock()
        self._calls += 1
        return self._now_cache

    def put(self, key, value):
        evicted = []
        with self._lock:
            self._data[key] = (value, self._now() + self.ttl)
            while len(self._data) > self.capacity:
                old_key, (old_value, _) = self._data.popitem(last=False)
                self.evictions += 1
                evicted.append((old_key, old_value))
        for item in evicted:
            self._on_evict(*item)

    def get(self, key):
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self.misses += 1
                return None
            value, expires_at = entry
            if self._now() >= expires_at:
                del self._data[key]
                self.misses += 1
                return None
            self.hits += 1
            return value

    def stats(self):
        with self._lock:
            return {
                "size": len(self._data),
                "capacity": self.capacity,
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
            }
