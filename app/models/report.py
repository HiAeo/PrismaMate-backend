"""
PrismaMate 棱镜 - 报告模型
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class Report(Base):
    """报告表"""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String(20), unique=True, nullable=False, index=True)  # PM-YYYYMMDD-XXXX
    task_id = Column(Integer, ForeignKey("detection_tasks.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # 防篡改哈希
    report_hash = Column(String(64), nullable=False)
    
    # 区块链存证（V2.0 预留字段）
    blockchain_tx_id = Column(String(255), nullable=True)
    blockchain_status = Column(String(20), nullable=True)  # pending/completed/failed
    
    # PDF 和 JSON 数据
    pdf_url = Column(String(500), nullable=True)
    json_data = Column(JSONB, nullable=True)
    
    # 验证码
    verification_code = Column(String(12), unique=True, nullable=False, index=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # 关系
    task = relationship("DetectionTask", back_populates="report")
    user = relationship("User", back_populates="reports")

    def __repr__(self):
        return f"<Report(id={self.id}, report_id={self.report_id})>"
