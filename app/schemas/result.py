"""
PrismaMate 棱镜 - 检测结果 Schemas
"""

from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel


class CitationSchema(BaseModel):
    """引用来源 Schema"""
    url: str
    source_domain: str
    anchor_text: Optional[str] = None
    position_in_response: int = 0


class ResultResponse(BaseModel):
    """检测结果响应 Schema"""
    id: int
    task_id: int
    platform: str
    keyword: str
    brand_name: str
    is_mentioned: bool
    mention_position: Optional[int] = None
    context_snippet: Optional[str] = None
    citations: Optional[List[CitationSchema]] = None
    detected_at: datetime
    detection_mode: Optional[str] = None

    class Config:
        from_attributes = True


class ResultListResponse(BaseModel):
    """检测结果列表响应 Schema"""
    total: int
    results: List[ResultResponse]
