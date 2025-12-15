"""
함수 호출 그래프 추출 모듈

C/Pro*C 소스 코드에서 함수 정의와 호출 관계를 추출합니다.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Dict, Set, Optional, Tuple
from .models import (
    CPG, FunctionNode, CallEdge, NodeType
)

try:
    from c_parser import CParser
    HAS_PARSER = True
except ImportError:
    HAS_PARSER = False


class CallGraphExtractor:
    """함수 호출 그래프 추출기"""
    
    def __init__(self):
        if HAS_PARSER:
            self.c_parser = CParser()
        else:
            self.c_parser = None
        
        # 함수 정의 맵: {함수명: FunctionNode}
        self.functions: Dict[str, FunctionNode] = {}
        # 호출 관계: {caller: [callee1, callee2, ...]}
        self.call_map: Dict[str, List[Tuple[str, int, List[str]]]] = {}
        # 역방향 호출 관계: {callee: [caller1, caller2, ...]}
        self.reverse_call_map: Dict[str, Set[str]] = {}
    
    def extract(self, source_code: str, file_path: str = "<unknown>") -> CPG:
        """
        소스 코드에서 호출 그래프를 추출합니다.
        
        Args:
            source_code: C/Pro*C 소스 코드
            file_path: 파일 경로 (노드 식별용)
            
        Returns:
            CPG: 함수 노드와 호출 엣지를 포함한 CPG
        """
        cpg = CPG()
        
        if not self.c_parser:
            return cpg
        
        # tree-sitter로 파싱
        elements = self.c_parser.parse(source_code)
        
        # 1단계: 함수 정의 수집
        for elem in elements:
            if elem.get("type") == "function":
                func_name = elem.get("name")
                if func_name:
                    node_id = f"{file_path}::{func_name}"
                    func_node = FunctionNode(
                        id=node_id,
                        node_type=NodeType.FUNCTION,
                        name=func_name,
                        file_path=file_path,
                        line_start=elem.get("line_start"),
                        line_end=elem.get("line_end"),
                        is_static=self._is_static_function(elem.get("raw_content", ""))
                    )
                    self.functions[func_name] = func_node
                    cpg.add_node(func_node)
        
        # 2단계: 함수 호출 수집
        current_function = None
        for elem in elements:
            if elem.get("type") == "function":
                current_function = elem.get("name")
            elif elem.get("type") == "function_call":
                callee_name = elem.get("name")
                caller_name = elem.get("function") or current_function
                
                if caller_name and callee_name:
                    # 호출 정보 저장
                    call_info = (
                        callee_name,
                        elem.get("line_start"),
                        elem.get("args", [])
                    )
                    
                    if caller_name not in self.call_map:
                        self.call_map[caller_name] = []
                    self.call_map[caller_name].append(call_info)
                    
                    # 역방향 맵 업데이트
                    if callee_name not in self.reverse_call_map:
                        self.reverse_call_map[callee_name] = set()
                    self.reverse_call_map[callee_name].add(caller_name)
                    
                    # 호출 엣지 생성
                    caller_id = f"{file_path}::{caller_name}"
                    callee_id = f"{file_path}::{callee_name}"
                    
                    # callee가 외부 함수인 경우 별도 노드 생성
                    if callee_name not in self.functions:
                        external_node = FunctionNode(
                            id=callee_id,
                            node_type=NodeType.FUNCTION,
                            name=callee_name,
                            file_path=None,  # 외부 함수
                            attributes={"external": True}
                        )
                        cpg.add_node(external_node)
                    
                    call_edge = CallEdge(
                        source_id=caller_id,
                        target_id=callee_id,
                        call_site_line=elem.get("line_start"),
                        arguments=elem.get("args", [])
                    )
                    cpg.add_edge(call_edge)
        
        return cpg
    
    def _is_static_function(self, raw_content: str) -> bool:
        """함수가 static인지 확인"""
        return raw_content.strip().startswith("static")
    
    def get_callers(self, func_name: str) -> List[str]:
        """특정 함수를 호출하는 함수 목록 반환"""
        return list(self.reverse_call_map.get(func_name, set()))
    
    def get_callees(self, func_name: str) -> List[str]:
        """특정 함수가 호출하는 함수 목록 반환"""
        calls = self.call_map.get(func_name, [])
        return list(set(callee for callee, _, _ in calls))
    
    def get_call_chain(self, func_name: str, max_depth: int = 10) -> Dict:
        """
        함수의 호출 체인을 반환합니다.
        
        Args:
            func_name: 시작 함수명
            max_depth: 최대 탐색 깊이
            
        Returns:
            호출 체인 트리 구조
        """
        visited = set()
        
        def _build_chain(name: str, depth: int) -> Dict:
            if depth > max_depth or name in visited:
                return {"name": name, "calls": [], "truncated": depth > max_depth}
            
            visited.add(name)
            callees = self.get_callees(name)
            
            return {
                "name": name,
                "calls": [_build_chain(c, depth + 1) for c in callees]
            }
        
        return _build_chain(func_name, 0)
