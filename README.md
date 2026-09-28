# GSB 修复类任务 · 初始环境仓库 01

本仓库用于给「修复类」标注任务提供**初始（带 bug 的）代码仓库**。

## 目录约定

一个仓库承载多个任务，**每个任务一个子目录**：

```
tasks/<UID>-<短名>/
```

`UID` 对应标注表里的任务编号，`短名` 是英文短标识。

**一个仓库最多放 10 个任务**，超出就另开新仓库（`gsb-bugfix-tasks-02` …）。

## 当前任务

| 子目录 | UID | 主题 |
| --- | --- | --- |
| `tasks/10979-webhook-delivery/` | 10979 | Webhook 幂等投递与重试 |
| `tasks/10980-ttl-cache-race/` | 10980 | TTL+LRU 缓存读到过期值 |
| `tasks/10981-wal-crash-recovery/` | 10981 | WAL 崩溃恢复丢写与半截记录 |
| `tasks/10982-dayreport-dst/` | 10982 | 时区/夏令时的日报边界 |
| `tasks/10984-consumer-idempotency/` | 10984 | 消费端重复投递重复记账 |
| `tasks/10985-sqlite-job-queue/` | 10985 | sqlite 任务队列并发领取 |
| `tasks/10992-cursor-pager/` | 10992 | 游标分页漏读与重复 |
| `tasks/10996-json-precision/` | 10996 | 大整数与金额精度 |
| `tasks/10997-list-api-perf/` | 10997 | 列表接口 N+1 与缺索引 |
| `tasks/11000-shard-router/` | 11000 | 分片路由跨进程不稳定 |

## 每个任务子目录的内容

| 文件 | 说明 |
| --- | --- |
| 业务模块 `.py` | 待修复的实现（带缺陷） |
| `repro.py` / `roundtrip.py` / `bench.py` / `crossproc.py` | 复现脚本，跑出明确的失败信号 |
| `tests/` | unittest 用例，其中一部分是**既有断言**（修复前后都必须通过） |
| `README.md` | 该任务的现象描述与运行方式 |

## 使用方式

以 `codex` 为例，工作目录是**仓库根目录**，任务在子目录里：

```
cd tasks/10982-dayreport-dst
python3 repro.py
python3 -m unittest discover -s tests
```

只允许改动自己任务子目录内的文件，不要跨目录改动。

## 共同约束

- 只使用 Python 3 标准库，不引入第三方依赖，不联网；
- 单文件 < 200 行；
- 既有测试的断言不得修改，只能新增用例；
- 复现脚本在修复前必须失败、修复后必须成功。
