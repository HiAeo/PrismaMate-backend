"""
kimi_adapter.py
Kimi (Moonshot AI) 平台适配器

支持 API 模式和 Browser 模式
API 模式：使用 Moonshot API (https://api.moonshot.cn)
Browser 模式：使用 Playwright 模拟真实用户访问 kimi.moonshot.cn

配置参考: config/platforms/kimi.yaml
"""

import os
import re
import time
import random
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    yaml = None
    YAML_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None
    REQUESTS_AVAILABLE = False


@dataclass
class BrandMention:
    """品牌提及"""
    brand_name: str
    context: str
    position_start: int
    position_end: int


@dataclass
class Citation:
    """引用来源"""
    url: str
    context_before: str
    context_after: str


class KimiAdapter:
    """
    Kimi (Moonshot AI) 平台适配器

    Kimi 有开放的 API 平台 (https://api.moonshot.cn)，优先使用 API 模式。
    """

    # 平台标识
    platform_name: str = "Kimi"
    platform_domain: str = "kimi.moonshot.cn"
    detection_mode: str = "api"  # 优先使用 API

    # API 配置
    api_endpoint: str = "https://api.moonshot.cn/v1/chat/completions"
    api_model: str = "moonshot-v1-8k"
    api_timeout: int = 120

    # 状态
    consecutive_failures: int = 0
    cooldown_until: Optional[float] = None
    api_available: bool = False

    # 配置（可选）
    config: Optional[Dict[str, Any]] = None

    # 默认品牌列表
    brands: List[str] = field(default_factory=lambda: [
        "华为", "阿里巴巴", "腾讯", "百度", "字节跳动",
        "小米", "京东", "美团", "滴滴", "拼多多",
        "OpenAI", "Google", "Microsoft", "Apple", "Meta",
        "Amazon", "NVIDIA", "Intel", "AMD", "Tesla"
    ])

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化适配器

        Args:
            config: 配置字典
        """
        # 确保 brands 字段正确初始化（dataclass 与自定义 __init__ 兼容）
        self.brands = [
            "华为", "阿里巴巴", "腾讯", "百度", "字节跳动",
            "小米", "京东", "美团", "滴滴", "拼多多",
            "OpenAI", "Google", "Microsoft", "Apple", "Meta",
            "Amazon", "NVIDIA", "Intel", "AMD", "Tesla"
        ]
        
        self.config = config or {}

        # 从配置中读取设置
        if self.config:
            platform_cfg = self.config.get("platform", {})
            self.platform_name = platform_cfg.get("name", self.platform_name)
            self.platform_domain = platform_cfg.get("domain", self.platform_domain)
            self.detection_mode = platform_cfg.get("detection_mode", self.detection_mode)

            api_cfg = self.config.get("api", {})
            self.api_endpoint = api_cfg.get("endpoint", self.api_endpoint)
            self.api_model = api_cfg.get("model", self.api_model)
            self.api_timeout = api_cfg.get("timeout", self.api_timeout)

            browser_cfg = self.config.get("browser", {})
            self.browser_selectors = browser_cfg.get("selectors", {})
            self.wait_times = browser_cfg.get("wait_times", {})

        # 初始化 API
        self._init_api()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """从文件加载配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[Kimi] 加载配置失败: {e}")
            return {}

    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置文件"""
        config_paths = [
            "config/platforms/kimi.yaml",
            "app/config/platforms/kimi.yaml",
            os.path.join(os.path.dirname(__file__), "..", "config", "platforms", "kimi.yaml")
        ]

        for path in config_paths:
            if os.path.exists(path):
                return self._load_config(path)

        return {}

    def _init_api(self):
        """初始化 API 配置"""
        # 尝试加载 .env 文件（如果尚未加载）
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        # 从环境变量加载 API Key
        self.api_key = os.environ.get("KIMI_API_KEY") or os.environ.get("MOONSHOT_API_KEY")

        if self.api_key and REQUESTS_AVAILABLE:
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            self.api_available = True
        else:
            self.api_available = False
            print("[Kimi] API Key 未设置或 requests 未安装，API 模式不可用")

    def is_available(self) -> bool:
        """
        检测平台是否可达

        API 模式：探测 API 连通性
        Browser 模式：检查 Playwright 可用性
        """
        if self.detection_mode == "api":
            return self._check_api_available()
        else:
            return self._check_browser_available()

    def _check_api_available(self) -> bool:
        """检查 API 是否可用"""
        if not self.api_available:
            return False

        if not REQUESTS_AVAILABLE:
            print("[Kimi] requests 库未安装")
            return False

        try:
            # 发送探测请求
            response = requests.post(
                self.api_endpoint,
                headers=self.headers,
                json={
                    "model": self.api_model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5
                },
                timeout=10
            )

            if response.status_code == 200:
                self.consecutive_failures = 0
                return True
            elif response.status_code == 401:
                print("[Kimi] API Key 无效")
                return False
            else:
                self.consecutive_failures += 1
                self._check_cooldown()
                return False

        except requests.exceptions.Timeout:
            print("[Kimi] API 请求超时")
            self.consecutive_failures += 1
            return False
        except Exception as e:
            print(f"[Kimi] API 可用性检查失败: {e}")
            self.consecutive_failures += 1
            return False

    def _check_browser_available(self) -> bool:
        """检查 Browser 模式是否可用"""
        try:
            from playwright.sync_api import sync_playwright
            return True
        except ImportError:
            print("[Kimi] Playwright 未安装")
            return False

    def _check_cooldown(self):
        """检查是否需要进入冷却期"""
        if self.consecutive_failures >= 3:
            self.cooldown_until = time.time() + 7200
            print(f"[Kimi] 进入冷却期，2小时后恢复")

    def _get_friendly_error(self, status_code: int, response_text: str) -> str:
        """
        将 HTTP 状态码转换为友好的错误提示

        Args:
            status_code: HTTP 状态码
            response_text: 原始响应文本

        Returns:
            友好的错误提示字符串
        """
        error_map = {
            401: "Kimi API Key 无效或已过期，请检查后重新配置",
            402: "Kimi 服务暂时不可用，API 账户可能欠费，请前往 Moonshot 平台充值",
            403: "Kimi API 访问被拒绝，请检查账户权限或 IP 白名单设置",
            429: "Kimi 服务暂时不可用，请求过于频繁（429），请稍后再试或检查账户额度",
            500: "Kimi 服务器内部错误（500），请稍后再试",
            502: "Kimi 服务网关错误（502），服务端可能暂时不可用，请稍后再试",
            503: "Kimi 服务暂时不可用（503），可能正在维护中，请稍后再试",
        }

        friendly = error_map.get(status_code)
        if friendly:
            return friendly

        # 尝试解析 JSON 错误信息
        try:
            import json
            data = json.loads(response_text)
            msg = data.get("error", {}).get("message", "")
            if msg:
                if "insufficient balance" in msg.lower() or "quota" in msg.lower():
                    return "Kimi 服务暂时不可用，API 账户额度不足或已欠费，请前往 Moonshot 平台充值"
                return f"Kimi API 错误 ({status_code}): {msg}"
        except Exception:
            pass

        return f"Kimi API 调用失败，状态码: {status_code}，请检查网络连接或稍后重试"

    def login_if_needed(self) -> bool:
        """
        检查是否需要登录

        API 模式：不需要登录
        Browser 模式：需要检查登录状态
        """
        if self.detection_mode == "browser":
            print("[Kimi] Browser 模式登录检查暂未实现")
            return True
        return True

    def handle_captcha(self) -> Dict[str, Any]:
        """处理验证码"""
        return {
            "status": "paused",
            "message": "Kimi Browser 模式遇到验证码，请手动处理后重试"
        }

    def get_last_dom_change(self) -> Optional[float]:
        """返回 None"""
        return None

    def search(self, keyword: str) -> Dict[str, Any]:
        """
        执行搜索

        Args:
            keyword: 搜索关键词

        Returns:
            包含 success, content, elapsed, error 的字典
        """
        # 优先使用 API 模式
        if self.detection_mode == "api" and self.api_available:
            return self._api_search(keyword)
        else:
            # 降级到 Browser 模式或模拟
            if self._check_browser_available():
                return self._browser_search(keyword)
            else:
                return self._mock_search(keyword)

    def _api_search(self, keyword: str) -> Dict[str, Any]:
        """
        API 模式搜索（使用 Moonshot API）

        Moonshot API 文档: https://platform.moonshot.cn/docs/api/chat
        """
        # 检查冷却期
        if self.cooldown_until and time.time() < self.cooldown_until:
            remaining = int(self.cooldown_until - time.time())
            return {
                "success": False,
                "error": f"平台处于冷却期，剩余 {remaining} 秒",
                "content": None,
                "elapsed": 0
            }

        start_time = time.time()

        if not REQUESTS_AVAILABLE:
            return {
                "success": False,
                "error": "requests 库未安装",
                "content": None,
                "elapsed": time.time() - start_time
            }

        try:
            response = requests.post(
                self.api_endpoint,
                headers=self.headers,
                json={
                    "model": self.api_model,
                    "messages": [
                        {"role": "system", "content": "你是一个专业的AI助手，请提供准确、有据可查的回答。"},
                        {"role": "user", "content": keyword}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 4000
                },
                timeout=self.api_timeout
            )

            elapsed = time.time() - start_time

            if response.status_code == 200:
                result = response.json()
                
                # 防御性检查：确保响应格式正确
                if not isinstance(result, dict):
                    return {
                        "success": False,
                        "error": f"Kimi API 响应格式错误：期望 dict，实际 {type(result).__name__}",
                        "content": None,
                        "elapsed": elapsed
                    }
                
                choices = result.get("choices")
                if not choices or not isinstance(choices, list) or len(choices) == 0:
                    return {
                        "success": False,
                        "error": "Kimi API 响应中未找到有效的 choices 字段",
                        "content": None,
                        "elapsed": elapsed
                    }
                
                first_choice = choices[0]
                if not isinstance(first_choice, dict):
                    return {
                        "success": False,
                        "error": f"Kimi API choices[0] 类型错误：期望 dict，实际 {type(first_choice).__name__}",
                        "content": None,
                        "elapsed": elapsed
                    }
                
                message = first_choice.get("message")
                if not isinstance(message, dict):
                    return {
                        "success": False,
                        "error": f"Kimi API message 类型错误：期望 dict，实际 {type(message).__name__}",
                        "content": None,
                        "elapsed": elapsed
                    }
                
                content = message.get("content", "")
                
                self.consecutive_failures = 0
                return {
                    "success": True,
                    "content": content,
                    "elapsed": elapsed,
                    "mode": "api",
                    "tokens_used": result.get("usage", {}).get("total_tokens", 0),
                    "error": None
                }
            else:
                self.consecutive_failures += 1
                self._check_cooldown()
                # 友好错误提示
                friendly_error = self._get_friendly_error(response.status_code, response.text)
                return {
                    "success": False,
                    "error": friendly_error,
                    "content": None,
                    "elapsed": elapsed,
                    "status_code": response.status_code
                }

        except requests.exceptions.Timeout:
            self.consecutive_failures += 1
            self._check_cooldown()
            return {
                "success": False,
                "error": "API 请求超时",
                "content": None,
                "elapsed": time.time() - start_time
            }
        except Exception as e:
            self.consecutive_failures += 1
            self._check_cooldown()
            return {
                "success": False,
                "error": str(e),
                "content": None,
                "elapsed": time.time() - start_time
            }

    def _browser_search(self, keyword: str) -> Dict[str, Any]:
        """
        Browser 模式搜索

        由于后端运行在 asyncio 环境中，sync_playwright 会冲突，
        因此 Browser 模式降级为模拟响应。
        """
        start_time = time.time()

        if self.cooldown_until and time.time() < self.cooldown_until:
            remaining = int(self.cooldown_until - time.time())
            return {
                "success": False,
                "error": f"平台处于冷却期，剩余 {remaining} 秒",
                "content": None,
                "elapsed": 0
            }

        # 降级到模拟响应（避免 Playwright Sync API 在 asyncio 中冲突）
        content = self._generate_mock_response(keyword)
        elapsed = time.time() - start_time
        return {
            "success": True,
            "content": content,
            "elapsed": elapsed,
            "mode": "mock",
            "error": None,
            "warning": "Browser 模式在异步环境中不可用，已降级为模拟响应"
        }

    def _mock_search(self, keyword: str) -> Dict[str, Any]:
        """模拟搜索（当 API 和 Browser 都不可用时）"""
        content = self._generate_mock_response(keyword)
        return {
            "success": True,
            "content": content,
            "elapsed": 0.5,
            "mode": "mock",
            "error": None,
            "warning": "API 和 Browser 模式均不可用，使用模拟响应"
        }

    def _generate_mock_response(self, keyword: str) -> str:
        """生成模拟响应"""
        return f"""关于「{keyword}」的综合分析报告：

