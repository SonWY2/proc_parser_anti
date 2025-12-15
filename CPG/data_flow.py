"""
데이터 흐름 분석 모듈

변수 정의/사용(def-use) 및 구조체 필드 접근을 추적합니다.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field
from .models import (
    CPG, VariableNode, StructNode, DataFlowEdge, Edge, 
    NodeType, EdgeType
)

try:
    from c_parser import CParser
    HAS_PARSER = True
except ImportError:
    HAS_PARSER = False


@dataclass
class VariableUse:
    """변수 사용 정보"""
    variable_name: str
    use_type: str  # "define", "read", "write", "parameter"
    line_number: int
    function_context: Optional[str] = None
    expression: Optional[str] = None


@dataclass
class FieldAccess:
    """구조체 필드 접근 정보"""
    struct_name: str
    field_name: str
    access_type: str  # "read", "write"
    line_number: int
    function_context: Optional[str] = None
    is_pointer: bool = False  # -> vs .


class DataFlowAnalyzer:
    """데이터 흐름 분석기"""
    
    # 정규식 패턴
    ASSIGNMENT_PATTERN = re.compile(
        r'(\w+)\s*((?:\[\w+\])?)\s*=\s*([^;]+);',
        re.MULTILINE
    )
    # 체인 할당: a = b = c = 0
    CHAIN_ASSIGNMENT_PATTERN = re.compile(
        r'((?:\w+\s*=\s*)+)([^;]+);',
        re.MULTILINE
    )
    # 포인터 연산: *(ptr + 1) = val, ptr[expr] = val
    POINTER_WRITE_PATTERN = re.compile(
        r'\*\s*\(([^)]+)\)\s*=\s*([^;]+);|'  # *(ptr + offset) = val
        r'(\w+)\s*\[([^\]]+)\]\s*=\s*([^;]+);',  # arr[expr] = val
        re.MULTILINE
    )
    STRUCT_ACCESS_PATTERN = re.compile(
        r'(\w+)\s*(->|\.)\s*(\w+)',
        re.MULTILINE
    )
    DECLARATION_PATTERN = re.compile(
        r'(?:static\s+|const\s+|volatile\s+)*'
        r'(\w+(?:\s*\*)*)\s+'
        r'(\w+)\s*'
        r'(?:\[([^\]]*)\])?\s*'
        r'(?:=\s*([^;]+))?\s*;',
        re.MULTILINE
    )
    # 매크로 정의: #define NAME(args) body
    MACRO_PATTERN = re.compile(
        r'^\s*#\s*define\s+(\w+)(?:\(([^)]*)\))?\s*(.*)$',
        re.MULTILINE
    )
    
    def __init__(self):
        if HAS_PARSER:
            self.c_parser = CParser()
        else:
            self.c_parser = None
        
        # 변수 정의: {변수명: VariableNode}
        self.variables: Dict[str, VariableNode] = {}
        # 변수 사용 목록
        self.variable_uses: List[VariableUse] = []
        # 구조체 정의: {구조체명: StructNode}
        self.structs: Dict[str, StructNode] = {}
        # 필드 접근 목록
        self.field_accesses: List[FieldAccess] = []
        # 매크로 정의: {매크로명: {params, body, line}}
        self.macros: Dict[str, Dict] = {}
    
    def analyze(self, source_code: str, file_path: str = "<unknown>") -> CPG:
        """
        소스 코드의 데이터 흐름을 분석합니다.
        
        Args:
            source_code: 소스 코드
            file_path: 파일 경로
            
        Returns:
            CPG: 변수 노드와 데이터 흐름 엣지를 포함한 CPG
        """
        cpg = CPG()
        lines = source_code.split('\n')
        
        current_function = None
        
        # tree-sitter 파싱 (가능한 경우)
        if self.c_parser:
            elements = self.c_parser.parse(source_code)
            self._process_parsed_elements(elements, file_path, cpg)
        
        # 정규식 기반 추가 분석
        self._analyze_declarations(source_code, file_path, cpg)
        self._analyze_assignments(source_code, file_path, cpg)
        self._analyze_chain_assignments(source_code, file_path, cpg)
        self._analyze_pointer_operations(source_code, file_path, cpg)
        self._analyze_struct_access(source_code, file_path, cpg)
        self._analyze_macros(source_code, file_path, cpg)
        
        # Pro*C 호스트 변수 분석
        self._analyze_host_variables(source_code, file_path, cpg)
        
        return cpg
    
    def _process_parsed_elements(self, elements: List[Dict], file_path: str, cpg: CPG):
        """tree-sitter 파싱 결과 처리"""
        current_function = None
        
        for elem in elements:
            elem_type = elem.get("type")
            
            if elem_type == "function":
                current_function = elem.get("name")
            
            elif elem_type == "variable":
                var_name = elem.get("name")
                if var_name:
                    node_id = f"{file_path}::var::{var_name}"
                    is_global = elem.get("function") is None
                    
                    var_node = VariableNode(
                        id=node_id,
                        node_type=NodeType.VARIABLE,
                        name=var_name,
                        file_path=file_path,
                        line_start=elem.get("line_start"),
                        line_end=elem.get("line_end"),
                        data_type=elem.get("data_type"),
                        is_global=is_global
                    )
                    self.variables[var_name] = var_node
                    cpg.add_node(var_node)
                    
                    # 정의 사용 기록
                    self.variable_uses.append(VariableUse(
                        variable_name=var_name,
                        use_type="define",
                        line_number=elem.get("line_start", 0),
                        function_context=current_function
                    ))
            
            elif elem_type == "struct":
                struct_name = elem.get("name")
                if struct_name:
                    node_id = f"{file_path}::struct::{struct_name}"
                    struct_node = StructNode(
                        id=node_id,
                        node_type=NodeType.STRUCT,
                        name=struct_name,
                        file_path=file_path,
                        line_start=elem.get("line_start"),
                        line_end=elem.get("line_end")
                    )
                    self.structs[struct_name] = struct_node
                    cpg.add_node(struct_node)
    
    def _analyze_declarations(self, source_code: str, file_path: str, cpg: CPG):
        """변수 선언 분석"""
        for match in self.DECLARATION_PATTERN.finditer(source_code):
            var_type = match.group(1).strip()
            var_name = match.group(2)
            array_size = match.group(3)
            init_value = match.group(4)
            line_num = source_code[:match.start()].count('\n') + 1
            
            if var_name and var_name not in self.variables:
                node_id = f"{file_path}::var::{var_name}"
                var_node = VariableNode(
                    id=node_id,
                    node_type=NodeType.VARIABLE,
                    name=var_name,
                    file_path=file_path,
                    line_start=line_num,
                    data_type=var_type,
                    attributes={
                        "array_size": array_size,
                        "has_initializer": init_value is not None
                    }
                )
                self.variables[var_name] = var_node
                cpg.add_node(var_node)
    
    def _analyze_assignments(self, source_code: str, file_path: str, cpg: CPG):
        """할당문 분석"""
        for match in self.ASSIGNMENT_PATTERN.finditer(source_code):
            target_var = match.group(1)
            array_idx = match.group(2)
            value_expr = match.group(3)
            line_num = source_code[:match.start()].count('\n') + 1
            
            # 좌변 변수 (write)
            self.variable_uses.append(VariableUse(
                variable_name=target_var,
                use_type="write",
                line_number=line_num,
                expression=value_expr.strip()
            ))
            
            # 우변 변수들 (read)
            for var_name in self.variables.keys():
                if re.search(rf'\b{re.escape(var_name)}\b', value_expr):
                    self.variable_uses.append(VariableUse(
                        variable_name=var_name,
                        use_type="read",
                        line_number=line_num
                    ))
                    
                    # 데이터 흐름 엣지 생성
                    if target_var in self.variables:
                        source_id = f"{file_path}::var::{var_name}"
                        target_id = f"{file_path}::var::{target_var}"
                        flow_edge = DataFlowEdge(
                            source_id=source_id,
                            target_id=target_id,
                            flow_type="assignment",
                            attributes={"line_number": line_num}
                        )
                        cpg.add_edge(flow_edge)
    
    def _analyze_chain_assignments(self, source_code: str, file_path: str, cpg: CPG):
        """체인 할당문 분석: a = b = c = 0"""
        for match in self.CHAIN_ASSIGNMENT_PATTERN.finditer(source_code):
            chain_part = match.group(1)  # "a = b = c = "
            final_value = match.group(2)  # "0"
            line_num = source_code[:match.start()].count('\n') + 1
            
            # 체인에서 모든 변수 추출
            chain_vars = re.findall(r'(\w+)\s*=', chain_part)
            
            if len(chain_vars) > 1:  # 실제 체인 할당인 경우만
                for i, var_name in enumerate(chain_vars):
                    # 모든 변수에 write 기록
                    self.variable_uses.append(VariableUse(
                        variable_name=var_name,
                        use_type="write",
                        line_number=line_num,
                        expression=f"chain assignment: {match.group(0).strip()}"
                    ))
                    
                    # 변수 간 데이터 흐름 엣지 (역순)
                    if i < len(chain_vars) - 1:
                        next_var = chain_vars[i + 1]
                        if var_name in self.variables and next_var in self.variables:
                            flow_edge = DataFlowEdge(
                                source_id=f"{file_path}::var::{next_var}",
                                target_id=f"{file_path}::var::{var_name}",
                                flow_type="chain_assignment",
                                attributes={"line_number": line_num}
                            )
                            cpg.add_edge(flow_edge)
    
    def _analyze_pointer_operations(self, source_code: str, file_path: str, cpg: CPG):
        """포인터 연산 분석: *(ptr + offset), arr[expr]"""
        for match in self.POINTER_WRITE_PATTERN.finditer(source_code):
            line_num = source_code[:match.start()].count('\n') + 1
            
            if match.group(1):  # *(ptr + offset) = val 형태
                ptr_expr = match.group(1)
                value_expr = match.group(2)
                
                # 포인터 표현식에서 변수 추출
                ptr_vars = re.findall(r'\b(\w+)\b', ptr_expr)
                for var_name in ptr_vars:
                    if var_name in self.variables:
                        self.variable_uses.append(VariableUse(
                            variable_name=var_name,
                            use_type="read",
                            line_number=line_num,
                            expression=f"pointer deref: *({ptr_expr})"
                        ))
                
            elif match.group(3):  # arr[expr] = val 형태
                arr_name = match.group(3)
                index_expr = match.group(4)
                value_expr = match.group(5)
                
                # 배열 접근 기록
                self.variable_uses.append(VariableUse(
                    variable_name=arr_name,
                    use_type="write",
                    line_number=line_num,
                    expression=f"{arr_name}[{index_expr}] = {value_expr}"
                ))
                
                # 인덱스 표현식 내 변수들 (read)
                idx_vars = re.findall(r'\b(\w+)\b', index_expr)
                for var_name in idx_vars:
                    if var_name in self.variables and var_name != arr_name:
                        self.variable_uses.append(VariableUse(
                            variable_name=var_name,
                            use_type="read",
                            line_number=line_num
                        ))
    
    def _analyze_macros(self, source_code: str, file_path: str, cpg: CPG):
        """매크로 정의 분석"""
        for match in self.MACRO_PATTERN.finditer(source_code):
            macro_name = match.group(1)
            macro_params = match.group(2)  # None if no params
            macro_body = match.group(3).strip()
            line_num = source_code[:match.start()].count('\n') + 1
            
            # 매크로 정보 저장
            self.macros[macro_name] = {
                "params": macro_params.split(',') if macro_params else [],
                "body": macro_body,
                "line": line_num,
                "is_function_like": macro_params is not None
            }
            
            # 매크로 내부에서 사용하는 변수 추적
            if macro_body:
                for var_name in self.variables.keys():
                    if re.search(rf'\b{re.escape(var_name)}\b', macro_body):
                        self.variable_uses.append(VariableUse(
                            variable_name=var_name,
                            use_type="read",
                            line_number=line_num,
                            expression=f"macro {macro_name}"
                        ))

    def _analyze_struct_access(self, source_code: str, file_path: str, cpg: CPG):
        """구조체 필드 접근 분석"""
        for match in self.STRUCT_ACCESS_PATTERN.finditer(source_code):
            struct_var = match.group(1)
            operator = match.group(2)
            field_name = match.group(3)
            line_num = source_code[:match.start()].count('\n') + 1
            
            is_pointer = operator == "->"
            
            # 할당의 좌변인지 확인
            full_match = match.group(0)
            match_end = match.end()
            remaining = source_code[match_end:match_end + 50]  # 다음 50자 확인
            is_write = remaining.strip().startswith('=')
            
            self.field_accesses.append(FieldAccess(
                struct_name=struct_var,
                field_name=field_name,
                access_type="write" if is_write else "read",
                line_number=line_num,
                is_pointer=is_pointer
            ))
            
            # 구조체 변수가 존재하면 필드 접근 엣지 추가
            if struct_var in self.variables:
                struct_var_id = f"{file_path}::var::{struct_var}"
                field_id = f"{file_path}::field::{struct_var}.{field_name}"
                
                # 필드 노드 생성
                field_node = VariableNode(
                    id=field_id,
                    node_type=NodeType.VARIABLE,
                    name=f"{struct_var}.{field_name}",
                    file_path=file_path,
                    line_start=line_num,
                    attributes={"is_field": True, "parent_struct": struct_var}
                )
                cpg.add_node(field_node)
                
                # 필드 접근 엣지
                access_edge = Edge(
                    source_id=struct_var_id,
                    target_id=field_id,
                    edge_type=EdgeType.FIELD_ACCESS,
                    attributes={
                        "access_type": "write" if is_write else "read",
                        "line_number": line_num,
                        "is_pointer_access": is_pointer
                    }
                )
                cpg.add_edge(access_edge)
    
    def _analyze_host_variables(self, source_code: str, file_path: str, cpg: CPG):
        """Pro*C 호스트 변수 분석"""
        # EXEC SQL BEGIN/END DECLARE SECTION 사이의 변수
        declare_pattern = re.compile(
            r'EXEC\s+SQL\s+BEGIN\s+DECLARE\s+SECTION\s*;'
            r'(.*?)'
            r'EXEC\s+SQL\s+END\s+DECLARE\s+SECTION\s*;',
            re.DOTALL | re.IGNORECASE
        )
        
        for match in declare_pattern.finditer(source_code):
            section_content = match.group(1)
            section_start = source_code[:match.start()].count('\n') + 1
            
            # 섹션 내 변수 선언 분석
            for decl_match in self.DECLARATION_PATTERN.finditer(section_content):
                var_name = decl_match.group(2)
                var_type = decl_match.group(1).strip()
                line_in_section = section_content[:decl_match.start()].count('\n')
                
                if var_name:
                    node_id = f"{file_path}::host_var::{var_name}"
                    
                    # 기존 변수 노드가 있으면 호스트 변수로 마킹
                    if var_name in self.variables:
                        self.variables[var_name].is_host_variable = True
                    else:
                        host_var_node = VariableNode(
                            id=node_id,
                            node_type=NodeType.VARIABLE,
                            name=var_name,
                            file_path=file_path,
                            line_start=section_start + line_in_section,
                            data_type=var_type,
                            is_host_variable=True,
                            is_global=True
                        )
                        self.variables[var_name] = host_var_node
                        cpg.add_node(host_var_node)
    
    def get_variable_uses(self, var_name: str) -> List[VariableUse]:
        """특정 변수의 모든 사용 위치 반환"""
        return [u for u in self.variable_uses if u.variable_name == var_name]
    
    def get_variable_definitions(self, var_name: str) -> List[VariableUse]:
        """변수 정의 위치 반환"""
        return [u for u in self.variable_uses 
                if u.variable_name == var_name and u.use_type == "define"]
    
    def get_variable_reads(self, var_name: str) -> List[VariableUse]:
        """변수 읽기 위치 반환"""
        return [u for u in self.variable_uses 
                if u.variable_name == var_name and u.use_type == "read"]
    
    def get_variable_writes(self, var_name: str) -> List[VariableUse]:
        """변수 쓰기 위치 반환"""
        return [u for u in self.variable_uses 
                if u.variable_name == var_name and u.use_type == "write"]
    
    def get_struct_field_accesses(self, struct_name: str) -> List[FieldAccess]:
        """특정 구조체의 필드 접근 목록 반환"""
        return [a for a in self.field_accesses if a.struct_name == struct_name]
    
    def get_def_use_chains(self, var_name: str) -> Dict:
        """변수의 def-use 체인 반환"""
        definitions = self.get_variable_definitions(var_name)
        reads = self.get_variable_reads(var_name)
        writes = self.get_variable_writes(var_name)
        
        return {
            "variable": var_name,
            "definitions": [{"line": d.line_number, "function": d.function_context} 
                           for d in definitions],
            "reads": [{"line": r.line_number, "function": r.function_context} 
                      for r in reads],
            "writes": [{"line": w.line_number, "function": w.function_context, 
                       "expression": w.expression} for w in writes]
        }
