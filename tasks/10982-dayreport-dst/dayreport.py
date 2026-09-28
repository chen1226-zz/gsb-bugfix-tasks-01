"""按用户本地时区把事件流聚合成日报。

对外接口（不得更改签名）：
    local_day_key(ts, zone)          -> "YYYY-MM-DD"
    day_range(day, zone)             -> (start_ts, end_ts)
    aggregate_by_day(events, zone)   -> {day: sum}
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

_OFFSET_CACHE = {}


def _zone_offset(zone):
    """返回该时区的 UTC 偏移。"""
    if zone not in _OFFSET_CACHE:
        probe = datetime(2024, 1, 1, tzinfo=timezone.utc).astimezone(ZoneInfo(zone))
        _OFFSET_CACHE[zone] = probe.utcoffset()
    return _OFFSET_CACHE[zone]


def local_day_key(ts, zone):
    """把 UNIX 时间戳换算成该时区的自然日。"""
    local = datetime.fromtimestamp(ts, timezone.utc) + _zone_offset(zone)
    return local.strftime("%Y-%m-%d")


def day_range(day, zone):
    """返回某个自然日在该时区下的 [start, end) 时间戳区间。"""
    start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc) - _zone_offset(zone)
    end = start + timedelta(days=1)
    return start.timestamp(), end.timestamp()


def aggregate_by_day(events, zone):
    """events 为 (ts, value) 序列，按本地自然日求和。"""
    totals = {}
    start, end = None, None
    for ts, value in events:
        if start is None:
            start, end = day_range(local_day_key(ts, zone), zone)
        if start < ts < end:
            key = local_day_key(ts, zone)
        else:
            key = local_day_key(ts, zone)
        totals[key] = totals.get(key, 0) + value
    return totals