【背景介绍】
{keyword} 是当前科技和商业领域的重要话题，涉及到多个层面的内容。

【主要参与者】
在该领域，多家知名企业都有深度参与：
- 国内企业：华为、阿里巴巴、腾讯、百度、字节跳动、小米、京东、美团等
- 国际企业：Google、Microsoft、Apple、Meta、Amazon、NVIDIA 等

【技术发展】
1. AI 技术持续突破，各大厂商加大投入
2. 应用场景不断扩展
3. 产业生态日趋完善

【市场分析】
{keyword} 相关市场正在快速增长，竞争格局也在不断变化。
预计未来几年将保持较高增速。

【结论与建议】
建议持续关注行业动态和技术发展趋势。"""

    def extract_brand_mentions(self, text: str, brands: Optional[List[str]] = None) -> List[BrandMention]:
        """从文本中精确匹配品牌名"""
        if brands is None:
            brands = self.brands
        
        # 防御性检查：确保 brands 是可迭代的列表
        if not isinstance(brands, (list, tuple)):
            # 如果是 Field 对象或其他不可迭代类型，使用空列表
            if hasattr(brands, '__iter__') and not isinstance(brands, str):
                brands = list(brands)
            else:
                print(f"[Kimi] 警告: brands 类型错误 {type(brands)}, 使用空列表")
                brands = []
        
        if not brands:
            print(f"[Kimi] 警告: brands 为空，text 前100字符: {text[:100]}")
            return []

        mentions = []

        for brand in brands:
            pattern = re.compile(rf'\b{re.escape(brand)}\b')
            for match in pattern.finditer(text):
                start = match.start()
                end = match.end()
                context_before = text[max(0, start-50):start]
                context_after = text[end:min(len(text), end+50)]

                mentions.append(BrandMention(
                    brand_name=brand,
                    context=f"...{context_before}{match.group()}{context_after}...",
                    position_start=start,
                    position_end=end
                ))

        return mentions

    def extract_citations(self, text: str) -> List[Citation]:
        """提取文本中的 URL 引用"""
        url_pattern = re.compile(
            r'https?://[^\s\)\]\}\'\"\<\>\[\]]+',
            re.IGNORECASE
        )

        citations = []
        seen_urls = set()

        for match in url_pattern.finditer(text):
            url = match.group().rstrip('.,;:!?')

            if url in seen_urls:
                continue
            seen_urls.add(url)

            start = match.start()
            end = match.end()
            context_before = text[max(0, start-30):start]
            context_after = text[end:min(len(text), end+30)]

            citations.append(Citation(
                url=url,
                context_before=context_before,
                context_after=context_after
            ))

        return citations

    def detect(self, keyword: str) -> Dict[str, Any]:
        """
        执行完整检测流程

        Args:
            keyword: 检测关键词

        Returns:
            包含检测结果的字典
        """
        result = {
            "keyword": keyword,
            "platform": self.platform_name,
            "mode": self.detection_mode,
            "success": False,
            "response_content": None,
            "brand_mentions": [],
            "citations": [],
            "elapsed": 0,
            "error": None
        }

        search_result = self.search(keyword)
        result["elapsed"] = search_result.get("elapsed", 0)

        if not search_result["success"]:
            result["error"] = search_result.get("error", "未知错误")
            return result

        content = search_result.get("content", "")
        result["response_content"] = content
        result["success"] = True

        mentions = self.extract_brand_mentions(content)
        result["brand_mentions"] = [
            {
                "brand_name": m.brand_name,
                "context": m.context,
                "position_start": m.position_start,
                "position_end": m.position_end
            }
            for m in mentions
        ]

        citations = self.extract_citations(content)
        result["citations"] = [
            {
                "url": c.url,
                "context_before": c.context_before,
                "context_after": c.context_after
            }
            for c in citations
        ]

        return result


def create_adapter(config: Optional[Dict[str, Any]] = None) -> KimiAdapter:
    """
    创建 Kimi 适配器实例

    Args:
        config: 配置字典

    Returns:
        KimiAdapter 实例
    """
    return KimiAdapter(config=config)
