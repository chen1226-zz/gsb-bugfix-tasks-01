"""Webhook 投递服务（本地持久化）。

对外接口（不得更改签名）：
    DeliveryService(path, sender, clock)
        .submit(endpoint, event_id, payload) -> task_id
        .process_due(max_tasks=10)           -> 本轮处理结果 dict
        .stats()                             -> dict
    send_signature(secret, timestamp, body)  -> str

sender(payload, headers) 由调用方注入；clock() 返回单调秒数，同样可注入。
"""

import hashlib
import hmac
import json
import os

BACKOFF = [1, 2, 4, 8, 16, 32, 60]
MAX_ATTEMPTS = 8
SECRET = b"demo-secret"


def send_signature(secret, timestamp, body):
    """HMAC-SHA256，签名内容为 timestamp + body。"""
    mac = hmac.new(secret, f"{timestamp}.".encode() + body, hashlib.sha256)
    return mac.hexdigest()


class DeliveryService:
    def __init__(self, path, sender, clock):
        self.path = path
        self.sender = sender
        self.clock = clock
        self.tasks = {}
        self.seq = 0
        if os.path.exists(path):
            self._load()

    # ---- 持久化 ----
    def _save(self):
        done = {tid: t for tid, t in self.tasks.items() if t["state"] == "delivered"}
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"seq": self.seq, "tasks": done}, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)

    def _load(self):
        with open(self.path, encoding="utf-8") as fh:
            blob = json.load(fh)
        self.seq = blob["seq"]
        self.tasks = blob["tasks"]

    # ---- 业务 ----
    def submit(self, endpoint, event_id, payload):
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
        for task in list(self.tasks.values()):
            if result["delivered"] + result["retried"] + result["dead"] >= max_tasks:
                break
            if task["state"] != "pending" or task["next_at"] > self.clock():
                continue
            task["attempts"] += 1
            try:
                self._deliver(task)
            except Exception:
                task["state"] = "dead"
                result["dead"] += 1
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
