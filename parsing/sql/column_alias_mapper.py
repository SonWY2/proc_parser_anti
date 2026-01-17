"""
Column Alias Mapper 모듈

SELECT 컬럼에 AS alias를 추가하여 MyBatis 변수 매핑을 지원합니다.

지원하는 SQL 구문:
- SELECT ... INTO :vars
- DECLARE CURSOR FOR SELECT ...
- INSERT ... RETURNING ... INTO :vars (Oracle)
- UPDATE ... RETURNING ... INTO :vars (Oracle)
- DELETE ... RETURNING ... INTO :vars (Oracle)
"""

import re
from typing import List, Optional, Callable, Tuple
from dataclasses import dataclass

# sqlglot 사용 시도, 없으면 regex fallback
try:
    import sqlglot
    from sqlglot import exp
    HAS_SQLGLOT = True
except ImportError:
    HAS_SQLGLOT = False


@dataclass
class AliasMapping:
    """컬럼-alias 매핑 정보"""
    original_column: str
    alias: str
    position: int


# ============================================================================
# 기본 alias 포맷터 함수들 (커스터마이징 가능)
# ============================================================================

def snake_to_camel(var_name: str) -> str:
    """
    snake_case를 camelCase로 변환
    
    Args:
        var_name: 변수명 (예: out_emp_name, :out_emp_name)
    
    Returns:
        camelCase 변환 결과 (예: outEmpName)
    """
    # 선행 콜론 제거
    clean_name = var_name.lstrip(':')
    
    # 언더스코어로 분리
    parts = clean_name.split('_')
    
    # 첫 단어는 소문자, 나머지는 첫 글자 대문자
    if not parts:
        return clean_name
    
    return parts[0].lower() + ''.join(p.capitalize() for p in parts[1:])


def keep_original(var_name: str) -> str:
    """원본 변수명 유지 (콜론만 제거)"""
    return var_name.lstrip(':')


def uppercase_first(var_name: str) -> str:
    """첫 글자 대문자"""
    clean_name = var_name.lstrip(':')
    return clean_name[0].upper() + clean_name[1:] if clean_name else clean_name


