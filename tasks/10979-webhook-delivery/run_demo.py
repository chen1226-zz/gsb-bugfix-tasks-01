"""复现脚本：3 次提交（其中 1 次重复）、1 次失败重试、重启后不丢任务。"""

import json
import os
import tempfile

import webhook_service
from webhook_service import DeliveryService

received = []
fail_once = {"n": 0}


def sender(endpoint, body, headers):
    if "flaky" in endpoint and fail_once["n"] == 0:
        fail_once["n"] = 1
        raise RuntimeError("下游 503")
    received.append((endpoint, body, headers))


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def main():
    path = os.path.join(tempfile.mkdtemp(), "tasks.json")
    clock = Clock()
    svc = DeliveryService(path, sender, clock)

    a = svc.submit("http://ok/1", "evt-1", {"n": 1})
    b = svc.submit("http://ok/1", "evt-1", {"n": 1})      # 重复提交
    svc.submit("http://flaky/2", "evt-2", {"n": 2})
    svc.submit("http://ok/1", "evt-3", {"n": 3})

    duplicate_skipped = 1 if a == b else 0

    svc.process_due()

    # 重启：此时还应有 1 个任务没投完，必须能恢复
    restarted = DeliveryService(path, sender, clock)
    after_restart = restarted.stats()

    for _ in range(12):
        clock.advance(5)
        restarted.process_due()
    stats = restarted.stats()

    # 校验出站签名可以复算
    signature_ok = False
    for endpoint, body, headers in received:
        want = webhook_service.send_signature(
            webhook_service.SECRET, int(headers["X-Timestamp"]), body
        )
        if headers["X-Signature"] == want and headers["X-Task-Id"]:
            signature_ok = True
            break

    problems = []
    if duplicate_skipped != 1:
        problems.append("重复提交没有被识别为同一任务")
    if after_restart["pending"] != 1:
        problems.append(
            f"重启后未完成任务应剩 1 个，实际 pending={after_restart['pending']} total={after_restart['total']}"
        )
    if stats["delivered"] != 3:
        problems.append(f"投递成功数应为 3，实际 {stats['delivered']}")
    if stats["pending"] != 0:
        problems.append(f"重启后仍有 {stats['pending']} 个任务未完成")
    if not signature_ok:
        problems.append("出站请求缺少签名或任务头")

    if problems:
        print("FAIL: " + "; ".join(problems))
        print("  stats=" + json.dumps(stats, ensure_ascii=False))
        raise SystemExit(1)

    print("OK: 3 tasks, 1 duplicate skipped, 1 retried, 0 lost")


if __name__ == "__main__":
    main()
