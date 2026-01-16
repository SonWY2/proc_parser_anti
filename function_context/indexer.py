"""
메타데이터 인덱서

UnifiedMetadataGenerator의 출력을 인덱싱하여 빠른 조회를 지원합니다.
"""
from typing import Dict, List, Optional, Tuple
from .types import FunctionInfo


class MetadataIndexer:
    """
    메타데이터 인덱싱 및 조회
    
    Pro*C 분석 메타데이터를 인덱싱하여 함수명, 라인 번호 등으로
    빠르게 관련 정보를 조회할 수 있게 합니다.
    """
    
    def __init__(self, metadata: Dict):
        """
        Args:
            metadata: UnifiedMetadataGenerator.generate() 출력
        """
        self.metadata = metadata
        
        # 인덱스 구축
        self._function_index: Dict[str, FunctionInfo] = {}
        self._line_to_function: List[Tuple[int, int, str]] = []  # (start, end, name) 정렬된 리스트
        self._sql_by_function: Dict[str, List[Dict]] = {}
        self._global_vars: List[Dict] = []
        self._macros: Dict[str, Dict] = {}
        self._structs: Dict[str, Dict] = {}
        
        self._build_indices()
    
    def _build_indices(self):
        """모든 인덱스 구축"""
        elements = self.metadata.get("elements", {})
        
        # 함수 인덱스
        self._build_function_index(elements.get("functions", []))
        
        # SQL을 함수별로 그룹화
        self._build_sql_index(elements.get("sql", []))
        
        # 전역 변수
        self._global_vars = [
            v for v in elements.get("variables", [])
            if v.get("scope") == "global"
        ]
        
        # 매크로 인덱스 (이름 → 정보)
        for macro in elements.get("macros", []):
            self._macros[macro.get("name", "")] = macro
        
        # 구조체 인덱스 (이름 → 정보)
        for struct in elements.get("structs", []):
            self._structs[struct.get("name", "")] = struct
    
    def _build_function_index(self, functions: List[Dict]):
        """함수 인덱스 구축"""
        for func in functions:
            name = func.get("name", "")
            if not name:
                continue
            
            info = FunctionInfo(
                name=name,
                line_start=func.get("line_start", 0),
                line_end=func.get("line_end", 0),
                return_type=func.get("return_type", "void"),
                parameters=func.get("parameters", [])
            )
            
            self._function_index[name] = info
            self._line_to_function.append((info.line_start, info.line_end, name))
        
        # 라인 범위로 정렬
        self._line_to_function.sort(key=lambda x: x[0])
    
    def _build_sql_index(self, sql_elements: List[Dict]):
        """SQL을 함수별로 그룹화"""
        for sql in sql_elements:
            func_name = sql.get("function_name") or sql.get("containing_function")
            
            # 함수명이 없으면 라인으로 찾기
            if not func_name:
                line = sql.get("line_start", 0)
                func_name = self.find_function_for_line(line)
            
            if func_name:
                if func_name not in self._sql_by_function:
                    self._sql_by_function[func_name] = []
                self._sql_by_function[func_name].append(sql)
    
    def get_function_info(self, name: str) -> Optional[FunctionInfo]:
        """함수명으로 함수 정보 조회"""
        return self._function_index.get(name)
    
    def list_functions(self) -> List[str]:
        """모든 함수명 목록 반환"""
        return list(self._function_index.keys())
    
    def find_function_for_line(self, line: int) -> Optional[str]:
        """특정 라인이 속한 함수 찾기 (이진 탐색)"""
        for start, end, name in self._line_to_function:
            if start <= line <= end:
                return name
        return None
    
    def get_sql_for_function(self, name: str) -> List[Dict]:
        """특정 함수의 SQL 목록 조회"""
        return self._sql_by_function.get(name, [])
    
    def get_local_variables(self, function_name: str) -> List[Dict]:
        """특정 함수의 로컬 변수 목록 조회"""
        func_info = self._function_index.get(function_name)
        if not func_info:
            return []
        
        elements = self.metadata.get("elements", {})
        variables = elements.get("variables", [])
        
        return [
            v for v in variables
            if v.get("scope") == "local" 
            and func_info.line_start <= v.get("line_start", 0) <= func_info.line_end
        ]
    
    def get_global_variables(self) -> List[Dict]:
        """전역 변수 목록 조회"""
        return self._global_vars
    
    def get_macro(self, name: str) -> Optional[Dict]:
        """매크로 이름으로 조회"""
        return self._macros.get(name)
    
    def get_all_macros(self) -> Dict[str, Dict]:
        """모든 매크로 반환"""
        return self._macros
    
    def get_struct(self, name: str) -> Optional[Dict]:
        """구조체 이름으로 조회"""
        return self._structs.get(name)
    
    def get_all_structs(self) -> Dict[str, Dict]:
        """모든 구조체 반환"""
        return self._structs
    
    def find_used_macros_in_function(self, function_name: str) -> List[Dict]:
        """
        함수 내에서 사용된 매크로 찾기
        
        함수의 raw_content에서 매크로 이름이 등장하는지 확인
        """
        func_info = self._function_index.get(function_name)
        if not func_info:
            return []
        
        elements = self.metadata.get("elements", {})
        functions = elements.get("functions", [])
        
        # 함수의 raw_content 찾기
        raw_content = ""
        for func in functions:
            if func.get("name") == function_name:
                raw_content = func.get("raw_content", "")
                break
        
        if not raw_content:
            return []
        
        used_macros = []
        for name, macro in self._macros.items():
            # 단순 문자열 매칭 (더 정교한 분석은 tree-sitter 필요)
            if name in raw_content:
                used_macros.append(macro)
        
        return used_macros
    
    def find_used_structs_in_function(self, function_name: str) -> List[Dict]:
        """
        함수 내에서 사용된 구조체 찾기
        
        함수의 로컬 변수 타입에서 구조체 이름이 등장하는지 확인
        """
        local_vars = self.get_local_variables(function_name)
        
        used_structs = []
        seen_names = set()
        
        for var in local_vars:
            var_type = var.get("data_type", "")
            for name, struct in self._structs.items():
                if name in var_type and name not in seen_names:
                    used_structs.append(struct)
                    seen_names.add(name)
        
        return used_structs
    
    def find_used_global_vars_in_function(self, function_name: str) -> List[Dict]:
        """
        함수 내에서 사용된 전역 변수 찾기
        
        함수의 raw_content에서 전역 변수 이름이 등장하는지 확인
        """
        func_info = self._function_index.get(function_name)
        if not func_info:
            return []
        
        elements = self.metadata.get("elements", {})
        functions = elements.get("functions", [])
        
        # 함수의 raw_content 찾기
        raw_content = ""
        for func in functions:
            if func.get("name") == function_name:
                raw_content = func.get("raw_content", "")
                break
        
        if not raw_content:
            return []
        
        used_globals = []
        for var in self._global_vars:
            var_name = var.get("name", "")
            if var_name and var_name in raw_content:
                used_globals.append(var)
        
        return used_globals
