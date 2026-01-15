"""
Tree-sitter 파싱 동작 디버그 스크립트
"""
import sys
sys.path.insert(0, '.')

try:
    import tree_sitter
    import tree_sitter_c
    print("tree-sitter loaded successfully")
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

# 파서 초기화
language = tree_sitter.Language(tree_sitter_c.language())
parser = tree_sitter.Parser(language)

# 간단한 테스트 코드
test_code = '''
int main() {
    EXEC SQL SELECT * FROM users;
    printf("hello");
    return 0;
}
'''

print("=== Test Code ===")
print(test_code)

# 파싱
tree = parser.parse(test_code.encode('utf8'))

def print_tree(node, indent=0):
    """AST 트리 출력"""
    text_preview = ""
    if node.child_count == 0:  # 리프 노드
        try:
            text = node.text.decode('utf8')
            if len(text) < 30:
                text_preview = f' = "{text}"'
        except:
            pass
    
    print(f"{'  ' * indent}{node.type} [{node.start_point.row}:{node.start_point.column}-{node.end_point.row}:{node.end_point.column}]{text_preview}")
    
    for child in node.children:
        print_tree(child, indent + 1)

print("\n=== AST Tree ===")
print_tree(tree.root_node)

# ERROR 노드 찾기
def find_error_nodes(node, results=None):
    if results is None:
        results = []
    
    if node.type == 'ERROR':
        results.append(node)
    
    for child in node.children:
        find_error_nodes(child, results)
    
    return results

print("\n=== ERROR Nodes ===")
errors = find_error_nodes(tree.root_node)
print(f"Found {len(errors)} ERROR nodes")
for err in errors:
    print(f"  - [{err.start_point.row}:{err.start_point.column}] {err.text.decode('utf8')[:50]}")

# 모든 노드 타입 찾기
def find_all_node_types(node, types=None):
    if types is None:
        types = set()
    
    types.add(node.type)
    
    for child in node.children:
        find_all_node_types(child, types)
    
    return types

print("\n=== All Node Types ===")
all_types = find_all_node_types(tree.root_node)
print(sorted(all_types))

# EXEC 문자열 찾기
def find_nodes_with_text(node, text, results=None):
    if results is None:
        results = []
    
    try:
        node_text = node.text.decode('utf8')
        if text.upper() in node_text.upper():
            results.append((node.type, node.start_point.row, node_text[:100]))
    except:
        pass
    
    for child in node.children:
        find_nodes_with_text(child, text, results)
    
    return results

print("\n=== Nodes containing 'EXEC' ===")
exec_nodes = find_nodes_with_text(tree.root_node, 'EXEC')
for node_type, line, text in exec_nodes:
    print(f"  - {node_type} [line {line}]: {text}")
