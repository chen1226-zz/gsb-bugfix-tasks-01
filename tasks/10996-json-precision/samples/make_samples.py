"""生成 50 条订单样例，写入 samples/samples.jsonl。

样例刻意使用了 18–19 位订单号、多位小数金额以及带末尾 0 的金额写法。
本文件是数据生成器，不属于需要修复的范围。
"""

import json
import os
import random

ORDER_IDS = [
    "1234567890123456789",
    "9007199254740993",          # 2**53 + 1，双精度无法表示
    "9223372036854775807",
    "-9007199254740993",
    "42",
    "1000000000000000001",
]
AMOUNTS = [
    "1234.560", "1234.56", "0.10", "100.00", "99999999.999",
    "0.0001", "12.345678", "7", "0", "1234567.89",
]
CURRENCIES = ["CNY", "USD", "EUR", "JPY", "HKD"]
ITEMS = [
    ["sku-1", "sku-2"],
    ["sku-9"],
    [],
    ["sku-3", "sku-4", "sku-5"],
]


def main():
    rnd = random.Random(20260928)
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "samples.jsonl")
    lines = []
    for i in range(50):
        order_id = ORDER_IDS[i % len(ORDER_IDS)]
        amount = AMOUNTS[i % len(AMOUNTS)]
        currency = CURRENCIES[i % len(CURRENCIES)]
        items = ITEMS[i % len(ITEMS)]
        body = (
            '{"amount":' + amount
            + ',"currency":"' + currency + '"'
            + ',"items":' + json.dumps(items, separators=(",", ":"))
            + ',"order_id":' + order_id
            + ',"seq":' + str(rnd.randrange(1, 10 ** 6))
            + "}"
        )
        lines.append(body)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} samples -> {out}")


if __name__ == "__main__":
    main()
