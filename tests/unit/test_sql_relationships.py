"""
SQL 관계 플러그인 테스트 모듈

커서, 동적 SQL, 트랜잭션 및 Array DML 관계 감지를 테스트합니다.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.cursor_relationship import CursorRelationshipPlugin
from plugins.dynamic_sql_relationship import DynamicSQLRelationshipPlugin
from plugins.transaction_relationship import TransactionRelationshipPlugin
from plugins.array_dml_relationship import ArrayDMLRelationshipPlugin


def test_cursor_relationship():
    """커서 패턴 감지를 테스트합니다."""
    plugin = CursorRelationshipPlugin()
    
    sql_elements = [
        {
            'sql_id': 'sql_001',
            'sql_type': 'DECLARE',
            'normalized_sql': 'DECLARE emp_cursor CURSOR FOR SELECT id, name FROM employees WHERE dept = ?',
            'input_host_vars': [':dept_id'],
            'output_host_vars': [],
            'line_start': 10,
            'function': 'test_func'
        },
        {
            'sql_id': 'sql_002',
            'sql_type': 'OPEN',
            'normalized_sql': 'OPEN emp_cursor',
            'input_host_vars': [],
            'output_host_vars': [],
            'line_start': 15,
            'function': 'test_func'
        },
        {
            'sql_id': 'sql_003',
            'sql_type': 'FETCH',
            'normalized_sql': 'FETCH emp_cursor',
            'input_host_vars': [],
            'output_host_vars': [':emp_id', ':emp_name'],
            'line_start': 18,
            'function': 'test_func'
        },
        {
            'sql_id': 'sql_004',
            'sql_type': 'CLOSE',
            'normalized_sql': 'CLOSE emp_cursor',
            'input_host_vars': [],
            'output_host_vars': [],
            'line_start': 22,
            'function': 'test_func'
        }
    ]
    
    assert plugin.can_handle(sql_elements)
    relationships = plugin.extract_relationships(sql_elements)
    
    assert len(relationships) == 1
    rel = relationships[0]
    
    assert rel['relationship_type'] == 'CURSOR'
    assert rel['sql_ids'] == ['sql_001', 'sql_002', 'sql_003', 'sql_004']
    assert rel['metadata']['cursor_name'] == 'emp_cursor'
    assert rel['metadata']['all_output_vars'] == [':emp_id', ':emp_name']
    assert rel['metadata']['is_loop_based'] == True
    
    print("✓ Cursor relationship test passed")


def test_dynamic_sql_relationship():
    """동적 SQL 패턴 감지를 테스트합니다."""
    plugin = DynamicSQLRelationshipPlugin()
    
    sql_elements = [
        {
            'sql_id': 'sql_010',
            'sql_type': 'PREPARE',
            'normalized_sql': 'PREPARE stmt1 FROM ?',
            'input_host_vars': [':query_string'],
            'output_host_vars': [],
            'line_start': 30,
            'raw_content': 'EXEC SQL PREPARE stmt1 FROM :query_string;',
            'function': 'dynamic_query'
        },
        {
            'sql_id': 'sql_011',
            'sql_type': 'EXECUTE',
            'normalized_sql': 'EXECUTE stmt1 USING ?',
            'input_host_vars': [':param1'],
            'output_host_vars': [],
            'line_start': 32,
            'function': 'dynamic_query'
        }
    ]
    
    assert plugin.can_handle(sql_elements)
    relationships = plugin.extract_relationships(sql_elements)
    
    assert len(relationships) == 1
    rel = relationships[0]
    
    assert rel['relationship_type'] == 'DYNAMIC_SQL'
    assert rel['sql_ids'] == ['sql_010', 'sql_011']
    assert rel['metadata']['statement_name'] == 'stmt1'
    assert rel['metadata']['execution_count'] == 1
    
    print("✓ Dynamic SQL relationship test passed")


def test_transaction_relationship():
    """트랜잭션 경계 감지를 테스트합니다."""
    plugin = TransactionRelationshipPlugin()
    
    sql_elements = [
        {
            'sql_id': 'sql_020',
            'sql_type': 'INSERT',
            'normalized_sql': 'INSERT INTO logs VALUES (?)',
            'input_host_vars': [':log_msg'],
            'output_host_vars': [],
            'line_start': 40,
            'function': 'save_log'
        },
        {
            'sql_id': 'sql_021',
            'sql_type': 'COMMIT',
            'normalized_sql': 'COMMIT',
            'input_host_vars': [],
            'output_host_vars': [],
            'line_start': 45,
            'function': 'save_log'
        }
    ]
    
    assert plugin.can_handle(sql_elements)
    relationships = plugin.extract_relationships(sql_elements)
    
    assert len(relationships) >= 1
    rel = relationships[0]
    
    assert rel['relationship_type'] == 'TRANSACTION'
    assert 'sql_020' in rel['sql_ids']
    assert 'sql_021' in rel['sql_ids']
    assert rel['metadata']['is_commit'] == True
    
    print("✓ Transaction relationship test passed")


def test_array_dml_relationship():
    """Array DML 패턴 감지를 테스트합니다."""
    plugin = ArrayDMLRelationshipPlugin()
    
    sql_elements = [
        {
            'sql_id': 'sql_030',
            'sql_type': 'INSERT',
            'normalized_sql': 'INSERT INTO temp_data VALUES (?, ?)',
            'input_host_vars': [':ids', ':names'],
            'output_host_vars': [],
            'line_start': 50,
            'raw_content': 'EXEC SQL FOR :batch_size INSERT INTO temp_data VALUES (:ids[i], :names[i]);',
            'function': 'batch_insert'
        }
    ]
    
    assert plugin.can_handle(sql_elements)
    relationships = plugin.extract_relationships(sql_elements)
    
    assert len(relationships) == 1
    rel = relationships[0]
    
    assert rel['relationship_type'] == 'ARRAY_DML'
    assert rel['sql_ids'] == ['sql_030']
    assert rel['metadata']['array_size_var'] == ':batch_size'
    assert len(rel['metadata']['array_host_vars']) == 2
    assert rel['metadata']['dml_type'] == 'INSERT'
    assert rel['metadata']['mybatis_hint'] == 'use_foreach'
    
    print("✓ Array DML relationship test passed")


if __name__ == '__main__':
    print("Running SQL Relationship Plugin Tests...\n")
    
    test_cursor_relationship()
    test_dynamic_sql_relationship()
    test_transaction_relationship()
    test_array_dml_relationship()
    
    print("\n✓ All tests passed!")
