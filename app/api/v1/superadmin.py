"""
PrismaMate 棱镜 - 超级管理员后台接口（Phase 3）

提供用户管理、套餐配置、订阅管理等管理员功能：
- POST /api/v1/superadmin/login - 管理员登录
- GET /api/v1/superadmin/dashboard - 仪表盘数据
- GET /api/v1/superadmin/users - 用户列表
- GET /api/v1/superadmin/users/{user_id} - 用户详情
- POST /api/v1/superadmin/users/{user_id}/points - 调整积分
- POST /api/v1/superadmin/users/{user_id}/plan - 调整套餐
- POST /api/v1/superadmin/users/{user_id}/ban - 封禁/解封
- GET /api/v1/superadmin/subscriptions - 订阅记录
- GET /api/v1/superadmin/points-transactions - 积分流水
- GET /api/v1/superadmin/plans - 套餐列表
- PUT /api/v1/superadmin/plans/{plan_id} - 修改套餐
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel

from app.services.admin_service import admin_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/superadmin", tags=["超级管理员"])


# ==================== 认证相关 ====================

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str
    admin: Optional[dict] = None
    token: Optional[str] = None


def get_current_admin_id(x_admin_id: str = Header(..., description="管理员ID")) -> str:
    """
    获取当前管理员ID（从请求头）
    
    实际生产中应使用 JWT Token 验证
    """
    return x_admin_id


# ==================== 管理员登录 ====================

@router.post("/login", response_model=LoginResponse)
async def admin_login(request: LoginRequest):
    """
    管理员登录
    
    - admin123 / admin123
    """
    success, message, admin = admin_service.admin_login(
        username=request.username,
        password=request.password
    )
    
    if success:
        # 简单 token 方案：使用 admin_id 作为 token
        # 生产环境应使用 JWT
        return LoginResponse(
            success=True,
            message="登录成功",
            admin=admin,
            token=admin["admin_id"]
        )
    
    return LoginResponse(
        success=False,
        message=message
    )


# ==================== 仪表盘 ====================

@router.get("/dashboard")
async def get_dashboard(admin_id: str = Depends(get_current_admin_id)):
    """
    获取仪表盘数据
    
    需要管理员身份认证
    """
    # 验证管理员权限
    if not admin_service.verify_admin_role(admin_id):
        raise HTTPException(status_code=403, detail="无权限访问")
    
    stats = admin_service.get_dashboard_stats()
    return {
        "status": "ok",
        **stats
    }


# ==================== 用户管理 ====================

@router.get("/users")
async def get_users(
    search: Optional[str] = Query(None, description="搜索关键词"),
    plan_id: Optional[str] = Query(None, description="套餐ID"),
    is_active: Optional[bool] = Query(None, description="用户状态"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    admin_id: str = Depends(get_current_admin_id)
):
    """
    获取用户列表（支持搜索、筛选、分页）
    """
    if not admin_service.verify_admin_role(admin_id):
        raise HTTPException(status_code=403, detail="无权限访问")
    
    result = admin_service.get_all_users(
        search=search,
        plan_id=plan_id,
        is_active=is_active,
        page=page,
        page_size=page_size
    )
    
    return {
        "status": "ok",
        **result
    }


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: str,
    admin_id: str = Depends(get_current_admin_id)
):
    """
    获取用户详情
    """
    if not admin_service.verify_admin_role(admin_id):
        raise HTTPException(status_code=403, detail="无权限访问")
    
    user = admin_service.get_user_detail(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return {
        "status": "ok",
        "user": user
    }


class AdjustPointsRequest(BaseModel):
    amount: int  # 正数增加，负数减少
    reason: str


@router.post("/users/{user_id}/points")
async def adjust_user_points(
    user_id: str,
    request: AdjustPointsRequest,
    admin_id: str = Depends(get_current_admin_id)
):
    """
    调整用户积分
    """
    if not admin_service.verify_admin_role(admin_id):
        raise HTTPException(status_code=403, detail="无权限访问")
    
    success, message = admin_service.adjust_user_points(
        admin_id=admin_id,
        target_user_id=user_id,
        amount=request.amount,
        reason=request.reason
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {
        "status": "ok",
        "message": message
    }


class AdjustPlanRequest(BaseModel):
    plan_id: str


@router.post("/users/{user_id}/plan")
async def adjust_user_plan(
    user_id: str,
    request: AdjustPlanRequest,
    admin_id: str = Depends(get_current_admin_id)
):
    """
    调整用户套餐
    """
    if not admin_service.verify_admin_role(admin_id):
        raise HTTPException(status_code=403, detail="无权限访问")
    
    success, message = admin_service.adjust_user_plan(
        admin_id=admin_id,
        target_user_id=user_id,
        plan_id=request.plan_id
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {
        "status": "ok",
        "message": message
    }


class BanUserRequest(BaseModel):
    ban: bool  # True=封禁，False=解封


@router.post("/users/{user_id}/ban")
async def toggle_user_ban(
    user_id: str,
    request: BanUserRequest,
    admin_id: str = Depends(get_current_admin_id)
):
    """
    封禁/解封用户
    """
    if not admin_service.verify_admin_role(admin_id):
        raise HTTPException(status_code=403, detail="无权限访问")
    
    success, message = admin_service.toggle_user_ban(
        admin_id=admin_id,
        target_user_id=user_id,
        ban=request.ban
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {
        "status": "ok",
        "message": message
    }


# ==================== 订阅管理 ====================

@router.get("/subscriptions")
async def get_subscriptions(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    admin_id: str = Depends(get_current_admin_id)
):
    """
    获取所有订阅记录
    """
    if not admin_service.verify_admin_role(admin_id):
        raise HTTPException(status_code=403, detail="无权限访问")
    
    result = admin_service.get_all_subscriptions(
        page=page,
        page_size=page_size
    )
    
    return {
        "status": "ok",
        **result
    }


@router.get("/points-transactions")
async def get_points_transactions(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    admin_id: str = Depends(get_current_admin_id)
):
    """
    获取所有积分流水
    """
    if not admin_service.verify_admin_role(admin_id):
        raise HTTPException(status_code=403, detail="无权限访问")
    
    result = admin_service.get_all_points_transactions(
        page=page,
        page_size=page_size
    )
    
    return {
        "status": "ok",
        **result
    }


# ==================== 套餐配置 ====================

@router.get("/plans")
async def get_plans(admin_id: str = Depends(get_current_admin_id)):
    """
    获取所有套餐配置
    """
    if not admin_service.verify_admin_role(admin_id):
        raise HTTPException(status_code=403, detail="无权限访问")
    
    plans = admin_service.get_plans()
    return {
        "status": "ok",
        "plans": plans
    }


class UpdatePlanRequest(BaseModel):
    monthly_price: Optional[int] = None
    yearly_price: Optional[int] = None
    monthly_quota: Optional[int] = None
    monthly_points: Optional[int] = None
    max_keywords: Optional[int] = None
    max_platforms: Optional[int] = None
    max_competitors: Optional[int] = None
    has_pdf_download: Optional[bool] = None
    has_api_access: Optional[bool] = None
    data_retention_days: Optional[int] = None


@router.put("/plans/{plan_id}")
async def update_plan(
    plan_id: str,
    request: UpdatePlanRequest,
    admin_id: str = Depends(get_current_admin_id)
):
    """
    修改套餐配置
    """
    if not admin_service.verify_admin_role(admin_id):
        raise HTTPException(status_code=403, detail="无权限访问")
    
    # 过滤掉 None 值
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    
    if not updates:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    
    success, message = admin_service.update_plan(
        admin_id=admin_id,
        plan_id=plan_id,
        updates=updates
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {
        "status": "ok",
        "message": message
    }
