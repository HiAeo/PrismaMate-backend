# brand_extractor.py
# 品牌提及提取规则引擎
# 支持精确匹配、别名映射、上下文提取
#
# 使用方法：
# from app.services.brand_extractor import BrandExtractor, create_extractor
#
# extractor = create_extractor()
# mentions = extractor.extract(text, brands=["华为", "阿里巴巴"])

import re
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field


@dataclass
class BrandMatch:
    """品牌匹配结果"""
    brand_name: str          # 品牌正式名称
    matched_text: str       # 匹配到的实际文本（可能是简称）
    position_start: int     # 起始位置
    position_end: int       # 结束位置
    context: str            # 上下文（前50后50字符）
    is_first_occurrence: bool = True  # 是否首次出现
    sentiment: str = "neutral"        # 情感极性（MVP阶段固定为neutral）


@dataclass
class BrandAlias:
    """品牌别名映射"""
    canonical_name: str      # 正式名称（用于存储和展示）
    aliases: List[str]      # 别名列表（简称、缩写等）


class BrandExtractor:
    """
    品牌提及提取规则引擎

    规则：
    1. 精确匹配：单词边界匹配，避免部分匹配
    2. 别名支持：同一品牌可有多个别名
    3. 排除规则：
       - 排除 URL 中的品牌名（http://xxx.huawei.com）
       - 排除引用来源标注中的品牌名（来源：xxx）
       - 排除 HTML/Markdown 标签内的品牌名
    4. 去重：同一品牌多次出现，只记录首次
    5. 上下文：返回提及位置前后50字符
    """

    # 默认情感极性（MVP阶段固定为neutral）
    DEFAULT_SENTIMENT = "neutral"

    # URL 正则模式
    URL_PATTERN = re.compile(
        r'https?://[^\s<>"\']+',
        re.IGNORECASE
    )

    # 引用来源正则（排除"来源：xxx"、"出处：xxx"等）
    CITATION_SOURCE_PATTERN = re.compile(
        r'[【\[(（]?\s*来源?\s*[:：]\s*[^】\]\)）\n]{0,50}?(?=[】\]\)）\n]|$)',
        re.IGNORECASE
    )

    # Markdown/HTML 标签正则
    TAG_PATTERN = re.compile(
        r'<[^>]+>|\[[^\]]+\]\([^)]+\)|!\[[^\]]*\]\([^)]+\)',
        re.IGNORECASE
    )

    def __init__(self, brand_aliases: Optional[List[BrandAlias]] = None):
        """
        初始化提取器

        Args:
            brand_aliases: 品牌别名列表，None时使用默认列表
        """
        self.brand_aliases = brand_aliases or self._get_default_brands()
        # 构建别名到正式名称的映射
        self._alias_to_canonical = self._build_alias_map()
        # 编译所有品牌的正则模式
        self._compiled_patterns = self._build_patterns()

    def _get_default_brands(self) -> List[BrandAlias]:
        """获取默认品牌列表"""
        return [
            # 中国科技公司
            BrandAlias("华为", ["华为", "华为公司", "华为技术"]),
            BrandAlias("阿里巴巴", ["阿里巴巴", "阿里", "Alibaba", "阿里云"]),
            BrandAlias("腾讯", ["腾讯", "腾讯公司", "Tencent"]),
            BrandAlias("百度", ["百度", "Baidu"]),
            BrandAlias("字节跳动", ["字节跳动", "字节", "ByteDance", "TikTok"]),
            BrandAlias("小米", ["小米", "小米公司", "Xiaomi", "Redmi"]),
            BrandAlias("京东", ["京东", "JD.com", "JD"]),
            BrandAlias("美团", ["美团", "Meituan"]),
            BrandAlias("滴滴", ["滴滴", "Didi", "滴滴出行"]),
            BrandAlias("拼多多", ["拼多多", "PDD", "Pinduoduo"]),

            # 国际科技公司
            BrandAlias("OpenAI", ["OpenAI", "ChatGPT", "GPT"]),
            BrandAlias("Google", ["Google", "Alphabet", "谷歌"]),
            BrandAlias("Microsoft", ["Microsoft", "MSFT", "微软", "Windows", "Azure"]),
            BrandAlias("Apple", ["Apple", "苹果", "iPhone", "iOS", "Mac"]),
            BrandAlias("Meta", ["Meta", "Facebook", "Facebook", "Instagram", "元宇宙"]),
            BrandAlias("Amazon", ["Amazon", "AWS", "亚马逊"]),
            BrandAlias("NVIDIA", ["NVIDIA", "英伟达", "Nvidia", "GPU"]),
            BrandAlias("Intel", ["Intel", "英特尔"]),
            BrandAlias("AMD", ["AMD", "Ryzen"]),
            BrandAlias("Tesla", ["Tesla", "特斯拉", "Tesla Inc"]),
        ]

    def _build_alias_map(self) -> Dict[str, str]:
        """构建别名到正式名称的映射"""
        alias_map = {}
        for brand in self.brand_aliases:
            # 正式名称映射到自身
            alias_map[brand.canonical_name] = brand.canonical_name
            # 所有别名映射到正式名称
            for alias in brand.aliases:
                alias_map[alias] = brand.canonical_name
        return alias_map

    def _build_patterns(self) -> List[Tuple[str, re.Pattern]]:
        """编译所有品牌的正则模式"""
        patterns = []
        for brand in self.brand_aliases:
            # 收集所有可能的匹配文本
            all_names = [brand.canonical_name] + brand.aliases
            # 去重
            unique_names = list(dict.fromkeys(all_names))
            # 用 | 连接，生成模式
            escaped_names = [re.escape(name) for name in unique_names]
            pattern_str = '|'.join(escaped_names)
            
            # 边界检测策略：
            # - 左边不能是：字母、数字（避免与英文混合词粘连）
            #   但中文之间的边界是允许的（如"和阿里巴巴"中的"阿里巴巴"）
            # - 右边不能是：字母、数字（中文后可以跟中文、标点、空格）
            # 这样能正确匹配"华为公司"、"和阿里巴巴"等中文语境
            boundary_pattern = rf'(?<![a-zA-Z0-9])({pattern_str})(?![a-zA-Z0-9])'
            pattern = re.compile(boundary_pattern, re.IGNORECASE)
            patterns.append((brand.canonical_name, pattern))
        return patterns

    def _preprocess_text(self, text: str) -> str:
        """
        预处理文本，标记需要排除的区域

        返回：元组(处理后的文本, 需要排除的位置集合)
        """
        # 收集所有需要排除的位置范围
        exclude_ranges: Set[int] = set()

        # 1. 标记 URL 区域
        for match in self.URL_PATTERN.finditer(text):
            for i in range(match.start(), match.end()):
                exclude_ranges.add(i)

        # 2. 标记 Markdown/HTML 标签区域
        for match in self.TAG_PATTERN.finditer(text):
            for i in range(match.start(), match.end()):
                exclude_ranges.add(i)

        return text, exclude_ranges

    def _get_context(self, text: str, start: int, end: int, context_size: int = 50) -> str:
        """
        获取匹配位置的上下文

        Args:
            text: 原始文本
            start: 匹配起始位置
            end: 匹配结束位置
            context_size: 前后字符数

        Returns:
            上下文字符串
        """
        # 截取前文
        context_before = text[max(0, start - context_size):start]
        if start > context_size:
            context_before = "..." + context_before

        # 截取后文
        context_after = text[end:min(len(text), end + context_size)]
        if end + context_size < len(text):
            context_after = context_after + "..."

        return f"{context_before}{text[start:end]}{context_after}"

    def extract(
        self,
        text: str,
        brands: Optional[List[str]] = None,
        return_first_only: bool = True
    ) -> List[BrandMatch]:
        """
        从文本中提取品牌提及

        Args:
            text: 待分析的文本
            brands: 指定品牌列表，None时使用全部品牌
            return_first_only: 是否只返回每个品牌的首次出现

        Returns:
            BrandMatch 列表
        """
        if not text:
            return []

        # 预处理文本
        processed_text, exclude_ranges = self._preprocess_text(text)

        # 记录已匹配的品牌（用于去重）
        matched_brands: Set[str] = set()

        # 收集所有匹配
        all_matches: List[BrandMatch] = []

        # 如果指定了品牌列表，筛选对应的模式（支持别名匹配）
        patterns_to_search = self._compiled_patterns
        if brands:
            brand_set = set(brands)
            # 用户传入的品牌名 → 转换为 canonical_name
            canonical_names_requested: Set[str] = set()
            for requested_brand in brands:
                if requested_brand in self._alias_to_canonical:
                    canonical_names_requested.add(self._alias_to_canonical[requested_brand])
                else:
                    # 如果不在映射中，直接添加（作为 canonical_name 处理）
                    canonical_names_requested.add(requested_brand)
            
            # 筛选匹配的品牌模式
            patterns_to_search = [
                (name, pattern) for name, pattern in patterns_to_search
                if name in canonical_names_requested
            ]

        # 遍历所有模式查找匹配
        for canonical_name, pattern in patterns_to_search:
            for match in pattern.finditer(processed_text):
                match_start, match_end = match.span()
                matched_text = match.group()

                # 检查是否在排除区域
                if any(i in exclude_ranges for i in range(match_start, match_end)):
                    continue

                # 检查是否已匹配过该品牌（去重）
                is_first = canonical_name not in matched_brands

                # 获取上下文
                context = self._get_context(processed_text, match_start, match_end)

                brand_match = BrandMatch(
                    brand_name=canonical_name,
                    matched_text=matched_text,
                    position_start=match_start,
                    position_end=match_end,
                    context=context,
                    is_first_occurrence=is_first,
                    sentiment=self.DEFAULT_SENTIMENT
                )

                all_matches.append(brand_match)

                if is_first:
                    matched_brands.add(canonical_name)

                # 如果只需要首次匹配，跳过后续
                if return_first_only and is_first:
                    continue

        # 按位置排序
        all_matches.sort(key=lambda x: x.position_start)

        # 如果只需要首次匹配，过滤结果
        if return_first_only:
            first_mentions = []
            seen_brands = set()
            for match in all_matches:
                if match.brand_name not in seen_brands:
                    first_mentions.append(match)
                    seen_brands.add(match.brand_name)
            return first_mentions

        return all_matches

    def extract_as_dict(self, text: str, brands: Optional[List[str]] = None) -> Dict[str, List[Dict]]:
        """
        以字典形式返回提取结果

        Args:
            text: 待分析的文本
            brands: 指定品牌列表

        Returns:
            {品牌名: [匹配结果列表]} 的字典
        """
        mentions = self.extract(text, brands, return_first_only=False)

        result: Dict[str, List[Dict]] = {}
        for mention in mentions:
            if mention.brand_name not in result:
                result[mention.brand_name] = []
            result[mention.brand_name].append({
                "matched_text": mention.matched_text,
                "position_start": mention.position_start,
                "position_end": mention.position_end,
                "context": mention.context,
                "is_first_occurrence": mention.is_first_occurrence,
                "sentiment": mention.sentiment
            })

        return result

    def get_statistics(self, text: str, brands: Optional[List[str]] = None) -> Dict:
        """
        获取品牌提及统计信息

        Args:
            text: 待分析的文本
            brands: 指定品牌列表

        Returns:
            统计信息字典
        """
        mentions = self.extract(text, brands, return_first_only=False)

        stats = {
            "total_mentions": len(mentions),
            "unique_brands": len(set(m.brand_name for m in mentions)),
            "brand_counts": {},
            "first_mentions": []
        }

        for mention in mentions:
            brand = mention.brand_name
            if brand not in stats["brand_counts"]:
                stats["brand_counts"][brand] = 0
            stats["brand_counts"][brand] += 1

            if mention.is_first_occurrence:
                stats["first_mentions"].append({
                    "brand": brand,
                    "position": mention.position_start,
                    "context": mention.context[:100] + "..."
                })

        return stats

    def get_brand_names(self) -> List[str]:
        """
        获取所有已配置品牌的 canonical_name 列表

        Returns:
            品牌正式名称列表
        """
        return [brand.canonical_name for brand in self.brand_aliases]

    def get_all_names(self) -> List[str]:
        """
        获取所有品牌名称（包括别名）

        Returns:
            所有名称列表
        """
        all_names = []
        for brand in self.brand_aliases:
            all_names.append(brand.canonical_name)
            all_names.extend(brand.aliases)
        return list(dict.fromkeys(all_names))


