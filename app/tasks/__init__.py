"""
PrismaMate 棱镜 - Celery 任务入口
"""

from app.celery_app import celery_app

# 导入任务模块
from app.tasks import detection  # noqa: F401
from app.tasks import cleanup    # noqa: F401
