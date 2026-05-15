"""
PrismaMate 棱镜 - 核心配置模块
"""

from functools import lru_cache
from pathlib import Path
from typing import List

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings


# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def load_yaml_config(filename: str) -> dict:
    """加载 YAML 配置文件"""
    config_path = BASE_DIR / "config" / filename
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


class DatabaseSettings(BaseModel):
    """数据库配置"""
    host: str = "localhost"
    port: int = 5432
    username: str = "postgres"
    password: str = "postgres"
    name: str = "prismamate"

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_url(self) -> str:
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseModel):
    """Redis 配置"""
    host: str = "localhost"
    port: int = 6379
    password: str = ""
    db: int = 0

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class CelerySettings(BaseModel):
    """Celery 配置"""
    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/0"


class Settings(BaseSettings):
    """应用全局配置"""

    # 应用基础配置
    APP_NAME: str = "PrismaMate 棱镜"
    DEBUG: bool = True
    VERSION: str = "1.0.0"

    # 安全配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 小时

    # API 密钥配置
    DEEPSEEK_API_KEY: str = ""
    KIMI_API_KEY: str = ""
    DOUBAO_API_KEY: str = ""

    # CORS 配置
    # 环境变量格式: CORS_ORIGINS=http://example.com,https://www.example.com
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        """解析 CORS_ORIGINS 字符串为列表"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # 数据库配置（从 YAML 加载）
    database: DatabaseSettings = DatabaseSettings()

    # Redis 配置（从 YAML 加载）
    redis: RedisSettings = RedisSettings()

    # Celery 配置（从 YAML 加载）
    celery: CelerySettings = CelerySettings()

    # 检测配置（从 YAML 加载）
    detection_config: dict = {}

    # 平台配置（从 YAML 加载）
    platforms_config: dict = {}

    class Config:
        env_file = ".env"
        case_sensitive = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 从 YAML 加载配置
        self.database = DatabaseSettings(**load_yaml_config("database.yaml"))
        self.redis = RedisSettings(**load_yaml_config("redis.yaml"))
        self.celery = CelerySettings(**{
            "broker_url": f"redis://{self.redis.host}:{self.redis.port}/{self.redis.db}",
            "result_backend": f"redis://{self.redis.host}:{self.redis.port}/{self.redis.db}",
        })
        self.detection_config = load_yaml_config("detection/retry.yaml")
        self.platforms_config = {
            "deepseek": load_yaml_config("platforms/deepseek.yaml"),
            "doubao": load_yaml_config("platforms/doubao.yaml"),
            "kimi": load_yaml_config("platforms/kimi.yaml"),
        }


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 导出 settings 实例供其他模块使用
settings = get_settings()
