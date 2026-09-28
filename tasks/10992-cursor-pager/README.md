# 10992 · 游标分页（pager）

`pager.py` 按「更新时间倒序 + id 倒序」对 `records` 表做游标分页。

对外接口（不得更改签名）：

- `encode_cursor(payload)` → `str`
- `decode_cursor(cursor)` → `dict`
- `fetch_page(conn, cursor, page_size)` → `(items, next_cursor)`

表结构：

```sql
CREATE TABLE records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  updated_at INTEGER NOT NULL,
  payload TEXT NOT NULL
);
```

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `pager.py` | 待修复的模块 |
| `repro.py` | 复现脚本（翻页期间有并发写入） |
| `tests/test_pager.py` | unittest 用例 |

## 已知现象

翻页过程中偶发漏掉或重复返回记录，在大量记录的 `updated_at` 相同时更容易
出现；单次查询结果正确。

生产环境里 `updated_at` 是秒级时间戳，批量导入的数据大量集中在同一秒，
重复排序键是常态而不是例外。

## 运行

```
python3 repro.py
python3 -m unittest tests/test_pager.py -v
```
