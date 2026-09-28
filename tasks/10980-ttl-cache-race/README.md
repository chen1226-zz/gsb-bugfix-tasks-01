# 10980 · TTL + LRU 缓存（cache）

`cache.py` 是一个带 TTL + LRU 的进程内缓存。

对外接口（不得更改签名）：

- `TTLCache(capacity, ttl, clock=None, on_evict=None)`
- `.get(key)` → 值或 `None`
- `.put(key, value)`
- `.stats()` → `dict`

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `cache.py` | 待修复的模块 |
| `run_race.py` | 复现脚本（注入时钟，统计过期读取） |
| `tests/test_cache.py` | unittest 用例 |

## 已知现象

并发读写压力下 `get()` 偶尔返回已经过期的条目（TTL 早就过了）；有时统计里的
容量与淘汰数也对不上。单线程测试全绿。

## 运行

```
python3 run_race.py
python3 -m unittest tests/test_cache.py -v
```
