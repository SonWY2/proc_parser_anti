"""
SQL Transform Plugin 패키지

MyBatis향 SQL 변환을 위한 플러그인 시스템입니다.

주요 컴포넌트:
- SQLTransformPlugin: 변환 플러그인 기본 클래스
- TransformPipeline: 플러그인 파이프라인 실행기
- PaginationPlugin: 페이징 SQL 변환
"""

from .base import SQLTransformPlugin, TransformPipeline, TransformResult
from .pagination import (
    PaginationPlugin,
    MySQLPaginationPlugin,
    OraclePaginationPlugin,
    PostgreSQLPaginationPlugin,
    DB2PaginationPlugin,
)
from .dialect import (
    DialectPlugin,
    OracleToMySQLPlugin,
    DB2ToMySQLPlugin,
    MySQLToOraclePlugin,
)

__all__ = [
    # 기본 클래스
    "SQLTransformPlugin",
    "TransformPipeline",
    "TransformResult",
    
    # 페이징 플러그인
    "PaginationPlugin",
    "MySQLPaginationPlugin",
    "OraclePaginationPlugin",
    "PostgreSQLPaginationPlugin",
    "DB2PaginationPlugin",
    
    # 방언 변환 플러그인
    "DialectPlugin",
    "OracleToMySQLPlugin",
    "DB2ToMySQLPlugin",
    "MySQLToOraclePlugin",
]
