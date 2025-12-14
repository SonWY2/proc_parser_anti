"""
SQL 추출에 사용되는 타입 정의 모듈

SqlType, HostVariable, ExtractedSQL 등의 데이터 클래스를 정의합니다.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional


class SqlType(Enum):
    """SQL 구문 타입"""
    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    DECLARE_CURSOR = "declare_cursor"
    OPEN = "open"
    CLOSE = "close"
    FETCH_INTO = "fetch_into"
    COMMIT = "commit"
    ROLLBACK = "rollback"
    INCLUDE = "include"
    DECLARE_SECTION_BEGIN = "declare_section_begin"
    DECLARE_SECTION_END = "declare_section_end"
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    PREPARE = "prepare"
    EXECUTE = "execute"
    WHENEVER = "whenever"
    UNKNOWN = "unknown"


class VariableDirection(Enum):
    """호스트 변수 방향"""
    INPUT = "input"
    OUTPUT = "output"
    INOUT = "inout"


class HostVariableType(Enum):
    """호스트 변수 형태"""
    BASIC = "basic"           # :var
    ARRAY = "array"           # :arr[idx]
    STRUCT = "struct"         # :struct.field
    INDICATOR = "indicator"   # :var:ind
    STRUCT_INDICATOR = "struct_indicator"  # :struct.field:ind
    ARRAY_INDICATOR = "array_indicator"    # :arr[idx]:ind


@dataclass
class HostVariable:
    """호스트 변수 정보"""
    name: str
    indicator: Optional[str] = None
    direction: VariableDirection = VariableDirection.INPUT
    var_type: HostVariableType = HostVariableType.BASIC
    array_index: Optional[str] = None
    field_name: Optional[str] = None
    raw_text: str = ""  # 원본 텍스트 (예: ":arr[idx]:ind")


@dataclass
class ExtractedSQL:
    """추출된 SQL 정보"""
    id: str                              # sql_0, sql_1, ...
    name: str                            # select_0, insert_0, ...
    sql: str                             # 원본 SQL 문
    sql_type: str                        # SQL 타입 문자열 (기존 호환성)
    line_start: int = 0                  # 시작 라인
    line_end: int = 0                    # 종료 라인
    function_name: Optional[str] = None  # 포함 함수명
    host_variables: List[HostVariable] = field(default_factory=list)
    input_vars: List[str] = field(default_factory=list)   # 입력 변수 목록
    output_vars: List[str] = field(default_factory=list)  # 출력 변수 목록
    confidence: float = 1.0              # 파싱 신뢰도
    parse_method: str = "pyparsing"      # pyparsing 또는 regex

    def to_dict(self) -> dict:
        """딕셔너리로 변환 (YAML/JSON 저장용)"""
        return {
            "id": self.id,
            "name": self.name,
            "sql": self.sql,
            "sql_type": self.sql_type,
            "function_name": self.function_name,
        }
