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

## 修复要点

- **幂等**：以 `(endpoint, event_id)` 为幂等键建立索引并持久化；重复提交返回
  同一个 `task_id`，下游只收到一次投递。
- **指数退避重试**：失败后按 `1s / 2s / 4s / 8s / 16s / 32s / 60s`（上限 60s）
  调度，并叠加最多 25% 的随机抖动。
- **失败分类**：`sender` 抛出带 `status` 属性的异常时按 HTTP 状态码分类；
  4xx 中除 `408`、`429` 外不重试，直接进入死信；其余错误（5xx、网络异常等）重试。
  连续失败 8 次后任务进入死信（`dead`）。
- **持久化**：任务与幂等索引以 JSON 原子落盘（临时文件 + `fsync` + `os.replace`），
  未完成任务在进程重启后仍可恢复。
- **出站头**：每次投递带 `X-Task-Id`、`X-Timestamp` 与 `X-Signature`
  （`HMAC-SHA256(secret, timestamp + "." + body)`）。
- **可注入时间/抖动**：`clock()` 控制“当前时间”，覆盖实例方法 `backoff_delay`
  或设置 `svc.jitter = lambda base: 0.0` 即可消除抖动；测试全程不真实 sleep。

## 运行

```
python3 run_demo.py
python3 -m unittest tests/test_webhook.py -v
```
