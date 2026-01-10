"""
SQL 추출에 사용되는 타입 정의 모듈

SqlType, HostVariable, ExtractedSQL 등의 데이터 클래스를 정의합니다.
proc_parser 호환 형식을 지원합니다.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


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
    FETCH = "fetch"
    COMMIT = "commit"
    ROLLBACK = "rollback"
    INCLUDE = "include"
    DECLARE_SECTION_BEGIN = "declare_section_begin"
    DECLARE_SECTION_END = "declare_section_end"
    BEGIN_DECLARE_SECTION = "begin_declare_section"
    END_DECLARE_SECTION = "end_declare_section"
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    PREPARE = "prepare"
    EXECUTE = "execute"
    WHENEVER = "whenever"
    SAVEPOINT = "savepoint"
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
    """
    추출된 SQL 정보 (proc_parser 호환)
    
    proc_parser와 sql_extractor 간 통합된 출력 형식을 제공합니다.
    """
    
    # === 기본 식별 정보 ===
    type: str = "sql"                      # 요소 타입 (항상 "sql")
    sql_id: str = ""                       # 고유 ID (sql_001, sql_002, ...)
    sql_type: str = ""                     # SQL 타입 (SELECT, INSERT, FETCH, ...)
    
    # === 내용 ===
    raw_content: str = ""                  # 원본 Pro*C SQL 전체 (EXEC SQL ... ;)
    normalized_sql: str = ""               # 정규화된 SQL (EXEC SQL, INTO 제거)
    
    # === 호스트 변수 ===
    input_host_vars: List[str] = field(default_factory=list)   # 입력 변수 [:in_id, :param]
    output_host_vars: List[str] = field(default_factory=list)  # 출력 변수 [:out_name, :result.field]
    host_variables: List[HostVariable] = field(default_factory=list)  # 상세 호스트 변수 정보
    
    # === 위치 정보 ===
    line_start: int = 0                    # 시작 라인 (1-indexed)
    line_end: int = 0                      # 종료 라인 (1-indexed)
    byte_start: int = 0                    # 시작 바이트 오프셋
    byte_end: int = 0                      # 종료 바이트 오프셋
    
    # === 컨텍스트 ===
    function: Optional[str] = None         # 포함된 함수명
    
    # === 관계 정보 (플러그인에 의해 채워짐) ===
    relationship: Optional[Dict[str, Any]] = None    # 커서/트랜잭션/동적SQL 관계
    
    # === 메타데이터 ===
    parse_method: str = "pyparsing"        # 파싱 방법 (pyparsing, regex)
    confidence: float = 1.0                # 파싱 신뢰도
    
    # === 변환 관련 (MyBatis용) ===
    mybatis_sql: Optional[str] = None      # MyBatis 형식 SQL (#{var})
    mybatis_type: Optional[str] = None     # MyBatis 태그 타입 (select, insert, ...)
    
    # === 기존 호환성 ===
    id: str = ""                           # 기존 sql_extractor 호환 (= sql_id)
    name: str = ""                         # 기존 sql_extractor 호환 (select_0, ...)
    sql: str = ""                          # 기존 sql_extractor 호환 (= raw_content)
    function_name: Optional[str] = None    # 기존 sql_extractor 호환 (= function)
    input_vars: List[str] = field(default_factory=list)   # 기존 호환 (= input_host_vars)
    output_vars: List[str] = field(default_factory=list)  # 기존 호환 (= output_host_vars)
    
    def __post_init__(self):
        """초기화 후 호환성 필드 동기화"""
        # id <-> sql_id 동기화
        if self.sql_id and not self.id:
            self.id = self.sql_id
        elif self.id and not self.sql_id:
            self.sql_id = self.id
            
        # raw_content <-> sql 동기화
        if self.raw_content and not self.sql:
            self.sql = self.raw_content
        elif self.sql and not self.raw_content:
            self.raw_content = self.sql
            
        # function <-> function_name 동기화
        if self.function and not self.function_name:
            self.function_name = self.function
        elif self.function_name and not self.function:
            self.function = self.function_name
            
        # input_host_vars <-> input_vars 동기화
        if self.input_host_vars and not self.input_vars:
            self.input_vars = self.input_host_vars.copy()
        elif self.input_vars and not self.input_host_vars:
            self.input_host_vars = self.input_vars.copy()
            
        # output_host_vars <-> output_vars 동기화
        if self.output_host_vars and not self.output_vars:
            self.output_vars = self.output_host_vars.copy()
        elif self.output_vars and not self.output_host_vars:
            self.output_host_vars = self.output_vars.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """proc_parser 호환 딕셔너리로 변환"""
        result = {
            "type": self.type,
            "sql_id": self.sql_id,
            "sql_type": self.sql_type,
            "raw_content": self.raw_content,
            "normalized_sql": self.normalized_sql,
            "input_host_vars": self.input_host_vars,
            "output_host_vars": self.output_host_vars,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "function": self.function,
            "relationship": self.relationship,
        }
        # 선택적 필드
        if self.mybatis_sql:
            result["mybatis_sql"] = self.mybatis_sql
            result["mybatis_type"] = self.mybatis_type
        return result
    
    def to_legacy_dict(self) -> Dict[str, Any]:
        """기존 sql_extractor 형식 딕셔너리로 변환 (YAML 저장용)"""
        return {
            "id": self.id,
            "name": self.name,
            "sql": self.sql,
            "sql_type": self.sql_type.lower() if self.sql_type else "",
            "function_name": self.function_name,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "input_vars": self.input_vars,
            "output_vars": self.output_vars,
        }


# MyBatisSQL은 mybatis_converter 모듈에 정의됨
# 편의를 위한 re-export
try:
    from .mybatis_converter import MyBatisSQL
except ImportError:
    pass
