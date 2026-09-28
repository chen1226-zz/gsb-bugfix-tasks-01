# 10981 · WAL 存储崩溃恢复（walstore）

`walstore.py` 是一个 append-only 键值存储：写入先追加预写日志（WAL），启动时重放
WAL 恢复索引。

对外接口（不得更改签名）：

- `WALStore(path)`
- `.open()` / `.put(key, value)` / `.get(key)` / `.close()` / `.keys()`

记录格式：`key_len(<H) | key | value_len(<I) | value`（UTF-8）。

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `walstore.py` | 待修复的模块 |
| `crash_test.py` | 复现脚本：写入确认后 SIGKILL，重启校验 |
| `tests/test_walstore.py` | unittest 用例 |

## 已知现象

进程被 SIGKILL 后重启，偶尔丢掉一部分明明已经返回成功的写入；个别情况还会读到
「半截」记录（key 正确但 value 被截断）。正常退出从不重现。

## 运行

```
python3 crash_test.py
python3 -m unittest tests/test_walstore.py -v
```
