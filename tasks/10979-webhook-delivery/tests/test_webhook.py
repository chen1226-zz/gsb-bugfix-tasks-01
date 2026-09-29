import os
import tempfile
import unittest
from unittest import mock

import webhook_service
from webhook_service import DeliveryService, send_signature


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


def make(sender=None, clock=None):
    path = os.path.join(tempfile.mkdtemp(), "t.json")
    return DeliveryService(path, sender or (lambda *a: None), clock or Clock()), path


class TestWebhook(unittest.TestCase):
    def test_signature_is_hmac_sha256(self):
        """既有断言：签名是 64 位十六进制。"""
        sig = send_signature(b"k", 1700000000, b"body")
        self.assertEqual(len(sig), 64)
        int(sig, 16)

    def test_submit_persists_task(self):
        """既有断言：提交后任务被写入文件。"""
        svc, path = make()
        svc.submit("http://x/1", "e1", {"a": 1})
        self.assertTrue(os.path.exists(path))

    def test_successful_delivery_counts(self):
        """既有断言：投递成功计入 delivered。"""
        svc, _ = make()
        svc.submit("http://x/1", "e1", {"a": 1})
        svc.process_due()
        self.assertEqual(svc.stats()["delivered"], 1)

    def test_stats_total_matches_submits(self):
        """既有断言：总任务数等于提交次数。"""
        svc, _ = make()
        svc.submit("http://x/1", "e1", {})
        svc.submit("http://x/1", "e2", {})
        self.assertEqual(svc.stats()["total"], 2)


class HttpError(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.status = status


class FlakySender:
    """前 fail_times 次抛异常，之后成功；记录所有调用。"""

    def __init__(self, fail_times=1, exc=None):
        self.fail_times = fail_times
        self.exc = exc or RuntimeError("boom")
        self.calls = []

    def __call__(self, endpoint, body, headers):
        self.calls.append((endpoint, body, headers))
        if len(self.calls) <= self.fail_times:
            raise self.exc


@mock.patch.object(webhook_service, "jitter", lambda: 1.0)
class TestDeliveryFixes(unittest.TestCase):
    def test_duplicate_submit_returns_same_task_id(self):
        svc, _ = make()
        first = svc.submit("http://x/1", "e1", {"a": 1})
        second = svc.submit("http://x/1", "e1", {"a": 1})
        self.assertEqual(first, second)
        self.assertEqual(svc.stats()["total"], 1)

    def test_duplicate_submit_not_delivered_twice(self):
        sender = FlakySender(fail_times=0)
        svc, _ = make(sender=sender)
        svc.submit("http://x/1", "e1", {"a": 1})
        svc.submit("http://x/1", "e1", {"a": 1})
        svc.process_due()
        self.assertEqual(len(sender.calls), 1)
        self.assertEqual(svc.stats()["delivered"], 1)

    def test_backoff_sequence_and_cap(self):
        self.assertEqual(webhook_service.backoff_seconds(1), 1)
        self.assertEqual(webhook_service.backoff_seconds(2), 2)
        self.assertEqual(webhook_service.backoff_seconds(3), 4)
        self.assertEqual(webhook_service.backoff_seconds(10), 60)
        self.assertEqual(webhook_service.backoff_seconds(100), 60)

    def test_failure_is_retried_after_backoff(self):
        clock = Clock()
        sender = FlakySender(fail_times=1)
        svc, _ = make(sender=sender, clock=clock)
        svc.submit("http://x/1", "e1", {})
        result = svc.process_due()
        self.assertEqual(result["retried"], 1)
        self.assertEqual(svc.stats()["pending"], 1)
        # 退避 1s 内不重试
        svc.process_due()
        self.assertEqual(len(sender.calls), 1)
        clock.advance(1)
        svc.process_due()
        self.assertEqual(len(sender.calls), 2)
        self.assertEqual(svc.stats()["delivered"], 1)

    def test_4xx_not_retried(self):
        for status in (400, 404, 422):
            sender = FlakySender(fail_times=99, exc=HttpError(status))
            svc, _ = make(sender=sender)
            svc.submit("http://x/1", "e1", {})
            result = svc.process_due()
            self.assertEqual(result["dead"], 1)
            self.assertEqual(result["retried"], 0)
            self.assertEqual(len(sender.calls), 1)

    def test_408_and_429_are_retried(self):
        for status in (408, 429):
            clock = Clock()
            sender = FlakySender(fail_times=99, exc=HttpError(status))
            svc, _ = make(sender=sender, clock=clock)
            svc.submit("http://x/1", "e1", {})
            result = svc.process_due()
            self.assertEqual(result["retried"], 1)
            self.assertEqual(svc.stats()["pending"], 1)

    def test_dead_letter_after_max_attempts(self):
        clock = Clock()
        sender = FlakySender(fail_times=99)
        svc, _ = make(sender=sender, clock=clock)
        svc.submit("http://x/1", "e1", {})
        for _ in range(webhook_service.MAX_ATTEMPTS - 1):
            svc.process_due()
            self.assertEqual(svc.stats()["pending"], 1)
            clock.advance(60)
        svc.process_due()
        self.assertEqual(svc.stats()["dead"], 1)
        self.assertEqual(len(sender.calls), webhook_service.MAX_ATTEMPTS)

    def test_restart_recovers_pending_tasks(self):
        clock = Clock()
        sender = FlakySender(fail_times=1)
        svc, path = make(sender=sender, clock=clock)
        task_id = svc.submit("http://x/1", "e1", {"a": 1})
        svc.process_due()  # 第一次失败，进入待重试
        restarted = DeliveryService(path, sender, clock)
        self.assertEqual(restarted.stats()["pending"], 1)
        clock.advance(1)
        restarted.process_due()
        self.assertEqual(restarted.stats()["delivered"], 1)
        # 重启后重复提交仍幂等
        self.assertEqual(restarted.submit("http://x/1", "e1", {"a": 1}), task_id)

    def test_outbound_headers_signed(self):
        sender = FlakySender(fail_times=0)
        svc, _ = make(sender=sender)
        task_id = svc.submit("http://x/1", "e1", {"a": 1})
        svc.process_due()
        _, body, headers = sender.calls[0]
        self.assertEqual(headers["X-Task-Id"], task_id)
        want = send_signature(
            webhook_service.SECRET, int(headers["X-Timestamp"]), body
        )
        self.assertEqual(headers["X-Signature"], want)


if __name__ == "__main__":
    unittest.main()
