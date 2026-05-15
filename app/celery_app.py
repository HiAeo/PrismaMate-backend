"""
PrismaMate 棱镜 - Celery 配置
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

# 创建 Celery 应用
celery_app = Celery(
    "prismamate",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend,
    include=["app.tasks.detection", "app.tasks.cleanup"]
)

# Celery 配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 分钟超时
    task_soft_time_limit=540,  # 9 分钟软超时
    worker_prefetch_multiplier=1,  # 同一平台任务串行执行
    worker_max_tasks_per_child=100,  # 每处理 100 个任务后重启 worker
)
