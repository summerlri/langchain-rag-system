"""
单元测试 — RAG Prompt 组装 (backend/rag/chain.py)
"""
import pytest
from langchain_core.documents import Document
from backend.rag.chain import format_docs, create_rag_prompt, RAG_SYSTEM_PROMPT


class TestFormatDocs:
    """文档格式化功能"""

    def test_single_doc_format(self):
        """单个文档格式化后应包含编号和来源"""
        doc = Document(
            page_content="iPhone 15 Pro Max 售价 ¥9,999",
            metadata={"filename": "apple.txt"},
        )
        result = format_docs([doc])
        assert "[1]" in result
        assert "apple.txt" in result
        assert "iPhone 15 Pro Max" in result

    def test_multiple_docs_format(self):
        """多个文档格式化后应有不同编号"""
        docs = [
            Document(page_content="内容A", metadata={"filename": "a.txt"}),
            Document(page_content="内容B", metadata={"filename": "b.txt"}),
            Document(page_content="内容C", metadata={"filename": "c.txt"}),
        ]
        result = format_docs(docs)
        assert "[1]" in result
        assert "[2]" in result
        assert "[3]" in result
        assert "a.txt" in result
        assert "b.txt" in result
        assert "c.txt" in result

    def test_empty_docs(self):
        """空列表格式化结果为空字符串"""
        result = format_docs([])
        assert result == ""

    def test_doc_without_filename(self):
        """没有 filename 元数据的文档使用 '未知来源'"""
        doc = Document(page_content="某内容", metadata={})
        result = format_docs([doc])
        assert "未知来源" in result


class TestRAGPrompt:
    """RAG 提示词"""

    def test_prompt_has_required_placeholders(self):
        """提示词模板应包含必需的占位符"""
        assert "{context}" in RAG_SYSTEM_PROMPT
        assert "{question}" in RAG_SYSTEM_PROMPT

    def test_prompt_includes_reference_instruction(self):
        """提示词应包含引用来源的说明"""
        assert "[1]" in RAG_SYSTEM_PROMPT or "来源" in RAG_SYSTEM_PROMPT

    def test_create_rag_prompt_returns_valid_template(self):
        """create_rag_prompt() 返回有效的 ChatPromptTemplate"""
        prompt = create_rag_prompt()
        assert prompt is not None
        # 可以 format
        formatted = prompt.format(context="测试上下文", question="测试问题？")
        assert "测试上下文" in formatted
        assert "测试问题" in formatted


class TestRAGSystemPrompt:
    """RAG 系统提示词质量"""

    def test_prompt_not_empty(self):
        assert len(RAG_SYSTEM_PROMPT) > 100

    def test_prompt_mentions_knowledge_base(self):
        assert "知识库" in RAG_SYSTEM_PROMPT

    def test_prompt_has_fallback_instruction(self):
        """提示词应包含知识库没有答案时的兜底说明"""
        assert "暂未收录" in RAG_SYSTEM_PROMPT or "不包含" in RAG_SYSTEM_PROMPT
