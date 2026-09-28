"""复现脚本：解析 → 落库 → 读回 → 重新序列化，与原始文本逐字符比对。"""

import json
import os
import sqlite3
import subprocess
import sys

import ordersvc

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "samples", "samples.jsonl")


def load_samples():
    if not os.path.exists(SAMPLES):
        subprocess.run([sys.executable, os.path.join(HERE, "samples", "make_samples.py")], check=True)
    with open(SAMPLES, encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip()]


def main():
    conn = sqlite3.connect(":memory:")
    ordersvc.ensure_schema(conn)
    samples = load_samples()
    same = 0
    diffs = []
    for raw in samples:
        oid = ordersvc.ingest(conn, raw)
        out = ordersvc.export(conn, oid)
        if out == raw:
            same += 1
        else:
            diffs.append((raw, out))

    if diffs:
        print(f"FAIL: {same}/{len(samples)} samples identical")
        for raw, out in diffs[:3]:
            print(f"  原样 : {raw}")
            print(f"  读回 : {out}")
        raise SystemExit(1)

    print(f"OK: {same}/{len(samples)} samples identical")


if __name__ == "__main__":
    main()
