"""
Transaction Relationship Plugin

Detects and groups transaction boundaries:
SQL statements -> COMMIT/ROLLBACK
"""

import re
from typing import List, Dict, Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sql_relationship_plugin import SQLRelationshipPlugin


class TransactionRelationshipPlugin(SQLRelationshipPlugin):
    """
    Plugin for detecting transaction relationships in Pro*C code.
    
    Groups SQL statements by transaction boundaries (COMMIT/ROLLBACK).
    Useful for converting to Spring @Transactional annotations.
    """
    
    def can_handle(self, sql_elements: List[Dict]) -> bool:
        """Check if any COMMIT or ROLLBACK statements exist."""
        return any(el.get('sql_type', '').upper() in ['COMMIT', 'ROLLBACK'] 
                  for el in sql_elements)
    
    def extract_relationships(self, sql_elements: List[Dict]) -> List[Dict]:
        """
        Extract transaction relationships.
        
        Groups SQL statements between transaction boundaries.
        """
        relationships = []
        txn_counter = 0
        
        # Group by function first
        functions = {}
        for el in sql_elements:
            func_name = el.get('function', 'global')
            if func_name not in functions:
                functions[func_name] = []
            functions[func_name].append(el)
        
        # Process each function
        for func_name, elements in functions.items():
            # Sort by line number
            elements.sort(key=lambda x: x.get('line_start', 0))
            
            # Find transaction boundaries
            boundaries = [el for el in elements 
                         if el.get('sql_type', '').upper() in ['COMMIT', 'ROLLBACK']]
            
            if not boundaries:
                continue
            
            # Group statements before each boundary
            for boundary_el in boundaries:
                txn_counter += 1
                
                # Find all SQL statements before this boundary in same function
                txn_statements = []
                for el in elements:
                    if (el.get('line_start', 0) < boundary_el.get('line_start', 0) and
                        el.get('sql_type', '').upper() not in ['COMMIT', 'ROLLBACK', 'CONNECT']):
                        # Check if not already in another transaction
                        already_grouped = any(
                            el['sql_id'] in r['sql_ids'] 
                            for r in relationships
                        )
                        if not already_grouped:
                            txn_statements.append(el)
                
                # Only create relationship if there are statements in the transaction
                if txn_statements:
                    related_sql_ids = [el['sql_id'] for el in txn_statements]
                    related_sql_ids.append(boundary_el['sql_id'])
                    
                    relationship_id = self._generate_relationship_id(
                        "txn", func_name or "unknown", txn_counter
                    )
                    
                    # Determine transaction type
                    is_commit = boundary_el.get('sql_type', '').upper() == 'COMMIT'
                    has_rollback = any(
                        el.get('sql_type', '').upper() == 'ROLLBACK' 
                        for el in elements
                        if el.get('line_start', 0) > boundary_el.get('line_start', 0)
                    )
                    
                    # Build metadata
                    metadata = {
                        'transaction_scope': 'function' if func_name != 'global' else 'global',
                        'commit_type': 'explicit',
                        'is_commit': is_commit,
                        'has_rollback': has_rollback,
                        'statement_count': len(txn_statements)
                    }
                    
                    relationships.append({
                        'relationship_id': relationship_id,
                        'relationship_type': 'TRANSACTION',
                        'sql_ids': related_sql_ids,
                        'metadata': metadata
                    })
        
        return relationships
