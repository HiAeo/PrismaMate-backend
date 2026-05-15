"""
PrismaMate 棱镜 - JWT 认证工具

提供 JWT Token 的生成和验证功能
直接使用 bcrypt 库（不使用 passlib 避免兼容性问题）
"""

from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
import bcrypt

# JWT 配置
ALGORITHM = "HS256"

# bcrypt 密码最大长度
MAX_PASSWORD_LENGTH = 72


def get_jwt_secret() -> str:
    """获取 JWT 密钥"""
    from app.core.config import settings
    return settings.SECRET_KEY


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码
    
    Returns:
        验证是否通过
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False


def hash_password(password: str) -> str:
    """
    哈希密码（直接使用 bcrypt）
    
    Args:
        password: 明文密码
    
    Returns:
        哈希后的密码字符串
    
    Note:
        bcrypt 限制密码最大 72 字节，超长密码会被截断
    """
    # bcrypt 限制最大 72 字节
    password_bytes = password.encode('utf-8')[:MAX_PASSWORD_LENGTH]
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建 JWT Access Token
    
    Args:
        data: 包含在 token 中的数据（通常包含 user_id）
        expires_delta: 过期时间，默认为 24 小时
    
    Returns:
        JWT token 字符串
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode,
        get_jwt_secret(),
        algorithm=ALGORITHM
    )
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    验证并解码 JWT Token
    
    Args:
        token: JWT token 字符串
    
    Returns:
        解码后的数据，如果 token 无效则返回 None
    """
    try:
        payload = jwt.decode(
            token,
            get_jwt_secret(),
            algorithms=[ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def get_user_id_from_token(token: str) -> Optional[str]:
    """
    从 JWT Token 中提取用户 ID
    
    Args:
        token: JWT token 字符串
    
    Returns:
        用户 ID，如果 token 无效则返回 None
    """
    payload = decode_access_token(token)
    if payload:
        return payload.get("user_id") or payload.get("sub")
    return None
