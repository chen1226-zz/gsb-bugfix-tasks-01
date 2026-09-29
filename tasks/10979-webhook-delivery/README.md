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

## 行为说明

- 幂等：`(endpoint, event_id)` 为幂等键，重复提交返回同一个 `task_id`，不重复投递。
- 重试：失败按指数退避（1s/2s/4s…，上限 60s）加抖动重试；4xx（除 408、429）不重试；
  连续失败 8 次进入死信（`dead`）。
- 签名：出站请求带 `X-Signature`（HMAC-SHA256，签名内容为 `时间戳.body`）、
  `X-Timestamp` 与 `X-Task-Id`。
- 持久化：所有任务状态原子写入本地 JSON 文件（tmp + rename + fsync），进程重启后
  未完成任务自动恢复。
- 可测试性：退避基数 `backoff_seconds(attempt)` 与抖动 `jitter()` 是模块级函数，
  测试可直接替换注入，无需真实 sleep。

## 运行

```
python3 run_demo.py
python3 -m unittest tests/test_webhook.py -v
```
