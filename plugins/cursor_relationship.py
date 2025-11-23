"""
Cursor Relationship Plugin

Detects and groups cursor-related SQL statements:
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
    Plugin for detecting cursor relationships in Pro*C code.
    
    Cursor operations typically follow this pattern:
    1. DECLARE cursor_name CURSOR FOR <query>
    2. OPEN cursor_name
    3. FETCH cursor_name INTO <variables> (possibly in a loop)
    4. CLOSE cursor_name
    
    This plugin groups these statements and extracts metadata useful
    for MyBatis conversion (SELECT query, output variables, etc.)
    """
    
    def can_handle(self, sql_elements: List[Dict]) -> bool:
        """Check if any DECLARE CURSOR statements exist."""
        return any(self._is_declare_cursor(el) for el in sql_elements)
    
    def extract_relationships(self, sql_elements: List[Dict]) -> List[Dict]:
        """
        Extract cursor relationships from SQL elements.
        
        Returns list of relationship dictionaries with cursor metadata.
        """
        relationships = []
        cursor_counter = {}
        
        # Find all DECLARE CURSOR statements
        for declare_el in sql_elements:
            if not self._is_declare_cursor(declare_el):
                continue
            
            cursor_name = self._extract_cursor_name(declare_el)
            if not cursor_name:
                continue
            
            # Generate unique relationship ID
            if cursor_name not in cursor_counter:
                cursor_counter[cursor_name] = 0
            cursor_counter[cursor_name] += 1
            
            relationship_id = self._generate_relationship_id(
                "cursor", cursor_name, cursor_counter[cursor_name]
            )
            
            # Find related OPEN, FETCH, CLOSE statements
            related_sql_ids = [declare_el['sql_id']]
            fetch_elements = []
            
            # Search for OPEN statement
            open_el = self._find_statement(sql_elements, 'OPEN', cursor_name, after_line=declare_el['line_start'])
            if open_el:
                related_sql_ids.append(open_el['sql_id'])
            
            # Search for FETCH statements (can be multiple in a loop)
            fetch_els = self._find_all_statements(sql_elements, 'FETCH', cursor_name, after_line=declare_el['line_start'])
            for fetch_el in fetch_els:
                related_sql_ids.append(fetch_el['sql_id'])
                fetch_elements.append(fetch_el)
            
            # Search for CLOSE statement
            close_el = self._find_statement(sql_elements, 'CLOSE', cursor_name, after_line=declare_el['line_start'])
            if close_el:
                related_sql_ids.append(close_el['sql_id'])
            
            # Extract cursor query from DECLARE statement
            cursor_query = self._extract_cursor_query(declare_el)
            
            # Aggregate all input/output variables
            all_input_vars = list(declare_el.get('input_host_vars', []))
            all_output_vars = []
            for fetch_el in fetch_elements:
                all_output_vars.extend(fetch_el.get('output_host_vars', []))
            
            # Remove duplicates while preserving order
            all_input_vars = list(dict.fromkeys(all_input_vars))
            all_output_vars = list(dict.fromkeys(all_output_vars))
            
            # Determine if loop-based (multiple FETCHes or FETCH in same function)
            is_loop_based = len(fetch_elements) > 1 or self._is_likely_in_loop(fetch_elements)
            
            # Build relationship metadata
            metadata = {
                'cursor_name': cursor_name,
                'cursor_query': cursor_query,
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
        # Use normalized_sql for reliable regex matching (whitespace collapsed)
        normalized = element.get('normalized_sql', '')
        match = re.search(r'DECLARE\s+(\w+)\s+CURSOR', normalized, re.IGNORECASE)
        return match.group(1) if match else None
    
    def _extract_cursor_query(self, declare_el: Dict) -> str:
        """Extract the SELECT query from DECLARE CURSOR statement."""
        sql = declare_el.get('normalized_sql', '')
        # Pattern: DECLARE cursor_name CURSOR FOR <query>
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
        Heuristic to determine if FETCH is likely in a loop.
        Currently assumes single FETCH might be in loop if it has output vars.
        """
        if not fetch_elements:
            return False
        # If there are output variables, it's likely meant to be called multiple times
        return any(el.get('output_host_vars') for el in fetch_elements)
