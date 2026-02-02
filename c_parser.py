"""
Tree-sitter를 사용하여 C 코드를 파싱하는 모듈입니다.
함수 정의, 변수 선언, 구조체 정의, 함수 호출 등을 추출합니다.
"""
import tree_sitter
try:
    import tree_sitter_c
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False
    print("Warning: tree-sitter-c not found. C parsing will be limited.")

KEYWORDS = {
    'auto', 'break', 'case', 'char', 'const', 'continue', 'default', 'do',
    'double', 'else', 'enum', 'extern', 'float', 'for', 'goto', 'if',
    'int', 'long', 'register', 'return', 'short', 'signed', 'sizeof', 'static',
    'struct', 'switch', 'typedef', 'union', 'unsigned', 'void', 'volatile',
    'while', '_Bool', '_Complex', '_Imaginary', 'inline', 'restrict', '_Atomic'
}

class CParser:
    def __init__(self):
        if HAS_TREE_SITTER:
            self.language = tree_sitter.Language(tree_sitter_c.language())
            self.parser = tree_sitter.Parser(self.language)
        else:
            self.parser = None

    def parse(self, source_code):
        """
        C 소스 코드를 파싱하여 함수, 구조체, 변수 등을 추출합니다.
        """
        elements = []
        if not self.parser:
            return elements

        tree = self.parser.parse(bytes(source_code, "utf8"))
        root_node = tree.root_node
        
        # 다양한 tree-sitter 버전 간의 호환성을 위해
        # 쿼리 대신 수동 순회 사용
        self._traverse(root_node, elements)
        
        return elements

    def _traverse(self, node, elements, current_function=None):
        # 재귀적 순회
        
        node_type = node.type
        
        if node_type == 'comment':
            elements.append({
                "type": "comment",
                "is_multiline": node.text.startswith(b'/*'),
                "line_start": node.start_point.row + 1,
                "line_end": node.end_point.row + 1,
                "raw_content": node.text.decode('utf8'),
                "function": current_function
            })

        elif node_type == 'function_definition':
            # 함수 이름 추출
            func_name = self._get_function_name(node)
            if func_name and func_name not in KEYWORDS:
                elements.append({
                    "type": "function",
                    "name": func_name,
                    "line_start": node.start_point.row + 1,
                    "line_end": node.end_point.row + 1,
                    "raw_content": node.text.decode('utf8'),
                    "function": None # 최상위 레벨
                })
                current_function = func_name
        
        elif node_type == 'declaration':
            # 변수 선언
            var_name, var_type = self._get_variable_info(node)
            if var_name:
                elements.append({
                    "type": "variable",
                    "name": var_name,
                    "data_type": var_type,
                    "line_start": node.start_point.row + 1,
                    "line_end": node.end_point.row + 1,
                    "raw_content": node.text.decode('utf8'),
                    "function": current_function
                })

        elif node_type == 'struct_specifier':
            struct_name = self._get_struct_name(node)
            if struct_name:
                 elements.append({
                    "type": "struct",
                    "name": struct_name,
                    "line_start": node.start_point.row + 1,
                    "line_end": node.end_point.row + 1,
                    "raw_content": node.text.decode('utf8'),
                    "function": current_function
                })

        elif node_type == 'call_expression':
            func_name, args, raw_args = self._get_function_call_info(node)
            if func_name:
                elements.append({
                    "type": "function_call",
                    "name": func_name,
                    "args": args,
                    "raw_content": node.text.decode('utf8'),
                    "line_start": node.start_point.row + 1,
                    "line_end": node.end_point.row + 1,
                    "function": current_function
                })

        for child in node.children:
            self._traverse(child, elements, current_function)

    def _get_function_name(self, node):
        # 자식: declarator -> function_declarator -> declarator -> identifier
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
        # type, declarator
        type_node = node.child_by_field_name('type')
        declarator = node.child_by_field_name('declarator')
        
        if not type_node or not declarator: return None, None
        
        var_type = type_node.text.decode('utf8')
        
        # 포인터, 배열, 초기화 처리
        while declarator.type in ['pointer_declarator', 'array_declarator', 'init_declarator']:
            declarator = declarator.child_by_field_name('declarator')
            
        if declarator and declarator.type == 'identifier':
            return declarator.text.decode('utf8'), var_type
            
        return None, None

    def _get_struct_name(self, node):
        name_node = node.child_by_field_name('name')
        if name_node and name_node.type == 'type_identifier':
            return name_node.text.decode('utf8')
        return None

    def _get_function_call_info(self, node):
        # function: identifier
        # arguments: argument_list
        function_node = node.child_by_field_name('function')
        arguments_node = node.child_by_field_name('arguments')
        
        if not function_node: return None, [], ""
        
        func_name = function_node.text.decode('utf8')
        args = []
        raw_args = ""
        
        if arguments_node:
            raw_args = arguments_node.text.decode('utf8')
            # 간단한 인자 추출 (자식의 텍스트만)
            for child in arguments_node.children:
                if child.type not in ['(', ')', ',']:
                    args.append(child.text.decode('utf8'))
                    
        return func_name, args, raw_args

