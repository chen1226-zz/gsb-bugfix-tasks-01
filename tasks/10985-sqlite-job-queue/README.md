# 10985 · sqlite 任务队列（jobstore）

`jobstore.py` 用 sqlite3 做任务队列，多个 worker 进程同时抢任务。

接口：`JobStore(path).add(titles)` / `.claim(worker)` / `.stats()`。

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `jobstore.py` | 待修复的模块 |
| `run_stress.py` | 复现脚本：4 进程并发领取 |
| `tests/test_jobstore.py` | unittest 用例 |

## 已知现象

并发一高就偶发 `sqlite3.OperationalError: database is locked`，而且部分任务状态更新
会静默丢失（事务回滚了却没有重试），最终统计对不上；低并发完全正常。

## 运行

```
python3 run_stress.py
python3 -m unittest tests/test_jobstore.py -v
```
