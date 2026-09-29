"""Webhook 投递服务（本地持久化）。

对外接口（不得更改签名）：
    DeliveryService(path, sender, clock)
        .submit(endpoint, event_id, payload) -> task_id
        .process_due(max_tasks=10)           -> 本轮处理结果 dict
        .stats()                             -> dict
    send_signature(secret, timestamp, body)  -> str

sender(endpoint, body, headers) 由调用方注入；clock() 返回单调秒数，同样可注入。
退避基数 backoff_seconds(attempt) 与抖动 jitter() 是模块级函数，测试可直接替换注入，
无需真实 sleep。
"""

import hashlib
import hmac
import json
import os
import random

MAX_ATTEMPTS = 8
MAX_BACKOFF = 60
SECRET = b"demo-secret"


def send_signature(secret, timestamp, body):
    """HMAC-SHA256，签名内容为 timestamp + body。"""
    mac = hmac.new(secret, f"{timestamp}.".encode() + body, hashlib.sha256)
    return mac.hexdigest()


def backoff_seconds(attempt):
    """第 attempt 次失败后的退避基数：1/2/4/8...，上限 60s。"""
    return min(2 ** (attempt - 1), MAX_BACKOFF)


def jitter():
    """抖动系数，避免大量任务同一时刻重试造成惊群。"""
    return random.uniform(0.5, 1.5)


def _retryable(exc):
    """4xx（除 408、429）不重试；其余异常（含网络错误）可重试。

    状态码取自异常的 status 或 code 属性（兼容 urllib.error.HTTPError）。
    """
    status = getattr(exc, "status", getattr(exc, "code", None))
    if status is None:
        return True
    return not (400 <= status < 500 and status not in (408, 429))


class DeliveryService:
    def __init__(self, path, sender, clock):
        self.path = path
        self.sender = sender
        self.clock = clock
        self.tasks = {}
        self.keys = {}
        self.seq = 0
        if os.path.exists(path):
            self._load()

    # ---- 持久化 ----
    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"seq": self.seq, "tasks": self.tasks}, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)

    def _load(self):
        with open(self.path, encoding="utf-8") as fh:
            blob = json.load(fh)
        self.seq = blob["seq"]
        self.tasks = blob["tasks"]
        self.keys = {
            (t["endpoint"], t["event_id"]): tid for tid, t in self.tasks.items()
        }

    # ---- 业务 ----
    def submit(self, endpoint, event_id, payload):
        key = (endpoint, event_id)
        if key in self.keys:  # 幂等：重复提交返回同一个 task_id，不重复投递
            return self.keys[key]
        self.seq += 1
        task_id = f"t{self.seq:04d}"
        self.tasks[task_id] = {
            "task_id": task_id,
            "endpoint": endpoint,
            "event_id": event_id,
            "payload": payload,
            "state": "pending",
            "attempts": 0,
            "next_at": self.clock(),
        }
        self.keys[key] = task_id
        self._save()
        return task_id

    def _deliver(self, task):
        body = json.dumps(task["payload"], sort_keys=True).encode()
        now = int(self.clock())
        headers = {
            "X-Task-Id": task["task_id"],
            "X-Timestamp": str(now),
            "X-Signature": send_signature(SECRET, now, body),
        }
        return self.sender(task["endpoint"], body, headers)

    def process_due(self, max_tasks=10):
        result = {"delivered": 0, "retried": 0, "dead": 0}
        now = self.clock()
        for task in list(self.tasks.values()):
            if sum(result.values()) >= max_tasks:
                break
            if task["state"] != "pending" or task["next_at"] > now:
                continue
            task["attempts"] += 1
            try:
                self._deliver(task)
            except Exception as exc:
                if not _retryable(exc) or task["attempts"] >= MAX_ATTEMPTS:
                    task["state"] = "dead"
                    result["dead"] += 1
                else:
                    task["next_at"] = now + backoff_seconds(task["attempts"]) * jitter()
                    result["retried"] += 1
                continue
            task["state"] = "delivered"
            result["delivered"] += 1
        self._save()
        return result

    def stats(self):
        counts = {"pending": 0, "delivered": 0, "dead": 0}
        for task in self.tasks.values():
            counts[task["state"]] = counts.get(task["state"], 0) + 1
        counts["total"] = len(self.tasks)
        return counts
