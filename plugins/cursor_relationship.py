"""
커서 관계 플러그인

커서 관련 SQL 문을 감지하고 그룹화합니다:
DECLARE CURSOR -> OPEN -> FETCH -> CLOSE
"""

import re
from typing import List, Dict, Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sql_relationship_plugin import SQLRelationshipPlugin


class CursorRelationshipPlugin(SQLRelationshipPlugin):
    """
    Pro*C 코드에서 커서 관계를 감지하는 플러그인입니다.
    
    커서 작업은 일반적으로 다음 패턴을 따릅니다:
    1. DECLARE cursor_name CURSOR FOR <query>
    2. OPEN cursor_name
    3. FETCH cursor_name INTO <variables> (루프 내에서 가능)
    4. CLOSE cursor_name
    
    이 플러그인은 이러한 문을 그룹화하고 MyBatis 변환에 유용한 메타데이터
    (SELECT 쿼리, 출력 변수 등)를 추출합니다.
    """
    
    def can_handle(self, sql_elements: List[Dict]) -> bool:
        """DECLARE CURSOR 문이 존재하는지 확인합니다."""
        return any(self._is_declare_cursor(el) for el in sql_elements)
    
    def extract_relationships(self, sql_elements: List[Dict], all_elements: List[Dict] = None) -> List[Dict]:
        """
        SQL 요소에서 커서 관계를 추출합니다.
        
        커서 메타데이터가 포함된 관계 딕셔너리 목록을 반환합니다.
        """
        relationships = []
        cursor_counter = {}
        
        # 모든 DECLARE CURSOR 문 찾기
        for declare_el in sql_elements:
            if not self._is_declare_cursor(declare_el):
                continue
            
            cursor_name = self._extract_cursor_name(declare_el)
            if not cursor_name:
                continue
            
            # 고유 관계 ID 생성
            if cursor_name not in cursor_counter:
                cursor_counter[cursor_name] = 0
            cursor_counter[cursor_name] += 1
            
            relationship_id = self._generate_relationship_id(
                "cursor", cursor_name, cursor_counter[cursor_name]
            )
            
            # 관련된 OPEN, FETCH, CLOSE 문 찾기
            related_sql_ids = [declare_el['sql_id']]
            fetch_elements = []
            
            # OPEN 문 검색
            open_el = self._find_statement(sql_elements, 'OPEN', cursor_name, after_line=declare_el['line_start'])
            if open_el:
                related_sql_ids.append(open_el['sql_id'])
            
            # FETCH 문 검색 (루프 내에서 여러 번 가능)
            fetch_els = self._find_all_statements(sql_elements, 'FETCH', cursor_name, after_line=declare_el['line_start'])
            for fetch_el in fetch_els:
                related_sql_ids.append(fetch_el['sql_id'])
                fetch_elements.append(fetch_el)
            
            # CLOSE 문 검색
            close_el = self._find_statement(sql_elements, 'CLOSE', cursor_name, after_line=declare_el['line_start'])
            if close_el:
                related_sql_ids.append(close_el['sql_id'])
            
            # DECLARE 문에서 커서 쿼리 추출
            cursor_query = self._extract_cursor_query(declare_el)
            
            # 모든 입력/출력 변수 집계
            all_input_vars = list(declare_el.get('input_host_vars', []))
            all_output_vars = []
            for fetch_el in fetch_elements:
                all_output_vars.extend(fetch_el.get('output_host_vars', []))
            
            # 순서를 유지하면서 중복 제거
            all_input_vars = list(dict.fromkeys(all_input_vars))
            all_output_vars = list(dict.fromkeys(all_output_vars))
            
            # 루프 기반인지 확인 (여러 FETCH 또는 동일한 함수의 FETCH)
            is_loop_based = len(fetch_elements) > 1 or self._is_likely_in_loop(fetch_elements)
            
            # 병합된 SQL 생성
            # 로직: cursor_query (SELECT ...)를 가져와서 FROM 앞이나 끝에 INTO 절 삽입?
            # 표준 SQL SELECT ... INTO ... FROM ...
            # 하지만 Pro*C는 종종 DECLARE ... SELECT ... FROM ... 하고 나서 FETCH ... INTO ... 함
            # 이를 SELECT ... INTO ... FROM ... 으로 표현하고 싶음
            
            merged_sql = cursor_query
            if all_output_vars:
                # INTO 절 구성
                # all_output_vars already have colons if they came from sql_converter
                vars_list = [v if v.startswith(':') else f":{v}" for v in all_output_vars]
                into_clause = "INTO " + ", ".join(vars_list)
                
                # SELECT 목록 뒤에 삽입 시도
                # 간단한 휴리스틱: FROM 키워드 찾기
                from_match = re.search(r'\bFROM\b', merged_sql, re.IGNORECASE)
                if from_match:
                    # FROM 앞에 삽입
                    merged_sql = merged_sql[:from_match.start()] + into_clause + " " + merged_sql[from_match.start():]
                else:
                    # 끝에 추가 (유효한 SELECT에는 드물지만 폴백)
                    merged_sql = merged_sql + " " + into_clause

            # 관계 메타데이터 생성
            metadata = {
                'cursor_name': cursor_name,
                'cursor_query': cursor_query,
                'merged_sql': merged_sql,
                'is_loop_based': is_loop_based,
                'all_input_vars': all_input_vars,
                'all_output_vars': all_output_vars,
                'total_fetches': len(fetch_elements)
            }
            
            relationships.append({
                'relationship_id': relationship_id,
                'relationship_type': 'CURSOR',
                'sql_ids': related_sql_ids,
                'metadata': metadata
            })
        
        return relationships
    
    def _is_declare_cursor(self, element: Dict) -> bool:
        """Check if element is a DECLARE CURSOR statement."""
        return (element.get('sql_type', '').upper() == 'DECLARE' and 
                'CURSOR' in element.get('normalized_sql', '').upper())
    
    def _extract_cursor_name(self, element: Dict) -> Optional[str]:
        """Extract cursor name from DECLARE statement."""
        # 신뢰할 수 있는 정규식 매칭을 위해 normalized_sql 사용 (공백 축소됨)
        normalized = element.get('normalized_sql', '')
        match = re.search(r'DECLARE\s+(\w+)\s+CURSOR', normalized, re.IGNORECASE)
        return match.group(1) if match else None
    
    def _extract_cursor_query(self, declare_el: Dict) -> str:
        """Extract the SELECT query from DECLARE CURSOR statement."""
        sql = declare_el.get('normalized_sql', '')
        # 패턴: DECLARE cursor_name CURSOR FOR <query>
        match = re.search(r'CURSOR\s+FOR\s+(.+)', sql, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else ''
    
    def _find_statement(self, sql_elements: List[Dict], stmt_type: str, 
                       cursor_name: str, after_line: int) -> Optional[Dict]:
        """Find a specific cursor-related statement (OPEN/CLOSE)."""
        for el in sql_elements:
            if (el.get('sql_type', '').upper() == stmt_type.upper() and
                el.get('line_start', 0) > after_line and
                cursor_name in el.get('normalized_sql', '')):
                return el
        return None
    
    def _find_all_statements(self, sql_elements: List[Dict], stmt_type: str,
                            cursor_name: str, after_line: int) -> List[Dict]:
        """Find all statements of a type referencing the cursor."""
        results = []
        for el in sql_elements:
            if (el.get('sql_type', '').upper() == stmt_type.upper() and
                el.get('line_start', 0) > after_line and
                cursor_name in el.get('normalized_sql', '')):
                results.append(el)
        return results
    
    def _is_likely_in_loop(self, fetch_elements: List[Dict]) -> bool:
        """
        FETCH가 루프 내에 있을 가능성이 있는지 확인하는 휴리스틱.
        현재는 출력 변수가 있는 경우 단일 FETCH도 루프 내에 있을 수 있다고 가정합니다.
        """
        if not fetch_elements:
            return False
        # 출력 변수가 있는 경우 여러 번 호출될 가능성이 높음
        return any(el.get('output_host_vars') for el in fetch_elements)
