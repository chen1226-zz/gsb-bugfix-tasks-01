# 10996 · 订单 JSON 精度（ordersvc）

`ordersvc.py` 解析上游 JSON 订单、写入 sqlite，再以 JSON 文本导出。

对外接口（不得更改签名）：

- `ensure_schema(conn)`
- `ingest(conn, raw_json)` → `order_id`
- `export(conn, order_id)` → `str`
- `log_line(conn, order_id)` → `str`

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `ordersvc.py` | 待修复的模块 |
| `roundtrip.py` | 复现脚本：解析 → 落库 → 读回 → 逐字符比对 |
| `samples/make_samples.py` | 样例生成器（不属于修复范围） |
| `samples/samples.jsonl` | 50 条样例数据（不属于修复范围） |
| `tests/test_ordersvc.py` | unittest 用例 |

## 已知现象

一是部分订单号（18–19 位整数）落库后末几位被抹成 0，导致同一订单出现两条
记录；二是金额偶发差 1 分，例如 `1234.56` 读回来变成 `1234.5599999999`，
对账时报不平。用小数值的测试用例全部通过，只有真实数据才暴露问题。

## 运行

```
python3 roundtrip.py
python3 -m unittest tests/test_ordersvc.py -v
```
