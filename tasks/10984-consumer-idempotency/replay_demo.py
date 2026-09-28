"""复现脚本：把同一批事件整体重放一遍，汇总值必须和只处理一遍相同。"""

import sqlite3

from consumer import Consumer

EVENTS = [
    {"event_id": f"e{i:03d}", "account": f"acct-{i % 5}", "amount": 10 + (i % 7)}
    for i in range(120)
]


def main():
    conn = sqlite3.connect(":memory:")
    Consumer(conn)

    first = Consumer(conn)
    for event in EVENTS:
        first.process(event)
    single_pass = sum(row[0] for row in conn.execute("SELECT balance FROM accounts"))

    # 重放：新的消费者实例，同一份事件流再来一遍
    replay = Consumer(conn)
    for event in EVENTS:
        replay.process(event)
    after_replay = sum(row[0] for row in conn.execute("SELECT balance FROM accounts"))

    if single_pass != after_replay:
        print(f"FAIL: replay {after_replay} != single-pass {single_pass}")
        raise SystemExit(1)
    print("OK: replay total == single-pass total")


if __name__ == "__main__":
    main()
