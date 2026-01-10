"""
SQL 유형 변환 매핑 설정
새로운 SQL 유형 추가 시 이 파일만 수정하면 됩니다.
"""
from typing import Optional

# =============================================================================
# SQL 유형 → MyBatis 태그 매핑
# =============================================================================
SQL_TYPE_TO_MYBATIS_TAG = {
    "select": "select",
    "insert": "insert",
    "update": "update",
    "delete": "delete",
    # DDL → update 태그 사용
    "create": "update",
    "drop": "update",
    "alter": "update",
    "truncate": "update",
    "merge": "update",
    # 기타
    "call": "select",      # stored procedure
    "execute": "update",
}

# =============================================================================
# DDL 유형 (parameterType/resultType 생략)
# =============================================================================
DDL_TYPES = {"create", "drop", "alter", "truncate"}

# =============================================================================
# 기본 반환 타입 (DTO가 없을 경우)
# =============================================================================
DEFAULT_RESULT_TYPES = {
    "select": "java.lang.String",
    "insert": "int",
    "update": "int",
    "delete": "int",
}


# =============================================================================
# 헬퍼 함수
# =============================================================================

def get_mybatis_tag(sql_type: str) -> str:
    """SQL 유형을 MyBatis 태그로 변환"""
    return SQL_TYPE_TO_MYBATIS_TAG.get(sql_type.lower(), "update")


def is_ddl(sql_type: str) -> bool:
    """DDL 유형인지 확인"""
    return sql_type.lower() in DDL_TYPES


def get_default_result_type(sql_type: str) -> str:
    """기본 반환 타입 조회"""
    return DEFAULT_RESULT_TYPES.get(sql_type.lower(), "int")
