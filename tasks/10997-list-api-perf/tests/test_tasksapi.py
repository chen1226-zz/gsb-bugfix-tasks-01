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
        conn = fresh()
        got = tasksapi.list_tasks(conn, 1)
        self.assertEqual([t["id"] for t in got], [3, 2, 1])

    def test_filters_by_status_and_tenant(self):
        """既有断言：租户与状态过滤生效。"""
        conn = fresh()
        got = tasksapi.list_tasks(conn, 1, status="open")
        self.assertEqual([t["id"] for t in got], [2, 1])
        self.assertEqual(tasksapi.list_tasks(conn, 2, status="done"), [])

    def test_joins_owner_name(self):
        """既有断言：返回里带 owner 名称。"""
        conn = fresh()
        got = tasksapi.list_tasks(conn, 1, status="open", page=1, page_size=1)
        self.assertEqual(got[0]["owner"], "bob")

    def test_keyword_filter_and_paging(self):
        """既有断言：关键字（前缀）过滤 + 分页边界。"""
        conn = fresh()
        got = tasksapi.list_tasks(conn, 1, keyword="ticket", page=1, page_size=2)
        self.assertEqual(len(got), 2)
        got2 = tasksapi.list_tasks(conn, 1, keyword="ticket", page=2, page_size=2)
        self.assertEqual(len(got2), 1)


if __name__ == "__main__":
    unittest.main()
