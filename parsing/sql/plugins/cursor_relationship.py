"""
커서 관계 플러그인

커서 관련 SQL 문을 감지하고 그룹화합니다:
DECLARE CURSOR -> OPEN -> FETCH -> CLOSE
"""

import re
from typing import List, Dict, Optional

from .base import SQLRelationshipPlugin


class CursorRelationshipPlugin(SQLRelationshipPlugin):
    """
    Pro*C 코드에서 커서 관계를 감지하는 플러그인입니다.
    
    커서 작업은 일반적으로 다음 패턴을 따릅니다:
    1. DECLARE cursor_name CURSOR FOR <query>
    2. OPEN cursor_name
    3. FETCH cursor_name INTO <variables> (루프 내에서 가능)
    4. CLOSE cursor_name
    """
    
    def can_handle(self, sql_elements: List[Dict]) -> bool:
        """DECLARE CURSOR 문이 존재하는지 확인합니다."""
        return any(self._is_declare_cursor(el) for el in sql_elements)
    
    def extract_relationships(self, sql_elements: List[Dict], all_elements: List[Dict] = None) -> List[Dict]:
        """SQL 요소에서 커서 관계를 추출합니다."""
        relationships = []
        cursor_counter = {}
        
        for declare_el in sql_elements:
            if not self._is_declare_cursor(declare_el):
                continue
            
            cursor_name = self._extract_cursor_name(declare_el)
            if not cursor_name:
                continue
            
            if cursor_name not in cursor_counter:
                cursor_counter[cursor_name] = 0
            cursor_counter[cursor_name] += 1
            
            relationship_id = self._generate_relationship_id(
                "cursor", cursor_name, cursor_counter[cursor_name]
            )
            
            related_sql_ids = [declare_el['sql_id']]
            fetch_elements = []
            
            # OPEN 문 검색
            open_el = self._find_statement(sql_elements, 'OPEN', cursor_name, after_line=declare_el['line_start'])
            if open_el:
                related_sql_ids.append(open_el['sql_id'])
            
            # FETCH 문 검색
            fetch_els = self._find_all_statements(sql_elements, 'FETCH', cursor_name, after_line=declare_el['line_start'])
            for fetch_el in fetch_els:
                related_sql_ids.append(fetch_el['sql_id'])
                fetch_elements.append(fetch_el)
            
            # CLOSE 문 검색
            close_el = self._find_statement(sql_elements, 'CLOSE', cursor_name, after_line=declare_el['line_start'])
            if close_el:
                related_sql_ids.append(close_el['sql_id'])
            
            cursor_query = self._extract_cursor_query(declare_el)
            
            all_input_vars = list(declare_el.get('input_host_vars', []))
            all_output_vars = []
            for fetch_el in fetch_elements:
                all_output_vars.extend(fetch_el.get('output_host_vars', []))
            
            all_input_vars = list(dict.fromkeys(all_input_vars))
            all_output_vars = list(dict.fromkeys(all_output_vars))
            
            is_loop_based = len(fetch_elements) > 1 or self._is_likely_in_loop(fetch_elements)
            
            # 병합된 SQL 생성
            merged_sql = cursor_query
            if all_output_vars:
                into_clause = "INTO " + ", ".join([f":{v}" for v in all_output_vars])
                from_match = re.search(r'\bFROM\b', merged_sql, re.IGNORECASE)
                if from_match:
                    merged_sql = merged_sql[:from_match.start()] + into_clause + " " + merged_sql[from_match.start():]
                else:
                    merged_sql = merged_sql + " " + into_clause

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
        normalized = element.get('normalized_sql', '')
        match = re.search(r'DECLARE\s+(\w+)\s+CURSOR', normalized, re.IGNORECASE)
        return match.group(1) if match else None
    
    def _extract_cursor_query(self, declare_el: Dict) -> str:
        """Extract the SELECT query from DECLARE CURSOR statement."""
        sql = declare_el.get('normalized_sql', '')
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
        """FETCH가 루프 내에 있을 가능성이 있는지 확인하는 휴리스틱."""
        if not fetch_elements:
            return False
        return any(el.get('output_host_vars') for el in fetch_elements)
