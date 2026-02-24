"""
함수 내 EXEC SQL DECLARE SECTION 변수 추출 모듈

Tree-sitter-c를 사용하여 Pro*C 코드의 함수 내부에 선언된 
EXEC SQL BEGIN/END DECLARE SECTION 블록의 변수들을 추출합니다.

이 모듈은 독립 실행 가능하도록 설계되어 복사/붙여넣기로 다른 프로젝트에서 사용 가능합니다.

Usage:
    from parsing.sql.declare_section_extractor import DeclareSectionVariableExtractor
    
    extractor = DeclareSectionVariableExtractor()
    result = extractor.extract_declare_section_variables_in_function(code)
"""

import re
from typing import List, Dict, Optional, Any, Tuple

try:
    import tree_sitter
    import tree_sitter_c
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False


class DeclareSectionVariableExtractor:
    """
    함수 내 EXEC SQL DECLARE SECTION 변수를 추출하는 클래스.
    
    Pro*C 코드에서 함수 내부의 EXEC SQL BEGIN DECLARE SECTION; ... 
    EXEC SQL END DECLARE SECTION; 블록 사이에 선언된 변수들을 추출합니다.
    
    독립 사용 가능: tree-sitter-c만 의존합니다.
    """
    
    # Pro*C 타입 -> Java 타입 매핑
    PROC_TO_JAVA_TYPE_MAP: Dict[str, str] = {
        # 정수형
        "int": "Integer",
        "long": "Long",
        "short": "Short",
        "unsigned int": "Integer",
        "unsigned long": "Long",
        "unsigned short": "Short",
        "signed int": "Integer",
        "signed long": "Long",
        "signed short": "Short",
        
        # 실수형
        "float": "Float",
        "double": "Double",
        
        # 문자형
        "char": "String",
        "unsigned char": "String",
        "signed char": "String",
        
        # 기타
        "void": "void",
        "VARCHAR": "String",
        "varchar": "String",
    }
    
    def __init__(self):
        """초기화: tree-sitter 파서 설정"""
        if HAS_TREE_SITTER:
            self.language = tree_sitter.Language(tree_sitter_c.language())
            self.parser = tree_sitter.Parser(self.language)
        else:
            self.parser = None
    
    def extract_declare_section_variables_in_function(
        self, 
        code: str
    ) -> List[Dict[str, Any]]:
        """
        Pro*C 코드에서 함수 내 declare section 변수들을 추출합니다.
        
        Args:
            code: Pro*C 소스 코드 문자열
            
        Returns:
            추출된 변수 정보 리스트. 각 변수는 다음 필드를 포함:
            - name: Pro*C 변수명
            - dtype: Pro*C 데이터 타입
            - is_struct: struct 타입 여부
            - value: 초기화 값 (없으면 None)
            - size: 기본 사이즈 (char[50] -> 50)
            - comment: 변수 선언 뒤 주석
            - list_count: array일 경우 배열 크기
            - is_static: static 키워드 여부
            - is_declare_section: 항상 True
            - function_name: 해당 변수가 속한 함수명
            - java_name: camelCase로 변환된 이름
            - java_type: 대응되는 Java 타입
        """
        if not self.parser:
            return []
        
        result: List[Dict[str, Any]] = []
        
        # 1. 함수 정의 찾기
        functions = self._find_functions(code)
        
        # 2. 각 함수 내에서 declare section 찾기
        for func_name, func_start, func_end in functions:
            func_code = code[func_start:func_end]
            
            # 3. declare section 범위 찾기
            sections = self._find_declare_sections_in_range(func_code)
            
            for section_start, section_end in sections:
                section_code = func_code[section_start:section_end]
                
                # 4. section 내 변수 파싱
                variables = self._parse_variables_in_section(
                    section_code, func_name, code
                )
                result.extend(variables)
        
        return result
    
    def _find_functions(self, code: str) -> List[Tuple[str, int, int]]:
        """
        코드에서 함수 정의를 찾습니다.
        
        Returns:
            (함수명, 시작 바이트, 종료 바이트) 튜플 리스트
        """
        tree = self.parser.parse(bytes(code, "utf8"))
        functions = []
        
        def traverse(node):
            if node.type == "function_definition":
                func_name = self._get_function_name(node)
                if func_name:
                    functions.append((
                        func_name, 
                        node.start_byte, 
                        node.end_byte
                    ))
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return functions
    
    def _get_function_name(self, node) -> Optional[str]:
        """함수 정의 노드에서 함수명 추출"""
        declarator = node.child_by_field_name('declarator')
        if not declarator:
            return None
        
        while declarator.type == 'pointer_declarator':
            declarator = declarator.child_by_field_name('declarator')
        
        if declarator.type == 'function_declarator':
            identifier = declarator.child_by_field_name('declarator')
            if identifier and identifier.type == 'identifier':
                return identifier.text.decode('utf8')
        return None
    
    def _find_declare_sections_in_range(
        self, 
        code: str
    ) -> List[Tuple[int, int]]:
        """
        코드 범위 내에서 EXEC SQL BEGIN/END DECLARE SECTION 블록을 찾습니다.
        
        Returns:
            (시작 인덱스, 종료 인덱스) 튜플 리스트
        """
        sections = []
        
        # BEGIN DECLARE SECTION 패턴
        begin_pattern = re.compile(
            r'EXEC\s+SQL\s+BEGIN\s+DECLARE\s+SECTION\s*;',
            re.IGNORECASE
        )
        # END DECLARE SECTION 패턴
        end_pattern = re.compile(
            r'EXEC\s+SQL\s+END\s+DECLARE\s+SECTION\s*;',
            re.IGNORECASE
        )
        
        begin_matches = list(begin_pattern.finditer(code))
        end_matches = list(end_pattern.finditer(code))
        
        # 매칭되는 BEGIN-END 쌍 찾기
        for begin_match in begin_matches:
            begin_end = begin_match.end()
            
            # 이 BEGIN 이후 가장 가까운 END 찾기
            closest_end = None
            for end_match in end_matches:
                if end_match.start() > begin_end:
                    closest_end = end_match
                    break
            
            if closest_end:
                sections.append((begin_end, closest_end.start()))
        
        return sections
    
    def _parse_variables_in_section(
        self, 
        section_code: str,
        function_name: str,
        full_code: str
    ) -> List[Dict[str, Any]]:
        """
        declare section 내의 변수들을 파싱합니다.
        """
        variables = []
        
        # tree-sitter로 파싱
        tree = self.parser.parse(bytes(section_code, "utf8"))
        
        def traverse(node):
            if node.type == 'declaration':
                var_info = self._extract_variable_info(node, section_code)
                if var_info and var_info.get('name'):
                    # 함수 정보 및 메타데이터 추가
                    var_info['function_name'] = function_name
                    var_info['is_declare_section'] = True
                    var_info['java_name'] = self._to_camel_case(var_info['name'])
                    var_info['java_type'] = self._map_to_java_type(
                        var_info['dtype'],
                        var_info.get('list_count') is not None
                    )
                    variables.append(var_info)
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return variables
    
    def _extract_variable_info(
        self, 
        node, 
        source_code: str
    ) -> Optional[Dict[str, Any]]:
        """
        declaration 노드에서 변수 정보를 추출합니다.
        """
        type_node = node.child_by_field_name('type')
        declarator = node.child_by_field_name('declarator')
        
        if not type_node or not declarator:
            return None
        
        # 기본 정보
        var_type = type_node.text.decode('utf8')
        is_struct = type_node.type in ('struct_specifier', 'type_identifier')
        
        # struct 키워드 체크
        if not is_struct and 'struct' in var_type:
            is_struct = True
        
        # Storage class 추출 (static, extern 등)
        is_static = False
        for child in node.children:
            if child.type == 'storage_class_specifier':
                if child.text.decode('utf8') == 'static':
                    is_static = True
                break
        
        # 배열 크기, 포인터, 초기화 값 추출
        array_sizes = []
        init_value = None
        
        while declarator and declarator.type in [
            'pointer_declarator', 'array_declarator', 'init_declarator'
        ]:
            if declarator.type == 'array_declarator':
                size_node = declarator.child_by_field_name('size')
                if size_node:
                    array_sizes.append(size_node.text.decode('utf8'))
                else:
                    array_sizes.append(None)
                declarator = declarator.child_by_field_name('declarator')
            elif declarator.type == 'init_declarator':
                # 초기화 값 추출
                value_node = declarator.child_by_field_name('value')
                if value_node:
                    init_value = value_node.text.decode('utf8')
                declarator = declarator.child_by_field_name('declarator')
            else:
                declarator = declarator.child_by_field_name('declarator')
        
        if not declarator or declarator.type != 'identifier':
            return None
        
        var_name = declarator.text.decode('utf8')
        
        # 배열 크기 역순 정렬 (가장 바깥 차원이 먼저)
        array_sizes = array_sizes[::-1]
        
        # size와 list_count 결정
        size = None
        list_count = None
        
        if array_sizes:
            # 첫 번째 배열 크기를 list_count로
            list_count = array_sizes[0]
            
            # char 타입이면 size로도 사용
            if var_type in ('char', 'unsigned char', 'signed char'):
                size = array_sizes[0]
                if len(array_sizes) > 1:
                    list_count = array_sizes[0]
                    size = array_sizes[-1]  # 마지막 차원이 문자열 크기
                else:
                    list_count = None  # 단순 char 배열은 문자열
        
        # 주석 추출
        comment = self._extract_trailing_comment(node, source_code)
        
        return {
            'name': var_name,
            'dtype': var_type,
            'is_struct': is_struct,
            'value': init_value,
            'size': size,
            'comment': comment,
            'list_count': list_count,
            'is_static': is_static,
        }
    
    def _extract_trailing_comment(
        self, 
        node, 
        source_code: str
    ) -> Optional[str]:
        """
        변수 선언 뒤에 있는 주석을 추출합니다.
        
        예: `int emp_id;  /* 직원 ID */` → `직원 ID`
        """
        line_num = node.start_point.row
        lines = source_code.split('\n')
        
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
    
    def _to_camel_case(self, snake_str: str) -> str:
        """
        snake_case를 camelCase로 변환합니다.
        
        예: emp_id → empId, H_iacnt_id → hIacntId
        """
        # 언더스코어로 분리
        components = snake_str.split('_')
        
        if not components:
            return snake_str
        
        # 첫 단어는 소문자, 나머지는 첫 글자만 대문자
        result = components[0].lower()
        for component in components[1:]:
            if component:
                result += component.capitalize()
        
        return result
    
    def _map_to_java_type(
        self, 
        proc_type: str, 
        is_array: bool
    ) -> str:
        """
        Pro*C 타입을 Java 타입으로 매핑합니다.
        
        배열인 경우 List<T> 형태로 반환합니다.
        """
        # 타입 정규화 (앞뒤 공백 제거, struct 분리)
        type_clean = proc_type.strip()
        
        # struct 타입 처리
        if type_clean.startswith('struct '):
            struct_name = type_clean[7:].strip()
            java_type = struct_name.title().replace('_', '')
            return f"List<{java_type}>" if is_array else java_type
        
        # 매핑 테이블에서 찾기
        java_type = self.PROC_TO_JAVA_TYPE_MAP.get(type_clean, "Object")
        
        if is_array:
            return f"List<{java_type}>"
        
        return java_type


# 편의 함수 (독립 사용 시)
def extract_declare_section_variables_in_function(
    code: str
) -> List[Dict[str, Any]]:
    """
    함수 내 declare section 변수를 추출하는 편의 함수.
    
    Args:
        code: Pro*C 소스 코드 문자열
        
    Returns:
        추출된 변수 정보 리스트
    """
    extractor = DeclareSectionVariableExtractor()
    return extractor.extract_declare_section_variables_in_function(code)


if __name__ == "__main__":
    # 간단한 테스트
    test_code = '''
int get_employees_by_dept(int dept_id) {
    EXEC SQL BEGIN DECLARE SECTION;
    int emp_id;              /* 직원 ID */
    char emp_name[50];       /* 직원명 */
    static int v_count = 0;  /* 카운터 */
    EXEC SQL END DECLARE SECTION;
    
    return 0;
}
'''
    
    extractor = DeclareSectionVariableExtractor()
    result = extractor.extract_declare_section_variables_in_function(test_code)
    
    print("=== 추출된 변수 ===")
    for var in result:
        print(f"\n{var['name']}:")
        for key, value in var.items():
            print(f"  {key}: {value}")
