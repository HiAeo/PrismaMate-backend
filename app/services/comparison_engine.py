"""
PrismaMate 棱镜 - 历史对比引擎

V3.0 Phase 1 功能：对比同一模板的两次体检报告
"""

from datetime import datetime
from typing import Dict, List, Optional, Any


def generate_comparison(current_report: dict, parent_report: dict) -> dict:
    """
    生成两份报告的对比数据
    
    Args:
        current_report: 当前报告 dict（包含 detection_results）
        parent_report: 上一次报告 dict（包含 detection_results）
    
    Returns:
        ComparisonResult 结构：
        {
            "current_report_id": str,
            "parent_report_id": str,
            "comparison_time_gap_days": int,
            "summary": {
                "total_new_mentions": int,
                "total_lost_mentions": int,
                "total_unchanged_mentions": int,
                "total_ranking_improved": int,
                "total_ranking_declined": int
            },
            "new_mentions": [...],   # 新增提及
            "lost_mentions": [...],  # 消失提及
            "ranking_changes": [...] # 位次变化
        }
    """
    current_id = current_report.get("report_id", "")
    parent_id = parent_report.get("report_id", "")
    
    # 计算时间间隔
    current_time = _parse_datetime(current_report.get("created_at"))
    parent_time = _parse_datetime(parent_report.get("created_at"))
    time_gap = (current_time - parent_time).days if current_time and parent_time else 0
    
    # 获取检测结果
    current_results = current_report.get("detection_results", [])
    parent_results = parent_report.get("detection_results", [])
    
    # 构建索引：key = "brand|keyword|platform"
    parent_index = _build_result_index(parent_results)
    current_index = _build_result_index(current_results)
    
    all_keys = set(parent_index.keys()) | set(current_index.keys())
    
    new_mentions = []
    lost_mentions = []
    ranking_changes = []
    unchanged_count = 0
    
    for key in all_keys:
        parent_item = parent_index.get(key)
        current_item = current_index.get(key)
        
        brand = _extract_brand(key)
        keyword = _extract_keyword(key)
        platform = _extract_platform(key)
        
        base_info = {
            "brand": brand,
            "keyword": keyword,
            "platform": platform
        }
        
        if current_item and not parent_item:
            # 新增提及
            new_mentions.append({
                **base_info,
                "current_position": current_item.get("position"),
                "current_mentioned": current_item.get("is_mentioned", True)
            })
        
        elif parent_item and not current_item:
            # 消失提及
            lost_mentions.append({
                **base_info,
                "previous_position": parent_item.get("position"),
                "previous_mentioned": parent_item.get("is_mentioned", True)
            })
        
        elif current_item and parent_item:
            # 两者都有，比较位次
            old_pos = parent_item.get("position") or 999
            new_pos = current_item.get("position") or 999
            
            # 只有提及状态或位次发生变化才记录
            if old_pos != new_pos:
                change = old_pos - new_pos  # 正数表示进步（位次提前）
                ranking_changes.append({
                    **base_info,
                    "previous_position": old_pos if old_pos != 999 else None,
                    "current_position": new_pos if new_pos != 999 else None,
                    "change": change,  # 正数=进步，负数=退步
                    "trend": "improved" if change > 0 else "declined"
                })
            else:
                unchanged_count += 1
    
    # 统计摘要
    summary = {
        "total_new_mentions": len(new_mentions),
        "total_lost_mentions": len(lost_mentions),
        "total_unchanged_mentions": unchanged_count,
        "total_ranking_improved": sum(1 for c in ranking_changes if c["trend"] == "improved"),
        "total_ranking_declined": sum(1 for c in ranking_changes if c["trend"] == "declined")
    }
    
    return {
        "current_report_id": current_id,
        "parent_report_id": parent_id,
        "comparison_time_gap_days": time_gap,
        "summary": summary,
        "new_mentions": new_mentions,
        "lost_mentions": lost_mentions,
        "ranking_changes": ranking_changes,
        "generated_at": datetime.utcnow().isoformat()
    }


def _build_result_index(results: List[dict]) -> Dict[str, dict]:
    """构建检测结果索引"""
    index = {}
    for item in results:
        brand = item.get("brand_name", "")
        keyword = item.get("keyword", "")
        platform = item.get("platform", "")
        key = _make_key(brand, keyword, platform)
        index[key] = item
    return index


def _make_key(brand: str, keyword: str, platform: str) -> str:
    """生成唯一键"""
    return f"{brand}|{keyword}|{platform}"


def _extract_brand(key: str) -> str:
    return key.split("|")[0] if "|" in key else key


def _extract_keyword(key: str) -> str:
    parts = key.split("|")
    return parts[1] if len(parts) > 1 else ""


def _extract_platform(key: str) -> str:
    parts = key.split("|")
    return parts[2] if len(parts) > 2 else ""


def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """解析 datetime 字符串"""
    if not dt_str:
        return None
    try:
        if isinstance(dt_str, datetime):
            return dt_str
        # 尝试 ISO 格式
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00").replace("+00:00", ""))
    except:
        return None


def get_comparison_summary_text(comparison: dict) -> str:
    """生成对比摘要文本"""
    summary = comparison.get("summary", {})
    
    new_count = summary.get("total_new_mentions", 0)
    lost_count = summary.get("total_lost_mentions", 0)
    improved = summary.get("total_ranking_improved", 0)
    declined = summary.get("total_ranking_declined", 0)
    gap_days = comparison.get("comparison_time_gap_days", 0)
    
    parts = []
    if gap_days > 0:
        parts.append(f"距上次体检 {gap_days} 天")
    
    if new_count > 0:
        parts.append(f"新增 {new_count} 项提及")
    if lost_count > 0:
        parts.append(f"消失 {lost_count} 项提及")
    if improved > 0:
        parts.append(f"位次提升 {improved} 项")
    if declined > 0:
        parts.append(f"位次下降 {declined} 项")
    
    if not parts:
        return "较上次体检无变化"
    
    return "，".join(parts)
