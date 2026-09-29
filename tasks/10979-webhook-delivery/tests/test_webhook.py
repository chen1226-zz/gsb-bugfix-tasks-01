import os
import tempfile
import unittest

from webhook_service import (
    DeliveryError,
    DeliveryService,
    SECRET,
    send_signature,
)


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


class RecordingSender:
    def __init__(self, fail_statuses=(), fail_times=0, fail_forever=False):
        self.calls = []
        self.fail_statuses = list(fail_statuses)
        self.fail_times = fail_times
        self.fail_forever = fail_forever

    def __call__(self, endpoint, body, headers):
        self.calls.append((endpoint, body, headers))
        if self.fail_statuses:
            raise DeliveryError("http", status=self.fail_statuses.pop(0))
        if self.fail_forever or self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("boom")


def no_jitter(svc):
    svc.jitter = lambda base: 0.0
    return svc


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

    def test_duplicate_returns_same_task_id_and_delivers_once(self):
        sender = RecordingSender()
        svc, _ = make(sender)
        first = svc.submit("http://x/1", "e1", {"a": 1})
        second = svc.submit("http://x/1", "e1", {"a": 1})
        self.assertEqual(first, second)
        svc.process_due()
        self.assertEqual(svc.stats()["total"], 1)
        self.assertEqual(len(sender.calls), 1)

    def test_different_event_ids_are_distinct_tasks(self):
        svc, _ = make()
        self.assertNotEqual(
            svc.submit("http://x/1", "e1", {}),
            svc.submit("http://x/1", "e2", {}),
        )

    def test_backoff_schedule_is_1_2_4_with_real_sleep_disabled(self):
        sender = RecordingSender(fail_forever=True)
        clock = Clock()
        svc, _ = make(sender, clock)
        no_jitter(svc)
        svc.submit("http://x/1", "e1", {})
        svc.process_due()  # 第 1 次失败，1s 后再试
        self.assertEqual(svc.tasks["t0001"]["next_at"], 1)
        clock.advance(0.9)
        self.assertEqual(svc.process_due()["retried"], 0)  # 未到期不投递
        clock.advance(0.1)
        svc.process_due()  # 第 2 次失败，再等 2s
        self.assertEqual(svc.tasks["t0001"]["next_at"], 3)
        clock.advance(4)
        svc.process_due()  # 第 3 次失败，再等 4s
        self.assertEqual(svc.tasks["t0001"]["next_at"], 9)

    def test_eventual_success_after_retries(self):
        sender = RecordingSender(fail_times=2)
        clock = Clock()
        svc, _ = make(sender, clock)
        no_jitter(svc)
        svc.submit("http://x/1", "e1", {})
        for _ in range(5):
            svc.process_due()
            clock.advance(10)
        self.assertEqual(svc.stats()["delivered"], 1)
        self.assertEqual(svc.stats()["pending"], 0)

    def test_4xx_except_408_429_is_not_retried(self):
        sender = RecordingSender(fail_statuses=[400])
        svc, _ = make(sender)
        svc.submit("http://x/1", "e1", {})
        result = svc.process_due()
        self.assertEqual(result["dead"], 1)
        self.assertEqual(svc.stats()["dead"], 1)
        self.assertEqual(svc.tasks["t0001"]["attempts"], 1)

    def test_408_and_429_are_retried(self):
        clock = Clock()
        svc, _ = make(RecordingSender(fail_statuses=[408, 429]), clock)
        no_jitter(svc)
        svc.submit("http://a/1", "e1", {})
        svc.submit("http://b/1", "e2", {})
        self.assertEqual(svc.process_due()["retried"], 2)
        self.assertEqual(svc.stats()["pending"], 2)

    def test_dead_after_eight_consecutive_failures(self):
        sender = RecordingSender(fail_forever=True)
        clock = Clock()
        svc, _ = make(sender, clock)
        no_jitter(svc)
        svc.submit("http://x/1", "e1", {})
        for _ in range(20):
            svc.process_due()
            if svc.tasks["t0001"]["state"] != "pending":
                break
            clock.advance(100)
        self.assertEqual(svc.stats()["dead"], 1)
        self.assertEqual(svc.tasks["t0001"]["attempts"], 8)

    def test_pending_task_survives_restart_and_keeps_idempotency(self):
        sender = RecordingSender(fail_times=1)
        clock = Clock()
        svc, path = make(sender, clock)
        no_jitter(svc)
        task_id = svc.submit("http://x/1", "e1", {})
        svc.process_due()  # 失败进入重试，任务仍未完成
        self.assertEqual(svc.stats()["pending"], 1)

        restarted = DeliveryService(path, RecordingSender(), clock)
        self.assertEqual(restarted.stats()["pending"], 1)
        self.assertEqual(restarted.submit("http://x/1", "e1", {}), task_id)
        clock.advance(10)
        restarted.process_due()
        self.assertEqual(restarted.stats()["delivered"], 1)

    def test_outbound_headers_carry_signature_task_id_and_timestamp(self):
        sender = RecordingSender()
        svc, _ = make(sender)
        task_id = svc.submit("http://x/1", "e1", {"a": 1})
        svc.process_due()
        endpoint, body, headers = sender.calls[0]
        self.assertEqual(headers["X-Task-Id"], task_id)
        self.assertTrue(headers["X-Timestamp"])
        expected = send_signature(SECRET, int(headers["X-Timestamp"]), body)
        self.assertEqual(headers["X-Signature"], expected)

    def test_jitter_is_injectable(self):
        svc, _ = make()
        svc.jitter = lambda base: 0.5
        self.assertEqual(svc.backoff_delay(1), 1.5)
        svc.jitter = lambda base: 0.0
        self.assertEqual(svc.backoff_delay(99), 60)  # 退避上限 60s


if __name__ == "__main__":
    unittest.main()
