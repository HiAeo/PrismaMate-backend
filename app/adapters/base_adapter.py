"""
PrismaMate 棱镜 - 平台适配器基类

定义所有平台适配器需要实现的接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class SearchResult:
    """搜索结果"""
    keyword: str
    content: str
    platform: str
    elapsed: float = 0
    error: Optional[str] = None


@dataclass
class BrandMention:
    """品牌提及"""
    brand_name: str
    canonical_name: str
    context: str
    position_start: int = 0
    position_end: int = 0
    sentiment: str = "neutral"  # positive, negative, neutral


@dataclass
class Citation:
    """引用来源"""
    url: str
    context_before: str = ""
    context_after: str = ""
    title: Optional[str] = None


@dataclass
class CaptchaResult:
    """验证码处理结果"""
    status: str  # "solved", "failed", "not_found"
    message: str = ""
    solve_time: float = 0


class BasePlatformAdapter(ABC):
    """
    平台适配器基类

    所有平台适配器都需要继承此类并实现以下方法：
    - is_available(): 检测平台是否可达
    - login_if_needed(): 确保已登录
    - search(): 执行搜索
    - extract_brand_mentions(): 提取品牌提及
    - extract_citations(): 提取引用来源
    - detect(): 完整检测流程
    """

    # 平台标识
    platform_name: str = "Unknown"
    platform_domain: str = ""
    detection_mode: str = "unknown"  # api, browser, hybrid

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化适配器

        Args:
            config: 可选的配置字典
        """
        self.config = config or {}

    @abstractmethod
    def is_available(self) -> bool:
        """
        检测平台是否可达

        Returns:
            True 表示可用，False 表示不可用
        """
        pass

    @abstractmethod
    def login_if_needed(self) -> bool:
        """
        确保已登录（如果需要）

        Returns:
            True 表示已登录或不需要登录，False 表示登录失败
        """
        pass

    @abstractmethod
    def search(self, keyword: str) -> Dict[str, Any]:
        """
        执行搜索

        Args:
            keyword: 搜索关键词

        Returns:
            包含 success, content, elapsed, error 的字典
        """
        pass

    @abstractmethod
    def extract_brand_mentions(
        self,
        text: str,
        brands: Optional[List[str]] = None
    ) -> List[BrandMention]:
        """
        从文本中提取品牌提及

        Args:
            text: 待分析的文本
            brands: 品牌列表，None 时使用默认列表

        Returns:
            BrandMention 列表
        """
        pass

    @abstractmethod
    def extract_citations(self, text: str) -> List[Citation]:
        """
        从文本中提取引用来源

        Args:
            text: 待分析的文本

        Returns:
            Citation 列表
        """
        pass

    def detect(self, keyword: str) -> Dict[str, Any]:
        """
        执行完整检测流程（默认实现）

        子类可以覆盖此方法以提供更优化的实现

        Args:
            keyword: 检测关键词

        Returns:
            包含检测结果的字典
        """
        result = {
            "keyword": keyword,
            "platform": self.platform_name,
            "success": False,
            "response_content": None,
            "brand_mentions": [],
            "citations": [],
            "elapsed": 0,
            "error": None
        }

        # 1. 搜索
        search_result = self.search(keyword)
        result["elapsed"] = search_result.get("elapsed", 0)

        if not search_result["success"]:
            result["error"] = search_result["error"]
            return result

        content = search_result["content"]
        result["response_content"] = content
        result["success"] = True

        # 2. 提取品牌提及
        mentions = self.extract_brand_mentions(content)
        result["brand_mentions"] = [
            {
                "brand_name": m.brand_name,
                "canonical_name": m.canonical_name,
                "context": m.context,
                "position_start": m.position_start,
                "position_end": m.position_end,
                "sentiment": m.sentiment
            }
            for m in mentions
        ]

        # 3. 提取引用来源
        citations = self.extract_citations(content)
        result["citations"] = [
            {
                "url": c.url,
                "context_before": c.context_before,
                "context_after": c.context_after,
                "title": c.title
            }
            for c in citations
        ]

        return result

    def handle_captcha(self) -> Dict[str, Any]:
        """
        处理验证码（默认实现）

        子类可以根据需要覆盖此方法
        """
        return {"status": "not_applicable", "message": "默认实现无验证码"}

    def get_last_dom_change(self) -> Optional[float]:
        """
        获取上次 DOM 变更时间戳

        仅 Browser 模式需要实现

        Returns:
            Unix 时间戳或 None
        """
        return None
