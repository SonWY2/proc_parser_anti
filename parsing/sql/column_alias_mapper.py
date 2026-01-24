"""
Column Alias Mapper 모듈

SELECT 컬럼에 AS alias를 추가하여 MyBatis 변수 매핑을 지원합니다.

지원하는 SQL 구문:
- SELECT ... INTO :vars
- DECLARE CURSOR FOR SELECT ...
- INSERT ... RETURNING ... INTO :vars (Oracle)
- UPDATE ... RETURNING ... INTO :vars (Oracle)
- DELETE ... RETURNING ... INTO :vars (Oracle)

Enhanced Features (v2):
- WITH (CTE) 절 지원
- 서브쿼리 내부 SELECT 제외
- UNION/INTERSECT/EXCEPT 처리
- SELECT DISTINCT/ALL/TOP 지원
- CASE WHEN 표현식 처리
- Oracle CONNECT BY/START WITH 지원
- 주석 앞 SQL 타입 감지
"""

import re
from typing import List, Optional, Callable, Tuple, Dict
from dataclasses import dataclass, field
from enum import Enum

# sqlglot 사용 시도, 없으면 regex fallback
try:
    import sqlglot
    from sqlglot import exp
    HAS_SQLGLOT = True
except ImportError:
    HAS_SQLGLOT = False


# ============================================================================
# Token Types and Data Classes
# ============================================================================

class TokenType(Enum):
    """SQL 토큰 타입"""
    KEYWORD = 'keyword'
    STRING = 'string'
    COMMENT = 'comment'
    HOST_VAR = 'host_var'
    IDENTIFIER = 'identifier'
    NUMBER = 'number'
    OPERATOR = 'operator'
    LPAREN = 'lparen'
    RPAREN = 'rparen'
    COMMA = 'comma'
    OTHER = 'other'
    WHITESPACE = 'whitespace'


@dataclass
class SqlToken:
    """SQL 토큰 정보"""
    type: TokenType
    value: str
    start: int
    end: int

    def __repr__(self):
        return f"Token({self.type.value}, '{self.value[:20]}...')" if len(self.value) > 20 else f"Token({self.type.value}, '{self.value}')"


@dataclass
class AliasMapping:
    """컬럼-alias 매핑 정보"""
    original_column: str
    alias: str
    position: int


# ============================================================================
# SQL Tokenizer
# ============================================================================

