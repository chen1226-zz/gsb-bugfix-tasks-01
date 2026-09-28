import os
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
