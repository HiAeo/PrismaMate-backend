"""
PrismaMate 棱镜 - 平台事件模型
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey

from app.core.database import Base


class PlatformCooldownEvent(Base):
    """平台冷却事件表"""
    __tablename__ = "platform_cooldown_events"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50), nullable=False, index=True)
    reason = Column(String(255), nullable=True)  # 触发冷却的原因
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    recovered_successfully = Column(Boolean, default=False)

    def __repr__(self):
        return f"<PlatformCooldownEvent(platform={self.platform}, started_at={self.started_at})>"


class PlatformSmokeTest(Base):
    """冒烟测试记录表"""
    __tablename__ = "platform_smoke_tests"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50), nullable=False, index=True)
    test_keyword = Column(String(255), nullable=False)  # 测试用的固定关键词
    status = Column(String(20), nullable=False)  # success/failed
    response_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    tested_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<PlatformSmokeTest(platform={self.platform}, status={self.status})>"


class CaptchaEvent(Base):
    """验证码事件表"""
    __tablename__ = "captcha_events"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("detection_tasks.id"), nullable=True, index=True)
    platform = Column(String(50), nullable=False, index=True)
    occurred_at = Column(DateTime, default=datetime.utcnow)
    handled_status = Column(String(20), default="paused")

    def __repr__(self):
        return f"<CaptchaEvent(platform={self.platform}, occurred_at={self.occurred_at})>"


class DataCleanupLog(Base):
    """数据清理任务记录表"""
    __tablename__ = "data_cleanup_logs"

    id = Column(Integer, primary_key=True, index=True)
    cleanup_type = Column(String(50), nullable=False)  # 例如: "raw_response_cleanup"
    records_deleted = Column(Integer, default=0)
    executed_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="success")  # success/failed

    def __repr__(self):
        return f"<DataCleanupLog(type={self.cleanup_type}, status={self.status})>"
