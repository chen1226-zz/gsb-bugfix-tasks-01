"""按「更新时间倒序 + id 倒序」做游标分页。

对外接口（不得更改签名）：
    encode_cursor(...)             -> str
    decode_cursor(cursor)          -> dict
    fetch_page(conn, cursor, size) -> (items, next_cursor)

表结构假定为：
    records(id INTEGER PRIMARY KEY AUTOINCREMENT,
            updated_at INTEGER NOT NULL,
            payload TEXT NOT NULL)
"""

import base64
import json


def encode_cursor(payload):
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor):
    raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
    return json.loads(raw.decode("utf-8"))


def fetch_page(conn, cursor=None, page_size=50):
    """取一页，返回 (items, next_cursor)。next_cursor 为 None 表示到底了。"""
    if cursor:
        marker = decode_cursor(cursor)
        sql = (
            "SELECT id, updated_at, payload FROM records "
            "WHERE updated_at <= ? ORDER BY updated_at DESC LIMIT ?"
        )
        rows = conn.execute(sql, (marker["updated_at"], page_size)).fetchall()
    else:
        sql = (
            "SELECT id, updated_at, payload FROM records "
            "ORDER BY updated_at DESC LIMIT ?"
        )
        rows = conn.execute(sql, (page_size,)).fetchall()

    items = [{"id": r[0], "updated_at": r[1], "payload": r[2]} for r in rows]
    if len(items) < page_size:
        return items, None
    return items, encode_cursor({"updated_at": items[-1]["updated_at"]})
