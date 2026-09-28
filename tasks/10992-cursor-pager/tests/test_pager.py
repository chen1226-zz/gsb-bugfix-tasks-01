import sqlite3
import unittest

import pager


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE records (id INTEGER PRIMARY KEY AUTOINCREMENT, updated_at INTEGER NOT NULL, payload TEXT NOT NULL)")
    return conn


class TestPagerBasics(unittest.TestCase):
    def test_empty_table(self):
        """既有断言：空表返回空页且没有下一页。"""
        conn = make_conn()
        items, cursor = pager.fetch_page(conn, None, 10)
        self.assertEqual(items, [])
        self.assertIsNone(cursor)

    def test_single_page_when_smaller_than_page_size(self):
        """既有断言：不足一页时一次取完。"""
        conn = make_conn()
        conn.executemany(
            "INSERT INTO records (updated_at, payload) VALUES (?, ?)",
            [(100, "a"), (90, "b"), (80, "c")],
        )
        items, cursor = pager.fetch_page(conn, None, 10)
        self.assertEqual([i["payload"] for i in items], ["a", "b", "c"])
        self.assertIsNone(cursor)

    def test_ordering_inside_page(self):
        """既有断言：页内按更新时间倒序。"""
        conn = make_conn()
        conn.executemany(
            "INSERT INTO records (updated_at, payload) VALUES (?, ?)",
            [(10, "old"), (30, "new"), (20, "mid")],
        )
        items, _ = pager.fetch_page(conn, None, 10)
        self.assertEqual([i["updated_at"] for i in items], [30, 20, 10])

    def test_cursor_roundtrip(self):
        """既有断言：游标编解码可往返。"""
        encoded = pager.encode_cursor({"updated_at": 12345})
        self.assertEqual(pager.decode_cursor(encoded)["updated_at"], 12345)


if __name__ == "__main__":
    unittest.main()
