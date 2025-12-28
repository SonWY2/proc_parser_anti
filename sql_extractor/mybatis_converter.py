"""
MyBatis SQL 변환기 모듈

Pro*C SQL을 MyBatis XML 형식으로 변환합니다.
포맷터 함수를 커스터마이징하여 다양한 출력 형식을 지원합니다.
"""

import re
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class MyBatisSQL:
    """MyBatis 변환된 SQL 정보"""
    id: str                              # select_0, insert_0, ...
    mybatis_type: str                    # select, insert, update, delete
    sql: str                             # 변환된 SQL
    original_sql: str                    # 원본 Pro*C SQL
    parameter_type: Optional[str] = None # parameterType
    result_type: Optional[str] = None    # resultType
    result_map: Optional[str] = None     # resultMap
    input_params: List[str] = field(default_factory=list)
    output_fields: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "mybatis_type": self.mybatis_type,
            "sql": self.sql,
            "original_sql": self.original_sql,
            "input_params": self.input_params,
            "output_fields": self.output_fields,
        }


# ============================================================================
# 기본 포맷터 함수들 (커스터마이징 가능)
# ============================================================================

def default_input_formatter(var_name: str) -> str:
    """
    입력 호스트 변수를 MyBatis 파라미터 형식으로 변환
    
    Args:
        var_name: 호스트 변수명 (콜론 제외)
    
    Returns:
        MyBatis 형식 문자열 (예: #{varName})
    """
    return f"#{{{var_name}}}"


def default_output_formatter(var_name: str) -> str:
    """
    출력 호스트 변수를 resultMap 필드명으로 변환
    
    Args:
        var_name: 호스트 변수명 (콜론 제외)
    
    Returns:
        필드명 문자열
    """
    return var_name


def camel_case_input_formatter(var_name: str) -> str:
    """snake_case를 camelCase로 변환하는 입력 포맷터"""
    parts = var_name.split('_')
    camel = parts[0].lower() + ''.join(p.capitalize() for p in parts[1:])
    return f"#{{{camel}}}"


# ============================================================================
# 시간 포맷 패턴 (호스트 변수로 오인 방지)
# ============================================================================

TIME_FORMAT_PATTERNS = [
    r"'[^']*HH:MI:SS[^']*'",           # 'HH:MI:SS'
    r"'[^']*HH24:MI:SS[^']*'",         # 'HH24:MI:SS'
    r"'[^']*YYYY-MM-DD[^']*'",         # 'YYYY-MM-DD'
    r"'[^']*HH:MM:SS[^']*'",           # 'HH:MM:SS'
    r"TO_CHAR\s*\([^)]*'[^']*:[^']*'", # TO_CHAR(..., 'format:with:colons')
    r"TO_DATE\s*\([^)]*'[^']*:[^']*'", # TO_DATE(..., 'format:with:colons')
]


