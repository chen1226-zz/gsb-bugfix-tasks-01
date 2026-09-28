"""复现脚本：翻页期间有并发写入时，检查「不重不漏」。

约定：
  * 写入方只 INSERT 新行，不修改也不删除已有行；
  * 一次完整翻页的结果，必须恰好等于「开始翻页那一刻」的
    {id <= 快照上界} 这些行，每行恰好出现一次。
"""

import os
import random
import sqlite3
import tempfile
import threading
import time

import pager

ROWS = 3000
TIE_GROUP = 10
PAGE_SIZE = 37
WRITER_INSERTS = 600


def build(conn):
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE records (id INTEGER PRIMARY KEY AUTOINCREMENT, updated_at INTEGER NOT NULL, payload TEXT NOT NULL)")
    base = 1_700_000_000
    conn.executemany(
        "INSERT INTO records (updated_at, payload) VALUES (?, ?)",
        [(base + (i // TIE_GROUP), f"row-{i}") for i in range(ROWS)],
    )
    conn.commit()


def writer(db_path, stop, inserted):
    conn = sqlite3.connect(db_path, timeout=30)
    rnd = random.Random(20260928)
    base = 1_700_000_000
    for i in range(WRITER_INSERTS):
        if stop.is_set():
            break
        conn.execute(
            "INSERT INTO records (updated_at, payload) VALUES (?, ?)",
            (base + rnd.randrange(0, ROWS // TIE_GROUP), f"late-{i}"),
        )
        conn.commit()
        inserted.append(1)
        time.sleep(0.0008)
    conn.close()


def scan(conn, page_size, first_items, cursor):
    seen = [item["id"] for item in first_items]
    for _ in range(1000):
        if cursor is None:
            return seen
        items, cursor = pager.fetch_page(conn, cursor, page_size)
        seen.extend(item["id"] for item in items)
    raise AssertionError("翻页没有终止（超过 1000 页）")


def one_run(seed):
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "pager.db")
    conn = sqlite3.connect(db_path, timeout=30)
    build(conn)
    snapshot_max = conn.execute("SELECT MAX(id) FROM records").fetchone()[0]
    expected = {row[0] for row in conn.execute("SELECT id FROM records WHERE id <= ?", (snapshot_max,))}

    # 第一页在写入方启动之前取，翻页快照就是这一刻的数据集
    first_items, cursor = pager.fetch_page(conn, None, PAGE_SIZE)

    stop = threading.Event()
    inserted = []
    t = threading.Thread(target=writer, args=(db_path, stop, inserted), daemon=True)
    t.start()
    try:
        seen = scan(conn, PAGE_SIZE, first_items, cursor)
    finally:
        stop.set()
        t.join(timeout=10)
        conn.close()

    counts = {}
    for row_id in seen:
        counts[row_id] = counts.get(row_id, 0) + 1
    dup = sum(c - 1 for c in counts.values() if c > 1)
    missing = len(expected - set(counts))
    extra = len(set(counts) - expected)
    return dup, missing, extra


def main():
    total_dup = total_missing = total_extra = 0
    for seed in range(40):
        dup, missing, extra = one_run(seed)
        total_dup += dup
        total_missing += missing
        total_extra += extra
        if dup or missing or extra:
            break

    if total_dup or total_missing or total_extra:
        print(f"FAIL: dup={total_dup} missing={total_missing} extra={total_extra}")
        raise SystemExit(1)
    print("OK: 40 runs, 0 dup, 0 missing, 0 extra")


if __name__ == "__main__":
    main()
