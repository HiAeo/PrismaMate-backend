"""
PrismaMate 棱镜 - 检测任务模型
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, JSON, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class TaskType(str, Enum):
    """任务类型枚举"""
    SINGLE = "single"       # 单次检测
    RECURRING = "recurring"  # 周期性检测


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"           # 等待调度
    RUNNING = "running"           # 正在调度
    COLLECTING = "collecting"     # 采集中
    PARSING = "parsing"           # 解析中
    GENERATING = "generating"     # 报告生成中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    RETRYING = "retrying"         # 重试中
    PAUSED = "paused"             # 暂停（等待平台恢复）


class DetectionTask(Base):
    """检测任务表"""
    __tablename__ = "detection_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    task_type = Column(SQLEnum(TaskType), default=TaskType.SINGLE, nullable=False)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING, nullable=False, index=True)
    
    # 品牌信息（JSONB）：[{"full_name": "华为", "short_names": ["华为", "Huawei"]}]
    brands = Column(JSONB, nullable=False)
    
    # 关键词列表
    keywords = Column(ARRAY(String), nullable=False)
    
    # 平台列表：["deepseek", "doubao", "kimi"]
    platforms = Column(ARRAY(String), nullable=False)
    
    # 竞品信息（JSONB）
    competitors = Column(JSONB, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # 关系
    user = relationship("User", back_populates="tasks")
    results = relationship("DetectionResult", back_populates="task", cascade="all, delete-orphan")
    report = relationship("Report", back_populates="task", uselist=False)

    def __repr__(self):
        return f"<DetectionTask(id={self.id}, status={self.status}, user_id={self.user_id})>"
