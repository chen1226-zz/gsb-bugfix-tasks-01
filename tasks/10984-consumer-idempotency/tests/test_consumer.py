import sqlite3
import unittest

from consumer import Consumer


def fresh():
    conn = sqlite3.connect(":memory:")
    return Consumer(conn), conn


class TestConsumer(unittest.TestCase):
    def test_applies_event(self):
        """既有断言：事件被计入余额。"""
        c, conn = fresh()
        c.process({"event_id": "e1", "account": "a", "amount": 5})
        self.assertEqual(c.balance("a"), 5)

    def test_same_instance_dedups(self):
        """既有断言：同一实例内重复事件只计一次。"""
        c, conn = fresh()
        e = {"event_id": "e1", "account": "a", "amount": 5}
        self.assertEqual(c.process(e), "applied")
        self.assertEqual(c.process(e), "duplicate")
        self.assertEqual(c.balance("a"), 5)

    def test_multiple_accounts(self):
        """既有断言：多账户分别累计。"""
        c, conn = fresh()
        c.process({"event_id": "e1", "account": "a", "amount": 3})
        c.process({"event_id": "e2", "account": "b", "amount": 4})
        self.assertEqual((c.balance("a"), c.balance("b")), (3, 4))

    def test_missing_account_balance_is_zero(self):
        """既有断言：未知账户余额为 0。"""
        c, conn = fresh()
        self.assertEqual(c.balance("nope"), 0)


if __name__ == "__main__":
    unittest.main()
