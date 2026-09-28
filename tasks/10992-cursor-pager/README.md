# 10992 · 双向游标分页（pager）

`pager.py` 按「更新时间倒序 + id 倒序」对 `records` 表做游标分页，支持前后双向翻页。

对外接口（不得更改签名）：

- `InvalidCursor(ValueError)`
- `encode_cursor(payload)` → `str`
- `decode_cursor(cursor)` → `dict`
- `fetch_page(conn, cursor=None, page_size=50, direction="next")` → `(items, next_cursor, prev_cursor)`

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `pager.py` | 待修复的模块 |
| `repro.py` | 复现脚本：并发写入 + 双向翻页 + 游标篡改 |
| `tests/test_pager.py` | unittest 用例 |

## 已知现象

翻页过程中偶发漏掉或重复返回记录，在大量记录的 `updated_at` 相同时更容易出现；
单次查询结果正确。生产上 `updated_at` 是秒级时间戳，批量导入的数据大量集中在
同一秒，重复排序键是常态而不是例外。

另外两个已知问题：调用方传入被篡改或过期的游标时接口不报错，而是静默从第一页
重新返回；反向翻页（上一页）的结果与正向对不上。

## 运行

```
python3 repro.py
python3 -m unittest discover -s tests
```
