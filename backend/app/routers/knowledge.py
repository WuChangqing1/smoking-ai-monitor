"""知识库查询接口。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import KnowledgeEventOut
from app.services.knowledge import get_knowledge_base

router = APIRouter(prefix="/api", tags=["knowledge"])


@router.get("/knowledge", response_model=list[KnowledgeEventOut], summary="知识库事件列表")
def list_knowledge(
    keyword: str | None = Query(None, description="全文关键词过滤"),
    event_type: str | None = Query(None, description="异常类型过滤"),
    limit: int = Query(50, ge=1, le=200),
) -> list[KnowledgeEventOut]:
    """历史异常处理经验库。数据来自 SQLite，种子记录按真实生产记录格式撰写。"""
    rows = get_knowledge_base().list_events(
        keyword=keyword, event_type=event_type, limit=limit
    )
    return [KnowledgeEventOut(**row) for row in rows]


@router.get("/knowledge/types", response_model=list[str], summary="知识库异常类型")
def knowledge_types() -> list[str]:
    return get_knowledge_base().event_types()


@router.get(
    "/knowledge/{event_code}",
    response_model=KnowledgeEventOut,
    summary="知识库事件详情",
)
def knowledge_detail(event_code: str) -> KnowledgeEventOut:
    row = get_knowledge_base().get(event_code)
    if row is None:
        raise HTTPException(status_code=404, detail=f"未找到知识库事件：{event_code}")
    return KnowledgeEventOut(**row)
