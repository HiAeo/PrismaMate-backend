"""
PrismaMate 棱镜 - 服务层
"""

from app.services.brand_extractor import (
    BrandExtractor,
    BrandAlias,
    BrandMatch,
    create_extractor,
    extract_brands,
)

from app.services.report_generator import (
    ReportGenerator,
    DetectionReport,
    DetectionResult,
    BrandMentionResult,
    convert_brand_match,
    convert_brand_matches,
    generate_report,
)

__all__ = [
    # 品牌提取引擎
    "BrandExtractor",
    "BrandAlias",
    "BrandMatch",
    "create_extractor",
    "extract_brands",
    # 报告生成器
    "ReportGenerator",
    "DetectionReport",
    "DetectionResult",
    "BrandMentionResult",
    "convert_brand_match",
    "convert_brand_matches",
    "generate_report",
    # 冒烟测试服务
    "SmokeTestService",
    "get_smoke_test_service",
]
