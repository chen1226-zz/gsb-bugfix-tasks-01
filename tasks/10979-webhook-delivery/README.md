# 10979 · Webhook 投递服务（webhook_service）

`webhook_service.py` 是一个 Webhook 投递服务：提交任务 → 本地持久化 → 后台投递。

对外接口（不得更改签名）：

- `DeliveryService(path, sender, clock)`
- `.submit(endpoint, event_id, payload)` → `task_id`
- `.process_due(max_tasks=10)` → 本轮结果 `dict`
- `.stats()` → `dict`
- `send_signature(secret, timestamp, body)` → `str`

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `webhook_service.py` | 待修复的模块 |
| `run_demo.py` | 复现脚本 |
| `tests/test_webhook.py` | unittest 用例 |

## 已知现象

一是同一个 `(endpoint, event_id)` 重复提交时会重复投递，下游重复记账；二是投递失败
之后没有重试，任务直接变成死信；三是进程重启后未投递的任务会丢。

生产上还要求出站请求带 `X-Signature`（HMAC-SHA256，签名含时间戳与 body）与
`X-Task-Id`。

## 运行

```
python3 run_demo.py
python3 -m unittest tests/test_webhook.py -v
```
