"""
header_parser 모듈
C 헤더 파일을 파싱하여 구조체 정보를 추출합니다.
"""

from .typedef_parser import TypedefStructParser, StructInfo, FieldInfo
from .stp_parser import STPParser
from .header_parser import HeaderParser
from .classifier import HeaderClassifier, HeaderType, HeaderInfo
from .macro_extractor import MacroExtractor
from .integrated_parser import IntegratedHeaderParser, ParseResult

__all__ = [
    # 기본 파서
    "TypedefStructParser",
    "StructInfo",
    "FieldInfo",
    "STPParser",
    "HeaderParser",
    # 헤더 분류
    "HeaderClassifier",
    "HeaderType",
    "HeaderInfo",
    # 매크로 추출
    "MacroExtractor",
    # 통합 파서
    "IntegratedHeaderParser",
    "ParseResult",
]
