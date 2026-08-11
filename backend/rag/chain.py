"""
LangChain RAG Chain 组装 — Prompt 模板 + 文档格式化 + LLM 创建

RAG 的"Generation"环节: 把检索到的文档+用户问题，拼成 Prompt 发给 LLM 生成回答。

为什么用自定义 Prompt 而不是 LangChain 默认的?
  - 电商场景需要精确的产品信息(价格、规格、功能)，通用 Prompt 容易让 LLM 自由发挥
  - 我们的 Prompt 强调"仅使用知识库内容"、"标注来源"、"商品比较用表格"，这些都是电商领域的刚需

temperature=0.3 是怎么选的?
  - 0.0: 完全确定性输出，同样输入总是同样输出，但可能死板
  - 1.0: 高创造性，适合创意写作，但可能编造价格
  - 0.3: 在电商场景下最合适 —— 既保持回答的准确性和一致性(不会对同一产品报不同价格)，
    又保留一点灵活性让措辞可以变化(避免重复的机械回复)
"""
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_community.llms import Tongyi
import json
from backend.config import get_settings

settings = get_settings()

# ══════════════════════════════════════════════════════════════════════════════
# RAG 系统提示词 — 这是整个系统输出质量的核心，控制 LLM 的"说话方式"
# ══════════════════════════════════════════════════════════════════════════════
RAG_SYSTEM_PROMPT = """你是一个专业的电商商品知识库问答助手。请根据以下知识库内容回答用户的问题。

## 回答规则：
1. **仅使用提供的知识库内容**来回答问题，不要编造知识库中没有的信息
2. 如果知识库中不包含相关信息，请明确告知用户："抱歉，知识库中暂未收录相关信息"
3. 回答时请引用知识库片段，使用 [1]、[2] 等标记标注来源编号
4. 回答要条理清晰、准确专业，给出商品的具体信息（如价格、参数、功能等）
5. 如果涉及多个商品比较，请使用表格形式清晰展示
6. 回答结尾列出参考的知识库来源

## 知识库内容：
{context}

## 最近对话：
{history}

## 用户问题：
{question}

## 回答："""


QUERY_REWRITE_PROMPT = """你负责把多轮对话中的最新问题改写成可独立检索知识库的问题。

要求：
1. 补全“它、这个、上一款”等指代，但不要添加对话中不存在的信息
2. 保留商品型号、价格、日期、规格等关键词
3. 如果最新问题已经完整，原样返回
4. 只输出改写后的问题，不要解释

最近对话：
{history}

最新问题：{question}

改写后的问题："""


def format_docs(docs: list) -> str:
    """
    将检索到的 Document 列表格式化为带编号的纯文本上下文字符串。

    为什么要格式化?
      LLM 的输入是纯文本，不能直接接收 LangChain Document 对象。
      需要把 Document.page_content 和 metadata.filename 转成结构化的文本。

    输出格式示例:
      [1] 来源: apple_products.txt
      iPhone 15 Pro Max 采用钛金属设计，售价 ¥9,999 起。

      ---

      [2] 来源: huawei_products.txt
      华为 Mate 60 Pro 支持卫星通话，售价 ¥6,999 起。

    为什么用 --- 分隔?
      告诉 LLM 这些是"不同的来源文档"，帮助它在回答中区分引用。
    """
    formatted = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("filename", "未知来源")
        content = doc.page_content.strip()
        formatted.append(f"[{i}] 来源: {source}\n{content}")
    return "\n\n---\n\n".join(formatted)


def format_history(history: list[dict], limit: int = 8) -> str:
    """把最近对话压缩成适合问题改写和回答生成的文本。"""
    if not history:
        return "（无历史对话）"
    role_names = {"user": "用户", "assistant": "助手"}
    lines = []
    for message in history[-limit:]:
        role = role_names.get(message.get("role"), message.get("role", "消息"))
        content = str(message.get("content", "")).strip()
        if content:
            lines.append(f"{role}：{content[:1000]}")
    return "\n".join(lines) or "（无历史对话）"


def create_rag_prompt() -> ChatPromptTemplate:
    """
    创建 RAG 提示词模板。

    为什么用 ChatPromptTemplate 而不是 string concatenation?
      - 类型安全: LLM 需要 system 和 human 的角色区分，ChatPromptTemplate 自动处理
      - 复用: 创建一次，全局用，修改时只需要改 RAG_SYSTEM_PROMPT 字符串
    """
    return ChatPromptTemplate.from_messages([
        ("system", RAG_SYSTEM_PROMPT),
    ])


def get_llm():
    """
    获取百炼 Qwen LLM 实例，启用流式输出。

    每次调用都会创建新的 Tongyi 实例。这不是 bug —— 因为 LLM 是无状态的，
    创建多个实例之间唯一的区别是 HTTP 连接。从 LangChain 0.1+ 开始，Tongyi
    类的内部 HTTP 连接被 urllib3 连接池管理，多个实例开销很小。

    为什么 streaming=True?
      这是 SSE 流式回答的前提: LLM 每次只生成一个 token，pipeline.py
      逐 token yield，前端逐字渲染。如果 streaming=False，LLM 会等全部
      生成完才返回，用户体验会变成"等 10 秒突然全部出现"。
    """
    from langchain_community.llms import Tongyi
    return Tongyi(
        model=settings.qwen_model,
        dashscope_api_key=settings.dashscope_api_key,
        streaming=True,
        temperature=0.3,  # 低温度 → 高确定性 → 适合电商产品信息的准确性要求
    )
