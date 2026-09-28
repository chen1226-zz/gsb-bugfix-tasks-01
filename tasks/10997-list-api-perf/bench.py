"""复现脚本：P99、每请求 SQL 条数、查询计划、游标在并发写入下的稳定性。"""

import math
import os
import sqlite3
import threading
import time

import tasksapi

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "bench.db")

REQUESTS = 60
PASSES = 2
P99_BUDGET_MS = 50.0
SQL_BUDGET = 3
PAGE_SIZE = 500
WRITER_INSERTS = 300


def requests_iter():
    for i in range(REQUESTS):
        page = (i % 8) + 1
        if i % 3 == 0:
            yield ("list", 1 + (i % 20), "open", None, page, 50)
        elif i % 3 == 1:
            yield ("list", 1 + (i % 20), "doing", "ticket-0", page, 50)
        else:
            yield ("count", 1 + (i % 20), None, None, page, 100)


def one_pass(conn):
    latencies = []
    for kind, tenant, status, keyword, page, page_size in requests_iter():
        start = time.perf_counter()
        if kind == "list":
            tasksapi.list_tasks(conn, tenant, status, keyword, page, page_size)
        else:
            tasksapi.count_tasks(conn, tenant, status, keyword)
        latencies.append((time.perf_counter() - start) * 1000.0)
    latencies.sort()
    return latencies[max(0, math.ceil(0.99 * len(latencies)) - 1)]


def count_sql_per_request(conn):
    counted = {"n": 0}
    conn.set_trace_callback(lambda _s: counted.__setitem__("n", counted["n"] + 1))
    tasksapi.list_tasks_cursor(conn, 3, "open", None, None, 50)
    conn.set_trace_callback(None)
    return counted["n"]


def plans(conn):
    out = []
    for sql, args in (
        (
            "SELECT t.id FROM tasks t WHERE t.tenant_id = ? AND t.status = ? "
            "ORDER BY t.created_at DESC, t.id DESC LIMIT 50",
            (3, "open"),
        ),
        (
            "SELECT COUNT(*) FROM tasks t WHERE t.tenant_id = ? AND t.status = ?",
            (3, "open"),
        ),
    ):
        rows = conn.execute("EXPLAIN QUERY PLAN " + sql, args).fetchall()
        out.append(" | ".join(row[3] for row in rows))
    return out


def writer(db_path, stop):
    conn = sqlite3.connect(db_path, timeout=30)
    base = 1_900_000_000
    for i in range(WRITER_INSERTS):
        if stop.is_set():
            break
        conn.execute(
            "INSERT INTO tasks (id, tenant_id, status, created_at, title, owner_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (2_000_000 + i, 3, "open", base + i, f"late-{i:04d} ticket", 1),
        )
        conn.commit()
        time.sleep(0.0005)
    conn.close()


def cursor_stability(conn, db_path):
    max_id = conn.execute("SELECT MAX(id) FROM tasks").fetchone()[0]
    expected = {
        row[0]
        for row in conn.execute(
            "SELECT id FROM tasks WHERE id <= ? AND tenant_id = 3 AND status = 'open'",
            (max_id,),
        )
    }
    items, cursor = tasksapi.list_tasks_cursor(conn, 3, "open", None, None, PAGE_SIZE)

    stop = threading.Event()
    thread = threading.Thread(target=writer, args=(db_path, stop), daemon=True)
    thread.start()
    seen = [item["id"] for item in items]
    try:
        while cursor is not None:
            items, cursor = tasksapi.list_tasks_cursor(conn, 3, "open", None, cursor, PAGE_SIZE)
            seen.extend(item["id"] for item in items)
    finally:
        stop.set()
        thread.join(timeout=10)

    counts = {}
    for row_id in seen:
        counts[row_id] = counts.get(row_id, 0) + 1
    dup = sum(c - 1 for c in counts.values() if c > 1)
    missing = len(expected - set(counts))
    extra = len(set(counts) - expected)
    return dup, missing, extra


def main():
    if not os.path.exists(DB):
        print("FAIL: 缺少 bench.db，请先运行 python3 seed.py")
        raise SystemExit(1)

    conn = sqlite3.connect(DB)
    tasksapi.list_tasks(conn, 1, "open", None, 1, 50)

    sql_per_request = count_sql_per_request(conn)
    plan_list, plan_count = plans(conn)
    best = min(one_pass(conn) for _ in range(PASSES))
    dup, missing, extra = cursor_stability(conn, DB)
    conn.close()

    problems = []
    if sql_per_request > SQL_BUDGET:
        problems.append(f"每请求 SQL 条数 {sql_per_request} > {SQL_BUDGET}")
    if "SCAN TASKS" in plan_list.upper():
        problems.append(f"列表查询仍在全表扫描: {plan_list}")
    if "SCAN TASKS" in plan_count.upper():
        problems.append(f"计数查询仍在全表扫描: {plan_count}")
    if best >= P99_BUDGET_MS:
        problems.append(f"p99 {best:.1f}ms >= {P99_BUDGET_MS}ms")
    if dup or missing or extra:
        problems.append(f"翻页期间 dup={dup} missing={missing} extra={extra}")

    if problems:
        print(f"FAIL: p99={best:.1f}ms sql_per_request={sql_per_request} dup={dup} missing={missing} extra={extra}")
        for item in problems:
            print("  - " + item)
        raise SystemExit(1)

    print(f"OK: p99 < {P99_BUDGET_MS:.0f}ms (实测 {best:.1f}ms), sql_per_request <= {SQL_BUDGET} "
          f"(实测 {sql_per_request}), no full scan, cursor stable")


if __name__ == "__main__":
    main()
