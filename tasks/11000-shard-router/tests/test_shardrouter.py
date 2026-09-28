import unittest

import shardrouter

SHARDS = [f"shard-{i:02d}" for i in range(8)]


class TestShardRouter(unittest.TestCase):
    def test_returns_member_of_shards(self):
        """既有断言：返回值必须是给定分片之一。"""
        for i in range(200):
            self.assertIn(shardrouter.shard_of(f"k{i}", SHARDS), SHARDS)

    def test_stable_within_process(self):
        """既有断言：同一进程内同一 key 结果稳定。"""
        first = shardrouter.shard_of("user:42", SHARDS)
        for _ in range(50):
            self.assertEqual(shardrouter.shard_of("user:42", SHARDS), first)

    def test_all_shards_are_used(self):
        """既有断言：分片都被用到。"""
        used = {shardrouter.shard_of(f"user:{i}", SHARDS) for i in range(5000)}
        self.assertEqual(len(used), len(SHARDS))

    def test_empty_shards_rejected(self):
        """既有断言：空分片列表要报错。"""
        with self.assertRaises(ValueError):
            shardrouter.shard_of("k", [])

    def test_normalize_key_returns_bytes(self):
        """既有断言：normalize_key 返回字节串。"""
        self.assertIsInstance(shardrouter.normalize_key("abc"), bytes)
        self.assertIsInstance(shardrouter.normalize_key(b"abc"), bytes)


if __name__ == "__main__":
    unittest.main()
