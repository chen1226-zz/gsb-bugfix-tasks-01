"""任务列表接口。

对外接口（不得更改签名）：
    ensure_schema(conn)
    list_tasks(conn, tenant_id, status=None, keyword=None, page=1, page_size=50)

返回值为 dict 列表，每个 dict 含：
    id, tenant_id, status, created_at, title, owner
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


def list_tasks(conn, tenant_id, status=None, keyword=None, page=1, page_size=50):
    sql = [
        "SELECT id, tenant_id, status, created_at, title, owner_id",
        "FROM tasks WHERE tenant_id = ?",
    ]
    args = [tenant_id]
    if status is not None:
        sql.append("AND status = ?")
        args.append(status)
    if keyword:
        sql.append("AND title LIKE ?")
        args.append(f"%{keyword}%")
    sql.append("ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?")
    args.extend([page_size, max(page - 1, 0) * page_size])

    rows = conn.execute(" ".join(sql), args).fetchall()
    result = []
    for row in rows:
        owner = conn.execute("SELECT name FROM owners WHERE id = ?", (row[5],)).fetchone()
        result.append(
            {
                "id": row[0],
                "tenant_id": row[1],
                "status": row[2],
                "created_at": row[3],
                "title": row[4],
                "owner": owner[0] if owner else None,
            }
        )
    return result
