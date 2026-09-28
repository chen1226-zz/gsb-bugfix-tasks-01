"""用 sqlite3 实现的任务队列，多进程 worker 并发领取。

对外接口（不得更改签名）：
    JobStore(path)
        .add(titles)
        .claim(worker) -> job_id | None
        .stats()  -> {"pending": int, "claimed": int, "total": int}
"""

import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id     INTEGER PRIMARY KEY AUTOINCREMENT,
  title  TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  worker TEXT
);
"""


class JobStore:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.execute(SCHEMA)
        self.conn.commit()

    def add(self, titles):
        self.conn.executemany(
            "INSERT INTO jobs (title) VALUES (?)", [(t,) for t in titles]
        )
        self.conn.commit()

    def claim(self, worker):
        try:
            row = self.conn.execute(
                "SELECT id FROM jobs WHERE status = 'pending' ORDER BY id LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            time.sleep(0.002)
            self.conn.execute(
                "UPDATE jobs SET status = 'claimed', worker = ? WHERE id = ?",
                (worker, row[0]),
            )
            self.conn.commit()
            return row[0]
        except sqlite3.OperationalError:
            return None

    def stats(self):
        counts = {"pending": 0, "claimed": 0, "total": 0}
        for status, n in self.conn.execute(
            "SELECT status, COUNT(*) FROM jobs GROUP BY status"
        ):
            counts[status] = n
            counts["total"] += n
        return counts

    def close(self):
        self.conn.close()
