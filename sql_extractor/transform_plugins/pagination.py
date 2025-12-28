"""
페이징 플러그인

커서 기반 SQL을 페이징 SQL로 변환합니다.
MySQL, Oracle, PostgreSQL 등 다양한 DB 방언을 지원합니다.
"""

import re
from typing import Dict, Any
from .base import SQLTransformPlugin


class PaginationPlugin(SQLTransformPlugin):
    """
    페이징 플러그인 기본 클래스
    
    커서 기반 SQL을 페이징 SQL로 변환합니다.
    DB별 구현은 하위 클래스에서 제공합니다.
    """
    
    name = "pagination_base"
    priority = 80  # alias 매핑 후에 실행
    
    # 페이징 파라미터 이름 (커스터마이징 가능)
    param_offset = "offset"
    param_limit = "limit"
    param_page = "page"
    param_page_size = "pageSize"
    
    def __init__(
        self,
        param_offset: str = None,
        param_limit: str = None,
        use_page_param: bool = False
    ):
        """
        초기화
        
        Args:
            param_offset: offset 파라미터 이름
            param_limit: limit 파라미터 이름
            use_page_param: page/pageSize 파라미터 사용 여부
        """
        if param_offset:
            self.param_offset = param_offset
        if param_limit:
            self.param_limit = param_limit
        self.use_page_param = use_page_param
    
    def can_transform(
        self, 
        sql: str, 
        sql_type: str, 
        metadata: Dict[str, Any]
    ) -> bool:
        """커서 기반 SELECT인 경우 변환"""
        if sql_type not in ['select', 'declare_cursor']:
            return False
        
        # 메타데이터에서 커서 기반 여부 확인
        if metadata.get('is_cursor_based', False):
            return True
        
        # 메타데이터에서 페이징 필요 여부 확인
        if metadata.get('needs_pagination', False):
            return True
        
        return False
    
    def transform(
        self, 
        sql: str, 
        sql_type: str, 
        metadata: Dict[str, Any]
    ) -> str:
        """하위 클래스에서 구현"""
        return sql
    
    def _get_offset_param(self) -> str:
        """offset 파라미터 반환"""
        if self.use_page_param:
            return f"(#{{{self.param_page}}} - 1) * #{{{self.param_page_size}}}"
        return f"#{{{self.param_offset}}}"
    
    def _get_limit_param(self) -> str:
        """limit 파라미터 반환"""
        if self.use_page_param:
            return f"#{{{self.param_page_size}}}"
        return f"#{{{self.param_limit}}}"


class MySQLPaginationPlugin(PaginationPlugin):
    """
    MySQL 페이징 플러그인
    
    SELECT ... LIMIT #{limit} OFFSET #{offset}
    """
    
    name = "mysql_pagination"
    
    def transform(
        self, 
        sql: str, 
        sql_type: str, 
        metadata: Dict[str, Any]
    ) -> str:
        """MySQL LIMIT/OFFSET 구문 추가"""
        # 이미 LIMIT이 있으면 스킵
        if re.search(r'\bLIMIT\b', sql, re.IGNORECASE):
            return sql
        
        # 끝의 세미콜론 제거
        sql = sql.rstrip(';').strip()
        
        limit_param = self._get_limit_param()
        offset_param = self._get_offset_param()
        
        return f"{sql} LIMIT {limit_param} OFFSET {offset_param}"


class PostgreSQLPaginationPlugin(PaginationPlugin):
    """
    PostgreSQL 페이징 플러그인
    
    SELECT ... LIMIT #{limit} OFFSET #{offset}
    """
    
    name = "postgresql_pagination"
    
    def transform(
        self, 
        sql: str, 
        sql_type: str, 
        metadata: Dict[str, Any]
    ) -> str:
        """PostgreSQL LIMIT/OFFSET 구문 추가 (MySQL과 동일)"""
        if re.search(r'\bLIMIT\b', sql, re.IGNORECASE):
            return sql
        
        sql = sql.rstrip(';').strip()
        
        limit_param = self._get_limit_param()
        offset_param = self._get_offset_param()
        
        return f"{sql} LIMIT {limit_param} OFFSET {offset_param}"


class OraclePaginationPlugin(PaginationPlugin):
    """
    Oracle 페이징 플러그인
    
    Oracle 12c 이전: ROWNUM 서브쿼리 래핑
    Oracle 12c 이후: OFFSET/FETCH 구문
    """
    
    name = "oracle_pagination"
    use_12c_syntax = False  # True면 12c 이후 구문 사용
    
    def __init__(
        self,
        param_offset: str = None,
        param_limit: str = None,
        use_page_param: bool = False,
        use_12c_syntax: bool = False
    ):
        super().__init__(param_offset, param_limit, use_page_param)
        self.use_12c_syntax = use_12c_syntax
    
    def transform(
        self, 
        sql: str, 
        sql_type: str, 
        metadata: Dict[str, Any]
    ) -> str:
        """Oracle 페이징 구문 추가"""
        # 이미 ROWNUM 또는 FETCH가 있으면 스킵
        if re.search(r'\bROWNUM\b|\bFETCH\s+FIRST\b|\bOFFSET\b', sql, re.IGNORECASE):
            return sql
        
        sql = sql.rstrip(';').strip()
        
        if self.use_12c_syntax:
            return self._transform_12c(sql)
        else:
            return self._transform_legacy(sql)
    
    def _transform_12c(self, sql: str) -> str:
        """Oracle 12c OFFSET/FETCH 구문"""
        offset_param = self._get_offset_param()
        limit_param = self._get_limit_param()
        
        return f"{sql} OFFSET {offset_param} ROWS FETCH NEXT {limit_param} ROWS ONLY"
    
    def _transform_legacy(self, sql: str) -> str:
        """Oracle ROWNUM 서브쿼리 래핑"""
        offset_param = self._get_offset_param()
        limit_param = self._get_limit_param()
        
        # 시작 = offset + 1, 끝 = offset + limit
        start_param = f"({offset_param} + 1)"
        end_param = f"({offset_param} + {limit_param})"
        
        return f"""SELECT * FROM (
    SELECT inner_query.*, ROWNUM AS rn FROM (
        {sql}
    ) inner_query WHERE ROWNUM <= {end_param}
) WHERE rn >= {start_param}"""


class DB2PaginationPlugin(PaginationPlugin):
    """
    DB2 페이징 플러그인
    
    SELECT ... FETCH FIRST #{limit} ROWS ONLY
    with offset: ROW_NUMBER() 사용
    """
    
    name = "db2_pagination"
    
    def transform(
        self, 
        sql: str, 
        sql_type: str, 
        metadata: Dict[str, Any]
    ) -> str:
        """DB2 페이징 구문 추가"""
        if re.search(r'\bFETCH\s+FIRST\b', sql, re.IGNORECASE):
            return sql
        
        sql = sql.rstrip(';').strip()
        
        offset_param = self._get_offset_param()
        limit_param = self._get_limit_param()
        
        # offset이 필요한 경우 ROW_NUMBER() 사용
        if metadata.get('needs_offset', True):
            start_param = f"({offset_param} + 1)"
            end_param = f"({offset_param} + {limit_param})"
            
            return f"""SELECT * FROM (
    SELECT inner_query.*, ROW_NUMBER() OVER() AS rn FROM (
        {sql}
    ) AS inner_query
) AS paged_query WHERE rn BETWEEN {start_param} AND {end_param}"""
        else:
            # offset 불필요시 FETCH FIRST만 사용
            return f"{sql} FETCH FIRST {limit_param} ROWS ONLY"
