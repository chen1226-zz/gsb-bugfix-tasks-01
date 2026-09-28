"""复现脚本：并发写入下的「不重不漏 + 双向一致 + 游标校验」。

约定：
  * 写入方只 INSERT 新行，不修改也不删除已有行；
  * 一次正向翻页的结果必须恰好等于「开始翻页那一刻」的
    {id <= 快照上界} 数据集，每行恰好出现一次；
  * 反向翻页必须逐页回到起点，页面 ID 序列与正向完全一致；
  * 被篡改的游标必须抛 InvalidCursor，不能静默从头开始。
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
RUNS = 40


def build(conn):
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE records (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "updated_at INTEGER NOT NULL, payload TEXT NOT NULL)"
    )
    base = 1_700_000_000
    conn.executemany(
        "INSERT INTO records (updated_at, payload) VALUES (?, ?)",
        [(base + (i // TIE_GROUP), f"row-{i}") for i in range(ROWS)],
    )
    conn.commit()


def writer(db_path, stop):
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
        time.sleep(0.0008)
    conn.close()


def walk_forward(conn, first_items, next_cursor):
    pages = [first_items]
    prev_cursor = None
    for _ in range(1000):
        if next_cursor is None:
            break
        items, next_cursor, prev_cursor = pager.fetch_page(conn, next_cursor, PAGE_SIZE, "next")
        pages.append(items)
    return pages, prev_cursor


def walk_backward(conn, start_prev_cursor, last_page):
    out = [last_page]
    cursor = start_prev_cursor
    for _ in range(1000):
        if cursor is None:
            break
        items, _, prev_cursor = pager.fetch_page(conn, cursor, PAGE_SIZE, "prev")
        if not items:
            break
        out.append(items)
        cursor = prev_cursor
    out.reverse()
    return out


def tamper(cursor):
    return ("A" if cursor[0] != "A" else "B") + cursor[1:]


def one_run():
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "pager.db")
    conn = sqlite3.connect(db_path, timeout=30)
    build(conn)
    snapshot_max = conn.execute("SELECT MAX(id) FROM records").fetchone()[0]
    expected = {
        row[0] for row in conn.execute("SELECT id FROM records WHERE id <= ?", (snapshot_max,))
    }

    first_items, next_cursor, first_prev = pager.fetch_page(conn, None, PAGE_SIZE, "next")

    stop = threading.Event()
    thread = threading.Thread(target=writer, args=(db_path, stop), daemon=True)
    thread.start()
    try:
        pages, last_prev = walk_forward(conn, first_items, next_cursor)
        back_pages = walk_backward(conn, last_prev or first_prev, pages[-1])

        bad_cursor = 0
        try:
            pager.fetch_page(conn, tamper(next_cursor or first_prev), PAGE_SIZE, "next")
        except pager.InvalidCursor:
            pass
        except Exception:  # noqa: BLE001
            bad_cursor = 1
        else:
            bad_cursor = 1
    finally:
        stop.set()
        thread.join(timeout=10)
        conn.close()

    seen = [item["id"] for page in pages for item in page]
    counts = {}
    for row_id in seen:
        counts[row_id] = counts.get(row_id, 0) + 1
    dup = sum(c - 1 for c in counts.values() if c > 1)
    missing = len(expected - set(counts))
    extra = len(set(counts) - expected)

    forward_order = [item["id"] for page in pages for item in page]
    back_order = [item["id"] for page in back_pages for item in page]
    if forward_order != back_order:
        dup += abs(len(forward_order) - len(back_order)) + sum(
            1 for a, b in zip(forward_order, back_order) if a != b
        )
    return dup, missing, extra, bad_cursor


def main():
    total_dup = total_missing = total_extra = total_bad = 0
    for _ in range(RUNS):
        dup, missing, extra, bad = one_run()
        total_dup += dup
        total_missing += missing
        total_extra += extra
        total_bad += bad
        if dup or missing or extra or bad:
            break

    if total_dup or total_missing or total_extra or total_bad:
        print(
            f"FAIL: {RUNS} runs, dup={total_dup} missing={total_missing} "
            f"extra={total_extra} bad-cursor={total_bad}"
        )
        raise SystemExit(1)
    print(f"OK: {RUNS} runs, 0 dup, 0 missing, 0 extra, 0 bad-cursor")


if __name__ == "__main__":
    main()
