"""
PrismaMate 棱镜 - 认证 API 路由

提供用户注册、登录、Token 验证功能
"""

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field

from app.core.auth import (
    verify_password,
    hash_password,
    create_access_token,
    decode_access_token
)
from app.core.user_store import user_store
from app.core.config import settings

router = APIRouter()

# Bearer Token 方案
security = HTTPBearer(auto_error=False)


# ==================== 请求/响应模型 ====================

class RegisterRequest(BaseModel):
    """注册请求"""
    email: EmailStr = Field(..., description="邮箱地址")
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")


class LoginRequest(BaseModel):
    """登录请求"""
    email: Optional[str] = Field(None, description="邮箱地址")
    username: Optional[str] = Field(None, description="用户名")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    """Token 响应"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """用户信息响应"""
    user_id: str
    email: str
    username: str
    created_at: str
    # Phase 3 新增
    plan_id: str
    plan_name: str
    points_balance: int
    monthly_usage: int
    monthly_quota: int


# ==================== 依赖项 ====================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    获取当前登录用户（需要认证）
    
    Raises:
        HTTPException: Token 无效或过期
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证 Token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user_id = payload.get("user_id") or payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 格式错误",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # 先尝试查找普通用户
    user = user_store.get_user_by_id(user_id)
    if user:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户已被禁用"
            )
        return user
    
    # 再尝试查找管理员（兼容 admin token）
    if payload.get("is_admin"):
        admin = user_store.get_admin_by_id(user_id)
        if admin:
            # 返回兼容普通用户的结构，方便前端统一处理
            return {
                "user_id": admin.admin_id,
                "email": admin.username,
                "username": admin.username,
                "created_at": admin.created_at.isoformat(),
                "is_admin": True,
                "role": admin.role,
                # 兼容普通用户字段
                "plan_id": "admin",
                "plan_name": "管理员",
                "points_balance": 999999,
                "monthly_usage": 0,
                "monthly_quota": 999999,
                "is_active": True,
            }
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="用户不存在",
        headers={"WWW-Authenticate": "Bearer"}
    )


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[dict]:
    """
    获取当前用户（可选）
    
    Returns:
        User 对象或 None
    """
    if not credentials:
        return None
    
    payload = decode_access_token(credentials.credentials)
    if not payload:
        return None
    
    user_id = payload.get("user_id") or payload.get("sub")
    if not user_id:
        return None
    
    return user_store.get_user_by_id(user_id)


# ==================== API 端点 ====================

@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    """
    用户注册
    
    流程：
    1. 验证邮箱和用户名格式
    2. 检查是否已存在
    3. 创建用户
    4. 返回 JWT Token
    """
    # 创建用户
    user = user_store.create_user(
        email=request.email,
        username=request.username,
        password=request.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱或用户名已存在"
        )
    
    # 生成 Token
    access_token = create_access_token(
        data={"user_id": user.user_id, "sub": user.email},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    用户登录
    
    支持邮箱登录、用户名登录或管理员账号登录
    
    流程：
    1. 验证必填参数
    2. 查找用户（先查普通用户，再查管理员）
    3. 验证密码
    4. 返回 JWT Token
    """
    if not request.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码不能为空"
        )
    
    # 获取登录标识（邮箱或用户名）
    login_id = request.email or request.username
    if not login_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供邮箱或用户名"
        )
    
    # 先尝试查找普通用户
    user = None
    if request.email:
        user = user_store.get_user_by_email(request.email)
    elif request.username:
        user = user_store.get_user_by_username(request.username)
    
    # 普通用户登录
    if user:
        if not verify_password(request.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="密码错误"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户已被禁用"
            )
        
        # 生成 Token
        access_token = create_access_token(
            data={"user_id": user.user_id, "sub": user.email},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    # 尝试管理员登录（支持用户名 admin 登录）
    admin = user_store.get_admin_by_username(login_id)
    if admin:
        if not verify_password(request.password, admin.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="密码错误"
            )
        
        # 管理员登录成功，生成带 admin 标识的 token
        access_token = create_access_token(
            data={
                "user_id": admin.admin_id,
                "sub": admin.username,
                "is_admin": True,
                "role": admin.role
            },
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    # 用户和管理员都不存在
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="用户不存在"
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    获取当前登录用户信息
    
    需要认证
    
    Phase 3: 返回套餐和积分信息
    """
    # 兼容管理员账号（get_current_user 返回的是 dict）
    if isinstance(current_user, dict):
        return UserResponse(
            user_id=current_user.get("user_id", ""),
            email=current_user.get("email", ""),
            username=current_user.get("username", ""),
            created_at=current_user.get("created_at", ""),
            plan_id=current_user.get("plan_id", ""),
            plan_name=current_user.get("plan_name", ""),
            points_balance=current_user.get("points_balance", 0),
            monthly_usage=current_user.get("monthly_usage", 0),
            monthly_quota=current_user.get("monthly_quota", 0),
        )
    
    plan = current_user.get_plan()
    return UserResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        username=current_user.username,
        created_at=current_user.created_at.isoformat(),
        plan_id=current_user.plan_id,
        plan_name=plan["name"],
        points_balance=current_user.points_balance,
        monthly_usage=current_user.monthly_usage,
        monthly_quota=current_user.get_monthly_quota()
    )
