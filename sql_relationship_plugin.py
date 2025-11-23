"""
SQL Relationship Plugin Interface

This module provides the base interface for SQL relationship plugins.
Each plugin analyzes SQL elements to detect and extract logical relationships
between multiple SQL statements (e.g., cursor operations, dynamic SQL, transactions).
"""

from typing import List, Dict, Optional
from abc import ABC, abstractmethod


class SQLRelationshipPlugin(ABC):
    """
    Base class for SQL relationship detection plugins.
    
    SQL relationship plugins analyze a list of SQL elements and identify
    logical groupings and dependencies between them. This is useful for
    converting Pro*C patterns to modern frameworks like MyBatis.
    """
    
    @abstractmethod
    def can_handle(self, sql_elements: List[Dict]) -> bool:
        """
        Determine if this plugin can handle any of the SQL elements.
        
        Args:
            sql_elements: List of SQL element dictionaries from the parser
            
        Returns:
            True if this plugin detected patterns it can handle
        """
        pass
    
    @abstractmethod
    def extract_relationships(self, sql_elements: List[Dict]) -> List[Dict]:
        """
        Extract relationships from SQL elements.
        
        Args:
            sql_elements: List of SQL element dictionaries, each containing:
                - sql_id: Unique identifier
                - sql_type: Type of SQL statement (SELECT, INSERT, etc.)
                - normalized_sql: Normalized SQL text
                - input_host_vars: List of input host variables
                - output_host_vars: List of output host variables
                - function: Function name containing this SQL
                - line_start, line_end: Source location
                
        Returns:
            List of relationship dictionaries, each containing:
                - relationship_id: Unique identifier for this relationship
                - relationship_type: Type (CURSOR, DYNAMIC_SQL, TRANSACTION, etc.)
                - sql_ids: List of sql_id values involved in this relationship
                - metadata: Dictionary of relationship-specific metadata
        """
        pass
    
    def _generate_relationship_id(self, relationship_type: str, identifier: str, counter: int) -> str:
        """
        Helper to generate unique relationship IDs.
        
        Args:
            relationship_type: Type of relationship (cursor, dynamic_sql, etc.)
            identifier: Identifying name (cursor name, statement name, etc.)
            counter: Unique counter for this type
            
        Returns:
            Formatted relationship ID (e.g., "cursor_emp_cursor_001")
        """
        return f"{relationship_type.lower()}_{identifier}_{counter:03d}"
