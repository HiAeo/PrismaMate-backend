"""
PrismaMate 棱镜 - 报告 Schemas
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ReportCreate(BaseModel):
    """报告创建 Schema"""
    task_id: int


class ReportResponse(BaseModel):
    """报告响应 Schema"""
    id: int
    report_id: str
    task_id: int
    report_hash: str
    pdf_url: Optional[str] = None
    verification_code: str
    created_at: datetime
    blockchain_tx_id: Optional[str] = None
    blockchain_status: Optional[str] = None

    class Config:
        from_attributes = True


class ReportVerifyResponse(BaseModel):
    """报告验证响应 Schema"""
    is_valid: bool
    report_id: str
    brand_names: list
    keywords: list
    platforms: list
    detection_time: str
    report_hash: str
    message: str
