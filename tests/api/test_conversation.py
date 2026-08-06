"""
API 集成测试 — 会话管理 (backend/api/conversation.py)
"""
import pytest
from tests.conftest import make_auth_header


class TestListConversations:
    """获取会话列表"""

    def test_list_empty(self, client, test_user, valid_token):
        """初始无会话时返回空列表"""
        resp = client.get("/api/conversations", headers=make_auth_header(valid_token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_with_conversation(self, client, test_user, valid_token, test_conversation):
        """有会话时列表应包含它"""
        resp = client.get("/api/conversations", headers=make_auth_header(valid_token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["title"] == "测试会话"

    def test_list_no_auth(self, client):
        """未登录 -> 401"""
        resp = client.get("/api/conversations")
        assert resp.status_code == 401


class TestCreateConversation:
    """创建会话"""

    def test_create_success(self, client, test_user, valid_token, test_kb):
        """创建新会话"""
        resp = client.post("/api/conversations", json={
            "title": "我的对话",
            "kb_id": test_kb.id,
        }, headers=make_auth_header(valid_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "我的对话"
        assert data["kb_id"] == test_kb.id
        assert data["message_count"] == 0

    def test_create_default_title(self, client, test_user, valid_token):
        """不传标题时使用默认标题"""
        resp = client.post("/api/conversations", json={}, headers=make_auth_header(valid_token))
        assert resp.status_code == 200
        assert resp.json()["title"] == "新对话"


class TestUpdateConversation:
    """更新会话标题"""

    def test_update_title(self, client, test_user, valid_token, test_conversation):
        """修改会话标题成功"""
        resp = client.put(
            f"/api/conversations/{test_conversation.id}",
            json={"title": "新标题"},
            headers=make_auth_header(valid_token),
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "新标题"

    def test_update_nonexistent(self, client, test_user, valid_token):
        """修改不存在的会话 -> 404"""
        resp = client.put(
            "/api/conversations/fake-id-999",
            json={"title": "新标题"},
            headers=make_auth_header(valid_token),
        )
        assert resp.status_code == 404

    def test_update_other_users_conversation(self, client, test_user, valid_token):
        """不能修改别人的会话"""
        # 创建一个不属于 test_user 的会话 ID
        resp = client.put(
            "/api/conversations/someone-elses-conv-id",
            json={"title": "篡改"},
            headers=make_auth_header(valid_token),
        )
        assert resp.status_code == 404  # 对当前用户来说不存在


class TestDeleteConversation:
    """删除会话"""

    def test_delete_success(self, client, test_user, valid_token, test_conversation):
        """删除自己的会话"""
        resp = client.delete(
            f"/api/conversations/{test_conversation.id}",
            headers=make_auth_header(valid_token),
        )
        assert resp.status_code == 200
        assert "已删除" in resp.json()["message"]

    def test_delete_nonexistent(self, client, test_user, valid_token):
        """删除不存在的会话 -> 404"""
        resp = client.delete(
            "/api/conversations/ghost-conv-000",
            headers=make_auth_header(valid_token),
        )
        assert resp.status_code == 404
