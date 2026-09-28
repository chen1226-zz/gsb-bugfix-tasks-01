"""append-only 键值存储：先写预写日志（WAL），启动时重放恢复索引。

对外接口（不得更改签名）：
    WALStore(path)
        .open()
        .put(key, value)
        .get(key) -> value | None
        .close()
        .keys() -> list

记录格式：key_len(<H) | key | value_len(<I) | value，均为 UTF-8。
"""

import os
import struct


class WALStore:
    def __init__(self, path):
        self.path = path
        self.wal_path = path + ".wal"
        self.index = {}
        self._fh = None

    def open(self):
        self._fh = open(self.wal_path, "ab")
        self._recover()

    def put(self, key, value):
        key_bytes = key.encode("utf-8")
        value_bytes = value.encode("utf-8")
        record = (
            struct.pack("<H", len(key_bytes))
            + key_bytes
            + struct.pack("<I", len(value_bytes))
            + value_bytes
        )
        self._fh.write(record)
        self.index[key] = value

    def get(self, key):
        return self.index.get(key)

    def keys(self):
        return list(self.index)

    def close(self):
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def _recover(self):
        if not os.path.exists(self.wal_path):
            return
        with open(self.wal_path, "rb") as fh:
            data = fh.read()
        pos = 0
        while pos + 2 <= len(data):
            (key_len,) = struct.unpack("<H", data[pos : pos + 2])
            pos += 2
            key = data[pos : pos + key_len].decode("utf-8", "ignore")
            pos += key_len
            if pos + 4 > len(data):
                break
            (value_len,) = struct.unpack("<I", data[pos : pos + 4])
            pos += 4
            value = data[pos : pos + value_len].decode("utf-8")
            pos += value_len
            self.index[key] = value
