# 10997 · 任务列表接口性能（tasksapi）

`tasksapi.py` 提供任务列表接口，底层是 sqlite3。

对外接口（不得更改签名）：

- `ensure_schema(conn)`
- `list_tasks(conn, tenant_id, status=None, keyword=None, page=1, page_size=50)`

返回 `dict` 列表，键为 `id / tenant_id / status / created_at / title / owner`。

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `tasksapi.py` | 待修复的模块 |
| `seed.py` | 生成 20 万行基准数据（不属于修复范围） |
| `bench.py` | 复现脚本：P99、每请求 SQL 条数、查询计划 |
| `tests/test_tasksapi.py` | unittest 用例 |

## 已知现象

数据量从几万涨到百万级后，接口 P99 从 50ms 涨到几百毫秒，数据库 CPU 打满；
把单条查询拿出来单独跑都很快。

生产上还有个约束：`keyword` 是用户手输的短词，接口只需要**前缀匹配**，
不需要前后模糊匹配。

## 运行

```
python3 seed.py
python3 bench.py
python3 -m unittest tests/test_tasksapi.py -v
```

`bench.db` 由 `seed.py` 生成，不进版本库。
