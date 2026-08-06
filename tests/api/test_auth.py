"""
API 集成测试 — 认证 (backend/api/auth.py)

使用 FastAPI TestClient + 内存 SQLite 数据库，无需启动真实服务器。
"""
import pytest
from tests.conftest import make_auth_header


class TestRegister:
    """用户注册"""

    def test_register_success(self, client, test_user):
        """正常注册应返回 token（test_user 确保 db_session 正确初始化）"""
        resp = client.post("/api/auth/register", json={
            "username": "newuser",
            "password": "pass123456",
            "email": "new@test.com",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["username"] == "newuser"
        assert data["is_admin"] is False

    def test_register_duplicate_username(self, client, test_user):
        """重复用户名注册应失败"""
        resp = client.post("/api/auth/register", json={
            "username": "testuser",  # test_user fixture 已存在
            "password": "anotherpassword123",
        })
        assert resp.status_code == 400
        assert "已存在" in resp.json()["detail"]

    def test_register_short_password(self, client):
        """密码太短应返回 422 校验错误"""
        resp = client.post("/api/auth/register", json={
            "username": "someone",
            "password": "12345",  # < 6
        })
        assert resp.status_code == 422

    def test_register_short_username(self, client):
        """用户名太短应返回 422"""
        resp = client.post("/api/auth/register", json={
            "username": "x",  # < 2
            "password": "validpass123",
        })
        assert resp.status_code == 422


class TestLogin:
    """用户登录"""

    def test_login_success(self, client, test_user):
        """正确密码登录成功"""
        resp = client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "TestPass123!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, test_user):
        """错误密码登录失败"""
        resp = client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "WrongPassword999!",
        })
        assert resp.status_code == 400
        assert "密码" in resp.json()["detail"] or "错误" in resp.json()["detail"]

    def test_login_nonexistent_user(self, client):
        """不存在的用户登录失败"""
        resp = client.post("/api/auth/login", json={
            "username": "ghost_user_404",
            "password": "whatever123456",
        })
        assert resp.status_code == 400

    def test_login_with_email_username(self, client, test_user):
        """仅支持用户名登录（email 字段在 login 中被忽略因为 schema 名为 username）"""
        resp = client.post("/api/auth/login", json={
            "username": "testuser",  # 只能用 username
            "password": "TestPass123!",
        })
        assert resp.status_code == 200


class TestGetMe:
    """获取当前用户信息"""

    def test_get_me_success(self, client, test_user, valid_token):
        """有效 token 可获取用户信息"""
        resp = client.get("/api/auth/me", headers=make_auth_header(valid_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser"

    def test_get_me_no_token(self, client):
        """无 token 返回 401"""
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_get_me_invalid_token(self, client):
        """无效 token 返回 401"""
        resp = client.get("/api/auth/me", headers=make_auth_header("garbage.token.here"))
        assert resp.status_code == 401


class TestChangePassword:
    """修改密码"""

    def test_change_password_success(self, client, test_user, valid_token):
        """正确的旧密码 + 合法新密码 -> 修改成功"""
        resp = client.put("/api/auth/password", json={
            "old_password": "TestPass123!",
            "new_password": "NewSecure456!",
        }, headers=make_auth_header(valid_token))
        assert resp.status_code == 200
        assert "成功" in resp.json()["message"]

    def test_change_password_wrong_old(self, client, test_user, valid_token):
        """旧密码错误 -> 修改失败"""
        resp = client.put("/api/auth/password", json={
            "old_password": "WrongOldPassword!",
            "new_password": "NewSecure456!",
        }, headers=make_auth_header(valid_token))
        assert resp.status_code == 400
        assert "原密码" in resp.json()["detail"]

    def test_change_password_no_auth(self, client):
        """未登录修改密码 -> 401"""
        resp = client.put("/api/auth/password", json={
            "old_password": "anything",
            "new_password": "anything123",
        })
        assert resp.status_code == 401
