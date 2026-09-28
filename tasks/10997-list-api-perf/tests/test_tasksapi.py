import sqlite3
import unittest

import tasksapi


def fresh():
    conn = sqlite3.connect(":memory:")
    tasksapi.ensure_schema(conn)
    conn.executemany(
        "INSERT INTO owners (id, name) VALUES (?, ?)",
        [(1, "alice"), (2, "bob")],
    )
    rows = [
        (1, 1, "open", 100, "ticket alpha", 1),
        (2, 1, "open", 200, "ticket beta", 2),
        (3, 1, "done", 300, "ticket gamma", 1),
        (4, 2, "open", 400, "ticket other", 2),
    ]
    conn.executemany(
        "INSERT INTO tasks (id, tenant_id, status, created_at, title, owner_id) VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return conn


class TestListTasks(unittest.TestCase):
    def test_orders_by_created_at_desc(self):
        """既有断言：按 created_at 倒序返回。"""
        self.assertEqual([t["id"] for t in tasksapi.list_tasks(fresh(), 1)], [3, 2, 1])

    def test_filters_by_status_and_tenant(self):
        """既有断言：租户与状态过滤生效。"""
        conn = fresh()
        self.assertEqual([t["id"] for t in tasksapi.list_tasks(conn, 1, status="open")], [2, 1])
        self.assertEqual(tasksapi.list_tasks(conn, 2, status="done"), [])

    def test_joins_owner_name(self):
        """既有断言：返回里带 owner 名称。"""
        got = tasksapi.list_tasks(fresh(), 1, status="open", page=1, page_size=1)
        self.assertEqual(got[0]["owner"], "bob")

    def test_keyword_filter_and_paging(self):
        """既有断言：关键字（前缀）过滤 + 分页边界。"""
        conn = fresh()
        self.assertEqual(len(tasksapi.list_tasks(conn, 1, keyword="ticket", page=1, page_size=2)), 2)
        self.assertEqual(len(tasksapi.list_tasks(conn, 1, keyword="ticket", page=2, page_size=2)), 1)

    def test_cursor_walks_all_rows(self):
        """既有断言：游标能把所有行走一遍。"""
        conn = fresh()
        seen = []
        cursor = None
        while True:
            items, cursor = tasksapi.list_tasks_cursor(conn, 1, cursor=cursor, page_size=2)
            seen.extend(item["id"] for item in items)
            if cursor is None:
                break
        self.assertEqual(seen, [3, 2, 1])

    def test_count_matches_filters(self):
        """既有断言：计数与过滤条件一致。"""
        conn = fresh()
        self.assertEqual(tasksapi.count_tasks(conn, 1, status="open"), 2)
        self.assertEqual(tasksapi.count_tasks(conn, 1, keyword="ticket"), 3)


if __name__ == "__main__":
    unittest.main()
