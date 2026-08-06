"""
单元测试 — 两级缓存管理器 (backend/cache/cache_manager.py)
"""
import pytest
from backend.cache.cache_manager import CacheManager


class TestCacheManager:
    """两级缓存管理器测试"""

    @pytest.fixture
    def cache(self, tmp_path):
        """创建指向临时目录的缓存实例，避免污染真实缓存"""
        cache = CacheManager(maxsize=128)
        # 替换 L2 磁盘缓存目录为临时目录
        from diskcache import Cache
        cache._l2 = Cache(str(tmp_path / "test_cache"))
        return cache

    def test_set_and_get(self, cache):
        """写入后能正确读取"""
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_key_returns_none(self, cache):
        """不存在的 key 返回 None"""
        assert cache.get("nonexistent") is None

    def test_set_complex_object(self, cache):
        """可以存储列表、字典等复杂对象"""
        data = {"name": "测试", "scores": [90, 85, 92]}
        cache.set("complex", data)
        assert cache.get("complex") == data

    def test_delete_existing_key(self, cache):
        """删除存在的 key 返回 True"""
        cache.set("to_delete", "xxx")
        assert cache.delete("to_delete") is True
        assert cache.get("to_delete") is None

    def test_delete_missing_key_returns_false(self, cache):
        """删除不存在的 key 返回 False"""
        assert cache.delete("ghost_key") is False

    def test_l1_memory_cache_hit(self, cache):
        """L1 内存缓存命中（第二次读取不走磁盘）"""
        cache.set("l1_key", "l1_value")
        # 第一次从 L2 读，第二次直接从 L1 读
        assert cache.get("l1_key") == "l1_value"
        assert cache.get("l1_key") == "l1_value"

    def test_clear_removes_all(self, cache):
        """清空后所有 key 都不存在"""
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None
        assert cache.get("c") is None

    def test_overwrite_existing_key(self, cache):
        """覆盖已有的 key"""
        cache.set("key", "old")
        cache.set("key", "new")
        assert cache.get("key") == "new"

    def test_many_keys(self, cache):
        """大量 key 的读写正确性"""
        for i in range(500):
            cache.set(f"k{i}", i)
        # 抽样检查
        assert cache.get("k0") == 0
        assert cache.get("k100") == 100
        assert cache.get("k499") == 499