def create_extractor(
    brand_aliases: Optional[List[BrandAlias]] = None,
    brands: Optional[List[str]] = None
) -> BrandExtractor:
    """
    创建品牌提取器实例

    Args:
        brand_aliases: 自定义品牌别名列表（BrandAlias 对象列表）
        brands: 品牌名称列表（字符串列表），将从默认配置中筛选

    Returns:
        BrandExtractor 实例
    """
    # 如果传入了品牌名称列表（字符串），需要转换为 BrandAlias
    if brands and not brand_aliases:
        # 获取默认品牌配置
        default_extractor = BrandExtractor()
        default_aliases = default_extractor.brand_aliases
        
        # 筛选匹配的品牌
        brand_set = set(brands)
        filtered_aliases = []
        for alias in default_aliases:
            # 检查 canonical_name 或任何别名是否在请求的品牌列表中
            if alias.canonical_name in brand_set:
                filtered_aliases.append(alias)
            elif any(a in brand_set for a in alias.aliases):
                filtered_aliases.append(alias)
        
        brand_aliases = filtered_aliases if filtered_aliases else None
    
    return BrandExtractor(brand_aliases)


# 快捷函数
def extract_brands(text: str, brands: Optional[List[str]] = None) -> List[BrandMatch]:
    """
    快速提取品牌提及

    Args:
        text: 待分析的文本
        brands: 指定品牌列表

    Returns:
        BrandMatch 列表
    """
    extractor = create_extractor()
    return extractor.extract(text, brands)
