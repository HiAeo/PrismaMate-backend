"""
PrismaMate 棱镜 - 管理接口

提供平台冷却状态和冒烟测试结果的管理接口：
- GET /api/v1/admin/platforms - 返回各平台冷却状态
- GET /api/v1/admin/smoke-tests - 返回历史测试记录
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["管理"])


def _get_cooldown_manager():
    """获取冷却管理器（延迟加载）"""
    try:
        from app.core.cooldown import get_cooldown_manager
        return get_cooldown_manager()
    except ImportError:
        return None


def _get_smoke_test_service():
    """获取冒烟测试服务（延迟加载）"""
    try:
        from app.services.smoke_test import get_smoke_test_service
        return get_smoke_test_service()
    except ImportError:
        return None


@router.get("/platforms")
async def get_platforms_status():
    """
    获取所有平台的冷却状态
    
    Returns:
        - in_cooldown: 是否处于冷却期
        - cooldown_remaining: 剩余冷却时间（秒）
        - consecutive_failures: 连续失败次数
        - paused_tasks: 暂停的任务列表
    """
    cooldown_manager = _get_cooldown_manager()
    
    if cooldown_manager is None:
        return {
            "status": "error",
            "message": "冷却期管理器不可用"
        }
    
    try:
        platforms_status = cooldown_manager.get_all_platforms_status()
        events = cooldown_manager.get_cooldown_events(limit=20)
        
        return {
            "status": "ok",
            "platforms": platforms_status,
            "recent_events": events
        }
    except Exception as e:
        logger.error(f"获取平台状态失败: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/platforms/{platform}")
async def get_platform_status(platform: str):
    """
    获取指定平台的冷却状态
    """
    cooldown_manager = _get_cooldown_manager()
    
    if cooldown_manager is None:
        return {
            "status": "error",
            "message": "冷却期管理器不可用"
        }
    
    try:
        status = cooldown_manager.get_platform_status(platform)
        return {
            "status": "ok",
            **status
        }
    except Exception as e:
        logger.error(f"获取平台 {platform} 状态失败: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/platforms/{platform}/uncooldown")
async def force_uncooldown_platform(platform: str):
    """
    强制解除平台冷却（管理操作）
    """
    cooldown_manager = _get_cooldown_manager()
    
    if cooldown_manager is None:
        return {
            "status": "error",
            "message": "冷却期管理器不可用"
        }
    
    try:
        # 直接移除冷却状态
        cooldown_manager._cooldown_platforms.pop(platform.lower(), None)
        cooldown_manager._failure_counts[platform.lower()] = 0
        
        return {
            "status": "ok",
            "message": f"平台 {platform} 已解除冷却"
        }
    except Exception as e:
        logger.error(f"解除平台 {platform} 冷却失败: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/smoke-tests")
async def get_smoke_tests(
    platform: Optional[str] = Query(None, description="平台名称（可选）"),
    limit: int = Query(10, ge=1, le=100, description="返回记录数")
):
    """
    获取冒烟测试历史记录
    
    Args:
        platform: 平台名称（可选），为 None 则返回所有平台
        limit: 返回记录数，默认 10
    """
    smoke_test_service = _get_smoke_test_service()
    
    if smoke_test_service is None:
        return {
            "status": "error",
            "message": "冒烟测试服务不可用"
        }
    
    try:
        results = smoke_test_service.get_test_results(platform=platform, limit=limit)
        all_status = smoke_test_service.get_all_status()
        next_run = smoke_test_service.get_next_run_time()
        
        return {
            "status": "ok",
            "results": results,
            "all_platforms_status": all_status,
            "next_run_time": next_run
        }
    except Exception as e:
        logger.error(f"获取冒烟测试记录失败: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/smoke-tests/trigger")
async def trigger_smoke_test():
    """
    手动触发一次冒烟测试（管理操作）
    """
    smoke_test_service = _get_smoke_test_service()
    
    if smoke_test_service is None:
        return {
            "status": "error",
            "message": "冒烟测试服务不可用"
        }
    
    try:
        results = smoke_test_service.run_smoke_test()
        
        return {
            "status": "ok",
            "message": "冒烟测试已触发",
            "results": {
                platform: {
                    "success": result.success,
                    "response_time": result.response_time,
                    "error": result.error_message
                }
                for platform, result in results.items()
            }
        }
    except Exception as e:
        logger.error(f"触发冒烟测试失败: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/health")
async def admin_health_check():
    """
    管理接口健康检查
    """
    cooldown_manager = _get_cooldown_manager()
    smoke_test_service = _get_smoke_test_service()
    
    return {
        "status": "healthy",
        "cooldown_manager": "ok" if cooldown_manager else "unavailable",
        "smoke_test_service": "ok" if smoke_test_service else "unavailable"
    }
