"""
커서 SQL 병합 모듈

DECLARE CURSOR + OPEN + FETCH INTO + CLOSE 문을 
하나의 MyBatis SELECT 문으로 병합합니다.

기존 CursorRelationshipPlugin 로직을 sql_extractor로 통합.
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class CursorGroup:
    """커서 관련 SQL 그룹"""
    cursor_name: str
    declare_sql: Dict
    open_sql: Optional[Dict] = None
    fetch_sqls: List[Dict] = field(default_factory=list)
    close_sql: Optional[Dict] = None


@dataclass  
class MergedCursorSQL:
    """병합된 커서 SQL"""
    cursor_name: str
    merged_sql: str
    original_declare: str
    original_fetch: str
    input_vars: List[str]
    output_vars: List[str]
    is_loop_based: bool = False


class CursorMerger:
    """
    커서 관련 SQL을 하나의 SELECT 문으로 병합
    
    Example:
        merger = CursorMerger()
        groups = merger.find_cursor_groups(sql_blocks)
        for group in groups:
            merged = merger.merge(group)
    """
    
    def find_cursor_groups(self, sql_blocks: List[Dict]) -> List[CursorGroup]:
        """
        SQL 블록들에서 커서 그룹 찾기
        
        Args:
            sql_blocks: SQL 블록 목록 (sql_type, sql, line_start 등 포함)
        
        Returns:
            CursorGroup 목록
        """
        groups = []
        cursor_declares = {}
        
        # 1단계: DECLARE CURSOR 찾기
        for block in sql_blocks:
            sql_type = block.get('sql_type', '').lower()
            if sql_type == 'declare_cursor':
                cursor_name = self._extract_cursor_name(block)
                if cursor_name:
                    cursor_declares[cursor_name] = CursorGroup(
                        cursor_name=cursor_name,
                        declare_sql=block
                    )
        
        # 2단계: 관련 OPEN, FETCH, CLOSE 찾기
        for block in sql_blocks:
            sql_type = block.get('sql_type', '').lower()
            sql_text = block.get('sql', '') or block.get('text', '')
            
            for cursor_name, group in cursor_declares.items():
                if cursor_name.upper() in sql_text.upper():
                    if sql_type == 'open':
                        group.open_sql = block
                    elif sql_type in ['fetch_into', 'fetch']:
                        group.fetch_sqls.append(block)
                    elif sql_type == 'close':
                        group.close_sql = block
        
        return list(cursor_declares.values())
    
    def merge(self, group: CursorGroup) -> MergedCursorSQL:
        """
        커서 그룹을 하나의 SELECT 문으로 병합
        
        Args:
            group: CursorGroup 객체
        
        Returns:
            MergedCursorSQL 객체
        """
        # DECLARE에서 기본 쿼리 추출
        declare_sql = group.declare_sql.get('sql', '') or group.declare_sql.get('text', '')
        base_query = self._extract_cursor_query(declare_sql)
        
        # FETCH에서 출력 변수 추출
        output_vars = []
        original_fetch = ""
        for fetch in group.fetch_sqls:
            fetch_sql = fetch.get('sql', '') or fetch.get('text', '')
            original_fetch = fetch_sql
            vars_from_fetch = self._extract_into_vars(fetch_sql)
            output_vars.extend(vars_from_fetch)
        
        # 중복 제거
        output_vars = list(dict.fromkeys(output_vars))
        
        # 입력 변수 추출 (WHERE 절 등)
        input_vars = self._extract_input_vars(base_query)
        
        # INTO 절 생성 및 삽입
        merged_sql = base_query
        if output_vars:
            into_clause = "INTO " + ", ".join([f":{v}" for v in output_vars])
            merged_sql = self._insert_into_clause(base_query, into_clause)
        
        return MergedCursorSQL(
            cursor_name=group.cursor_name,
            merged_sql=merged_sql,
            original_declare=declare_sql,
            original_fetch=original_fetch,
            input_vars=input_vars,
            output_vars=output_vars,
            is_loop_based=len(group.fetch_sqls) > 1
        )
    
    def _extract_cursor_name(self, block: Dict) -> Optional[str]:
        """DECLARE 문에서 커서 이름 추출"""
        sql = block.get('sql', '') or block.get('text', '')
        match = re.search(r'DECLARE\s+(\w+)\s+CURSOR', sql, re.IGNORECASE)
        return match.group(1) if match else None
    
    def _extract_cursor_query(self, declare_sql: str) -> str:
        """DECLARE CURSOR FOR 뒤의 쿼리 추출"""
        match = re.search(r'CURSOR\s+FOR\s+(.+)', declare_sql, re.IGNORECASE | re.DOTALL)
        if match:
            query = match.group(1).strip()
            # EXEC SQL 제거
            query = re.sub(r'^\s*EXEC\s+SQL\s+', '', query, flags=re.IGNORECASE)
            # 끝의 세미콜론 제거
            query = query.rstrip(';').strip()
            return query
        return ""
    
    def _extract_into_vars(self, fetch_sql: str) -> List[str]:
        """FETCH ... INTO 문에서 변수 추출"""
        match = re.search(r'INTO\s+(.+?)(?:;|$)', fetch_sql, re.IGNORECASE | re.DOTALL)
        if match:
            into_part = match.group(1)
            # 호스트 변수 추출 (:var_name)
            vars_found = re.findall(r':(\w+(?:\.\w+)?)', into_part)
            return vars_found
        return []
    
    def _extract_input_vars(self, sql: str) -> List[str]:
        """SQL에서 입력 변수 추출"""
        # INTO 절 이전 또는 WHERE/VALUES 등의 입력 위치
        # 간단히 모든 :var 추출 후 INTO 절 변수 제외
        all_vars = re.findall(r':(\w+(?:\.\w+)?)', sql)
        
        # INTO 절 변수 찾기
        into_match = re.search(r'INTO\s+(.+?)(?:FROM|WHERE|$)', sql, re.IGNORECASE | re.DOTALL)
        into_vars = []
        if into_match:
            into_vars = re.findall(r':(\w+(?:\.\w+)?)', into_match.group(1))
        
        # INTO 절 변수 제외
        input_vars = [v for v in all_vars if v not in into_vars]
        return list(dict.fromkeys(input_vars))
    
    def _insert_into_clause(self, sql: str, into_clause: str) -> str:
        """SQL에 INTO 절 삽입"""
        # FROM 앞에 삽입
        from_match = re.search(r'\bFROM\b', sql, re.IGNORECASE)
        if from_match:
            return sql[:from_match.start()] + into_clause + " " + sql[from_match.start():]
        
        # FROM이 없으면 끝에 추가
        return sql + " " + into_clause
