import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import dayreport


def ts_of(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


class TestLocalDayKey(unittest.TestCase):
    def test_utc_day_key_for_shanghai(self):
        """既有断言：东八区无夏令时，换算必须正确。"""
        self.assertEqual(dayreport.local_day_key(ts_of("2024-06-01T16:00:00Z"), "Asia/Shanghai"), "2024-06-02")
        self.assertEqual(dayreport.local_day_key(ts_of("2024-06-01T15:59:59Z"), "Asia/Shanghai"), "2024-06-01")

    def test_utc_offset_zone_without_dst(self):
        """既有断言：45 分钟偏移的时区。"""
        self.assertEqual(dayreport.local_day_key(ts_of("2024-06-01T18:15:00Z"), "Asia/Kathmandu"), "2024-06-02")


class TestDayRange(unittest.TestCase):
    def test_range_covers_twenty_four_hours_in_utc_zone(self):
        """既有断言：UTC 时区的一天是 24 小时。"""
        start, end = dayreport.day_range("2024-06-01", "UTC")
        self.assertAlmostEqual(end - start, 86400, places=6)
        self.assertEqual(start, ts_of("2024-06-01T00:00:00Z"))


if __name__ == "__main__":
    unittest.main()
