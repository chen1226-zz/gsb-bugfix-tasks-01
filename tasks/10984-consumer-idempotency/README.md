# 10984 · 消费端幂等（consumer）

`consumer.py` 从上游拉事件并落库（sqlite3）。

接口：`Consumer(conn).process(event)` → `"applied" | "duplicate"`；`.balance(account)`。

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `consumer.py` | 待修复的模块 |
| `replay_demo.py` | 复现脚本：整体重放 |
| `tests/test_consumer.py` | unittest 用例 |

## 已知现象

下游偶尔重复记账（同一笔业务被扣两次），把历史事件整体重放一遍必现；逐条处理时
完全正常。

## 运行

```
python3 replay_demo.py
python3 -m unittest tests/test_consumer.py -v
```
