"""
PrismaMate 棱镜 - GEO 差异计算引擎

V3.0 Phase 2 功能：对比乙方声称数据与 PrismaMate 独立检测结果
"""

from typing import Dict, List, Any, Tuple


def compute_differences(
    geo_data: List[dict],
    prismamate_data: List[dict],
    supported_platforms: List[str]
) -> dict:
    """
    计算 GEO 验证差异
    
    Args:
        geo_data: 乙方声称的数据，每项含 {
            brand, keyword, platform,
            is_mentioned?, mention_position?, mention_rate?
        }
        prismamate_data: PrismaMate 独立检测结果，结构同上
        supported_platforms: PrismaMate 支持的平台列表
    
    Returns:
        {
            "differences": [
                {
                    "brand": str,
                    "keyword": str,
                    "platform": str,
                    "field": str,  # "is_mentioned" | "mention_position" | "mention_rate"
                    "claimed_value": Any,
                    "detected_value": Any,
                    "verdict": "一致" | "有差异" | "超出覆盖范围"
                }
            ],
            "summary": {
                "total_items": int,
                "consistent": int,      # 一致的项数
                "different": int,      # 有差异的项数
                "out_of_coverage": int # 超出覆盖范围的项数
            }
        }
    """
    # 构建 PrismaMate 检测数据的索引: key = "brand|keyword|platform"
    pm_index = _build_data_index(prismamate_data)
    
    differences = []
    consistent_count = 0
    different_count = 0
    out_of_coverage_count = 0
    
    for geo_item in geo_data:
        brand = geo_item.get("brand", "")
        keyword = geo_item.get("keyword", "")
        platform = geo_item.get("platform", "")
        
        # 检查平台是否在支持范围内
        if platform not in supported_platforms:
            # 超出覆盖范围 - 标记所有字段
            for field in ["is_mentioned", "mention_position", "mention_rate"]:
                if field in geo_item:
                    differences.append({
                        "brand": brand,
                        "keyword": keyword,
                        "platform": platform,
                        "field": field,
                        "claimed_value": geo_item.get(field),
                        "detected_value": None,
                        "verdict": "超出覆盖范围"
                    })
                    out_of_coverage_count += 1
            continue
        
        # 在支持范围内，进行正常对比
        key = _make_key(brand, keyword, platform)
        pm_item = pm_index.get(key, {})
        
        # 对比每个字段
        fields_to_compare = [
            ("is_mentioned", "is_mentioned"),
            ("mention_position", "mention_position"),
            ("mention_rate", "mention_rate")
        ]
        
        for geo_field, pm_field in fields_to_compare:
            if geo_field not in geo_item:
                continue
            
            claimed_value = geo_item.get(geo_field)
            detected_value = pm_item.get(pm_field)
            
            # 判断是否一致
            is_consistent = _compare_values(claimed_value, detected_value)
            
            if is_consistent:
                consistent_count += 1
            else:
                different_count += 1
                differences.append({
                    "brand": brand,
                    "keyword": keyword,
                    "platform": platform,
                    "field": geo_field,
                    "claimed_value": claimed_value,
                    "detected_value": detected_value,
                    "verdict": "一致" if is_consistent else "有差异"
                })
    
    return {
        "differences": differences,
        "summary": {
            "total_items": len(geo_data),
            "consistent": consistent_count,
            "different": different_count,
            "out_of_coverage": out_of_coverage_count
        }
    }


def _build_data_index(data: List[dict]) -> Dict[str, dict]:
    """构建数据索引"""
    index = {}
    for item in data:
        brand = item.get("brand_name", "") or item.get("brand", "")
        keyword = item.get("keyword", "")
        platform = item.get("platform", "")
        key = _make_key(brand, keyword, platform)
        index[key] = item
    return index


def _make_key(brand: str, keyword: str, platform: str) -> str:
    """生成唯一键"""
    return f"{brand}|{keyword}|{platform}"


def _compare_values(v1: Any, v2: Any) -> bool:
    """
    比较两个值是否一致
    
    - None 和 None 视为一致
    - 数值比较允许小误差（用于提及率）
    - 布尔值严格比较
    """
    if v1 is None and v2 is None:
        return True
    
    if v1 is None or v2 is None:
        return False
    
    # 数值比较（提及率等），允许 1% 误差
    if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
        return abs(v1 - v2) <= 1.0
    
    # 布尔值严格比较
    if isinstance(v1, bool) or isinstance(v2, bool):
        return bool(v1) == bool(v2)
    
    # 字符串比较（位次等）
    return str(v1).strip() == str(v2).strip()


def get_verdict_label(verdict: str) -> str:
    """获取判决标签的显示文本"""
    labels = {
        "一致": "✅ 一致",
        "有差异": "⚠️ 有差异",
        "超出覆盖范围": "❌ 超出覆盖范围"
    }
    return labels.get(verdict, verdict)
