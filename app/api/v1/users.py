"""
PrismaMate 棱镜 - 用户 API 路由

提供用户信息、用量统计等功能
"""

from fastapi import APIRouter, Depends

from app.api.v1.auth import get_current_user
from app.core.user_store import user_store

router = APIRouter()


# ==================== 响应模型 ====================

class ProfileResponse:
    """用户信息响应"""
    def __init__(self, user: dict):
        self.user_id = user.user_id
        self.email = user.email
        self.username = user.username
        self.created_at = user.created_at.isoformat()


class UsageResponse:
    """用量统计响应"""
    def __init__(self, stats: dict):
        self.total_tasks = stats["total_tasks"]
        self.completed_tasks = stats["completed_tasks"]
        self.total_reports = stats["total_reports"]
        self.total_mentions = stats["total_mentions"]
        self.total_detections = stats["total_detections"]


# ==================== API 端点 ====================

@router.get("/profile")
async def get_profile(current_user: dict = Depends(get_current_user)):
    """
    获取当前用户信息
    
    需要认证
    """
    return ProfileResponse(current_user)


@router.get("/usage")
async def get_usage(current_user: dict = Depends(get_current_user)):
    """
    获取用户用量统计
    
    需要认证
    
    返回：
    - total_tasks: 总任务数
    - completed_tasks: 已完成任务数
    - total_reports: 总报告数
    - total_mentions: 总品牌提及数
    - total_detections: 总检测次数
    """
    stats = user_store.get_user_stats(current_user.user_id)
    return UsageResponse(stats)
