"""
PrismaMate 棱镜 - 任务 Schemas
"""

from datetime import datetime
from typing import List, Optional, Any

from pydantic import BaseModel


class BrandInfo(BaseModel):
    """品牌信息 Schema"""
    full_name: str
    short_names: List[str] = []


class TaskCreate(BaseModel):
    """任务创建 Schema"""
    brands: List[BrandInfo]
    keywords: List[str]
    platforms: List[str]
    competitors: Optional[List[BrandInfo]] = None
    task_type: str = "single"


class TaskResponse(BaseModel):
    """任务响应 Schema"""
    id: int
    task_type: str
    status: str
    brands: List[dict]
    keywords: List[str]
    platforms: List[str]
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TaskStatusResponse(BaseModel):
    """任务状态响应 Schema"""
    task_id: int
    status: str
    progress: float = 0.0  # 0.0 - 1.0
    message: Optional[str] = None
    results_count: Optional[int] = None
    errors: List[str] = []
