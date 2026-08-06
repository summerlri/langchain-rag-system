"""
知识库相关 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import Optional


class KBCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="知识库名称")
    description: str = Field(default="", max_length=500, description="知识库描述")


class KBUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class KBResponse(BaseModel):
    id: str
    name: str
    description: str = ""
    owner_id: str
    doc_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class DocumentResponse(BaseModel):
    id: str
    kb_id: str
    filename: str
    file_type: str = ""
    file_size: int = 0
    status: str
    chunk_count: int = 0
    error_message: str | None = None
    uploaded_at: str | None = None
    processed_at: str | None = None
