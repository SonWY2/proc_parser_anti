"""
header_parser 모듈
C 헤더 파일을 파싱하여 구조체 정보를 추출합니다.

플러그인 아키텍처를 지원하여 다양한 헤더 포맷을 확장 가능하게 처리합니다.
"""

# 기본 파서 (하위 호환성)
from .typedef_parser import TypedefStructParser, StructInfo, FieldInfo
from .stp_parser import STPParser
from .header_parser import HeaderParser
from .classifier import HeaderClassifier, HeaderType, HeaderInfo
from .macro_extractor import MacroExtractor
from .integrated_parser import IntegratedHeaderParser, ParseResult

# 플러그인 인터페이스 (새 API)
from .parser_interface import HeaderParserPlugin, HeaderFormatType, ParseContext

# 플러그인 (새 API)
from .plugins import (
    MacroParserPlugin,
    TypedefParserPlugin,
    STPParserPlugin,
    get_default_plugins,
)

__all__ = [
    # 기본 파서 (하위 호환성)
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
    # 플러그인 인터페이스 (새 API)
    "HeaderParserPlugin",
    "HeaderFormatType",
    "ParseContext",
    # 기본 플러그인 (새 API)
    "MacroParserPlugin",
    "TypedefParserPlugin",
    "STPParserPlugin",
    "get_default_plugins",
]
