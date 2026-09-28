"""复现脚本：子进程写入并确认后立刻被 SIGKILL，重启校验不丢不截断。"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time

import walstore

ROUNDS = 500
KEYS = 12
VALUE = "v" * 64

CHILD = r"""
import sys, time, walstore
path = sys.argv[1]
s = walstore.WALStore(path)
s.open()
for i in range(int(sys.argv[2])):
    s.put("k%02d" % i, sys.argv[3])
sys.stdout.write("DONE\n")
sys.stdout.flush()
time.sleep(30)
"""


def one_round(path):
    proc = subprocess.Popen(
        [sys.executable, "-c", CHILD, path, str(KEYS), VALUE],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(os.path.abspath(__file__)),
        text=True,
    )
    line = proc.stdout.readline().strip()
    proc.send_signal(signal.SIGKILL)
    proc.wait(timeout=10)
    if line != "DONE":
        return ["子进程未能确认写入完成"]

    store = walstore.WALStore(path)
    store.open()
    problems = []
    for i in range(KEYS):
        key = "k%02d" % i
        got = store.get(key)
        if got is None:
            problems.append(f"{key} 丢失")
        elif got != VALUE:
            problems.append(f"{key} 被截断（{len(got)} 字节）")
    store.close()
    return problems


def main():
    root = tempfile.mkdtemp()
    for round_no in range(ROUNDS):
        path = os.path.join(root, f"db{round_no}")
        problems = one_round(path)
        if problems:
            print(f"FAIL: 第 {round_no + 1} 轮出现问题：{problems[0]}")
            print(f"  共 {len(problems)} 处异常")
            raise SystemExit(1)
    print(f"OK: {ROUNDS} rounds, 0 lost, 0 truncated")


if __name__ == "__main__":
    main()
