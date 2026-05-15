"""
PrismaMate 棱镜 - 用户端订阅接口（Phase 3）

提供用户订阅管理、积分充值等功能：
- GET /api/v1/subscription/my-plan - 获取当前套餐详情
- GET /api/v1/subscription/plans - 获取所有套餐列表
- POST /api/v1/subscription/upgrade - 升级套餐
- GET /api/v1/subscription/points-history - 积分流水
- POST /api/v1/subscription/purchase-points - 积分充值
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

from app.services.subscription_service import subscription_service
from app.core.user_store import user_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscription", tags=["订阅管理"])


# ==================== 认证依赖 ====================

async def get_current_user_id(authorization: str = Header(...)) -> str:
    """
    获取当前用户ID（从 Authorization Header）
    使用 Bearer Token 认证
    """
    from app.core.security import decode_access_token
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # payload 可能是 TokenData 对象或 dict
    if hasattr(payload, 'user_id'):
        return payload.user_id
    return payload.get("user_id") or payload.get("sub")


# ==================== 套餐管理 ====================

@router.get("/my-plan")
async def get_my_plan(user_id: str = Depends(get_current_user_id)):
    """
    获取当前套餐详情 + 剩余额度
    """
    user = user_store.get_user_by_id(user_id)
    if user:
        plan = subscription_service.get_user_plan(user_id)
        return {"status": "ok", "plan": plan}
    
    # 兼容管理员账号
    admin = user_store.get_admin_by_id(user_id)
    if admin:
        return {
            "status": "ok",
            "plan": {
                "id": "admin",
                "name": "管理员套餐",
                "monthly_price": 0,
                "yearly_price": 0,
                "monthly_quota": 999999,
                "monthly_points": 999999,
                "max_keywords": 999,
                "max_platforms": 999,
                "max_competitors": 999,
                "has_pdf_download": True,
                "has_api_access": True,
                "data_retention_days": 365,
                "features": ["无限检测", "无限积分", "全功能开放", "数据保留 365 天"],
                "user_plan_id": "admin",
                "points_balance": 999999,
                "monthly_usage": 0,
                "monthly_remaining": 999999,
                "subscription_expires_at": None
            }
        }
    
    raise HTTPException(status_code=404, detail="用户不存在")


@router.get("/plans")
async def get_plans():
    """
    获取所有套餐列表（供用户升级参考）
    """
    plans = subscription_service.get_all_plans()
    
    return {
        "status": "ok",
        "plans": plans
    }


class UpgradePlanRequest(BaseModel):
    plan_id: str


@router.post("/upgrade")
async def upgrade_plan(
    request: UpgradePlanRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    升级套餐（预留支付，直接生效）
    
    注意：实际生产中应集成支付网关
    """
    success, message = subscription_service.upgrade_plan(
        user_id=user_id,
        plan_id=request.plan_id
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {
        "status": "ok",
        "message": message
    }


# ==================== 积分管理 ====================

@router.get("/points-history")
async def get_points_history(
    limit: int = 50,
    user_id: str = Depends(get_current_user_id)
):
    """
    获取积分流水
    """
    history = subscription_service.get_points_history(user_id, limit)
    
    return {
        "status": "ok",
        "history": history
    }


class PurchasePointsRequest(BaseModel):
    points_amount: int  # 必须是100的倍数


@router.post("/purchase-points")
async def purchase_points(
    request: PurchasePointsRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    积分充值（预留支付，直接增加积分模拟）
    
    注意：实际生产中应集成支付网关
    """
    success, message, order = subscription_service.purchase_points(
        user_id=user_id,
        points_amount=request.points_amount
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # 获取最新积分余额
    user = user_store.get_user_by_id(user_id)
    
    return {
        "status": "ok",
        "message": message,
        "order": order,
        "new_balance": user.points_balance if user else 0
    }


@router.get("/my-subscriptions")
async def get_my_subscriptions(user_id: str = Depends(get_current_user_id)):
    """
    获取我的订阅记录
    """
    subscriptions = subscription_service.get_my_subscriptions(user_id)
    
    return {
        "status": "ok",
        "subscriptions": subscriptions
    }
