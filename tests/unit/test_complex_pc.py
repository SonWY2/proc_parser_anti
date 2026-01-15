"""
복잡한 .pc 파일 테스트 스크립트

complex_test.pc 파일을 사용하여 SQL 추출기를 테스트합니다.
"""

import os
import sys

# 상위 디렉토리 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sql_extractor import (
    SQLExtractor,
    SQLExtractorConfig,
    TreeSitterSQLExtractor,
)


def test_complex_pc_file():
    """complex_test.pc 파일 테스트"""
    
    # 테스트 파일 경로
    test_file = os.path.join(
        os.path.dirname(__file__), 
        "samples", 
        "complex_test.pc"
    )
    
    if not os.path.exists(test_file):
        print(f"Error: Test file not found: {test_file}")
        return
    
    # 파일 읽기
    with open(test_file, "r", encoding="utf-8") as f:
        source_code = f.read()
    
    print(f"=== Testing complex_test.pc ===")
    print(f"File size: {len(source_code)} bytes")
    print(f"Lines: {source_code.count(chr(10)) + 1}")
    print()
    
    # SQLExtractor 초기화
    extractor = SQLExtractor()
    
    # DB2 규칙 로드
    extractor.sql_type_registry.load_db2_rules()
    print(f"Loaded {extractor.sql_type_registry.rule_count} SQL type rules")
    print(f"Loaded {extractor.host_var_registry.rule_count} host variable rules")
    print()
    
    # Tree-sitter로 SQL 블록 추출
    print("=== Tree-sitter SQL Block Extraction ===")
    
    if extractor.use_tree_sitter:
        ts_extractor = extractor.tree_sitter_extractor
        
        # 함수 목록 추출
        functions = ts_extractor.get_functions(source_code)
        print(f"Found {len(functions)} functions:")
        for func in functions:
            print(f"  - {func['name']} (lines {func['line_start']}-{func['line_end']})")
        print()
        
        # SQL 블록 추출
        sql_blocks = ts_extractor.extract_sql_blocks(source_code, functions)
        print(f"Found {len(sql_blocks)} SQL blocks:")
        print()
        
        for i, block in enumerate(sql_blocks):
            # SQL 타입 결정
            result = extractor.sql_type_registry.determine_type(block.text)
            sql_type = result.value
            metadata = result.metadata if result.metadata else {}
            
            # 호스트 변수 추출
            host_vars = extractor.host_var_registry.extract_all(block.text)
            input_vars, output_vars = extractor.host_var_registry.classify_by_direction(
                block.text, sql_type
            )
            
            # 출력
            print(f"[{i}] Line {block.start_line}-{block.end_line}: {sql_type.upper()}")
            print(f"    Function: {block.containing_function or 'global'}")
            print(f"    Length: {len(block.text)} chars")
            
            if metadata:
                print(f"    Metadata: {metadata}")
            
            if host_vars:
                print(f"    Host variables ({len(host_vars)}):")
                # 처음 5개만 표시
                for var in host_vars[:5]:
                    print(f"      - {var['raw']} ({var['type']})")
                if len(host_vars) > 5:
                    print(f"      ... and {len(host_vars) - 5} more")
            
            if output_vars:
                print(f"    Output vars: {len(output_vars)}")
            if input_vars:
                print(f"    Input vars: {len(input_vars)}")
            
            # SQL 미리보기 (첫 100자)
            preview = block.text.replace('\n', ' ').replace('\r', '')[:100]
            print(f"    Preview: {preview}...")
            print()
    else:
        print("Tree-sitter not available, skipping...")
    
    print("=== Test Complete ===")


def test_sql_type_detection():
    """SQL 타입 감지 테스트"""
    
    extractor = SQLExtractor()
    extractor.sql_type_registry.load_db2_rules()
    
    test_cases = [
        ("EXEC SQL SELECT * FROM users;", "select"),
        ("EXEC SQL INSERT INTO logs VALUES (:msg);", "insert"),
        ("EXEC SQL UPDATE inventory SET qty = :qty;", "update"),
        ("EXEC SQL DELETE FROM temp WHERE id = :id;", "delete"),
        ("EXEC SQL DECLARE cur CURSOR FOR SELECT * FROM t;", "declare_cursor"),
        ("EXEC SQL OPEN cur;", "open"),
        ("EXEC SQL FETCH cur INTO :id, :name;", "fetch_into"),
        ("EXEC SQL CLOSE cur;", "close"),
        ("EXEC SQL COMMIT WORK;", "commit"),
        ("EXEC SQL ROLLBACK;", "rollback"),
        ("EXEC SQL INCLUDE SQLCA;", "include"),
        ("EXEC SQL PREPARE stmt FROM :sql;", "prepare"),
        ("EXEC SQL EXECUTE stmt;", "execute"),
        ("EXEC SQL SELECT * FROM t WITH UR;", "select"),  # DB2
    ]
    
    print("=== SQL Type Detection Test ===")
    passed = 0
    failed = 0
    
    for sql, expected in test_cases:
        result = extractor.sql_type_registry.determine_type(sql)
        actual = result.value
        
        if actual == expected:
            print(f"  ✓ {expected}: OK")
            passed += 1
        else:
            print(f"  ✗ Expected {expected}, got {actual}: {sql[:50]}...")
            failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed")
    print()


def test_host_variable_extraction():
    """호스트 변수 추출 테스트"""
    
    extractor = SQLExtractor()
    
    test_cases = [
        (":user_id", ["basic"]),
        (":arr[10]", ["array"]),
        (":user.name", ["struct"]),
        (":value:ind", ["indicator"]),
        (":user.name:ind", ["struct_indicator"]),
        (":arr[i]:ind", ["array_indicator"]),
        (":a, :b, :c", ["basic", "basic", "basic"]),
        (":user.id, :arr[0]:ind, :val", ["struct", "array_indicator", "basic"]),
    ]
    
    print("=== Host Variable Extraction Test ===")
    passed = 0
    failed = 0
    
    for sql, expected_types in test_cases:
        result = extractor.host_var_registry.extract_all(sql)
        actual_types = [v['type'] for v in result]
        
        if actual_types == expected_types:
            print(f"  ✓ {sql}: {actual_types}")
            passed += 1
        else:
            print(f"  ✗ {sql}: expected {expected_types}, got {actual_types}")
            failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed")
    print()


if __name__ == "__main__":
    print("Pro*C SQL Extractor Complex Test\n")
    print("=" * 60)
    
    test_sql_type_detection()
    test_host_variable_extraction()
    test_complex_pc_file()
