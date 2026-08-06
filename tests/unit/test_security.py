"""
单元测试 — JWT 认证和密码哈希 (backend/core/security.py)
"""
import pytest
from backend.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)


class TestPasswordHashing:
    """密码哈希和验证"""

    def test_hash_returns_different_from_input(self, sample_password):
        """哈希值应该与明文密码不同"""
        hashed = hash_password(sample_password)
        assert hashed != sample_password

    def test_hash_is_stable_under_same_input(self, sample_password):
        """相同输入每次 hash 结果不同（bcrypt 加盐），但都能验证通过"""
        h1 = hash_password(sample_password)
        h2 = hash_password(sample_password)
        assert h1 != h2  # bcrypt 每次生成不同盐值
        assert verify_password(sample_password, h1)
        assert verify_password(sample_password, h2)

    def test_verify_correct_password(self, sample_password, hashed_password):
        """正确密码验证通过"""
        assert verify_password(sample_password, hashed_password) is True

    def test_verify_wrong_password(self, hashed_password):
        """错误密码验证失败"""
        assert verify_password("WrongPassword456!", hashed_password) is False

    def test_verify_empty_password(self, hashed_password):
        """空密码验证失败"""
        assert verify_password("", hashed_password) is False

    def test_hash_empty_string(self):
        """空字符串也可以哈希"""
        hashed = hash_password("")
        assert hashed
        assert verify_password("", hashed)


class TestJWTToken:
    """JWT Token 生成和解析"""

    def test_create_token_returns_string(self):
        """生成的 token 应该是非空字符串"""
        token = create_access_token(data={"sub": "user-1"})
        assert isinstance(token, str)
        assert len(token) > 0
        assert token.count(".") == 2  # JWT 格式: header.payload.signature

    def test_decode_valid_token_returns_payload(self):
        """有效 token 可以正常解码出原始数据"""
        token = create_access_token(data={"sub": "user-1", "username": "alice"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user-1"
        assert payload["username"] == "alice"

    def test_decode_token_has_expiry(self):
        """解码后的 token 含有过期时间"""
        token = create_access_token(data={"sub": "user-1"})
        payload = decode_access_token(token)
        assert "exp" in payload

    def test_decode_expired_token_returns_none(self, expired_token):
        """过期 token 解码返回 None"""
        payload = decode_access_token(expired_token)
        assert payload is None

    def test_decode_invalid_token_returns_none(self):
        """乱码 token 解码返回 None"""
        payload = decode_access_token("this-is-not-a-valid-jwt-token")
        assert payload is None

    def test_decode_empty_token_returns_none(self):
        """空字符串解码返回 None"""
        payload = decode_access_token("")
        assert payload is None

    def test_token_with_extra_claims(self):
        """Token 可以携带自定义的额外字段"""
        token = create_access_token(data={
            "sub": "user-2",
            "role": "moderator",
            "permissions": ["read", "write"],
        })
        payload = decode_access_token(token)
        assert payload["role"] == "moderator"
        assert "write" in payload["permissions"]
