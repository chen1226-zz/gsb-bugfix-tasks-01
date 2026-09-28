"""任务列表接口。

对外接口（不得更改签名）：
    ensure_schema(conn)
    list_tasks(conn, tenant_id, status=None, keyword=None, page=1, page_size=50) -> list[dict]
    list_tasks_cursor(conn, tenant_id, status=None, keyword=None, cursor=None, page_size=50)
        -> (list[dict], next_cursor)
    count_tasks(conn, tenant_id, status=None, keyword=None) -> int

返回的 dict 含：id, tenant_id, status, created_at, title, owner
排序固定为 created_at DESC, id DESC。
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS owners (
  id   INTEGER PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
  id         INTEGER PRIMARY KEY,
  tenant_id  INTEGER NOT NULL,
  status     TEXT    NOT NULL,
  created_at INTEGER NOT NULL,
  title      TEXT    NOT NULL,
  owner_id   INTEGER NOT NULL
);
"""


def ensure_schema(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def _where(tenant_id, status, keyword):
    clauses = ["t.tenant_id = ?"]
    args = [tenant_id]
    if status is not None:
        clauses.append("t.status = ?")
        args.append(status)
    if keyword:
        clauses.append("t.title LIKE ?")
        args.append(f"%{keyword}%")
    return " AND ".join(clauses), args


def _rows_to_items(rows):
    return [
        {
            "id": row[0],
            "tenant_id": row[1],
            "status": row[2],
            "created_at": row[3],
            "title": row[4],
            "owner": row[5],
        }
        for row in rows
    ]


def _page(conn, where, args, limit, offset):
    sql = (
        "SELECT t.id, t.tenant_id, t.status, t.created_at, t.title, o.name "
        "FROM tasks t LEFT JOIN owners o ON o.id = t.owner_id "
        f"WHERE {where} ORDER BY t.created_at DESC, t.id DESC LIMIT ? OFFSET ?"
    )
    return conn.execute(sql, args + [limit, offset]).fetchall()


def list_tasks(conn, tenant_id, status=None, keyword=None, page=1, page_size=50):
    where, args = _where(tenant_id, status, keyword)
    return _rows_to_items(_page(conn, where, args, page_size, max(page - 1, 0) * page_size))


def list_tasks_cursor(conn, tenant_id, status=None, keyword=None, cursor=None, page_size=50):
    where, args = _where(tenant_id, status, keyword)
    offset = int(cursor) if cursor else 0
    items = _rows_to_items(_page(conn, where, args, page_size, offset))
    next_cursor = str(offset + page_size) if len(items) == page_size else None
    return items, next_cursor


def count_tasks(conn, tenant_id, status=None, keyword=None):
    where, args = _where(tenant_id, status, keyword)
    return conn.execute(f"SELECT COUNT(*) FROM tasks t WHERE {where}", args).fetchone()[0]
