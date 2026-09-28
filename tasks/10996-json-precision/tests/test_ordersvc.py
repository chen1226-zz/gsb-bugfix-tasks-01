import json
import sqlite3
import unittest

import ordersvc


def fresh():
    conn = sqlite3.connect(":memory:")
    ordersvc.ensure_schema(conn)
    return conn


class TestOrdersvc(unittest.TestCase):
    def test_small_values_roundtrip(self):
        """既有断言：小数值订单读回后数值语义不变。"""
        conn = fresh()
        raw = '{"amount":1.5,"currency":"CNY","items":["a"],"order_id":42,"seq":7}'
        oid = ordersvc.ingest(conn, raw)
        doc = json.loads(ordersvc.export(conn, oid))
        self.assertEqual(doc["currency"], "CNY")
        self.assertEqual(float(doc["amount"]), 1.5)
        self.assertEqual(int(doc["order_id"]), 42)
        self.assertEqual(doc["items"], ["a"])

    def test_export_missing_returns_none(self):
        """既有断言：查不到返回 None。"""
        conn = fresh()
        self.assertIsNone(ordersvc.export(conn, 999))

    def test_ingest_is_idempotent_by_order_id(self):
        """既有断言：同一订单号重复落库只留一条。"""
        conn = fresh()
        raw = '{"amount":10.00,"currency":"USD","items":[],"order_id":7,"seq":1}'
        ordersvc.ingest(conn, raw)
        ordersvc.ingest(conn, raw)
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        self.assertEqual(count, 1)

    def test_log_line_contains_currency(self):
        """既有断言：日志行里带币种。"""
        conn = fresh()
        raw = '{"amount":3.25,"currency":"EUR","items":[],"order_id":11,"seq":2}'
        oid = ordersvc.ingest(conn, raw)
        self.assertIn("EUR", ordersvc.log_line(conn, oid))


if __name__ == "__main__":
    unittest.main()
