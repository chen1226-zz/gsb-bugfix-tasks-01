"""把 key 路由到固定分片。

对外接口（不得更改签名）：
    normalize_key(key) -> bytes
    hash_key(key) -> int
    shard_of(key, shards) -> str

`shards` 是分片名字列表，例如 ["shard-00", ..., "shard-15"]。
"""


def normalize_key(key):
    """把 key 统一成字节串。"""
    if isinstance(key, bytes):
        return key
    return str(key).encode("utf-8")


def hash_key(key):
    """返回 key 的哈希值。"""
    return hash(key)


def shard_of(key, shards):
    """返回 key 所属的分片名。"""
    if not shards:
        raise ValueError("shards 不能为空")
    return shards[hash_key(key) % len(shards)]
