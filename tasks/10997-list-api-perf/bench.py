"""复现脚本：测 P99、每请求 SQL 条数，并检查查询计划。"""

import math
import os
import sqlite3
import time

import tasksapi

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "bench.db")

REQUESTS = 60
PASSES = 2
P99_BUDGET_MS = 50.0
SQL_BUDGET = 3


def requests_iter():
    for i in range(REQUESTS):
        page = (i % 8) + 1
        if i % 3 == 0:
            yield (1 + (i % 20), "open", None, page, 50)
        elif i % 3 == 1:
            yield (1 + (i % 20), "doing", "ticket-0", page, 50)
        else:
            yield (1 + (i % 20), None, None, page, 100)


def one_pass(conn):
    latencies = []
    for tenant, status, keyword, page, page_size in requests_iter():
        start = time.perf_counter()
        tasksapi.list_tasks(conn, tenant, status, keyword, page, page_size)
        latencies.append((time.perf_counter() - start) * 1000.0)
    latencies.sort()
    idx = max(0, math.ceil(0.99 * len(latencies)) - 1)
    return latencies[idx]


def count_sql_per_request(conn):
    counted = {"n": 0}
    conn.set_trace_callback(lambda _stmt: counted.__setitem__("n", counted["n"] + 1))
    tasksapi.list_tasks(conn, 3, "open", None, 1, 50)
    conn.set_trace_callback(None)
    return counted["n"]


def plan_of_list_query(conn):
    sql = (
        "SELECT id, tenant_id, status, created_at, title, owner_id FROM tasks "
        "WHERE tenant_id = ? AND status = ? ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
    )
    rows = conn.execute("EXPLAIN QUERY PLAN " + sql, (3, "open", 50, 0)).fetchall()
    return " | ".join(row[3] for row in rows)


def main():
    if not os.path.exists(DB):
        print("FAIL: 缺少 bench.db，请先运行 python3 seed.py")
        raise SystemExit(1)

    conn = sqlite3.connect(DB)
    tasksapi.list_tasks(conn, 1, "open", None, 1, 50)

    sql_per_request = count_sql_per_request(conn)
    plan = plan_of_list_query(conn)
    best = min(one_pass(conn) for _ in range(PASSES))
    conn.close()

    problems = []
    if sql_per_request > SQL_BUDGET:
        problems.append(f"每请求 SQL 条数 {sql_per_request} > {SQL_BUDGET}")
    if "SCAN TASKS" in plan.upper():
        problems.append(f"列表查询仍在全表扫描: {plan}")
    if best >= P99_BUDGET_MS:
        problems.append(f"p99 {best:.1f}ms >= {P99_BUDGET_MS}ms")

    if problems:
        print(f"FAIL: p99={best:.1f}ms sql_per_request={sql_per_request}")
        for item in problems:
            print("  - " + item)
        raise SystemExit(1)

    print(f"OK: p99 < {P99_BUDGET_MS:.0f}ms (实测 {best:.1f}ms), sql_per_request <= {SQL_BUDGET} (实测 {sql_per_request})")


if __name__ == "__main__":
    main()
