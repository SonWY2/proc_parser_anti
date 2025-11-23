"""
Array DML Relationship Plugin

Detects and groups array DML operations (FOR clause):
FOR :array_size INSERT/UPDATE/DELETE ...
"""

import re
from typing import List, Dict, Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sql_relationship_plugin import SQLRelationshipPlugin


class ArrayDMLRelationshipPlugin(SQLRelationshipPlugin):
    """
    Plugin for detecting array DML (bulk operations) in Pro*C code.
    
    Array DML uses FOR clause to execute DML on arrays:
    EXEC SQL FOR :array_size
      INSERT INTO table VALUES (:arr1[i], :arr2[i]);
    
    This plugin extracts metadata for converting to MyBatis <foreach> tags.
    """
    
    def can_handle(self, sql_elements: List[Dict]) -> bool:
        """Check if any array DML patterns exist."""
        return any(self._is_array_dml(el) for el in sql_elements)
    
    def extract_relationships(self, sql_elements: List[Dict]) -> List[Dict]:
        """
        Extract array DML relationships.
        
        Returns list of relationship dictionaries with array DML metadata.
        """
        relationships = []
        array_counter = 0
        
        for el in sql_elements:
            if not self._is_array_dml(el):
                continue
            
            array_counter += 1
            
            # Generate relationship ID
            func_name = el.get('function', 'unknown')
            relationship_id = self._generate_relationship_id(
                "array", func_name, array_counter
            )
            
            # Extract array size variable
            array_size_var = self._extract_array_size_var(el)
            
            # Extract array host variables (variables with [i] or array subscript)
            array_host_vars = self._extract_array_variables(el)
            
            # Determine DML type
            dml_type = el.get('sql_type', 'UNKNOWN').upper()
            if dml_type not in ['INSERT', 'UPDATE', 'DELETE']:
                # Try to extract from raw content
                raw = el.get('raw_content', '').upper()
                for dtype in ['INSERT', 'UPDATE', 'DELETE']:
                    if dtype in raw:
                        dml_type = dtype
                        break
            
            # Build metadata
            metadata = {
                'array_size_var': array_size_var,
                'array_host_vars': array_host_vars,
                'dml_type': dml_type,
                'mybatis_hint': 'use_foreach'
            }
            
            relationships.append({
                'relationship_id': relationship_id,
                'relationship_type': 'ARRAY_DML',
                'sql_ids': [el['sql_id']],
                'metadata': metadata
            })
        
        return relationships
    
    def _is_array_dml(self, element: Dict) -> bool:
        """Check if element is an array DML statement."""
        raw = element.get('raw_content', '')
        normalized = element.get('normalized_sql', '').upper()
        
        # Explicitly exclude CURSOR declarations
        if 'CURSOR FOR' in normalized or 'CURSOR FOR' in raw.upper():
            return False
            
        # Check for FOR clause pattern
        # Must be FOR :variable or FOR number
        # Avoid matching 'FOR UPDATE', 'FOR SELECT' etc.
        return bool(re.search(r'FOR\s+(:[a-zA-Z_]\w*|\d+)', raw, re.IGNORECASE))
    
    def _extract_array_size_var(self, element: Dict) -> str:
        """Extract the array size variable from FOR clause."""
        raw = element.get('raw_content', '')
        # Pattern: FOR :array_size or FOR array_size
        match = re.search(r'FOR\s+(:?\w+)', raw, re.IGNORECASE)
        return match.group(1) if match else ''
    
    def _extract_array_variables(self, element: Dict) -> List[Dict]:
        """
        Extract array variables (those with subscripts like :arr[i]).
        
        Returns list of dicts with var name and is_array flag.
        """
        raw = element.get('raw_content', '')
        array_vars = []
        
        # Pattern: :varname[index] or :varname
        # First find all with subscripts
        array_pattern = re.compile(r':(\w+)\[', re.IGNORECASE)
        for match in array_pattern.finditer(raw):
            var_name = ':' + match.group(1)
            if not any(v['var'] == var_name for v in array_vars):
                array_vars.append({
                    'var': var_name,
                    'is_array': True
                })
        
        # Also include regular host vars from input_host_vars
        # (some might not have explicit subscripts in normalized form)
        for var in element.get('input_host_vars', []):
            if not any(v['var'] == var for v in array_vars):
                # If FOR clause present, assume it's an array
                array_vars.append({
                    'var': var,
                    'is_array': True
                })
        
        return array_vars
