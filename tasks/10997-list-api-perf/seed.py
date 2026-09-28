"""生成基准数据集 bench.db（每次运行都会重建）。"""

import os
import random
import sqlite3

import tasksapi

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "bench.db")

TENANTS = list(range(1, 21))
STATUSES = ["open", "doing", "blocked", "done", "archived"]
OWNERS = 500
ROWS = 1_000_000


def build():
    if os.path.exists(DB):
        os.remove(DB)
    conn = sqlite3.connect(DB)
    tasksapi.ensure_schema(conn)
    rnd = random.Random(20260928)

    conn.executemany(
        "INSERT INTO owners (id, name) VALUES (?, ?)",
        [(i, f"owner-{i:03d}") for i in range(1, OWNERS + 1)],
    )

    batch = []
    base = 1_700_000_000
    for i in range(1, ROWS + 1):
        batch.append(
            (
                i,
                TENANTS[i % len(TENANTS)],
                STATUSES[rnd.randrange(len(STATUSES))],
                base + i,
                f"ticket-{i:06d} 处理客户反馈 {i % 977}",
                rnd.randrange(1, OWNERS + 1),
            )
        )
        if len(batch) >= 20_000:
            conn.executemany(
                "INSERT INTO tasks (id, tenant_id, status, created_at, title, owner_id) VALUES (?, ?, ?, ?, ?, ?)",
                batch,
            )
            batch.clear()
    if batch:
        conn.executemany(
            "INSERT INTO tasks (id, tenant_id, status, created_at, title, owner_id) VALUES (?, ?, ?, ?, ?, ?)",
            batch,
        )
    conn.commit()
    conn.execute("ANALYZE")
    conn.commit()
    conn.close()
    print(f"OK: seeded {ROWS} tasks -> {DB}")


if __name__ == "__main__":
    build()
