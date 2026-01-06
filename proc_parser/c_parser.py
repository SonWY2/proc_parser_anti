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
        
        if node_type == 'function_definition':
            # 함수 이름 추출
            func_name = self._get_function_name(node)
            if func_name:
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
        """
        변수 선언에서 상세 정보를 추출합니다.
        
        Returns:
            dict: 변수 정보를 담은 딕셔너리
                - name: 변수 이름
                - data_type: 데이터 타입
                - array_sizes: 다차원 배열 크기 리스트 (예: ["10", "20", "30"])
                - is_pointer: 포인터 여부
                - storage_class: 저장 클래스 (static, extern 등)
        """
        type_node = node.child_by_field_name('type')
        declarator = node.child_by_field_name('declarator')
        
        if not type_node or not declarator:
            return None
        
        var_type = type_node.text.decode('utf8')
        array_sizes = []
        is_pointer = False
        storage_class = None
        
        # storage_class 추출 (static, extern, register, auto)
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
                # 배열 크기 추출
                size_node = declarator.child_by_field_name('size')
                if size_node:
                    array_sizes.append(size_node.text.decode('utf8'))
                else:
                    array_sizes.append(None)  # 크기 미지정 (예: int arr[])
                declarator = declarator.child_by_field_name('declarator')
            elif declarator.type == 'init_declarator':
                declarator = declarator.child_by_field_name('declarator')
        
        if declarator and declarator.type == 'identifier':
            # 배열 크기는 역순으로 저장되므로 뒤집음 (가장 바깥 차원이 먼저)
            return {
                'name': declarator.text.decode('utf8'),
                'data_type': var_type,
                'array_sizes': array_sizes[::-1],
                'is_pointer': is_pointer,
                'storage_class': storage_class
            }
        
        return None

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
