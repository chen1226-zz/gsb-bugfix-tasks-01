"""复现脚本：
  1. 两个独立进程（PYTHONHASHSEED 不同）分别计算 10 万个 key 的路由，逐 key 比对；
  2. 增加一个分片后，统计有多少 key 换了分片；
  3. 统计 16 个分片的负载是否均匀。
"""

import json
import os
import subprocess
import sys
import tempfile

import shardrouter

KEYS = 100_000
SHARDS = [f"shard-{i:02d}" for i in range(16)]
OUT = os.path.join(tempfile.mkdtemp(), "routes.json")
PREFIX = "user:"


def child_source():
    return (
        "import json, sys\n"
        "import shardrouter\n"
        "keys = [f'user:{i}' for i in range(int(sys.argv[1]))]\n"
        "shards = json.loads(sys.argv[2])\n"
        "routes = [shardrouter.shard_of(k, shards) for k in keys]\n"
        "json.dump(routes, open(sys.argv[3], 'w'))\n"
    )


def run_child(seed, path):
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = str(seed)
    subprocess.run(
        [sys.executable, "-c", child_source(), str(KEYS), json.dumps(SHARDS), path],
        check=True,
        env=env,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main():
    a_path = os.path.join(os.path.dirname(OUT), "routes-a.json")
    b_path = os.path.join(os.path.dirname(OUT), "routes-b.json")
    routes_a = run_child(0, a_path)
    routes_b = run_child(1, b_path)

    mismatch = sum(1 for x, y in zip(routes_a, routes_b) if x != y)
    if mismatch:
        print(f"FAIL: {KEYS} keys, {mismatch} mismatch")
        print(f"  例：key=user:7 -> 进程A={routes_a[7]} 进程B={routes_b[7]}")
        raise SystemExit(1)

    # 增加一个分片，统计迁移比例
    wider = SHARDS + ["shard-16"]
    moved = 0
    for i in range(KEYS):
        if shardrouter.shard_of(f"{PREFIX}{i}", SHARDS) != shardrouter.shard_of(f"{PREFIX}{i}", wider):
            moved += 1
    moved_ratio = moved / KEYS

    loads = {name: 0 for name in SHARDS}
    for i in range(KEYS):
        loads[shardrouter.shard_of(f"{PREFIX}{i}", SHARDS)] += 1
    ideal = KEYS / len(SHARDS)
    max_ratio = max(loads.values()) / ideal

    problems = []
    if moved_ratio > 1.6 / len(SHARDS):
        problems.append(f"加一个分片迁移了 {moved_ratio:.1%}（上限 {1.6 / len(SHARDS):.1%}）")
    if max_ratio > 1.5:
        problems.append(f"分片负载不均，最大/平均 = {max_ratio:.2f}")

    if problems:
        print(f"FAIL: {KEYS} keys, 0 mismatch, 但迁移/分布不达标")
        for item in problems:
            print("  - " + item)
        raise SystemExit(1)

    print(f"OK: {KEYS} keys, 0 mismatch, moved {moved_ratio:.1%} (<= {1.6 / len(SHARDS):.1%}), max/avg {max_ratio:.2f}")


if __name__ == "__main__":
    main()
