import sys
sys.path.insert(0, '.')
from sql_converter import SQLConverter
from plugins.naming_convention import SnakeToCamelPlugin

def test_all():
    errors = []
    plugin = SnakeToCamelPlugin()
    converter = SQLConverter(naming_convention=plugin)
    
    # Test 1: Comment before SQL type
    sql = "/* 주석 */ SELECT * FROM users"
    result = converter.normalize_sql(sql)
    if result['sql_type'] != 'SELECT':
        errors.append(f"Test 1 FAILED: Expected SELECT, got {result['sql_type']}")
    else:
        print("Test 1 PASSED: Comment before SQL type")
    
    # Test 2: EXEC SQL removed
    sql = "EXEC SQL SELECT * FROM users WHERE id = :user_id"
    result = converter.normalize_sql(sql)
    if "EXEC SQL" in result['normalized_sql']:
        errors.append(f"Test 2 FAILED: EXEC SQL not removed")
    elif result['sql_type'] != 'SELECT':
        errors.append(f"Test 2 FAILED: Wrong type {result['sql_type']}")
    else:
        print("Test 2 PASSED: EXEC SQL removed")
    
    # Test 3: Indicator variable
    conv2 = SQLConverter()
    sql = "SELECT name INTO :emp_name:emp_name_ind FROM employees"
    result = conv2.normalize_sql(sql)
    if ':emp_name' not in result['output_host_vars'] or ':emp_name_ind' not in result['output_host_vars']:
        errors.append(f"Test 3 FAILED: Indicator vars not extracted: {result['output_host_vars']}")
    else:
        print("Test 3 PASSED: Indicator variable")
    
    # Test 4: Array host variable
    sql = "INSERT INTO t VALUES (:arr[i], :name[idx])"
    result = conv2.normalize_sql(sql)
    if ':arr[i]' not in result['input_host_vars'] or ':name[idx]' not in result['input_host_vars']:
        errors.append(f"Test 4 FAILED: Array vars not extracted: {result['input_host_vars']}")
    else:
        print("Test 4 PASSED: Array host variable")
    
    # Test 5: Semicolon stripped
    sql = "SELECT * FROM users;"
    result = converter.normalize_sql(sql)
    if result['normalized_sql'].endswith(';'):
        errors.append(f"Test 5 FAILED: Semicolon not stripped")
    else:
        print("Test 5 PASSED: Semicolon stripped")
    
    # Test 6: Semicolon preserved
    conv3 = SQLConverter(strip_semicolon=False)
    sql = "SELECT * FROM users;"
    result = conv3.normalize_sql(sql)
    if not result['normalized_sql'].endswith(';'):
        errors.append(f"Test 6 FAILED: Semicolon not preserved")
    else:
        print("Test 6 PASSED: Semicolon preserved")
    
    # Test 7: FOR array DML
    sql = "EXEC SQL FOR :count INSERT INTO t VALUES (:id, :name)"
    result = conv2.normalize_sql(sql)
    if result['sql_type'] != 'INSERT':
        errors.append(f"Test 7 FAILED: Type should be INSERT, got {result['sql_type']}")
    elif ':count' not in result['input_host_vars']:
        errors.append(f"Test 7 FAILED: :count not in input vars: {result['input_host_vars']}")
    else:
        print("Test 7 PASSED: FOR array DML")
    
    # Test 8: Additional SQL types
    test_cases = [
        ("CREATE TABLE t (id INT)", "CREATE"),
        ("DROP TABLE t", "DROP"),
        ("TRUNCATE TABLE t", "TRUNCATE"),
    ]
    all_passed = True
    for sql, expected_type in test_cases:
        result = conv2.normalize_sql(sql)
        if result['sql_type'] != expected_type:
            errors.append(f"Test 8 FAILED for {sql}: Expected {expected_type}, got {result['sql_type']}")
            all_passed = False
    if all_passed:
        print("Test 8 PASSED: Additional SQL types")
    
    print("\n" + "="*50)
    if errors:
        print(f"FAILURES: {len(errors)}")
        for e in errors:
            print(f"  - {e}")
        return 1
    else:
        print("ALL TESTS PASSED!")
        return 0

if __name__ == '__main__':
    exit(test_all())
