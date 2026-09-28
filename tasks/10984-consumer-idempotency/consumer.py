"""从上游拉取事件并落库（sqlite3）。

对外接口（不得更改签名）：
    Consumer(conn)
        .process(event)  -> "applied" | "duplicate"
        .balance(account) -> int

event 形如 {"event_id": str, "account": str, "amount": int}。
"""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
  id      TEXT PRIMARY KEY,
  balance INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS processed (
  event_id TEXT
);
"""


class Consumer:
    def __init__(self, conn):
        self.conn = conn
        self.seen = set()
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def process(self, event):
        event_id = event["event_id"]
        if event_id in self.seen:
            return "duplicate"
        self.seen.add(event_id)

        self.conn.execute(
            "INSERT INTO accounts (id, balance) VALUES (?, 0) "
            "ON CONFLICT(id) DO NOTHING",
            (event["account"],),
        )
        self.conn.execute(
            "UPDATE accounts SET balance = balance + ? WHERE id = ?",
            (event["amount"], event["account"]),
        )
        self.conn.commit()

        self.conn.execute("INSERT INTO processed (event_id) VALUES (?)", (event_id,))
        self.conn.commit()
        return "applied"

    def balance(self, account):
        row = self.conn.execute(
            "SELECT balance FROM accounts WHERE id = ?", (account,)
        ).fetchone()
        return row[0] if row else 0
