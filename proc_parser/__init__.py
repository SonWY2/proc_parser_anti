"""
proc_parser - Pro*C 파서 모듈

Pro*C/C 소스 파일을 파싱하여 SQL, 함수, 변수, 매크로 등의 요소를 추출합니다.

주요 클래스:
- ProCParser: Pro*C 파일 파싱 메인 클래스
- CParser: Tree-sitter 기반 C 코드 파서
- SQLConverter: SQL 정규화 및 호스트 변수 처리

주요 함수:
- process_directory: 디렉토리 내 모든 .pc/.h 파일 일괄 처리

Example:
    from proc_parser import ProCParser, process_directory
    
    # 단일 파일 파싱
    parser = ProCParser()
    elements = parser.parse_file("sample.pc")
    
    # 디렉토리 일괄 처리
    process_directory("input_dir", "output_dir")
"""

from .core import ProCParser
from .c_parser import CParser
from .sql_converter import SQLConverter
from .file_handler import process_directory
from .interfaces import ParserPlugin, SQLRelationshipPlugin
from .patterns import (
    PATTERN_INCLUDE,
    PATTERN_MACRO,
    PATTERN_SQL,
    PATTERN_BAMCALL,
    PATTERN_HOST_VAR,
    PATTERN_COMMENT_SINGLE,
    PATTERN_COMMENT_MULTI,
    PATTERN_ARRAY_DML,
)

# 플러그인 re-export
from .plugins import (
    NamingConventionPlugin,
    SnakeToCamelPlugin,
    BamCallPlugin,
    CursorRelationshipPlugin,
    DynamicSQLRelationshipPlugin,
    TransactionRelationshipPlugin,
    ArrayDMLRelationshipPlugin,
)

__all__ = [
    # 메인 클래스
    "ProCParser",
    "CParser",
    "SQLConverter",
    
    # 디렉토리 처리
    "process_directory",
    
    # 인터페이스
    "ParserPlugin",
    "SQLRelationshipPlugin",
    
    # 패턴 상수
    "PATTERN_INCLUDE",
    "PATTERN_MACRO",
    "PATTERN_SQL",
    "PATTERN_BAMCALL",
    "PATTERN_HOST_VAR",
    "PATTERN_COMMENT_SINGLE",
    "PATTERN_COMMENT_MULTI",
    "PATTERN_ARRAY_DML",
    
    # 플러그인
    "NamingConventionPlugin",
    "SnakeToCamelPlugin",
    "BamCallPlugin",
    "CursorRelationshipPlugin",
    "DynamicSQLRelationshipPlugin",
    "TransactionRelationshipPlugin",
    "ArrayDMLRelationshipPlugin",
]
