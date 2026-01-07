"""
다차원 배열 및 변수 스코프 추출 테스트
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# c_parser만 직접 임포트
import tree_sitter
import tree_sitter_c

class TestCParser:
    def __init__(self):
        self.language = tree_sitter.Language(tree_sitter_c.language())
        self.parser = tree_sitter.Parser(self.language)
    
    def parse(self, source_code):
        elements = []
        tree = self.parser.parse(bytes(source_code, "utf8"))
        root_node = tree.root_node
        self._traverse(root_node, elements)
        return elements
    
    def _traverse(self, node, elements, current_function=None):
        node_type = node.type
        
        if node_type == 'function_definition':
            func_name = self._get_function_name(node)
            if func_name:
                elements.append({
                    "type": "function",
                    "name": func_name,
                    "line_start": node.start_point.row + 1,
                    "line_end": node.end_point.row + 1,
                })
                current_function = func_name
        
        elif node_type == 'declaration':
            var_info = self._get_variable_info(node)
            if var_info and var_info.get('name'):
                elements.append({
                    "type": "variable",
                    "name": var_info['name'],
                    "data_type": var_info['data_type'],
                    "array_sizes": var_info.get('array_sizes', []),
                    "is_pointer": var_info.get('is_pointer', False),
                    "storage_class": var_info.get('storage_class'),
                    "line_start": node.start_point.row + 1,
                    "line_end": node.end_point.row + 1,
                    "raw_content": node.text.decode('utf8'),
                    "function": current_function
                })
        
        for child in node.children:
            self._traverse(child, elements, current_function)
    
    def _get_function_name(self, node):
        declarator = node.child_by_field_name('declarator')
        if not declarator: return None
        while declarator.type == 'pointer_declarator':
            declarator = declarator.child_by_field_name('declarator')
        if declarator.type == 'function_declarator':
            identifier = declarator.child_by_field_name('declarator')
            if identifier and identifier.type == 'identifier':
                return identifier.text.decode('utf8')
        return None

    def _get_variable_info(self, node):
        type_node = node.child_by_field_name('type')
        declarator = node.child_by_field_name('declarator')
        
        if not type_node or not declarator:
            return None
        
        var_type = type_node.text.decode('utf8')
        array_sizes = []
        is_pointer = False
        storage_class = None
        
        # storage_class 추출
        for child in node.children:
            if child.type == 'storage_class_specifier':
                storage_class = child.text.decode('utf8')
                break
        
        # 포인터, 배열, 초기화 처리 - 배열 크기도 수집
        while declarator and declarator.type in ['pointer_declarator', 'array_declarator', 'init_declarator']:
            if declarator.type == 'pointer_declarator':
                is_pointer = True
                declarator = declarator.child_by_field_name('declarator')
            elif declarator.type == 'array_declarator':
                size_node = declarator.child_by_field_name('size')
                if size_node:
                    array_sizes.append(size_node.text.decode('utf8'))
                else:
                    array_sizes.append(None)
                declarator = declarator.child_by_field_name('declarator')
            elif declarator.type == 'init_declarator':
                declarator = declarator.child_by_field_name('declarator')
        
        if declarator and declarator.type == 'identifier':
            return {
                'name': declarator.text.decode('utf8'),
                'data_type': var_type,
                'array_sizes': array_sizes[::-1],  # 뒤집기
                'is_pointer': is_pointer,
                'storage_class': storage_class
            }
        
        return None


def test_multidimensional_arrays():
    """다차원 배열 크기 추출 테스트"""
    parser = TestCParser()
    
    test_cases = [
        # (code, expected_name, expected_array_sizes)
        ("int matrix[10][20][30];", "matrix", ["10", "20", "30"]),
        ("char buffer[256];", "buffer", ["256"]),
        ("float values[100][50];", "values", ["100", "50"]),
        ("int simple;", "simple", []),
        ("char *ptr;", "ptr", []),
        ("static int counter;", "counter", []),
        ("static char data[1024];", "data", ["1024"]),
    ]
    
    print("=== 다차원 배열 크기 추출 테스트 ===\n")
    
    passed = 0
    failed = 0
    
    for code, expected_name, expected_sizes in test_cases:
        result = parser.parse(code)
        vars = [e for e in result if e['type'] == 'variable']
        
        if vars:
            var = vars[0]
            actual_name = var['name']
            actual_sizes = var['array_sizes']
            
            if actual_name == expected_name and actual_sizes == expected_sizes:
                print(f"✓ {code}")
                print(f"  Name: {actual_name}, Array Sizes: {actual_sizes}")
                passed += 1
            else:
                print(f"✗ {code}")
                print(f"  Expected: {expected_name}, {expected_sizes}")
                print(f"  Got: {actual_name}, {actual_sizes}")
                failed += 1
        else:
            print(f"✗ {code} - No variable found")
            failed += 1
        print()
    
    print(f"Results: {passed} passed, {failed} failed\n")
    return failed == 0


def test_storage_class():
    """storage_class 추출 테스트"""
    parser = TestCParser()
    
    test_cases = [
        ("static int counter;", "counter", "static"),
        ("extern int global_val;", "global_val", "extern"),
        ("int normal;", "normal", None),
        ("static char buffer[100];", "buffer", "static"),
    ]
    
    print("=== Storage Class 추출 테스트 ===\n")
    
    passed = 0
    failed = 0
    
    for code, expected_name, expected_storage in test_cases:
        result = parser.parse(code)
        vars = [e for e in result if e['type'] == 'variable']
        
        if vars:
            var = vars[0]
            actual_storage = var.get('storage_class')
            
            if actual_storage == expected_storage:
                print(f"✓ {code}")
                print(f"  Storage Class: {actual_storage}")
                passed += 1
            else:
                print(f"✗ {code}")
                print(f"  Expected: {expected_storage}, Got: {actual_storage}")
                failed += 1
        else:
            print(f"✗ {code} - No variable found")
            failed += 1
        print()
    
    print(f"Results: {passed} passed, {failed} failed\n")
    return failed == 0


def test_pointer():
    """포인터 감지 테스트"""
    parser = TestCParser()
    
    test_cases = [
        ("char *ptr;", "ptr", True),
        ("int **double_ptr;", "double_ptr", True),
        ("int normal;", "normal", False),
        ("char arr[10];", "arr", False),
    ]
    
    print("=== 포인터 감지 테스트 ===\n")
    
    passed = 0
    failed = 0
    
    for code, expected_name, expected_pointer in test_cases:
        result = parser.parse(code)
        vars = [e for e in result if e['type'] == 'variable']
        
        if vars:
            var = vars[0]
            actual_pointer = var.get('is_pointer', False)
            
            if actual_pointer == expected_pointer:
                print(f"✓ {code}")
                print(f"  Is Pointer: {actual_pointer}")
                passed += 1
            else:
                print(f"✗ {code}")
                print(f"  Expected: {expected_pointer}, Got: {actual_pointer}")
                failed += 1
        else:
            print(f"✗ {code} - No variable found")
            failed += 1
        print()
    
    print(f"Results: {passed} passed, {failed} failed\n")
    return failed == 0


if __name__ == "__main__":
    print("=" * 60)
    print("변수 추출 기능 향상 테스트")
    print("=" * 60)
    print()
    
    all_passed = True
    all_passed &= test_multidimensional_arrays()
    all_passed &= test_storage_class()
    all_passed &= test_pointer()
    
    if all_passed:
        print("✓ 모든 테스트 통과!")
    else:
        print("✗ 일부 테스트 실패")
