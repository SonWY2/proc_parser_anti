"""
Tree-sitter를 사용하여 C 코드를 파싱하는 모듈입니다.
함수 정의, 변수 선언, 구조체 정의, 함수 호출 등을 추출합니다.
"""
import re
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
        self._source_code = source_code  # Store source for comment extraction
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
            # Check if it's a function prototype first
            proto_info = self._get_function_prototype_info(node)
            if proto_info:
                elements.append({
                    "type": "function_prototype",
                    "name": proto_info['name'],
                    "return_type": proto_info['return_type'],
                    "parameters": proto_info.get('parameters', []),
                    "storage_class": proto_info.get('storage_class'),
                    "line_start": node.start_point.row + 1,
                    "line_end": node.end_point.row + 1,
                    "raw_content": node.text.decode('utf8'),
                    "function": current_function
                })
            else:
                # 변수 선언
                var_info = self._get_variable_info(node)
                if var_info and var_info.get('name'):
                    # Extract trailing comment
                    comment = self._extract_trailing_comment(node)
                    elements.append({
                        "type": "variable",
                        "name": var_info['name'],
                        "data_type": var_info['data_type'],
                        "array_sizes": var_info.get('array_sizes', []),
                        "is_pointer": var_info.get('is_pointer', False),
                        "storage_class": var_info.get('storage_class'),
                        "comment": comment,
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

    def _extract_trailing_comment(self, node):
        """
        변수 선언 뒤에 있는 주석을 추출합니다.
        예: `static long H_iacnt_id;  /* 계좌ID */` → `계좌ID`
        
        Returns:
            str: 주석 내용 (없으면 None)
        """
        if not hasattr(self, '_source_code'):
            return None
        
        # 변수 선언이 있는 라인 가져오기
        line_num = node.start_point.row
        lines = self._source_code.split('\n')
        
        if line_num >= len(lines):
            return None
        
        line = lines[line_num]
        
        # /* comment */ 패턴 추출
        block_comment_match = re.search(r'/\*\s*(.+?)\s*\*/', line)
        if block_comment_match:
            return block_comment_match.group(1).strip()
        
        # // comment 패턴 추출
        line_comment_match = re.search(r'//\s*(.+?)$', line)
        if line_comment_match:
            return line_comment_match.group(1).strip()
        
        return None

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
                - pointer_level: 포인터 깊이 (예: **ptr → 2)
                - is_reference: C++ 레퍼런스 여부 (int &ref)
                - storage_class: 저장 클래스 (static, extern 등)
        """
        type_node = node.child_by_field_name('type')
        declarator = node.child_by_field_name('declarator')
        
        if not type_node or not declarator:
            return None
        
        var_type = type_node.text.decode('utf8')
        array_sizes = []
        is_pointer = False
        pointer_level = 0
        is_reference = False
        storage_class = None
        
        # storage_class 추출 (static, extern, register, auto)
        for child in node.children:
            if child.type == 'storage_class_specifier':
                storage_class = child.text.decode('utf8')
                break
        
        # 포인터, 배열, 초기화 처리 - 배열 크기도 수집
        while declarator and declarator.type in ['pointer_declarator', 'array_declarator', 'init_declarator', 'reference_declarator']:
            if declarator.type == 'pointer_declarator':
                is_pointer = True
                pointer_level += 1
                declarator = declarator.child_by_field_name('declarator')
            elif declarator.type == 'reference_declarator':
                is_reference = True
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
                'pointer_level': pointer_level,
                'is_reference': is_reference,
                'storage_class': storage_class
            }
        
        return None

    def _get_struct_name(self, node):
        name_node = node.child_by_field_name('name')
        if name_node and name_node.type == 'type_identifier':
            return name_node.text.decode('utf8')
        return None

    def _get_function_prototype_info(self, node):
        """
        함수 프로토타입(전방 선언)인지 확인하고 정보를 추출합니다.
        
        Returns:
            dict: 함수 프로토타입 정보 또는 None (프로토타입이 아닌 경우)
                - name: 함수 이름
                - return_type: 반환 타입
                - parameters: 파라미터 목록
                - storage_class: 저장 클래스 (static, extern 등)
        """
        declarator = node.child_by_field_name('declarator')
        if not declarator:
            return None
        
        # pointer_declarator를 따라가기 (예: int *func())
        while declarator and declarator.type == 'pointer_declarator':
            declarator = declarator.child_by_field_name('declarator')
        
        # function_declarator가 아니면 함수 프로토타입이 아님
        if not declarator or declarator.type != 'function_declarator':
            return None
        
        # 함수 이름 추출
        func_name = None
        func_declarator = declarator.child_by_field_name('declarator')
        if func_declarator and func_declarator.type == 'identifier':
            func_name = func_declarator.text.decode('utf8')
        
        if not func_name:
            return None
        
        # 반환 타입 추출
        type_node = node.child_by_field_name('type')
        return_type = type_node.text.decode('utf8') if type_node else None
        
        # 저장 클래스 추출
        storage_class = None
        for child in node.children:
            if child.type == 'storage_class_specifier':
                storage_class = child.text.decode('utf8')
                break
        
        # 파라미터 추출
        params = []
        param_list = declarator.child_by_field_name('parameters')
        if param_list:
            for child in param_list.children:
                if child.type == 'parameter_declaration':
                    params.append(child.text.decode('utf8'))
        
        return {
            'name': func_name,
            'return_type': return_type,
            'storage_class': storage_class,
            'parameters': params
        }

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
