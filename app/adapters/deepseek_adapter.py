# deepseek_adapter.py
# DeepSeek 平台 API 适配器
# 支持 API 模式调用

import os
import re
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

import requests


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


@dataclass
class DeepSeekAdapter:
    """DeepSeek 平台适配器（API 模式）"""

    # 平台标识
    platform_name: str = "DeepSeek"
    platform_domain: str = "api.deepseek.com"
    detection_mode: str = "api"

    # API 配置
    api_endpoint: str = "https://api.deepseek.com/v1/chat/completions"
    api_model: str = "deepseek-chat"
    api_timeout: int = 60

    # 状态
    consecutive_failures: int = 0
    cooldown_until: Optional[float] = None  # Unix timestamp

    # 配置（可选）
    config: Optional[Dict[str, Any]] = None

    # 品牌列表（可在初始化时传入）
    brands: List[str] = field(default_factory=lambda: [
        "华为", "阿里巴巴", "腾讯", "百度", "字节跳动",
        "小米", "京东", "美团", "滴滴", "拼多多",
        "OpenAI", "Google", "Microsoft", "Apple", "Meta",
        "Amazon", "NVIDIA", "Intel", "AMD", "Tesla"
    ])

    def __post_init__(self):
        """初始化后置处理"""
        self.api_key = None  # 延迟加载
        self.headers = None

    def _ensure_api_key(self) -> str:
        """确保 API Key 已加载"""
        if self.api_key is None:
            self.api_key = os.environ.get("DEEPSEEK_API_KEY")
            if not self.api_key:
                raise ValueError(
                    "环境变量 DEEPSEEK_API_KEY 未设置。\n"
                    "请执行以下步骤：\n"
                    "1. 复制 prismamate-backend/.env.example 为 .env\n"
                    "2. 在 .env 文件中设置 DEEPSEEK_API_KEY=sk-your-real-api-key\n"
                    "3. 重启后端服务"
                )
            if self.api_key == "sk-placeholder-replace-with-real-key":
                raise ValueError(
                    "DEEPSEEK_API_KEY 当前为占位符值。\n"
                    "请在 prismamate-backend/.env 文件中\n"
                    "将 DEEPSEEK_API_KEY 替换为实际的 API Key，然后重启服务。"
                )
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        return self.api_key

    def is_available(self) -> bool:
        """
        检测平台是否可达（API 模式）

        实现指引：
        1. 发送轻量请求探测 API 连通性
        2. 验证认证是否成功
        3. 返回 True 表示可用，False 表示不可用
        """
        try:
            # 发送一个最小化的请求探测
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
                # API Key 无效
                print(f"[DeepSeek] API Key 无效: {response.status_code}")
                return False
            else:
                # 其他错误，增加失败计数
                self.consecutive_failures += 1
                self._check_cooldown()
                return False

        except requests.exceptions.Timeout:
            print("[DeepSeek] API 请求超时")
            self.consecutive_failures += 1
            self._check_cooldown()
            return False
        except Exception as e:
            print(f"[DeepSeek] 可用性检查失败: {e}")
            self.consecutive_failures += 1
            self._check_cooldown()
            return False

    def _check_cooldown(self):
        """检查是否需要进入冷却期"""
        # 连续失败3次，进入2小时冷却期
        if self.consecutive_failures >= 3:
            self.cooldown_until = time.time() + 7200  # 2小时
            print(f"[DeepSeek] 进入冷却期，2小时后恢复")

    def login_if_needed(self) -> bool:
        """
        API 模式不需要登录，每次请求自带认证
        """
        return True

    def handle_captcha(self) -> Dict[str, Any]:
        """
        API 模式不会遇到验证码
        """
        return {"status": "not_applicable", "message": "API 模式无验证码"}

    def get_last_dom_change(self) -> Optional[float]:
        """
        API 模式不需要 DOM 检查
        """
        return None

    def search(self, keyword: str) -> Dict[str, Any]:
        """
        调用 DeepSeek API 搜索关键词

        Args:
            keyword: 搜索关键词

        Returns:
            包含 success, content, elapsed, error 的字典
        """
        # 确保 API Key 已加载
        try:
            self._ensure_api_key()
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "content": None,
                "elapsed": 0
            }

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
                    "max_tokens": 2000
                },
                timeout=self.api_timeout
            )

            elapsed = time.time() - start_time

            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                self.consecutive_failures = 0
                return {
                    "success": True,
                    "content": content,
                    "elapsed": elapsed,
                    "tokens_used": result.get("usage", {}).get("total_tokens", 0),
                    "error": None
                }
            else:
                self.consecutive_failures += 1
                self._check_cooldown()
                return {
                    "success": False,
                    "error": f"API 错误 {response.status_code}: {response.text}",
                    "content": None,
                    "elapsed": elapsed
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
            # 精确匹配整个词
            pattern = re.compile(rf'\b{re.escape(brand)}\b')
            for match in pattern.finditer(text):
                start = match.start()
                end = match.end()
                # 获取上下文（前50后50字符）
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
        # 匹配常见 URL 格式
        url_pattern = re.compile(
            r'https?://[^\s\)\]\}\'\"\<\>\[\]]+',
            re.IGNORECASE
        )

        citations = []
        seen_urls = set()  # 去重

        for match in url_pattern.finditer(text):
            url = match.group()
            # 去除 URL 末尾的标点
            url = url.rstrip('.,;:!?')

            # 跳过重复的 URL
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # 获取 URL 前后的上下文
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
            "success": False,
            "response_content": None,
            "brand_mentions": [],
            "citations": [],
            "elapsed": 0,
            "error": None
        }

        # 1. 调用 API 搜索
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
                "context": m.context,
                "position_start": m.position_start,
                "position_end": m.position_end
            }
            for m in mentions
        ]

        # 3. 提取引用来源
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


# 快捷函数
def create_adapter(config: Optional[Dict[str, Any]] = None) -> DeepSeekAdapter:
    """创建 DeepSeek 适配器实例"""
    return DeepSeekAdapter(config=config)