class SqlTokenizer:
    """
    SQL 문자열을 토큰으로 분리하는 토크나이저
    
    문자열 리터럴, 주석, 호스트 변수 등을 올바르게 식별합니다.
    """
    
    # SQL 키워드 목록 (대소문자 구분 없이 매칭)
    KEYWORDS = {
        'SELECT', 'FROM', 'WHERE', 'INTO', 'VALUES', 'INSERT', 'UPDATE', 'DELETE',
        'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'FULL', 'CROSS', 'ON',
        'AND', 'OR', 'NOT', 'IN', 'EXISTS', 'BETWEEN', 'LIKE', 'IS', 'NULL',
        'ORDER', 'BY', 'GROUP', 'HAVING', 'LIMIT', 'OFFSET', 'DISTINCT', 'ALL',
        'UNION', 'INTERSECT', 'EXCEPT', 'AS', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
        'WITH', 'RECURSIVE', 'DECLARE', 'CURSOR', 'FOR', 'FETCH', 'OPEN', 'CLOSE',
        'RETURNING', 'TOP', 'FIRST', 'ROWNUM', 'ROWID',
        'START', 'CONNECT', 'PRIOR', 'LEVEL', 'NOCYCLE', 'SIBLINGS',
        'PIVOT', 'UNPIVOT', 'EXEC', 'SQL', 'SET', 'CREATE', 'DROP', 'ALTER', 'TRUNCATE',
        'MERGE', 'USING', 'MATCHED', 'WHENEVER', 'CONTINUE', 'GOTO', 'STOP'
    }
    
    def tokenize(self, sql: str) -> List[SqlToken]:
        """
        SQL 문자열을 토큰 리스트로 변환
        
        Args:
            sql: SQL 문자열
            
        Returns:
            토큰 리스트
        """
        tokens = []
        pos = 0
        length = len(sql)
        
        while pos < length:
            # 공백
            if sql[pos].isspace():
                start = pos
                while pos < length and sql[pos].isspace():
                    pos += 1
                tokens.append(SqlToken(TokenType.WHITESPACE, sql[start:pos], start, pos))
                continue
            
            # 한 줄 주석 (--)
            if sql[pos:pos+2] == '--':
                start = pos
                pos += 2
                while pos < length and sql[pos] != '\n':
                    pos += 1
                tokens.append(SqlToken(TokenType.COMMENT, sql[start:pos], start, pos))
                continue
            
            # 블록 주석 (/* */)
            if sql[pos:pos+2] == '/*':
                start = pos
                pos += 2
                while pos < length - 1 and sql[pos:pos+2] != '*/':
                    pos += 1
                pos += 2  # skip */
                tokens.append(SqlToken(TokenType.COMMENT, sql[start:pos], start, pos))
                continue
            
            # 문자열 리터럴 (')
            if sql[pos] == "'":
                start = pos
                pos += 1
                while pos < length:
                    if sql[pos] == "'" and pos + 1 < length and sql[pos+1] == "'":
                        pos += 2  # escaped quote
                    elif sql[pos] == "'":
                        pos += 1
                        break
                    else:
                        pos += 1
                tokens.append(SqlToken(TokenType.STRING, sql[start:pos], start, pos))
                continue
            
            # 문자열 리터럴 (")  - 일부 DB에서 사용
            if sql[pos] == '"':
                start = pos
                pos += 1
                while pos < length and sql[pos] != '"':
                    pos += 1
                pos += 1  # skip closing quote
                tokens.append(SqlToken(TokenType.STRING, sql[start:pos], start, pos))
                continue
            
            # 호스트 변수 (:var 또는 :var:indicator)
            if sql[pos] == ':':
                # 시간 포맷 체크 (12:30:00 형태는 호스트 변수가 아님)
                if pos > 0 and sql[pos-1].isdigit():
                    tokens.append(SqlToken(TokenType.OPERATOR, ':', pos, pos+1))
                    pos += 1
                    continue
                
                start = pos
                pos += 1
                # 변수명 추출
                while pos < length and (sql[pos].isalnum() or sql[pos] in '_.[]:'):
                    if sql[pos] == ':':  # indicator variable
                        pos += 1
                        while pos < length and (sql[pos].isalnum() or sql[pos] == '_'):
                            pos += 1
                        break
                    pos += 1
                tokens.append(SqlToken(TokenType.HOST_VAR, sql[start:pos], start, pos))
                continue
            
            # 괄호
            if sql[pos] == '(':
                tokens.append(SqlToken(TokenType.LPAREN, '(', pos, pos+1))
                pos += 1
                continue
            
            if sql[pos] == ')':
                tokens.append(SqlToken(TokenType.RPAREN, ')', pos, pos+1))
                pos += 1
                continue
            
            # 쉼표
            if sql[pos] == ',':
                tokens.append(SqlToken(TokenType.COMMA, ',', pos, pos+1))
                pos += 1
                continue
            
            # 숫자
            if sql[pos].isdigit():
                start = pos
                while pos < length and (sql[pos].isdigit() or sql[pos] == '.'):
                    pos += 1
                tokens.append(SqlToken(TokenType.NUMBER, sql[start:pos], start, pos))
                continue
            
            # 식별자 또는 키워드
            if sql[pos].isalpha() or sql[pos] == '_':
                start = pos
                while pos < length and (sql[pos].isalnum() or sql[pos] == '_'):
                    pos += 1
                value = sql[start:pos]
                if value.upper() in self.KEYWORDS:
                    tokens.append(SqlToken(TokenType.KEYWORD, value, start, pos))
                else:
                    tokens.append(SqlToken(TokenType.IDENTIFIER, value, start, pos))
                continue
            
            # 연산자 및 기타
            tokens.append(SqlToken(TokenType.OTHER, sql[pos], pos, pos+1))
            pos += 1
        
        return tokens

    def rebuild_sql(self, tokens: List[SqlToken]) -> str:
        """토큰 리스트를 SQL 문자열로 재구성"""
        return ''.join(t.value for t in tokens)


# ============================================================================
# Statement Parser
# ============================================================================

