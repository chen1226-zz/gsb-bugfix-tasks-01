import os
import tempfile
import unittest

from walstore import WALStore


def fresh():
    return os.path.join(tempfile.mkdtemp(), "db")


class TestWALStore(unittest.TestCase):
    def test_put_then_get_in_same_process(self):
        """既有断言：同进程写入后可读。"""
        path = fresh()
        s = WALStore(path)
        s.open()
        s.put("a", "1")
        self.assertEqual(s.get("a"), "1")
        s.close()

    def test_missing_key_returns_none(self):
        """既有断言：不存在的 key 返回 None。"""
        path = fresh()
        s = WALStore(path)
        s.open()
        self.assertIsNone(s.get("nope"))
        s.close()

    def test_reopen_after_clean_close(self):
        """既有断言：正常关闭后重开能读回。"""
        path = fresh()
        s = WALStore(path)
        s.open()
        s.put("a", "x" * 100)
        s.close()
        again = WALStore(path)
        again.open()
        self.assertEqual(again.get("a"), "x" * 100)
        again.close()

    def test_unicode_roundtrip(self):
        """既有断言：非 ASCII 值可往返。"""
        path = fresh()
        s = WALStore(path)
        s.open()
        s.put("名字", "值")
        s.close()
        again = WALStore(path)
        again.open()
        self.assertEqual(again.get("名字"), "值")
        again.close()


if __name__ == "__main__":
    unittest.main()
