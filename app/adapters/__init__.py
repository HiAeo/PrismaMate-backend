"""
PrismaMate 棱镜 - 平台适配器模块

提供统一的适配器注册表，根据平台名称获取对应的适配器实例。
"""

from typing import Optional, Dict, Any, Type, List
import os

from app.adapters.base_adapter import (
    BasePlatformAdapter,
    SearchResult,
    BrandMention,
    Citation,
    CaptchaResult,
)
from app.adapters.deepseek_adapter import DeepSeekAdapter, create_adapter as create_deepseek_adapter
from app.adapters.doubao_adapter import DoubaoAdapter, create_adapter as create_doubao_adapter
from app.adapters.kimi_adapter import KimiAdapter, create_adapter as create_kimi_adapter


# 标准化平台名称映射（别名 -> 标准名称）
_PLATFORM_ALIASES: Dict[str, str] = {
    # DeepSeek 别名
    "deepseek": "deepseek",
    "DeepSeek": "deepseek",
    "DEEPSEEK": "deepseek",
    # Kimi 别名
    "kimi": "kimi",
    "Kimi": "kimi",
    "KIMI": "kimi",
    "moonshot": "kimi",
    "月之暗面": "kimi",
    # Doubao 别名
    "doubao": "doubao",
    "Doubao": "doubao",
    "DOUBao": "doubao",
    "豆包": "doubao",
}

# 适配器注册表（标准名称 -> 适配器类）
_ADAPTER_REGISTRY: Dict[str, Type[BasePlatformAdapter]] = {
    "deepseek": DeepSeekAdapter,
    "kimi": KimiAdapter,
    "doubao": DoubaoAdapter,
}

# 创建适配器的工厂函数注册表（标准名称 -> 工厂函数）
_ADAPTER_FACTORIES: Dict[str, callable] = {
    "deepseek": create_deepseek_adapter,
    "kimi": create_kimi_adapter,
    "doubao": create_doubao_adapter,
}


def _normalize_platform_name(name: str) -> str:
    """
    标准化平台名称，将别名映射到标准名称

    Args:
        name: 平台名称（可能是别名）

    Returns:
        标准平台名称，如果未知则返回原始名称
    """
    normalized = name.strip().lower()
    return _PLATFORM_ALIASES.get(normalized, normalized)


def get_adapter(platform: str, config: Optional[Dict[str, Any]] = None) -> Optional[BasePlatformAdapter]:
    """
    根据平台名称获取适配器实例

    Args:
        platform: 平台名称（支持别名、大小写不敏感）
        config: 可选的配置字典

    Returns:
        适配器实例，如果平台不支持则返回 None
    """
    # 标准化平台名称
    normalized = _normalize_platform_name(platform)

    # 查找适配器工厂
    factory = _ADAPTER_FACTORIES.get(normalized)

    if factory:
        try:
            return factory(config)
        except Exception as e:
            print(f"[适配器] 创建 {normalized} 适配器失败: {e}")
            return None

    return None


def is_adapter_available(platform: str) -> bool:
    """
    检测适配器是否可用

    Args:
        platform: 平台名称

    Returns:
        是否可用
    """
    normalized = _normalize_platform_name(platform)
    return normalized in _ADAPTER_FACTORIES


def register_adapter(platform: str, adapter_class: Type[BasePlatformAdapter],
                     factory: Optional[callable] = None) -> None:
    """
    注册新的平台适配器

    Args:
        platform: 平台名称
        adapter_class: 适配器类
        factory: 可选的工厂函数
    """
    normalized = _normalize_platform_name(platform)
    _ADAPTER_REGISTRY[normalized] = adapter_class
    if factory:
        _ADAPTER_FACTORIES[normalized] = factory


def list_supported_platforms() -> List[str]:
    """
    列出所有支持的平台（标准名称，去重）

    Returns:
        平台名称列表
    """
    return list(_ADAPTER_FACTORIES.keys())


def get_platform_info() -> Dict[str, Dict[str, Any]]:
    """
    获取所有平台的信息

    Returns:
        平台信息字典
    """
    return {
        "deepseek": {
            "name": "deepseek",
            "display_name": "DeepSeek 深度求索",
            "mode": "api",
            "api_required": True,
            "env_var": "DEEPSEEK_API_KEY",
            "domain": "api.deepseek.com",
            "status": "production",
            "description": "功能强大，性价比高"
        },
        "kimi": {
            "name": "kimi",
            "display_name": "Kimi (Moonshot AI)",
            "mode": "api",
            "api_required": True,
            "env_var": "KIMI_API_KEY",
            "domain": "api.moonshot.cn",
            "status": "production",
            "description": "支持长文本处理，适合长篇分析"
        },
        "doubao": {
            "name": "doubao",
            "display_name": "豆包",
            "mode": "browser",
            "api_required": False,
            "env_var": None,
            "domain": "www.doubao.com",
            "status": "beta",
            "description": "需要浏览器登录态，MVP 阶段暂不可用"
        }
    }


# 导出
__all__ = [
    # 基类
    "BasePlatformAdapter",
    "SearchResult",
    "BrandMention",
    "Citation",
    "CaptchaResult",
    # 适配器
    "DeepSeekAdapter",
    "DoubaoAdapter",
    "KimiAdapter",
    # 工厂函数
    "create_deepseek_adapter",
    "create_doubao_adapter",
    "create_kimi_adapter",
    # 注册表函数
    "get_adapter",
    "register_adapter",
    "list_supported_platforms",
    "get_platform_info",
    "is_adapter_available",
]
