"""
PrismaMate 棱镜 - 用户 Schemas
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """用户基础 Schema"""
    email: EmailStr
    company_name: Optional[str] = None


class UserCreate(UserBase):
    """用户创建 Schema"""
    password: str
    role: str = "client"


class UserLogin(BaseModel):
    """用户登录 Schema"""
    email: EmailStr
    password: str


class UserResponse(UserBase):
    """用户响应 Schema"""
    id: int
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Token 响应 Schema"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
