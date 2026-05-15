"""
PrismaMate 棱镜 - 数据清理任务
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import update

from app.celery_app import celery_app
from app.core.database import get_sync_db
from app.models.detection_result import DetectionResult
from app.models.platform_event import DataCleanupLog

logger = logging.getLogger(__name__)


@celery_app.task
def cleanup_expired_raw_responses():
    """清理过期的 raw_response 数据"""
    db = next(get_sync_db())
    try:
        # 清理 90 天前的 raw_response
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        
        # 查询过期记录数
        expired_count = db.query(DetectionResult).filter(
            DetectionResult.raw_response_expires_at < datetime.utcnow(),
            DetectionResult.raw_response.isnot(None)
        ).count()
        
        # 执行清理
        stmt = (
            update(DetectionResult)
            .where(
                DetectionResult.raw_response_expires_at < datetime.utcnow(),
                DetectionResult.raw_response.isnot(None)
            )
            .values(raw_response=None, raw_response_expires_at=None)
        )
        result = db.execute(stmt)
        db.commit()
        
        # 记录清理日志
        log = DataCleanupLog(
            cleanup_type="raw_response_cleanup",
            records_deleted=expired_count,
            status="success"
        )
        db.add(log)
        db.commit()
        
        logger.info(f"Cleaned up {expired_count} expired raw_response records")
        return {"deleted": expired_count}
        
    except Exception as exc:
        logger.error(f"Cleanup failed: {exc}")
        
        # 记录失败日志
        log = DataCleanupLog(
            cleanup_type="raw_response_cleanup",
            records_deleted=0,
            status="failed"
        )
        db.add(log)
        db.commit()
        
        raise
    finally:
        db.close()


@celery_app.task
def cleanup_old_cooldown_events():
    """清理旧的冷却事件记录（保留 30 天）"""
    db = next(get_sync_db())
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        from app.models.platform_event import PlatformCooldownEvent
        deleted_count = db.query(PlatformCooldownEvent).filter(
            PlatformCooldownEvent.started_at < cutoff_date,
            PlatformCooldownEvent.ended_at.isnot(None)
        ).delete()
        db.commit()
        
        logger.info(f"Cleaned up {deleted_count} old cooldown events")
        return {"deleted": deleted_count}
        
    except Exception as exc:
        logger.error(f"Cleanup failed: {exc}")
        raise
    finally:
        db.close()