class ColumnAliasMapper:
    """
    SQL 컬럼에 alias를 추가하는 매퍼
    
    MyBatis에서 ResultMap 없이 직접 매핑하려면 SELECT 컬럼명과 
    Java 변수명이 일치해야 합니다. 이 클래스는 INTO 절의 변수를 기반으로
    SELECT 컬럼에 AS alias를 추가합니다.
    
    Example:
        mapper = ColumnAliasMapper()
        result = mapper.add_aliases(
            sql="SELECT emp_name, emp_age FROM employees",
            output_vars=[":out_name", ":out_age"]
        )
        # 결과: SELECT emp_name AS outName, emp_age AS outAge FROM employees
    """
    
    # Alias 처리가 필요한 SQL 타입
    ALIASABLE_TYPES = {
        'select',
        'declare_cursor',
        'fetch_into',
    }
    
    # RETURNING 절을 지원하는 SQL 타입 (Oracle/PostgreSQL)
    RETURNING_TYPES = {
        'insert',
        'update', 
        'delete',
    }
    
    def __init__(
        self,
        alias_formatter: Callable[[str], str] = None,
        overwrite_existing: bool = False
    ):
        """
        매퍼 초기화
        
        Args:
            alias_formatter: alias 변환 함수 (기본: snake_to_camel)
            overwrite_existing: 기존 alias 덮어쓰기 여부
        """
        self.alias_formatter = alias_formatter or snake_to_camel
        self.overwrite_existing = overwrite_existing
        self._use_sqlglot = HAS_SQLGLOT
    
    def add_aliases(
        self,
        sql: str,
        output_vars: List[str],
        sql_type: str = None
    ) -> str:
        """
        SQL 컬럼에 output_vars 기반 alias 추가
        
        Args:
            sql: SQL 문자열
            output_vars: 출력 변수 목록 (예: [":out_name", ":out_age"])
            sql_type: SQL 타입 (select, insert, update 등)
        
        Returns:
            alias가 추가된 SQL
        """
        if not output_vars:
            return sql
        
        # SQL 타입 자동 감지
        if sql_type is None:
            sql_type = self._detect_sql_type(sql)
        
        # RETURNING 절 처리
        if sql_type in self.RETURNING_TYPES:
            return self._add_returning_aliases(sql, output_vars)
        
        # SELECT 컬럼 처리
        if self._use_sqlglot:
            return self._add_aliases_with_sqlglot(sql, output_vars)
        else:
            return self._add_aliases_with_regex(sql, output_vars)
    
    def extract_select_columns(self, sql: str) -> List[str]:
        """
        최상위 SELECT 컬럼 추출
        
        Args:
            sql: SQL 문자열
        
        Returns:
            컬럼명 목록
        """
        if self._use_sqlglot:
            return self._extract_columns_with_sqlglot(sql)
        else:
            return self._extract_columns_with_regex(sql)
    
    def needs_alias(self, sql_type: str) -> bool:
        """해당 SQL 타입이 alias 처리가 필요한지 확인"""
        return sql_type in self.ALIASABLE_TYPES or sql_type in self.RETURNING_TYPES
    
    # =========================================================================
    # sqlglot 기반 구현
    # =========================================================================
    
    def _add_aliases_with_sqlglot(self, sql: str, output_vars: List[str]) -> str:
        """sqlglot을 사용하여 alias 추가"""
        if not HAS_SQLGLOT:
            return self._add_aliases_with_regex(sql, output_vars)
        
        try:
            # EXEC SQL 제거
            clean_sql = re.sub(r'^\s*EXEC\s+SQL\s+', '', sql, flags=re.IGNORECASE)
            # 끝 세미콜론 제거
            clean_sql = clean_sql.rstrip(';').strip()
            
            # CURSOR FOR 처리
            cursor_match = re.search(r'CURSOR\s+FOR\s+(.+)', clean_sql, re.IGNORECASE | re.DOTALL)
            if cursor_match:
                inner_sql = cursor_match.group(1).strip()
                aliased_inner = self._add_aliases_with_sqlglot(inner_sql, output_vars)
                return clean_sql[:cursor_match.start(1)] + aliased_inner
            
            # SQL 파싱
            parsed = sqlglot.parse_one(clean_sql)
            
            # SELECT 표현식 찾기
            select_exprs = list(parsed.find_all(exp.Select))
            if not select_exprs:
                return sql
            
            # 최상위 SELECT의 컬럼들
            top_select = select_exprs[0]
            columns = list(top_select.expressions)
            
            # 컬럼 수와 변수 수 매칭
            for i, (col, var) in enumerate(zip(columns, output_vars)):
                alias_name = self.alias_formatter(var)
                
                # 이미 alias가 있는 경우
                if isinstance(col, exp.Alias):
                    if self.overwrite_existing:
                        col.set("alias", exp.to_identifier(alias_name))
                else:
                    # alias 추가
                    new_col = exp.Alias(
                        this=col,
                        alias=exp.to_identifier(alias_name)
                    )
                    top_select.expressions[i] = new_col
            
            return parsed.sql()
            
        except Exception as e:
            # 파싱 실패시 regex fallback
            return self._add_aliases_with_regex(sql, output_vars)
    
    def _extract_columns_with_sqlglot(self, sql: str) -> List[str]:
        """sqlglot을 사용하여 컬럼 추출"""
        if not HAS_SQLGLOT:
            return self._extract_columns_with_regex(sql)
        
        try:
            clean_sql = re.sub(r'^\s*EXEC\s+SQL\s+', '', sql, flags=re.IGNORECASE)
            clean_sql = clean_sql.rstrip(';').strip()
            
            parsed = sqlglot.parse_one(clean_sql)
            select_exprs = list(parsed.find_all(exp.Select))
            
            if not select_exprs:
                return []
            
            columns = []
            for col in select_exprs[0].expressions:
                if isinstance(col, exp.Alias):
                    columns.append(col.alias)
                elif isinstance(col, exp.Column):
                    columns.append(col.name)
                else:
                    columns.append(str(col))
            
            return columns
            
        except Exception:
            return self._extract_columns_with_regex(sql)
    
    # =========================================================================
    # Regex 기반 구현 (fallback)
    # =========================================================================
    
    def _add_aliases_with_regex(self, sql: str, output_vars: List[str]) -> str:
        """정규식을 사용하여 alias 추가 (fallback)"""
        # EXEC SQL 제거
        clean_sql = re.sub(r'^\s*EXEC\s+SQL\s+', '', sql, flags=re.IGNORECASE)
        
        # INTO 절 제거
        clean_sql = re.sub(
            r'\bINTO\s+[^F]+(?=\bFROM\b)',
            '',
            clean_sql,
            flags=re.IGNORECASE | re.DOTALL
        )
        
        # SELECT ... FROM 사이의 컬럼 추출
        select_match = re.search(
            r'\bSELECT\s+(.*?)\s+FROM\b',
            clean_sql,
            re.IGNORECASE | re.DOTALL
        )
        
        if not select_match:
            return sql
        
        columns_str = select_match.group(1)
        columns = self._split_columns(columns_str)
        
        if len(columns) != len(output_vars):
            # 컬럼 수와 변수 수 불일치 - 가능한 만큼만 처리
            pass
        
        # alias 추가
        new_columns = []
        for i, col in enumerate(columns):
            col = col.strip()
            if i < len(output_vars):
                alias = self.alias_formatter(output_vars[i])
                
                # 이미 AS가 있는지 확인
                if re.search(r'\bAS\s+\w+\s*$', col, re.IGNORECASE):
                    if self.overwrite_existing:
                        col = re.sub(r'\bAS\s+\w+\s*$', f'AS {alias}', col, flags=re.IGNORECASE)
                else:
                    col = f"{col} AS {alias}"
            
            new_columns.append(col)
        
        new_columns_str = ', '.join(new_columns)
        result = clean_sql[:select_match.start(1)] + new_columns_str + clean_sql[select_match.end(1):]
        
        return result
    
    def _extract_columns_with_regex(self, sql: str) -> List[str]:
        """정규식을 사용하여 컬럼 추출"""
        clean_sql = re.sub(r'^\s*EXEC\s+SQL\s+', '', sql, flags=re.IGNORECASE)
        
        select_match = re.search(
            r'\bSELECT\s+(.*?)\s+FROM\b',
            clean_sql,
            re.IGNORECASE | re.DOTALL
        )
        
        if not select_match:
            return []
        
        return self._split_columns(select_match.group(1))
    
    def _split_columns(self, columns_str: str) -> List[str]:
        """컬럼 문자열을 쉼표로 분리 (괄호 고려)"""
        columns = []
        current = []
        paren_depth = 0
        
        for char in columns_str:
            if char == '(':
                paren_depth += 1
                current.append(char)
            elif char == ')':
                paren_depth -= 1
                current.append(char)
            elif char == ',' and paren_depth == 0:
                columns.append(''.join(current).strip())
                current = []
            else:
                current.append(char)
        
        if current:
            columns.append(''.join(current).strip())
        
        return columns
    
    # =========================================================================
    # RETURNING 절 처리 (Oracle/PostgreSQL)
    # =========================================================================
    
    def _add_returning_aliases(self, sql: str, output_vars: List[str]) -> str:
        """
        INSERT/UPDATE/DELETE RETURNING 절에 alias 추가
        
        Oracle: INSERT ... RETURNING col1, col2 INTO :var1, :var2
        → INSERT ... RETURNING col1 AS var1, col2 AS var2
        """
        # RETURNING ... INTO 패턴 찾기
        returning_match = re.search(
            r'\bRETURNING\s+(.*?)\s+INTO\b',
            sql,
            re.IGNORECASE | re.DOTALL
        )
        
        if not returning_match:
            return sql
        
        columns_str = returning_match.group(1)
        columns = self._split_columns(columns_str)
        
        # alias 추가
        new_columns = []
        for i, col in enumerate(columns):
            col = col.strip()
            if i < len(output_vars):
                alias = self.alias_formatter(output_vars[i])
                col = f"{col} AS {alias}"
            new_columns.append(col)
        
        new_columns_str = ', '.join(new_columns)
        
        # INTO 절 제거하고 alias 적용
        result = sql[:returning_match.start(1)] + new_columns_str
        
        # INTO 이후 부분 (세미콜론 등) 유지
        into_end = re.search(r'\bINTO\s+[^;]+', sql[returning_match.end():], re.IGNORECASE)
        if into_end:
            result += sql[returning_match.end() + into_end.end():]
        
        return result
    
    # =========================================================================
    # 유틸리티
    # =========================================================================
    
    def _detect_sql_type(self, sql: str) -> str:
        """SQL 타입 자동 감지"""
        clean_sql = sql.upper().strip()
        
        if clean_sql.startswith('SELECT') or 'EXEC SQL SELECT' in clean_sql.upper():
            return 'select'
        elif 'DECLARE' in clean_sql and 'CURSOR' in clean_sql:
            return 'declare_cursor'
        elif clean_sql.startswith('INSERT') or 'EXEC SQL INSERT' in clean_sql.upper():
            return 'insert'
        elif clean_sql.startswith('UPDATE') or 'EXEC SQL UPDATE' in clean_sql.upper():
            return 'update'
        elif clean_sql.startswith('DELETE') or 'EXEC SQL DELETE' in clean_sql.upper():
            return 'delete'
        elif clean_sql.startswith('FETCH') or 'EXEC SQL FETCH' in clean_sql.upper():
            return 'fetch_into'
        
        return 'unknown'


# 편의 함수
def add_column_aliases(
    sql: str,
    output_vars: List[str],
    formatter: Callable[[str], str] = None
) -> str:
    """
    SQL 컬럼에 alias 추가 (편의 함수)
    
    Args:
        sql: SQL 문자열
        output_vars: 출력 변수 목록
        formatter: alias 변환 함수
    
    Returns:
        alias가 추가된 SQL
    """
    mapper = ColumnAliasMapper(alias_formatter=formatter)
    return mapper.add_aliases(sql, output_vars)
