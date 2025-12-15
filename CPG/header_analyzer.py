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
    
    def __init__(self):
        # 파일 -> 포함하는 헤더 목록
        self.dependencies: Dict[str, List[IncludeInfo]] = {}
        # 헤더 -> 해당 헤더를 포함하는 파일 목록
        self.dependents: Dict[str, Set[str]] = {}
    
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
