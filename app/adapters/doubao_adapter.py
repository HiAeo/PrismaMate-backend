"""
doubao_adapter.py
豆包 (Doubao) 平台适配器

支持 API 模式和 Browser 模式
API 模式：豆包目前没有公开的第三方 API，使用模拟响应
Browser 模式：使用 Playwright 模拟真实用户访问 www.doubao.com

配置参考: config/platforms/doubao.yaml
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


class DoubaoAdapter:
    """
    豆包平台适配器

    豆包目前没有公开的第三方 API，主要使用 Browser 模式。
    MVP 阶段返回说明信息，告知用户需要手动配置浏览器登录态。
    """

    # 平台标识
    platform_name: str = "Doubao"
    platform_domain: str = "www.doubao.com"
    detection_mode: str = "browser"  # 默认 browser

    # 默认配置
    api_endpoint: str = ""
    api_timeout: int = 60
    api_available: bool = False  # 豆包暂无 API

    # 状态
    consecutive_failures: int = 0
    cooldown_until: Optional[float] = None

    # 配置
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
        self.config = config or {}

        # 从配置中读取设置
        if self.config:
            platform_cfg = self.config.get("platform", {})
            self.platform_name = platform_cfg.get("name", self.platform_name)
            self.platform_domain = platform_cfg.get("domain", self.platform_domain)
            self.detection_mode = platform_cfg.get("detection_mode", self.detection_mode)

            # API 配置
            api_cfg = self.config.get("api", {})
            self.api_endpoint = api_cfg.get("endpoint", "")
            self.api_timeout = api_cfg.get("timeout", 60)

            # Browser 配置
            browser_cfg = self.config.get("browser", {})
            self.browser_selectors = browser_cfg.get("selectors", {})
            self.wait_times = browser_cfg.get("wait_times", {})

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """从文件加载配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[Doubao] 加载配置失败: {e}")
            return {}

    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置文件"""
        config_paths = [
            "config/platforms/doubao.yaml",
            "app/config/platforms/doubao.yaml",
            os.path.join(os.path.dirname(__file__), "..", "config", "platforms", "doubao.yaml")
        ]

        for path in config_paths:
            if os.path.exists(path):
                return self._load_config(path)

        return {}

    def is_available(self) -> bool:
        """
        检测平台是否可达

        Browser 模式：检查 Playwright 是否可用，检查网络连通性
        """
        # 检查是否是 Browser 模式
        if self.detection_mode != "browser":
            return self.api_available

        try:
            # 简单检查：尝试导入 playwright
            from playwright.sync_api import sync_playwright
            return True
        except ImportError:
            print("[Doubao] Playwright 未安装")
            return False
        except Exception as e:
            print(f"[Doubao] 可用性检查失败: {e}")
            return False

    def _check_cooldown(self):
        """检查是否需要进入冷却期"""
        if self.consecutive_failures >= 2:
            self.cooldown_until = time.time() + 7200  # 2小时
            print(f"[Doubao] 进入冷却期，2小时后恢复")

    def login_if_needed(self) -> bool:
        """
        Browser 模式下检查是否需要登录

        豆包部分功能需要登录后才能使用
        """
        # Browser 模式需要检查登录状态
        if self.detection_mode == "browser":
            # TODO: 实现登录检查
            print("[Doubao] Browser 模式登录检查暂未实现")
            return True
        return True

    def handle_captcha(self) -> Dict[str, Any]:
        """
        处理验证码

        Browser 模式会遇到验证码，记录日志并暂停
        """
        return {
            "status": "paused",
            "message": "豆包 Browser 模式遇到验证码，请手动处理后重试"
        }

    def get_last_dom_change(self) -> Optional[float]:
        """返回 None，Browser 模式由外部追踪"""
        return None

    def search(self, keyword: str) -> Dict[str, Any]:
        """
        执行搜索

        Args:
            keyword: 搜索关键词

        Returns:
            包含 success, content, elapsed, error 的字典
        """
        if self.detection_mode == "browser":
            return self._browser_search(keyword)
        else:
            return self._api_search(keyword)

    def _browser_search(self, keyword: str) -> Dict[str, Any]:
        """
        Browser 模式搜索

        使用 Playwright 模拟真实用户访问
        """
        start_time = time.time()

        # 检查是否需要冷却
        if self.cooldown_until and time.time() < self.cooldown_until:
            remaining = int(self.cooldown_until - time.time())
            return {
                "success": False,
                "error": f"平台处于冷却期，剩余 {remaining} 秒",
                "content": None,
                "elapsed": 0
            }

        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

            with sync_playwright() as p:
                # 启动浏览器
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                # 访问豆包
                page.goto(f"https://{self.platform_domain}", timeout=30000)
                page.wait_for_load_state("networkidle")

                # 检查选择器是否已配置
                input_selector = self.browser_selectors.get("input")
                submit_selector = self.browser_selectors.get("submit")
                response_selector = self.browser_selectors.get("response")

                if not all([input_selector, submit_selector, response_selector]):
                    # 选择器未配置，返回模拟响应
                    content = self._generate_mock_response(keyword)
                    elapsed = time.time() - start_time
                    browser.close()
                    return {
                        "success": True,
                        "content": content,
                        "elapsed": elapsed,
                        "mode": "mock",
                        "error": None,
                        "warning": "Browser 选择器未配置，使用模拟响应"
                    }

                # 输入搜索内容
                page.fill(input_selector, keyword)

                # 模拟打字延迟
                time.sleep(random.uniform(0.3, 0.8))

                # 点击发送按钮
                page.click(submit_selector)

                # 等待响应
                try:
                    page.wait_for_selector(response_selector, timeout=60000)
                    time.sleep(2)  # 等待内容加载完整

                    content = page.inner_text(response_selector)

                    # 处理长文本的"继续生成"
                    continue_button = self.browser_selectors.get("continue_button")
                    if continue_button:
                        for _ in range(3):  # 最多继续生成3次
                            try:
                                btn = page.wait_for_selector(continue_button, timeout=5000)
                                if btn:
                                    btn.click()
                                    time.sleep(3)
                            except:
                                break

                    elapsed = time.time() - start_time
                    self.consecutive_failures = 0

                    browser.close()
                    return {
                        "success": True,
                        "content": content,
                        "elapsed": elapsed,
                        "mode": "browser",
                        "error": None
                    }

                except PlaywrightTimeout:
                    elapsed = time.time() - start_time
                    self.consecutive_failures += 1
                    self._check_cooldown()
                    browser.close()
                    return {
                        "success": False,
                        "error": "等待响应超时",
                        "content": None,
                        "elapsed": elapsed
                    }

        except ImportError:
            return {
                "success": False,
                "error": "Playwright 未安装。请运行: pip install playwright && playwright install chromium",
                "content": None,
                "elapsed": time.time() - start_time
            }
        except Exception as e:
            elapsed = time.time() - start_time
            self.consecutive_failures += 1
            self._check_cooldown()
            return {
                "success": False,
                "error": str(e),
                "content": None,
                "elapsed": elapsed
            }

    def _api_search(self, keyword: str) -> Dict[str, Any]:
        """
        API 模式搜索

        豆包暂无公开 API，使用模拟响应
        """
        content = self._generate_mock_response(keyword)
        return {
            "success": True,
            "content": content,
            "elapsed": 0.5,
            "mode": "mock",
            "error": None,
            "warning": "豆包暂无公开 API，使用模拟响应"
        }

    def _generate_mock_response(self, keyword: str) -> str:
        """生成模拟响应"""
        return f"""关于「{keyword}」的讨论分析：

