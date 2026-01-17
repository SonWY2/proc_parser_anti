"""
타입 변환 매핑 설정
새로운 타입 추가/수정 시 이 파일만 수정하면 됩니다.
"""
from typing import Tuple, Optional

# =============================================================================
# C 타입 → (Java 타입, JDBC 타입) 매핑
# =============================================================================
C_TO_JAVA_TYPE_MAP = {
    "int": ("Integer", "INTEGER"),
    "char": ("String", "VARCHAR"),
    "long": ("BigDecimal", "NUMERIC"),
    "double": ("BigDecimal", "DECIMAL"),
    "float": ("BigDecimal", "DECIMAL"),
    "short": ("Integer", "SMALLINT"),
    "unsigned int": ("Integer", "INTEGER"),
    "unsigned long": ("BigDecimal", "NUMERIC"),
    "unsigned short": ("Integer", "SMALLINT"),
}

# =============================================================================
# STP 타입 코드 설정
# =============================================================================

# STP에서 size/decimal 업데이트 대상 타입 (숫자 타입)
STP_NUMERIC_TYPES = {"o", "d", "i", "l", "g"}

# STP에서 무시하는 타입 (typedef 값 유지)
STP_SKIP_TYPES = {"s", "c", "w", "\0", "0"}

# STP 타입 코드 → Java 타입 (참고용)
STP_TYPE_TO_JAVA = {
    "i": "Integer",
    "o": "Integer",      # output (일반 출력)
    "d": "BigDecimal",   # decimal
    "l": "BigDecimal",   # long
    "g": "Integer",      # general
    "s": "String",       # string
    "c": "String",       # char
}


# =============================================================================
# 헬퍼 함수
# =============================================================================

def get_java_type(c_type: str) -> str:
    """C 타입을 Java 타입으로 변환"""
    mapping = C_TO_JAVA_TYPE_MAP.get(c_type)
    if mapping:
        return mapping[0]
    return "String"  # 기본값


def get_jdbc_type(c_type: str) -> str:
    """C 타입을 JDBC 타입으로 변환"""
    mapping = C_TO_JAVA_TYPE_MAP.get(c_type)
    if mapping:
        return mapping[1]
    return "VARCHAR"  # 기본값


def get_type_mapping(c_type: str) -> Tuple[str, str]:
    """C 타입을 (Java 타입, JDBC 타입) 튜플로 변환"""
    return C_TO_JAVA_TYPE_MAP.get(c_type, ("String", "VARCHAR"))
