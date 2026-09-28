"""订单落库与导出。

对外接口（不得更改签名）：
    ensure_schema(conn)
    ingest(conn, raw_json)   -> order_id
    export(conn, order_id)   -> str（JSON 文本）
    log_line(conn, order_id) -> str
"""

import json

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
  order_id REAL PRIMARY KEY,
  amount   REAL NOT NULL,
  currency TEXT NOT NULL,
  items    TEXT NOT NULL,
  seq      INTEGER NOT NULL
);
"""


def ensure_schema(conn):
    conn.execute(SCHEMA)
    conn.commit()


def ingest(conn, raw_json):
    """解析一条订单 JSON 并落库，返回订单号。"""
    doc = json.loads(raw_json)
    order_id = float(doc["order_id"])
    amount = float(doc["amount"])
    conn.execute(
        "INSERT OR REPLACE INTO orders (order_id, amount, currency, items, seq) VALUES (?, ?, ?, ?, ?)",
        (order_id, amount, doc["currency"], json.dumps(doc["items"], separators=(",", ":")), int(doc["seq"])),
    )
    conn.commit()
    return order_id


def export(conn, order_id):
    """把库里的订单还原成 JSON 文本。"""
    row = conn.execute(
        "SELECT order_id, amount, currency, items, seq FROM orders WHERE order_id = ?",
        (order_id,),
    ).fetchone()
    if row is None:
        return None
    doc = {
        "amount": row[1],
        "currency": row[2],
        "items": json.loads(row[3]),
        "order_id": row[0],
        "seq": row[4],
    }
    return json.dumps(doc, separators=(",", ":"), sort_keys=True)


def log_line(conn, order_id):
    """给日志用的定长摘要行。"""
    row = conn.execute(
        "SELECT order_id, amount, currency FROM orders WHERE order_id = ?",
        (order_id,),
    ).fetchone()
    if row is None:
        return "ORDER <missing>"
    return f"ORDER id={row[0]} amount={row[1]} {row[2]}"
