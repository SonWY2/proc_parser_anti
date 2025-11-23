"""
Dynamic SQL Relationship Plugin

Detects and groups dynamic SQL statements:
PREPARE -> EXECUTE (-> DEALLOCATE)
"""

import re
from typing import List, Dict, Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sql_relationship_plugin import SQLRelationshipPlugin


class DynamicSQLRelationshipPlugin(SQLRelationshipPlugin):
    """
    Plugin for detecting dynamic SQL relationships in Pro*C code.
    
    Dynamic SQL operations typically follow:
    1. PREPARE statement_name FROM <sql_source>
    2. EXECUTE statement_name [USING <params>] (possibly multiple times)
    3. DEALLOCATE statement_name (optional)
    
    This plugin groups these statements and extracts metadata for MyBatis conversion.
    """
    
    def can_handle(self, sql_elements: List[Dict]) -> bool:
        """Check if any PREPARE statements exist."""
        return any(el.get('sql_type', '').upper() == 'PREPARE' for el in sql_elements)
    
    def extract_relationships(self, sql_elements: List[Dict]) -> List[Dict]:
        """
        Extract dynamic SQL relationships.
        
        Returns list of relationship dictionaries with dynamic SQL metadata.
        """
        relationships = []
        stmt_counter = {}
        
        # Find all PREPARE statements
        for prepare_el in sql_elements:
            if prepare_el.get('sql_type', '').upper() != 'PREPARE':
                continue
            
            stmt_name = self._extract_statement_name(prepare_el)
            if not stmt_name:
                continue
            
            # Generate unique relationship ID
            if stmt_name not in stmt_counter:
                stmt_counter[stmt_name] = 0
            stmt_counter[stmt_name] += 1
            
            relationship_id = self._generate_relationship_id(
                "dynamic_sql", stmt_name, stmt_counter[stmt_name]
            )
            
            # Find related EXECUTE and DEALLOCATE statements
            related_sql_ids = [prepare_el['sql_id']]
            execute_elements = []
            
            # Search for EXECUTE statements
            execute_els = self._find_all_statements(
                sql_elements, 'EXECUTE', stmt_name, after_line=prepare_el['line_start']
            )
            for exec_el in execute_els:
                related_sql_ids.append(exec_el['sql_id'])
                execute_elements.append(exec_el)
            
            # Search for DEALLOCATE statement (optional)
            deallocate_el = self._find_statement(
                sql_elements, 'DEALLOCATE', stmt_name, after_line=prepare_el['line_start']
            )
            if deallocate_el:
                related_sql_ids.append(deallocate_el['sql_id'])
            
            # Extract SQL source (host variable or literal)
            sql_source = self._extract_sql_source(prepare_el)
            is_literal = not sql_source.startswith(':')
            
            # Aggregate all parameters from EXECUTE statements
            all_parameters = []
            for exec_el in execute_elements:
                params = exec_el.get('input_host_vars', [])
                all_parameters.extend(params)
            all_parameters = list(dict.fromkeys(all_parameters))  # Remove duplicates
            
            # Build relationship metadata
            metadata = {
                'statement_name': stmt_name,
                'sql_source': sql_source,
                'is_literal_source': is_literal,
                'execution_count': len(execute_elements),
                'all_parameters': all_parameters,
                'has_deallocate': deallocate_el is not None
            }
            
            # If literal, try to extract the actual SQL
            if is_literal:
                metadata['literal_sql'] = self._extract_literal_sql(prepare_el)
            
            relationships.append({
                'relationship_id': relationship_id,
                'relationship_type': 'DYNAMIC_SQL',
                'sql_ids': related_sql_ids,
                'metadata': metadata
            })
        
        return relationships
    
    def _extract_statement_name(self, prepare_el: Dict) -> Optional[str]:
        """Extract statement name from PREPARE statement."""
        sql = prepare_el.get('normalized_sql', '')
        # Pattern: PREPARE <stmt_name> FROM ...
        match = re.search(r'PREPARE\s+(\w+)\s+FROM', sql, re.IGNORECASE)
        return match.group(1) if match else None
    
    def _extract_sql_source(self, prepare_el: Dict) -> str:
        """Extract the SQL source (host var or literal) from PREPARE."""
        sql = prepare_el.get('normalized_sql', '')
        # Pattern: PREPARE stmt FROM <source>
        match = re.search(r'FROM\s+(.+)', sql, re.IGNORECASE)
        if match:
            source = match.group(1).strip()
            # Remove trailing semicolon if present
            return source.rstrip(';').strip()
        return ''
    
    def _extract_literal_sql(self, prepare_el: Dict) -> str:
        """Extract literal SQL string if source is a literal."""
        raw = prepare_el.get('raw_content', '')
        # Pattern: PREPARE ... FROM "SELECT ..." or 'SELECT ...'
        # Handle potential C string concatenation or multiline strings roughly
        match = re.search(r'FROM\s+([\'"])(.*?)\1', raw, re.IGNORECASE | re.DOTALL)
        if match:
            sql = match.group(2)
            # Basic cleanup: replace newlines with spaces, collapse spaces
            return re.sub(r'\s+', ' ', sql).strip()
        return ''
    
    def _find_statement(self, sql_elements: List[Dict], stmt_type: str,
                       stmt_name: str, after_line: int) -> Optional[Dict]:
        """Find a specific statement referencing the prepared statement."""
        for el in sql_elements:
            if (el.get('sql_type', '').upper() == stmt_type.upper() and
                el.get('line_start', 0) > after_line and
                stmt_name in el.get('normalized_sql', '')):
                return el
        return None
    
    def _find_all_statements(self, sql_elements: List[Dict], stmt_type: str,
                            stmt_name: str, after_line: int) -> List[Dict]:
        """Find all statements of a type referencing the prepared statement."""
        results = []
        for el in sql_elements:
            if (el.get('sql_type', '').upper() == stmt_type.upper() and
                el.get('line_start', 0) > after_line and
                stmt_name in el.get('normalized_sql', '')):
                results.append(el)
        return results
