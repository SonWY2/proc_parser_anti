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

# 신규 모듈 (MyBatis 변환 관련)
from .mybatis_converter import (
    MyBatisConverter, 
    MyBatisSQL,
    default_input_formatter,
    default_output_formatter,
    camel_case_input_formatter,
)
from .sql_id_generator import SQLIdGenerator, get_global_generator, reset_global_generator
from .comment_marker import (
    SQLCommentMarker,
    create_marker,
    default_comment_formatter,
    detailed_comment_formatter,
)
from .cursor_merger import CursorMerger, CursorGroup, MergedCursorSQL
from .dynamic_sql_extractor import DynamicSQLExtractor, DynamicSQL

# Column Alias Mapper
from .column_alias_mapper import (
    ColumnAliasMapper,
    add_column_aliases,
    snake_to_camel,
    keep_original,
)

# 플러그인 (별도 모듈)
from .plugins import (
    SQLRelationshipPlugin,
    CursorRelationshipPlugin,
    DynamicSQLRelationshipPlugin,
)

# Transform Plugins
from .transform_plugins import (
    SQLTransformPlugin,
    TransformPipeline,
    TransformResult,
    MySQLPaginationPlugin,
    OraclePaginationPlugin,
    PostgreSQLPaginationPlugin,
    DB2PaginationPlugin,
    OracleToMySQLPlugin,
    DB2ToMySQLPlugin,
)

# proc_parser 호환 어댑터
from .proc_parser_adapter import ProcParserSQLAdapter, get_proc_parser_adapter

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
    
    # MyBatis 변환
    "MyBatisConverter",
    "MyBatisSQL",
    "default_input_formatter",
    "default_output_formatter",
    "camel_case_input_formatter",
    
    # SQL ID 생성
    "SQLIdGenerator",
    "get_global_generator",
    "reset_global_generator",
    
    # 주석 마커
    "SQLCommentMarker",
    "create_marker",
    "default_comment_formatter",
    "detailed_comment_formatter",
    
    # 커서 병합
    "CursorMerger",
    "CursorGroup",
    "MergedCursorSQL",
    
    # 동적 SQL 추출
    "DynamicSQLExtractor",
    "DynamicSQL",
    
    # Column Alias Mapper
    "ColumnAliasMapper",
    "add_column_aliases",
    "snake_to_camel",
    "keep_original",
    
    # 플러그인
    "SQLRelationshipPlugin",
    "CursorRelationshipPlugin",
    "DynamicSQLRelationshipPlugin",
    
    # Transform Plugins
    "SQLTransformPlugin",
    "TransformPipeline",
    "TransformResult",
    "MySQLPaginationPlugin",
    "OraclePaginationPlugin",
    "PostgreSQLPaginationPlugin",
    "DB2PaginationPlugin",
    "OracleToMySQLPlugin",
    "DB2ToMySQLPlugin",
    
    # proc_parser 호환 어댑터
    "ProcParserSQLAdapter",
    "get_proc_parser_adapter",
]

