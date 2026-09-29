"""Webhook 投递服务（本地持久化、幂等、指数退避重试）。

对外接口（签名不变）：
    DeliveryService(path, sender, clock)
        .submit(endpoint, event_id, payload) -> task_id
        .process_due(max_tasks=10)           -> 本轮处理结果 dict
        .stats()                             -> dict
    send_signature(secret, timestamp, body)  -> str

sender(endpoint, body, headers) 由调用方注入；clock() 返回单调秒数，可注入。
重试与 4xx 分类约定：
    - sender 正常返回即视为投递成功；
    - sender 抛出带 int 属性 status 的异常时按 HTTP 状态码分类：
      4xx（除 408、429）不重试，直接死信；其余状态码重试；
    - 抛出其它异常一律重试。
退避时间与抖动均可注入（测试无需 sleep）：覆盖实例方法 .backoff_delay，
或注入可调用属性 .jitter（如 lambda base: 0.0）。
"""

import hashlib
import hmac
import json
import os
import random

BACKOFF = [1, 2, 4, 8, 16, 32, 60]
MAX_ATTEMPTS = 8
RETRIABLE_4XX = (408, 429)
SECRET = b"demo-secret"


def send_signature(secret, timestamp, body):
    """HMAC-SHA256，签名内容为 timestamp + "." + body。"""
    mac = hmac.new(secret, f"{timestamp}.".encode() + body, hashlib.sha256)
    return mac.hexdigest()


class DeliveryError(Exception):
    """投递失败；携带可选 HTTP 状态码 status 用于重试分类。"""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def _retryable(exc):
    """4xx（除 408、429）不重试，其余异常重试。"""
    status = getattr(exc, "status", None)
    if isinstance(status, int) and 400 <= status < 500:
        return status in RETRIABLE_4XX
    return True


class DeliveryService:
    def __init__(self, path, sender, clock):
        self.path = path
        self.sender = sender
        self.clock = clock
        self.tasks = {}
        self.index = {}
        self.seq = 0
        self._rand = random.Random()
        self.jitter = None  # 可注入：base(秒) -> 额外等待秒数
        if os.path.exists(path):
            self._load()

    # ---- 持久化（全部状态落盘，重启可恢复）----
    def _save(self):
        blob = {"seq": self.seq, "index": self.index, "tasks": self.tasks}
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(blob, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)

    def _load(self):
        with open(self.path, encoding="utf-8") as fh:
            blob = json.load(fh)
        self.seq = blob.get("seq", 0)
        self.tasks = blob.get("tasks", {})
        self.index = blob.get("index") or {
            self._key(t["endpoint"], t["event_id"]): tid
            for tid, t in self.tasks.items()
        }

    # ---- 业务 ----
    @staticmethod
    def _key(endpoint, event_id):
        return json.dumps([endpoint, event_id], ensure_ascii=False)

    def submit(self, endpoint, event_id, payload):
        # 幂等：相同 (endpoint, event_id) 返回同一 task_id，不重复投递。
        existing = self.index.get(self._key(endpoint, event_id))
        if existing is not None:
            return existing
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
        self.index[self._key(endpoint, event_id)] = task_id
        self._save()
        return task_id

    def backoff_delay(self, attempts):
        """第 attempts 次失败后到下次投递的间隔（秒）：指数退避 + 抖动，上限 60s。"""
        base = BACKOFF[min(attempts - 1, len(BACKOFF) - 1)]
        if self.jitter is not None:
            return base + self.jitter(base)
        return base + self._rand.uniform(0, base * 0.25)

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
            if result["delivered"] + result["retried"] + result["dead"] >= max_tasks:
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
                    task["next_at"] = self.clock() + self.backoff_delay(task["attempts"])
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