class StatementParser:
    """
    SQL 문장 구조를 분석하는 파서
    
    최상위 SELECT 식별, CTE 분리, 서브쿼리 감지 등을 수행합니다.
    """
    
    def __init__(self, tokenizer: SqlTokenizer = None):
        self.tokenizer = tokenizer or SqlTokenizer()
    
    def find_main_select_columns(self, sql: str) -> Tuple[int, int, str]:
        """
        최상위 SELECT의 컬럼 영역을 찾습니다.
        
        서브쿼리, CTE 내부의 SELECT는 무시하고 최종 결과를 반환하는 
        메인 SELECT의 컬럼 부분만 반환합니다.
        
        Args:
            sql: SQL 문자열
            
        Returns:
            (컬럼 시작 위치, 컬럼 끝 위치, 컬럼 문자열)
            찾지 못하면 (-1, -1, '')
        """
        tokens = self.tokenizer.tokenize(sql)
        
        # CTE (WITH) 절 건너뛰기
        main_start = self._skip_cte(tokens)
        
        # 최상위 SELECT 찾기 (괄호 depth = 0)
        select_idx = self._find_top_level_select(tokens, main_start)
        if select_idx < 0:
            return (-1, -1, '')
        
        # SELECT 다음의 수식어 건너뛰기 (DISTINCT, ALL, TOP N)
        col_start_idx = self._skip_select_modifiers(tokens, select_idx + 1)
        if col_start_idx < 0:
            return (-1, -1, '')
        
        # FROM/INTO/WHERE/UNION 등 종료 키워드 찾기 (괄호 depth = 0)
        col_end_idx = self._find_column_end(tokens, col_start_idx)
        if col_end_idx < 0:
            col_end_idx = len(tokens)
        
        # 위치 계산
        start_pos = tokens[col_start_idx].start
        
        # col_end_idx가 가리키는 토큰의 시작 위치를 사용해야 함 (FROM 등)
        # 만약 col_end_idx가 len(tokens)라면 문자열 끝
        if col_end_idx < len(tokens):
            end_pos = tokens[col_end_idx].start
        else:
            end_pos = len(sql)
            
        columns_str = sql[start_pos:end_pos]
        
        return (start_pos, end_pos, columns_str)
    
    def split_cte(self, sql: str) -> Tuple[str, str]:
        """
        WITH 절과 메인 쿼리를 분리합니다.
        
        Args:
            sql: SQL 문자열
            
        Returns:
            (CTE 부분, 메인 쿼리 부분)
        """
        tokens = self.tokenizer.tokenize(sql)
        
        # WITH 키워드 찾기
        for i, token in enumerate(tokens):
            if token.type == TokenType.KEYWORD and token.value.upper() == 'WITH':
                break
        else:
            return ('', sql)
        
        # CTE 끝 찾기 - 마지막 괄호 닫힘 후 SELECT/INSERT/UPDATE/DELETE
        paren_depth = 0
        cte_end = -1
        
        for j, token in enumerate(tokens[i+1:], start=i+1):
            if token.type == TokenType.LPAREN:
                paren_depth += 1
            elif token.type == TokenType.RPAREN:
                paren_depth -= 1
            elif paren_depth == 0 and token.type == TokenType.KEYWORD:
                if token.value.upper() in ('SELECT', 'INSERT', 'UPDATE', 'DELETE'):
                    cte_end = token.start
                    break
        
        if cte_end < 0:
            return ('', sql)
        
        return (sql[:cte_end], sql[cte_end:])
    
    def get_first_union_part(self, sql: str) -> str:
        """
        UNION/INTERSECT/EXCEPT 전 첫 번째 SELECT 부분만 반환
        
        Args:
            sql: SQL 문자열
            
        Returns:
            첫 번째 SELECT 부분
        """
        tokens = self.tokenizer.tokenize(sql)
        paren_depth = 0
        
        for i, token in enumerate(tokens):
            if token.type == TokenType.LPAREN:
                paren_depth += 1
            elif token.type == TokenType.RPAREN:
                paren_depth -= 1
            elif paren_depth == 0 and token.type == TokenType.KEYWORD:
                if token.value.upper() in ('UNION', 'INTERSECT', 'EXCEPT'):
                    return sql[:token.start].strip()
        
        return sql
    
    def is_subquery_context(self, sql: str, position: int) -> bool:
        """
        해당 위치가 서브쿼리 내부인지 확인
        
        Args:
            sql: SQL 문자열
            position: 확인할 위치
            
        Returns:
            서브쿼리 내부이면 True
        """
        tokens = self.tokenizer.tokenize(sql)
        paren_depth = 0
        
        for token in tokens:
            if token.start >= position:
                break
            if token.type == TokenType.LPAREN:
                paren_depth += 1
            elif token.type == TokenType.RPAREN:
                paren_depth -= 1
        
        return paren_depth > 0
    
    def _skip_cte(self, tokens: List[SqlToken]) -> int:
        """CTE (WITH) 절을 건너뛰고 메인 쿼리 시작 인덱스 반환"""
        for i, token in enumerate(tokens):
            if token.type == TokenType.KEYWORD and token.value.upper() == 'WITH':
                # CTE 끝까지 건너뛰기
                paren_depth = 0
                for j, t in enumerate(tokens[i+1:], start=i+1):
                    if t.type == TokenType.LPAREN:
                        paren_depth += 1
                    elif t.type == TokenType.RPAREN:
                        paren_depth -= 1
                    elif paren_depth == 0 and t.type == TokenType.KEYWORD:
                        if t.value.upper() in ('SELECT', 'INSERT', 'UPDATE', 'DELETE'):
                            return j
                return i  # WITH만 있고 끝나지 않은 경우
        return 0
    
    def _find_top_level_select(self, tokens: List[SqlToken], start_idx: int = 0) -> int:
        """괄호 depth=0인 최상위 SELECT 인덱스 반환"""
        paren_depth = 0
        
        for i, token in enumerate(tokens[start_idx:], start=start_idx):
            if token.type == TokenType.LPAREN:
                paren_depth += 1
            elif token.type == TokenType.RPAREN:
                paren_depth -= 1
            elif paren_depth == 0 and token.type == TokenType.KEYWORD:
                if token.value.upper() == 'SELECT':
                    return i
        
        return -1
    
    def _skip_select_modifiers(self, tokens: List[SqlToken], start_idx: int) -> int:
        """SELECT 다음의 DISTINCT, ALL, TOP N 등을 건너뛰고 실제 컬럼 시작 인덱스 반환"""
        i = start_idx
        
        while i < len(tokens):
            token = tokens[i]
            
            # 공백 건너뛰기
            if token.type == TokenType.WHITESPACE:
                i += 1
                continue
            
            # DISTINCT, ALL 건너뛰기
            if token.type == TokenType.KEYWORD and token.value.upper() in ('DISTINCT', 'ALL'):
                i += 1
                continue
            
            # TOP N 건너뛰기 (SQL Server)
            if token.type == TokenType.KEYWORD and token.value.upper() == 'TOP':
                i += 1
                # 숫자 또는 괄호 건너뛰기
                while i < len(tokens):
                    if tokens[i].type == TokenType.WHITESPACE:
                        i += 1
                    elif tokens[i].type == TokenType.NUMBER:
                        i += 1
                        break
                    elif tokens[i].type == TokenType.LPAREN:
                        # TOP (N) 형태
                        paren_depth = 1
                        i += 1
                        while i < len(tokens) and paren_depth > 0:
                            if tokens[i].type == TokenType.LPAREN:
                                paren_depth += 1
                            elif tokens[i].type == TokenType.RPAREN:
                                paren_depth -= 1
                            i += 1
                        break
                    else:
                        break
                continue
            
            # 실제 컬럼 시작
            return i
        
        return -1
    
    def _find_column_end(self, tokens: List[SqlToken], start_idx: int) -> int:
        """
        컬럼 영역 종료 인덱스 반환
        
        FROM, INTO, WHERE, UNION, INTERSECT, EXCEPT 등의 키워드를 만나면 종료
        """
        paren_depth = 0
        end_keywords = {'FROM', 'INTO', 'WHERE', 'UNION', 'INTERSECT', 'EXCEPT', 
                        'ORDER', 'GROUP', 'HAVING', 'LIMIT', 'FOR'}
        
        for i, token in enumerate(tokens[start_idx:], start=start_idx):
            if token.type == TokenType.LPAREN:
                paren_depth += 1
            elif token.type == TokenType.RPAREN:
                paren_depth -= 1
            elif paren_depth == 0 and token.type == TokenType.KEYWORD:
                if token.value.upper() in end_keywords:
                    return i
        
        return len(tokens)


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
    
    # 인디케이터 변수 제거 (:var:ind -> var)
    if ':' in clean_name:
        clean_name = clean_name.split(':')[0]
    
    # 배열 인덱스 제거 (:arr[i] -> arr)
    if '[' in clean_name:
        clean_name = clean_name.split('[')[0]
    
    # 구조체 필드 처리 (:struct.field -> struct_field)
    clean_name = clean_name.replace('.', '_')
    
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


