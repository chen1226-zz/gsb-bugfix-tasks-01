"""按「更新时间倒序 + id 倒序」做双向游标分页。

对外接口（不得更改签名）：
    InvalidCursor(ValueError)
    encode_cursor(payload) -> str
    decode_cursor(cursor)  -> dict
    fetch_page(conn, cursor=None, page_size=50, direction="next")
        -> (items, next_cursor, prev_cursor)

表结构假定为：
    records(id INTEGER PRIMARY KEY AUTOINCREMENT,
            updated_at INTEGER NOT NULL,
            payload TEXT NOT NULL)
"""

import base64
import json


class InvalidCursor(ValueError):
    pass


def encode_cursor(payload):
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor):
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


_SELECT = "SELECT id, updated_at, payload FROM records"
_ORDER = "ORDER BY updated_at DESC, id DESC"


def fetch_page(conn, cursor=None, page_size=50, direction="next"):
    """取一页，返回 (items, next_cursor, prev_cursor)。"""
    marker = decode_cursor(cursor) if cursor else {}

    if direction == "prev" and cursor:
        rows = conn.execute(f"{_SELECT} {_ORDER} LIMIT ?", (page_size,)).fetchall()
    elif cursor:
        sql = f"{_SELECT} WHERE updated_at <= ? {_ORDER} LIMIT ?"
        rows = conn.execute(sql, (marker.get("updated_at", 0), page_size)).fetchall()
    else:
        rows = conn.execute(f"{_SELECT} {_ORDER} LIMIT ?", (page_size,)).fetchall()

    items = [{"id": r[0], "updated_at": r[1], "payload": r[2]} for r in rows]
    if not items:
        return [], None, None

    next_cursor = None
    if len(items) == page_size:
        last = items[-1]
        next_cursor = encode_cursor({"updated_at": last["updated_at"], "id": last["id"]})
    first = items[0]
    prev_cursor = encode_cursor({"updated_at": first["updated_at"], "id": first["id"]})
    return items, next_cursor, prev_cursor
