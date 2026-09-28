# 11000 · 分片路由（shardrouter）

`shardrouter.py` 把 key 路由到固定分片。

对外接口（不得更改签名）：

- `normalize_key(key)` → `bytes`
- `hash_key(key)` → `int`
- `shard_of(key, shards)` → `str`
- `route_with_legacy(key, shards, legacy)` → `str`（`legacy` 是 `{key: shard}` 的既有归属表）

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `shardrouter.py` | 待修复的模块 |
| `crossproc.py` | 复现脚本：跨进程一致性 + 扩容迁移量 + 负载分布 |
| `tests/test_shardrouter.py` | unittest 用例 |

## 已知现象

一是服务重启后，同一批 key 有 30%–40% 被路由到不同分片，缓存命中率骤降、部分数据
「找不到」；在同一个进程内反复计算则永远一致。

二是运维提的两条要求：以后扩容加机器时不能把绝大多数 key 都挪走；已经落库的那批
key 有历史归属表，新版本必须继续把它们路由回原来的分片，不能因为换了算法就整体
搬家。

## 运行

```
python3 crossproc.py
python3 -m unittest tests/test_shardrouter.py -v
```
