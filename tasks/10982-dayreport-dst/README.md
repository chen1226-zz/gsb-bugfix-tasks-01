# 10982 · 时区日报聚合（dayreport）

`dayreport.py` 负责把事件流按「用户本地时区」聚合成日报。

对外接口（不得更改签名）：

- `local_day_key(ts, zone)` → `"YYYY-MM-DD"`
- `day_range(day, zone)` → `(start_ts, end_ts)`
- `aggregate_by_day(events, zone)` → `{day: sum}`

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `dayreport.py` | 待修复的模块 |
| `repro.py` | 复现脚本，自带一份独立参照实现用于比对 |
| `tests/test_dayreport.py` | unittest 用例 |

## 已知现象

跨夏令时切换的那几天，日报边界会错一小时，个别日期会少算或多算一小时的
数据。只跑 UTC 的单元测试全绿，所以问题一直没被发现。

受影响时区不止整小时偏移的：`Australia/Lord_Howe` 的夏令时只差 30 分钟，
`Pacific/Chatham`、`Asia/Kathmandu` 使用的是 45 分钟偏移。

## 运行

```
python3 repro.py
python3 -m unittest tests/test_dayreport.py -v
```

`repro.py` 会用一份不使用 `dayreport` 内部函数的参照实现，对多组时区与切换
时刻做逐条比对。
