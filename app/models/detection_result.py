"""
PrismaMate 棱镜 - 检测结果模型
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class DetectionResult(Base):
    """检测结果表"""
    __tablename__ = "detection_results"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("detection_tasks.id"), nullable=False, index=True)
    
    # 平台信息
    platform = Column(String(50), nullable=False, index=True)
    keyword = Column(String(500), nullable=False)
    brand_name = Column(String(255), nullable=False)
    
    # 检测结果
    is_mentioned = Column(Boolean, default=False)
    mention_position = Column(Integer, nullable=True)  # 在回答中的位次，未提及则为 NULL
    context_snippet = Column(Text, nullable=True)     # 提及上下文
    
    # 引用来源列表
    citations = Column(JSONB, nullable=True)
    
    # 原始响应
    raw_response = Column(Text, nullable=True)
    raw_response_expires_at = Column(DateTime, nullable=True)  # 90天后过期
    
    # 检测模式：api 或 browser
    detection_mode = Column(String(20), nullable=True)
    
    # 时间戳
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)

    # 关系
    task = relationship("DetectionTask", back_populates="results")

    def __repr__(self):
        return f"<DetectionResult(id={self.id}, platform={self.platform}, is_mentioned={self.is_mentioned})>"