class MyBatisConverter:
    """
    Pro*C SQL을 MyBatis 형식으로 변환하는 변환기
    
    Example:
        converter = MyBatisConverter()
        result = converter.convert_sql(
            sql="SELECT name INTO :out_name FROM users WHERE id = :in_id",
            sql_type="select",
            sql_id="select_0",
            input_vars=[":in_id"],
            output_vars=[":out_name"]
        )
    """
    
    # SQL 타입 → MyBatis 태그 매핑
    TYPE_MAPPING = {
        "select": "select",
        "insert": "insert",
        "update": "update",
        "delete": "delete",
        "declare_cursor": "select",  # 커서는 select로 처리
        "fetch_into": "select",
    }
    
    def __init__(
        self,
        input_formatter: Callable[[str], str] = None,
        output_formatter: Callable[[str], str] = None
    ):
        """
        변환기 초기화
        
        Args:
            input_formatter: 입력 변수 포맷터 (기본: #{varName})
            output_formatter: 출력 변수 포맷터 (기본: varName)
        """
        self.input_formatter = input_formatter or default_input_formatter
        self.output_formatter = output_formatter or default_output_formatter
        self._time_format_regex = re.compile(
            '|'.join(TIME_FORMAT_PATTERNS), 
            re.IGNORECASE
        )
    
    def convert_sql(
        self,
        sql: str,
        sql_type: str,
        sql_id: str,
        input_vars: List[str] = None,
        output_vars: List[str] = None
    ) -> MyBatisSQL:
        """
        Pro*C SQL을 MyBatis 형식으로 변환
        
        Args:
            sql: 원본 Pro*C SQL
            sql_type: SQL 타입 (select, insert, update, delete, ...)
            sql_id: SQL ID (select_0, insert_1, ...)
            input_vars: 입력 호스트 변수 목록
            output_vars: 출력 호스트 변수 목록
        
        Returns:
            MyBatisSQL 객체
        """
        input_vars = input_vars or []
        output_vars = output_vars or []
        
        # 1. EXEC SQL 제거
        converted = self._remove_exec_sql(sql)
        
        # 2. INTO 절 제거 (SELECT의 경우)
        if sql_type in ["select", "fetch_into"]:
            converted = self.remove_into_clause(converted)
        
        # 3. 시간 포맷 보호 (임시 치환)
        converted, time_placeholders = self._protect_time_formats(converted)
        
        # 4. 호스트 변수 변환
        converted = self._convert_host_variables(converted, input_vars)
        
        # 5. 시간 포맷 복원
        converted = self._restore_time_formats(converted, time_placeholders)
        
        # 6. 정리
        converted = self._cleanup_sql(converted)
        
        # 출력 필드 처리
        output_fields = [
            self.output_formatter(self._strip_colon(v)) 
            for v in output_vars
        ]
        
        input_params = [
            self._strip_colon(v) for v in input_vars
        ]
        
        return MyBatisSQL(
            id=sql_id,
            mybatis_type=self.TYPE_MAPPING.get(sql_type, "select"),
            sql=converted,
            original_sql=sql,
            input_params=input_params,
            output_fields=output_fields,
        )
    
    def remove_into_clause(self, sql: str) -> str:
        """
        SELECT ... INTO :vars ... FROM 구문에서 INTO 절 제거
        
        Args:
            sql: SQL 문자열
        
        Returns:
            INTO 절이 제거된 SQL
        """
        # INTO ... FROM 패턴
        pattern = r'\bINTO\s+[^F]+(?=\bFROM\b)'
        result = re.sub(pattern, '', sql, flags=re.IGNORECASE | re.DOTALL)
        
        # INTO ... WHERE 패턴 (FROM 없는 경우)
        if 'FROM' not in sql.upper():
            pattern = r'\bINTO\s+[^W]+(?=\bWHERE\b)'
            result = re.sub(pattern, '', result, flags=re.IGNORECASE | re.DOTALL)
        
        return result
    
    def determine_mybatis_type(self, sql_type: str) -> str:
        """SQL 타입을 MyBatis 태그 타입으로 변환"""
        return self.TYPE_MAPPING.get(sql_type, "select")
    
    def _remove_exec_sql(self, sql: str) -> str:
        """EXEC SQL 제거"""
        return re.sub(r'^\s*EXEC\s+SQL\s+', '', sql, flags=re.IGNORECASE)
    
    def _protect_time_formats(self, sql: str) -> tuple:
        """시간 포맷 문자열을 임시 플레이스홀더로 치환"""
        placeholders = {}
        counter = 0
        
        def replace_match(match):
            nonlocal counter
            placeholder = f"__TIME_FMT_{counter}__"
            placeholders[placeholder] = match.group(0)
            counter += 1
            return placeholder
        
        protected = self._time_format_regex.sub(replace_match, sql)
        return protected, placeholders
    
    def _restore_time_formats(self, sql: str, placeholders: dict) -> str:
        """임시 플레이스홀더를 원래 시간 포맷으로 복원"""
        for placeholder, original in placeholders.items():
            sql = sql.replace(placeholder, original)
        return sql
    
    def _convert_host_variables(self, sql: str, input_vars: List[str]) -> str:
        """호스트 변수를 MyBatis 형식으로 변환"""
        result = sql
        
        # 입력 변수 변환
        for var in input_vars:
            var_name = self._strip_colon(var)
            # 인디케이터 처리 (:var:ind → var만 사용)
            if ':' in var_name:
                var_name = var_name.split(':')[0]
            
            # 배열 인덱스 처리 (:arr[i] → arr)
            if '[' in var_name:
                var_name = var_name.split('[')[0]
            
            # 구조체 필드 처리 (:struct.field → struct_field)
            var_name = var_name.replace('.', '_')
            
            mybatis_var = self.input_formatter(var_name)
            
            # 원본 변수 패턴 매칭 및 치환
            pattern = re.escape(var)
            result = re.sub(pattern, mybatis_var, result)
        
        # 남은 호스트 변수도 변환 (명시적 목록에 없는 경우)
        remaining_pattern = r':(\w+(?:\.\w+)?(?:\[\w+\])?(?::\w+)?)'
        
        def replace_remaining(match):
            full_var = match.group(1)
            var_name = full_var
            # 인디케이터 제거
            if ':' in var_name:
                var_name = var_name.split(':')[0]
            # 배열 인덱스 제거
            if '[' in var_name:
                var_name = var_name.split('[')[0]
            # 구조체 필드 처리
            var_name = var_name.replace('.', '_')
            return self.input_formatter(var_name)
        
        result = re.sub(remaining_pattern, replace_remaining, result)
        
        return result
    
    def _strip_colon(self, var: str) -> str:
        """호스트 변수에서 선행 콜론 제거"""
        return var.lstrip(':')
    
    def _cleanup_sql(self, sql: str) -> str:
        """SQL 정리 (공백, 세미콜론 등)"""
        # 연속 공백 축소
        sql = re.sub(r'\s+', ' ', sql)
        # 앞뒤 공백 제거
        sql = sql.strip()
        # 끝의 세미콜론 제거
        sql = sql.rstrip(';')
        return sql