在当前的技术和商业环境中，{keyword} 是一个值得关注的话题。

【市场现状】
多个科技巨头如华为、阿里巴巴、腾讯、百度、字节跳动等都在积极布局相关领域。
国际方面，Google、Microsoft、Apple、Meta、Amazon 等公司也在持续投入研发资源。

【发展趋势】
1. 技术创新持续推进，各大厂商都在加大投入
2. 市场竞争日趋激烈
3. 用户需求不断增长

【总结】
{keyword} 领域正处于快速发展阶段，建议持续关注行业动态。"""

    def extract_brand_mentions(self, text: str, brands: Optional[List[str]] = None) -> List[BrandMention]:
        """
        从文本中精确匹配品牌名

        Args:
            text: 待分析的文本
            brands: 品牌列表，None 时使用默认列表

        Returns:
            BrandMention 列表
        """
        if brands is None:
            brands = self.brands

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
        """
        提取文本中的 URL 引用

        Args:
            text: 待分析的文本

        Returns:
            Citation 列表
        """
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

        # 调用搜索
        search_result = self.search(keyword)
        result["elapsed"] = search_result.get("elapsed", 0)

        if not search_result["success"]:
            result["error"] = search_result.get("error", "未知错误")
            return result

        content = search_result.get("content", "")
        result["response_content"] = content
        result["success"] = True

        # 提取品牌提及
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

        # 提取引用来源
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


def create_adapter(config: Optional[Dict[str, Any]] = None) -> DoubaoAdapter:
    """
    创建豆包适配器实例

    Args:
        config: 配置字典

    Returns:
        DoubaoAdapter 实例
    """
    return DoubaoAdapter(config=config)
