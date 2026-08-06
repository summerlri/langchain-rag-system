"""
API 集成测试 — 知识库管理 (backend/api/knowledge_base.py)

知识库 CRUD 操作需要管理员权限。
"""
import pytest
from tests.conftest import make_auth_header


def _admin_token(test_admin):
    """为 admin fixture 生成有效 JWT token"""
    from backend.core.security import create_access_token
    return create_access_token(data={"sub": test_admin.id, "username": test_admin.username})


class TestListKnowledgeBases:
    """获取知识库列表"""

    def test_list_empty(self, client, test_admin):
        """初始无知识库时返回空列表"""
        token = _admin_token(test_admin)
        resp = client.get("/api/knowledge-bases", headers=make_auth_header(token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_with_kb(self, client, test_admin, test_kb):
        """有知识库时列表应包含它"""
        token = _admin_token(test_admin)
        resp = client.get("/api/knowledge-bases", headers=make_auth_header(token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        kb_names = [kb["name"] for kb in data]
        assert "测试知识库" in kb_names

    def test_list_requires_admin(self, client, test_user, valid_token):
        """非管理员无法获取知识库列表"""
        resp = client.get("/api/knowledge-bases", headers=make_auth_header(valid_token))
        assert resp.status_code == 403


class TestCreateKnowledgeBase:
    """创建知识库"""

    def test_create_success(self, client, test_admin):
        """管理员创建知识库成功"""
        token = _admin_token(test_admin)
        resp = client.post("/api/knowledge-bases", json={
            "name": "新产品库",
            "description": "产品信息",
        }, headers=make_auth_header(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "新产品库"
        assert data["doc_count"] == 0

    def test_create_empty_name(self, client, test_admin):
        """知识库名为空 -> 422"""
        token = _admin_token(test_admin)
        resp = client.post("/api/knowledge-bases", json={
            "name": "",
            "description": "测试",
        }, headers=make_auth_header(token))
        assert resp.status_code == 422

    def test_create_no_auth(self, client):
        """未登录 -> 401"""
        resp = client.post("/api/knowledge-bases", json={"name": "匿名库"})
        assert resp.status_code == 401 or resp.status_code == 403


class TestUpdateKnowledgeBase:
    """更新知识库"""

    def test_update_name(self, client, test_admin, test_kb):
        """更新知识库名称"""
        token = _admin_token(test_admin)
        resp = client.put(f"/api/knowledge-bases/{test_kb.id}", json={
            "name": "改名后的知识库",
        }, headers=make_auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "改名后的知识库"

    def test_update_nonexistent(self, client, test_admin):
        """更新不存在的知识库 -> 404"""
        token = _admin_token(test_admin)
        resp = client.put("/api/knowledge-bases/nonexistent-id", json={
            "name": "新名称",
        }, headers=make_auth_header(token))
        assert resp.status_code == 404


class TestDeleteKnowledgeBase:
    """删除知识库"""

    def test_delete_success(self, client, test_admin, test_kb):
        """删除已有知识库"""
        token = _admin_token(test_admin)
        resp = client.delete(
            f"/api/knowledge-bases/{test_kb.id}",
            headers=make_auth_header(token),
        )
        assert resp.status_code == 200
        assert "已删除" in resp.json()["message"]

    def test_delete_nonexistent(self, client, test_admin):
        """删除不存在的知识库 -> 404"""
        token = _admin_token(test_admin)
        resp = client.delete(
            "/api/knowledge-bases/ghost-kb-id",
            headers=make_auth_header(token),
        )
        assert resp.status_code == 404


class TestListDocuments:
    """获取文档列表"""

    def test_empty_documents(self, client, test_admin, test_kb):
        """初始无文档时返回空列表"""
        token = _admin_token(test_admin)
        resp = client.get(
            f"/api/knowledge-bases/{test_kb.id}/documents",
            headers=make_auth_header(token),
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) == 0
