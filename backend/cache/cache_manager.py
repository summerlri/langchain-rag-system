"""
多级缓存管理：L1 内存 LRU → L2 diskcache 磁盘缓存
"""
import hashlib
import json
from typing import Optional, Any
from cachetools import LRUCache
from diskcache import Cache
from backend.config import get_settings

settings = get_settings()


class CacheManager:
    """两级缓存管理器"""

    def __init__(self, maxsize: int = 1024):
        self._l1 = LRUCache(maxsize=maxsize)  # 内存缓存
        self._l2 = Cache(settings.cache_dir)   # 磁盘缓存

    def _hash_key(self, key: str) -> str:
        return hashlib.md5(key.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        hashed = self._hash_key(key)
        # L1 内存
        if hashed in self._l1:
            return self._l1[hashed]
        # L2 磁盘
        value = self._l2.get(hashed)
        if value is not None:
            # 回填 L1
            self._l1[hashed] = value
            return value
        return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        hashed = self._hash_key(key)
        self._l1[hashed] = value
        self._l2.set(hashed, value, expire=ttl)

    def delete(self, key: str) -> bool:
        hashed = self._hash_key(key)
        del_l1 = self._l1.pop(hashed, None) is not None
        del_l2 = self._l2.delete(hashed)
        return del_l1 or del_l2

    def clear(self) -> None:
        self._l1.clear()
        self._l2.clear()


# 全局单例
cache_manager = CacheManager(maxsize=2048)