# ============================================================================
# Column Alias Mapper (Enhanced)
# ============================================================================

class ColumnAliasMapper:
    """
    SQL 컬럼에 alias를 추가하는 매퍼 (Enhanced v2)
    
    MyBatis에서 ResultMap 없이 직접 매핑하려면 SELECT 컬럼명과 
    Java 변수명이 일치해야 합니다. 이 클래스는 INTO 절의 변수를 기반으로
    SELECT 컬럼에 AS alias를 추가합니다.
    
    Supports:
    - WITH (CTE) 절
    - 서브쿼리 내부 SELECT 제외
    - UNION/INTERSECT/EXCEPT
    - SELECT DISTINCT/ALL/TOP
    - CASE WHEN 표현식
    - Oracle CONNECT BY
    
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
        self._tokenizer = SqlTokenizer()
        self._parser = StatementParser(self._tokenizer)
    
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
            # Oracle 특수 구문은 sqlglot이 기본 dialect로 처리하지 못할 수 있으므로 regex fallback 사용
            oracle_syntax = {'CONNECT BY', 'START WITH', 'PIVOT', 'UNPIVOT'}
            has_oracle_syntax = any(kw in sql.upper() for kw in oracle_syntax)
            
            if not has_oracle_syntax:
                result = self._add_aliases_with_sqlglot(sql, output_vars)
                if result != sql:  # sqlglot이 성공한 경우
                    return result
        
        # Enhanced regex 기반 처리
        return self._add_aliases_with_regex_enhanced(sql, output_vars)
    
    def extract_select_columns(self, sql: str) -> List[str]:
        """
        최상위 SELECT 컬럼 추출
        
        Args:
            sql: SQL 문자열
        
        Returns:
            컬럼명 목록
        """
        if self._use_sqlglot:
            result = self._extract_columns_with_sqlglot(sql)
            if result:
                return result
        
        return self._extract_columns_with_regex_enhanced(sql)
    
    def needs_alias(self, sql_type: str) -> bool:
        """해당 SQL 타입이 alias 처리가 필요한지 확인"""
        return sql_type in self.ALIASABLE_TYPES or sql_type in self.RETURNING_TYPES
    
    # =========================================================================
    # sqlglot 기반 구현
    # =========================================================================
    
    def _add_aliases_with_sqlglot(self, sql: str, output_vars: List[str]) -> str:
        """sqlglot을 사용하여 alias 추가"""
        if not HAS_SQLGLOT:
            return sql
        
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
            
            # INTO 절 임시 제거 (sqlglot이 파싱하지 못할 수 있음)
            into_removed, into_clause = self._remove_into_clause_temp(clean_sql)
            
            # SQL 파싱
            parsed = sqlglot.parse_one(into_removed)
            
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
            # 파싱 실패시 원본 반환 (regex fallback으로 이동)
            return sql
    
    def _extract_columns_with_sqlglot(self, sql: str) -> List[str]:
        """sqlglot을 사용하여 컬럼 추출"""
        if not HAS_SQLGLOT:
            return []
        
        try:
            clean_sql = re.sub(r'^\s*EXEC\s+SQL\s+', '', sql, flags=re.IGNORECASE)
            clean_sql = clean_sql.rstrip(';').strip()
            
            # INTO 절 제거
            into_removed, _ = self._remove_into_clause_temp(clean_sql)
            
            parsed = sqlglot.parse_one(into_removed)
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
            return []
    
    def _remove_into_clause_temp(self, sql: str) -> Tuple[str, str]:
        """INTO 절을 임시 제거 (sqlglot 파싱용)"""
        into_match = re.search(
            r'\bINTO\s+[^F]+(?=\bFROM\b)',
            sql,
            re.IGNORECASE | re.DOTALL
        )
        if into_match:
            return sql[:into_match.start()] + sql[into_match.end():], into_match.group()
        return sql, ''
    
    # =========================================================================
    # Enhanced Regex 기반 구현
    # =========================================================================
    
    def _add_aliases_with_regex_enhanced(self, sql: str, output_vars: List[str]) -> str:
        """
        고도화된 정규식 기반 alias 추가
        
        CTE, 서브쿼리, UNION 등을 올바르게 처리합니다.
        """
        # EXEC SQL 제거
        clean_sql = re.sub(r'^\s*EXEC\s+SQL\s+', '', sql, flags=re.IGNORECASE)
        
        # CURSOR FOR 처리
        cursor_match = re.search(r'(DECLARE\s+\w+\s+CURSOR\s+FOR\s+)', clean_sql, re.IGNORECASE)
        cursor_prefix = ''
        if cursor_match:
            cursor_prefix = cursor_match.group(1)
            clean_sql = clean_sql[cursor_match.end():]
        
        # CTE (WITH) 절 분리
        cte_part, main_part = self._parser.split_cte(clean_sql)
        
        # UNION 처리 - 첫 번째 SELECT만 처리
        first_select = self._parser.get_first_union_part(main_part)
        remaining_part = main_part[len(first_select):]
        
        # INTO 절 제거
        first_select_no_into = self._remove_into_clause(first_select)
        
        # 최상위 SELECT 컬럼 영역 찾기
        col_start, col_end, columns_str = self._parser.find_main_select_columns(first_select_no_into)
        
        if col_start < 0:
            return sql  # SELECT 컬럼을 찾지 못함
        
        # 컬럼 분리
        columns = self._split_columns_robust(columns_str)
        
        # alias 추가
        new_columns = []
        for i, col_str in enumerate(columns):
            if i < len(output_vars):
                alias = self.alias_formatter(output_vars[i])
                
                # 이미 alias가 있는 경우 처리 (overwrite_existing=False면 스킵)
                if self._has_alias(col_str) and not self.overwrite_existing:
                    new_columns.append(col_str)
                    continue
                
                # 강건한 alias 삽입: 마지막 '의미 있는' 토큰 뒤에 삽입
                # (주석이나 줄바꿈 등이 뒤에 오는 경우를 고려)
                col_tokens = self._tokenizer.tokenize(col_str)
                last_meaningful_idx = -1
                
                # 뒤에서부터 주석/공백이 아닌 토큰 찾기
                for j in range(len(col_tokens) - 1, -1, -1):
                    if col_tokens[j].type not in (TokenType.WHITESPACE, TokenType.COMMENT):
                        last_meaningful_idx = j
                        break
                
                if last_meaningful_idx >= 0:
                    # 기존에 다른 alias가 있었다면 교체 시도
                    if self._has_alias(col_str) and self.overwrite_existing:
                        # 이미 alias가 있는 토큰들을 찾아 교체하는 로직
                        col_str = self._replace_alias(col_str, alias)
                    else:
                        # 마지막 의미 있는 토큰 뒤에 ' AS alias' 추가
                        # 토큰 기반 재구성
                        prefix_tokens = col_tokens[:last_meaningful_idx + 1]
                        suffix_tokens = col_tokens[last_meaningful_idx + 1:]
                        
                        # ' AS alias' 토큰 추가
                        alias_tokens = [
                            SqlToken(TokenType.WHITESPACE, ' ', -1, -1),
                            SqlToken(TokenType.KEYWORD, 'AS', -1, -1),
                            SqlToken(TokenType.WHITESPACE, ' ', -1, -1),
                            SqlToken(TokenType.IDENTIFIER, alias, -1, -1)
                        ]
                        
                        new_col_tokens = prefix_tokens + alias_tokens + suffix_tokens
                        col_str = self._tokenizer.rebuild_sql(new_col_tokens)
                
            new_columns.append(col_str)
        
        # SQL 재조립
        # [주의] 컬럼 사이에 원래 있던 콤마 위치의 공백 등도 최대한 보존하려면 join 시 주의
        # 여기서는 단순히 ','로 합치지만, 각 컬럼 문자열이 이미 앞뒤 공백을 포함하고 있으므로 비교적 안전함
        new_columns_str = ','.join(new_columns)
        
        # SQL 재조립
        result = cursor_prefix + cte_part + first_select_no_into[:col_start] + new_columns_str + first_select_no_into[col_end:] + remaining_part
        
        return result.strip()
    
    def _extract_columns_with_regex_enhanced(self, sql: str) -> List[str]:
        """고도화된 정규식 기반 컬럼 추출"""
        clean_sql = re.sub(r'^\s*EXEC\s+SQL\s+', '', sql, flags=re.IGNORECASE)
        
        # INTO 절 제거
        clean_sql = self._remove_into_clause(clean_sql)
        
        # 컬럼 영역 찾기
        _, _, columns_str = self._parser.find_main_select_columns(clean_sql)
        
        if not columns_str:
            return []
        
        return self._split_columns_robust(columns_str)
    
    def _split_columns_robust(self, columns_str: str) -> List[str]:
        """
        컬럼 문자열을 견고하게 분리
        
        괄호, CASE WHEN, 문자열 리터럴 등을 고려합니다.
        """
        tokens = self._tokenizer.tokenize(columns_str)
        
        columns = []
        current_tokens = []
        paren_depth = 0
        case_depth = 0
        
        for token in tokens:
            if token.type == TokenType.LPAREN:
                paren_depth += 1
                current_tokens.append(token)
            elif token.type == TokenType.RPAREN:
                paren_depth -= 1
                current_tokens.append(token)
            elif token.type == TokenType.KEYWORD and token.value.upper() == 'CASE':
                case_depth += 1
                current_tokens.append(token)
            elif token.type == TokenType.KEYWORD and token.value.upper() == 'END':
                if case_depth > 0:
                    case_depth -= 1
                current_tokens.append(token)
            elif token.type == TokenType.COMMA and paren_depth == 0 and case_depth == 0:
                # 컬럼 구분자
                col_str = self._tokenizer.rebuild_sql(current_tokens).strip()
                if col_str:
                    columns.append(col_str)
                current_tokens = []
            else:
                current_tokens.append(token)
        
        # 마지막 컬럼
        if current_tokens:
            col_str = self._tokenizer.rebuild_sql(current_tokens).strip()
            if col_str:
                columns.append(col_str)
        
        return columns
    
    def _remove_into_clause(self, sql: str) -> str:
        """INTO 절 제거"""
        # INTO ... FROM 패턴
        result = re.sub(
            r'\bINTO\s+[^F]+(?=\bFROM\b)',
            '',
            sql,
            flags=re.IGNORECASE | re.DOTALL
        )
        
        # INTO ... WHERE 패턴 (FROM 없는 경우)
        if 'FROM' not in sql.upper():
            result = re.sub(
                r'\bINTO\s+[^W]+(?=\bWHERE\b)',
                '',
                result,
                flags=re.IGNORECASE | re.DOTALL
            )
        
        return result
    
    def _has_alias(self, column: str) -> bool:
        """컬럼에 이미 AS alias가 있는지 확인"""
        # 문자열 리터럴 내의 AS는 제외
        tokens = self._tokenizer.tokenize(column)
        
        for i, token in enumerate(tokens):
            if token.type == TokenType.KEYWORD and token.value.upper() == 'AS':
                # 다음 토큰이 식별자인지 확인
                for j in range(i + 1, len(tokens)):
                    if tokens[j].type == TokenType.WHITESPACE:
                        continue
                    if tokens[j].type in (TokenType.IDENTIFIER, TokenType.KEYWORD):
                        return True
                    break
        
        return False
    
    def _replace_alias(self, column: str, new_alias: str) -> str:
        """기존 alias를 새 alias로 교체"""
        return re.sub(
            r'\bAS\s+\w+\s*$',
            f'AS {new_alias}',
            column,
            flags=re.IGNORECASE
        )
    
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
        columns = self._split_columns_robust(columns_str)
        
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
        """SQL 타입 자동 감지 (주석 제거 후)"""
        # 주석 제거
        clean_sql = self._strip_comments(sql)
        clean_sql = clean_sql.upper().strip()
        
        # EXEC SQL 제거
        clean_sql = re.sub(r'^EXEC\s+SQL\s+', '', clean_sql).strip()
        
        # FOR :count 제거 (배열 DML)
        clean_sql = re.sub(r'^FOR\s+:\w+\s+', '', clean_sql).strip()
        
        # CTE (WITH)로 시작하면 SELECT
        if clean_sql.startswith('WITH'):
            return 'select'
        elif clean_sql.startswith('SELECT'):
            return 'select'
        elif 'DECLARE' in clean_sql and 'CURSOR' in clean_sql:
            return 'declare_cursor'
        elif clean_sql.startswith('INSERT'):
            return 'insert'
        elif clean_sql.startswith('UPDATE'):
            return 'update'
        elif clean_sql.startswith('DELETE'):
            return 'delete'
        elif clean_sql.startswith('FETCH'):
            return 'fetch_into'
        
        return 'unknown'
    
    def _strip_comments(self, sql: str) -> str:
        """SQL에서 주석 제거"""
        tokens = self._tokenizer.tokenize(sql)
        result = []
        for token in tokens:
            if token.type != TokenType.COMMENT:
                result.append(token.value)
        return ''.join(result)


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
