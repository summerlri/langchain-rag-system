"""
文本分割器 — 中文友好的文本分块策略
"""
from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def get_text_splitter(chunk_size: int = 500, chunk_overlap: int = 50) -> RecursiveCharacterTextSplitter:
    """获取中文友好的文本分割器"""
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=[
            "\n\n",    # 段落
            "\n",      # 换行
            "。",      # 中文句号
            "；",      # 中文分号
            "，",      # 中文逗号
            ".",       # 英文句号
            ";",       # 英文分号
            ",",       # 英文逗号
            " ",       # 空格
            "",        # 字符级回退
        ],
        length_function=len,
        is_separator_regex=False,
    )


def split_documents(documents: List[Document], chunk_size: int = 500, chunk_overlap: int = 50) -> List[Document]:
    """将文档列表分割为小块"""
    splitter = get_text_splitter(chunk_size, chunk_overlap)
    chunks = splitter.split_documents(documents)

    # 为每个 chunk 添加索引
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i

    return chunks
