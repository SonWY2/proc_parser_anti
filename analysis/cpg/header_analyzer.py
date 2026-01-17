"""
헤더 파일 의존성 분석 모듈

#include 및 EXEC SQL INCLUDE 문을 분석하여 파일 간 의존성을 추출합니다.
"""

import re
import os
from typing import List, Dict, Set, Optional
from dataclasses import dataclass
from .models import CPG, Node, IncludeEdge, NodeType


@dataclass
class IncludeInfo:
    """Include 정보"""
    header_name: str
    is_system_header: bool
    line_number: int
    is_sql_include: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "header_name": self.header_name,
            "is_system_header": self.is_system_header,
            "line_number": self.line_number,
            "is_sql_include": self.is_sql_include
        }


class HeaderAnalyzer:
    """헤더 파일 의존성 분석기"""
    
    # 정규식 패턴
    SYSTEM_INCLUDE_PATTERN = re.compile(r'^\s*#\s*include\s*<([^>]+)>', re.MULTILINE)
    LOCAL_INCLUDE_PATTERN = re.compile(r'^\s*#\s*include\s*"([^"]+)"', re.MULTILINE)
    SQL_INCLUDE_PATTERN = re.compile(
        r'EXEC\s+SQL\s+INCLUDE\s+(\w+)\s*;',
        re.IGNORECASE | re.MULTILINE
    )
    
    def __init__(self, include_paths: List[str] = None, verbose: bool = False):
        """헤더 분석기 초기화
        
        Args:
            include_paths: 헤더 파일 검색 경로 리스트
            verbose: 상세 로그 출력 여부
        """
        self.include_paths: List[str] = include_paths or []
        self.verbose = verbose
        
        # 파일 -> 포함하는 헤더 목록
        self.dependencies: Dict[str, List[IncludeInfo]] = {}
        # 헤더 -> 해당 헤더를 포함하는 파일 목록
        self.dependents: Dict[str, Set[str]] = {}
        # 순환 참조 방지용 방문 기록
        self.visited_headers: Set[str] = set()
        # 실제 해결된 헤더 경로 기록 {헤더명: 실제경로}
        self.resolved_paths: Dict[str, str] = {}
    
    def set_include_paths(self, paths: List[str]):
        """헤더 검색 경로를 설정합니다.
        
        Args:
            paths: 헤더 파일 검색 경로 리스트
        """
        self.include_paths = paths
    
    def add_include_path(self, path: str):
        """헤더 검색 경로를 추가합니다.
        
        Args:
            path: 추가할 경로
        """
        if path not in self.include_paths:
            self.include_paths.append(path)
    
    def resolve_header_path(self, header_name: str, source_dir: str) -> Optional[str]:
        """헤더 파일의 실제 경로를 검색합니다.
        
        검색 순서:
        1. 소스 파일과 같은 디렉토리
        2. include_paths에 지정된 경로들 (순서대로)
        
        Args:
            header_name: 헤더 파일명 (예: "utils.h", "common/types.h")
            source_dir: 현재 소스 파일의 디렉토리
            
        Returns:
            헤더 파일의 절대 경로, 찾지 못하면 None
        """
        candidates = []
        
        # 1. 소스 파일과 같은 디렉토리
        local_path = os.path.join(source_dir, header_name)
        candidates.append(local_path)
        
        # 2. include_paths 순서대로
        for inc_path in self.include_paths:
            candidate = os.path.join(inc_path, header_name)
            candidates.append(candidate)
        
        # 순서대로 검색
        for candidate in candidates:
            abs_path = os.path.abspath(candidate)
            if os.path.isfile(abs_path):
                if self.verbose:
                    print(f"[HeaderAnalyzer] '{header_name}' -> '{abs_path}'")
                return abs_path
        
        if self.verbose:
            print(f"[HeaderAnalyzer] '{header_name}' 찾을 수 없음 (검색 경로: {candidates})")
        
        return None
    
    def analyze_recursive(self, file_path: str, source_code: str = None) -> CPG:
        """파일에서 시작하여 모든 include된 헤더를 재귀적으로 분석합니다.
        
        Args:
            file_path: 시작 파일 경로
            source_code: 소스 코드 (None이면 파일에서 읽음)
            
        Returns:
            CPG: 모든 파일/헤더 노드와 include 엣지를 포함한 CPG
        """
        # 방문 기록 초기화
        self.visited_headers.clear()
        self.resolved_paths.clear()
        
        cpg = CPG()
        self._analyze_file_recursive(file_path, source_code, cpg)
        
        return cpg
    
    def _analyze_file_recursive(self, file_path: str, source_code: str, cpg: CPG):
        """재귀적으로 파일을 분석합니다 (내부 메서드)."""
        file_path = os.path.abspath(file_path)
        
        # 순환 참조 방지
        if file_path in self.visited_headers:
            if self.verbose:
                print(f"[HeaderAnalyzer] 순환 참조 스킵: {file_path}")
            return
        
        self.visited_headers.add(file_path)
        
        # 소스 코드 로드
        if source_code is None:
            if not os.path.exists(file_path):
                if self.verbose:
                    print(f"[HeaderAnalyzer] 파일 없음: {file_path}")
                return
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    source_code = f.read()
            except Exception as e:
                if self.verbose:
                    print(f"[HeaderAnalyzer] 파일 읽기 오류: {file_path} - {e}")
                return
        
        source_dir = os.path.dirname(file_path)
        
        # 파일 노드 추가
        file_node = Node(
            id=f"file::{file_path}",
            node_type=NodeType.FILE,
            name=os.path.basename(file_path),
            file_path=file_path
        )
        cpg.add_node(file_node)
        
        # include 문 추출
        includes = self.extract_includes(source_code, file_path)
        
        for inc in includes:
            # 헤더 노드 추가
            header_id = f"header::{inc.header_name}"
            if header_id not in cpg.nodes:
                header_node = Node(
                    id=header_id,
                    node_type=NodeType.HEADER,
                    name=inc.header_name,
                    attributes={
                        "is_system_header": inc.is_system_header,
                        "is_sql_include": inc.is_sql_include
                    }
                )
                cpg.add_node(header_node)
            
            # include 엣지 추가
            include_edge = IncludeEdge(
                source_id=f"file::{file_path}",
                target_id=header_id,
                is_system_header=inc.is_system_header,
                attributes={"line_number": inc.line_number}
            )
            cpg.add_edge(include_edge)
            
            # 로컬 헤더만 재귀적으로 분석 (시스템 헤더 제외)
            if not inc.is_system_header:
                resolved_path = self.resolve_header_path(inc.header_name, source_dir)
                
                if resolved_path:
                    # 해결된 경로 기록
                    self.resolved_paths[inc.header_name] = resolved_path
                    
                    # 헤더 노드에 실제 경로 추가
                    if header_id in cpg.nodes:
                        cpg.nodes[header_id].file_path = resolved_path
                    
                    # 재귀적으로 분석
                    self._analyze_file_recursive(resolved_path, None, cpg)
    
    def extract_includes(self, source_code: str, file_path: str = "<unknown>") -> List[IncludeInfo]:
        """
        소스 코드에서 include 문을 추출합니다.
        
        Args:
            source_code: 소스 코드
            file_path: 파일 경로
            
        Returns:
            IncludeInfo 리스트
        """
        includes = []
        lines = source_code.split('\n')
        
        # 시스템 헤더 (<header.h>)
        for match in self.SYSTEM_INCLUDE_PATTERN.finditer(source_code):
            header_name = match.group(1)
            line_num = source_code[:match.start()].count('\n') + 1
            includes.append(IncludeInfo(
                header_name=header_name,
                is_system_header=True,
                line_number=line_num
            ))
        
        # 로컬 헤더 ("header.h")
        for match in self.LOCAL_INCLUDE_PATTERN.finditer(source_code):
            header_name = match.group(1)
            line_num = source_code[:match.start()].count('\n') + 1
            includes.append(IncludeInfo(
                header_name=header_name,
                is_system_header=False,
                line_number=line_num
            ))
        
        # EXEC SQL INCLUDE
        for match in self.SQL_INCLUDE_PATTERN.finditer(source_code):
            header_name = match.group(1)
            line_num = source_code[:match.start()].count('\n') + 1
            includes.append(IncludeInfo(
                header_name=header_name,
                is_system_header=False,
                line_number=line_num,
                is_sql_include=True
            ))
        
        # 의존성 맵 업데이트
        self.dependencies[file_path] = includes
        for inc in includes:
            if inc.header_name not in self.dependents:
                self.dependents[inc.header_name] = set()
            self.dependents[inc.header_name].add(file_path)
        
        return includes
    
    def build_dependency_cpg(self, files: Dict[str, str]) -> CPG:
        """
        여러 파일의 의존성 그래프를 CPG로 구성합니다.
        
        Args:
            files: {파일경로: 소스코드} 딕셔너리
            
        Returns:
            CPG: 파일/헤더 노드와 include 엣지를 포함한 CPG
        """
        cpg = CPG()
        
        # 모든 파일에서 include 추출
        for file_path, source_code in files.items():
            # 파일 노드 추가
            file_node = Node(
                id=f"file::{file_path}",
                node_type=NodeType.FILE,
                name=os.path.basename(file_path),
                file_path=file_path
            )
            cpg.add_node(file_node)
            
            # include 추출
            includes = self.extract_includes(source_code, file_path)
            
            for inc in includes:
                # 헤더 노드 추가
                header_id = f"header::{inc.header_name}"
                if header_id not in cpg.nodes:
                    header_node = Node(
                        id=header_id,
                        node_type=NodeType.HEADER,
                        name=inc.header_name,
                        attributes={
                            "is_system_header": inc.is_system_header,
                            "is_sql_include": inc.is_sql_include
                        }
                    )
                    cpg.add_node(header_node)
                
                # include 엣지 추가
                include_edge = IncludeEdge(
                    source_id=f"file::{file_path}",
                    target_id=header_id,
                    is_system_header=inc.is_system_header,
                    attributes={"line_number": inc.line_number}
                )
                cpg.add_edge(include_edge)
        
        return cpg
    
    def get_dependents(self, header_name: str) -> List[str]:
        """
        특정 헤더를 사용하는 모든 파일 목록을 반환합니다.
        
        Args:
            header_name: 헤더 파일명
            
        Returns:
            헤더를 포함하는 파일 경로 목록
        """
        return list(self.dependents.get(header_name, set()))
    
    def get_dependencies(self, file_path: str) -> List[IncludeInfo]:
        """
        특정 파일이 포함하는 헤더 목록을 반환합니다.
        
        Args:
            file_path: 파일 경로
            
        Returns:
            IncludeInfo 리스트
        """
        return self.dependencies.get(file_path, [])
    
    def get_common_headers(self, file_paths: List[str]) -> List[str]:
        """
        여러 파일이 공통으로 포함하는 헤더 목록을 반환합니다.
        
        Args:
            file_paths: 파일 경로 목록
            
        Returns:
            공통 헤더 이름 목록
        """
        if not file_paths:
            return []
        
        common = None
        for file_path in file_paths:
            headers = set(inc.header_name for inc in self.dependencies.get(file_path, []))
            if common is None:
                common = headers
            else:
                common = common.intersection(headers)
        
        return list(common) if common else []
    
    def get_files_sharing_header(self, header_name: str) -> List[str]:
        """
        같은 헤더를 공유하는 파일 간 연결을 반환합니다.
        
        Args:
            header_name: 헤더 파일명
            
        Returns:
            해당 헤더를 포함하는 파일 목록
        """
        return self.get_dependents(header_name)
