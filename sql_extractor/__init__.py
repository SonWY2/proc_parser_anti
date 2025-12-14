"""
Pro*C/SQLC SQL 추출 패키지

Tree-sitter 기반 SQL 추출과 규칙 기반 타입 결정을 제공합니다.

주요 클래스:
- SQLExtractor: 메인 SQL 추출기
- SQLTypeRegistry: SQL 타입 규칙 레지스트리
- HostVariableRegistry: 호스트 변수 규칙 레지스트리
- TreeSitterSQLExtractor: Tree-sitter 기반 추출기

Example:
    from sql_extractor import SQLExtractor, SQLExtractorConfig
    
    # 기본 사용
    extractor = SQLExtractor()
    code = extractor.decompose_sql(code, "program", {})
    
    # DB2 규칙 추가
    extractor.sql_type_registry.load_db2_rules()
    
    # 커스텀 규칙 추가
    from sql_extractor.rules import SQLTypeRule
    
    class MyRule(SQLTypeRule):
        name = "my_type"
        priority = 60
        pattern = re.compile(r'EXEC\\s+SQL\\s+MY_STMT')
    
    extractor.sql_type_registry.register(MyRule())
"""

from .extractor import SQLExtractor
from .config import SQLExtractorConfig
from .types import (
    SqlType, 
    ExtractedSQL, 
    HostVariable, 
    VariableDirection,
    HostVariableType,
)
from .registry import SQLTypeRegistry, HostVariableRegistry
from .tree_sitter_extractor import TreeSitterSQLExtractor, SQLBlock
from .rules import SQLTypeRule, HostVariableRule, RuleMatch

__all__ = [
    # 메인 클래스
    "SQLExtractor",
    "SQLExtractorConfig",
    
    # 레지스트리
    "SQLTypeRegistry",
    "HostVariableRegistry",
    
    # Tree-sitter
    "TreeSitterSQLExtractor",
    "SQLBlock",
    
    # 규칙 기본 클래스
    "SQLTypeRule",
    "HostVariableRule",
    "RuleMatch",
    
    # 타입
    "SqlType",
    "ExtractedSQL",
    "HostVariable",
    "VariableDirection",
    "HostVariableType",
]
