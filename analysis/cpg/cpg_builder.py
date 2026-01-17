"""
CPG 통합 빌더 모듈

CallGraphExtractor, HeaderAnalyzer, DataFlowAnalyzer를 통합하여
전체 Code Property Graph를 생성합니다.
"""

import os
import json
from typing import Dict, List, Optional, Set
from pathlib import Path

from .models import CPG, Node, NodeType
from .call_graph import CallGraphExtractor
from .header_analyzer import HeaderAnalyzer
from .data_flow import DataFlowAnalyzer


class CPGBuilder:
    """Code Property Graph 통합 빌더"""
    
    # 지원 파일 확장자
    SUPPORTED_EXTENSIONS = {'.c', '.pc', '.h', '.cpp', '.hpp'}
    
    def __init__(self, include_paths: List[str] = None, verbose: bool = False):
        """CPG 빌더 초기화
        
        Args:
            include_paths: 헤더 파일 검색 경로 리스트
            verbose: 상세 로그 출력 여부
        """
        self.include_paths = include_paths or []
        self.verbose = verbose
        
        self.call_graph_extractor = CallGraphExtractor()
        self.header_analyzer = HeaderAnalyzer(
            include_paths=self.include_paths,
            verbose=self.verbose
        )
        self.data_flow_analyzer = DataFlowAnalyzer()
        self.cpg = CPG()
    
    def set_include_paths(self, paths: List[str]):
        """헤더 검색 경로를 설정합니다.
        
        Args:
            paths: 헤더 파일 검색 경로 리스트
        """
        self.include_paths = paths
        self.header_analyzer.set_include_paths(paths)
    
    def add_include_path(self, path: str):
        """헤더 검색 경로를 추가합니다.
        
        Args:
            path: 추가할 경로
        """
        if path not in self.include_paths:
            self.include_paths.append(path)
        self.header_analyzer.add_include_path(path)
    
    def build_from_file(self, file_path: str, follow_includes: bool = True) -> CPG:
        """
        단일 파일에서 CPG를 생성합니다.
        
        Args:
            file_path: 소스 파일 경로
            follow_includes: True면 include된 헤더를 재귀적으로 분석
            
        Returns:
            CPG: 생성된 Code Property Graph
        """
        file_path = os.path.abspath(file_path)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source_code = f.read()
        
        return self.build_from_source(source_code, file_path, follow_includes)
    
    def build_from_source(self, source_code: str, file_path: str = "<unknown>", 
                          follow_includes: bool = False) -> CPG:
        """
        소스 코드에서 CPG를 생성합니다.
        
        Args:
            source_code: 소스 코드 문자열
            file_path: 파일 경로 (식별용)
            follow_includes: True면 include된 헤더를 재귀적으로 분석
            
        Returns:
            CPG: 생성된 Code Property Graph
        """
        cpg = CPG()
        file_path = os.path.abspath(file_path) if file_path != "<unknown>" else file_path
        
        # 1. 함수 호출 그래프 추출
        call_cpg = self.call_graph_extractor.extract(source_code, file_path)
        cpg.merge(call_cpg)
        
        # 2. 헤더 의존성 분석
        if follow_includes and file_path != "<unknown>":
            # 재귀적 헤더 분석
            header_cpg = self.header_analyzer.analyze_recursive(file_path, source_code)
            cpg.merge(header_cpg)
            
            # 각 해결된 헤더에 대해서도 함수/데이터흐름 분석
            for header_name, header_path in self.header_analyzer.resolved_paths.items():
                try:
                    with open(header_path, 'r', encoding='utf-8', errors='ignore') as f:
                        header_code = f.read()
                    
                    # 헤더의 함수 호출 그래프
                    header_call_cpg = self.call_graph_extractor.extract(header_code, header_path)
                    cpg.merge(header_call_cpg)
                    
                    # 헤더의 데이터 흐름
                    header_data_cpg = self.data_flow_analyzer.analyze(header_code, header_path)
                    cpg.merge(header_data_cpg)
                except Exception as e:
                    if self.verbose:
                        print(f"[CPGBuilder] 헤더 분석 오류: {header_path} - {e}")
        else:
            # 기존 방식: 단순 include 추출만
            includes = self.header_analyzer.extract_includes(source_code, file_path)
            
            # 파일 노드 추가
            file_node = Node(
                id=f"file::{file_path}",
                node_type=NodeType.FILE,
                name=os.path.basename(file_path),
                file_path=file_path
            )
            cpg.add_node(file_node)
            
            # 헤더 노드 및 엣지 추가
            from .models import IncludeEdge
            for inc in includes:
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
                
                include_edge = IncludeEdge(
                    source_id=f"file::{file_path}",
                    target_id=header_id,
                    is_system_header=inc.is_system_header,
                    attributes={"line_number": inc.line_number}
                )
                cpg.add_edge(include_edge)
        
        # 3. 데이터 흐름 분석 (메인 파일)
        data_cpg = self.data_flow_analyzer.analyze(source_code, file_path)
        cpg.merge(data_cpg)
        
        return cpg
    
    def build_from_directory(self, dir_path: str, recursive: bool = True) -> CPG:
        """
        디렉토리의 모든 소스 파일에서 CPG를 생성합니다.
        
        Args:
            dir_path: 디렉토리 경로
            recursive: 하위 디렉토리 포함 여부
            
        Returns:
            CPG: 병합된 Code Property Graph
        """
        dir_path = os.path.abspath(dir_path)
        
        if not os.path.isdir(dir_path):
            raise NotADirectoryError(f"디렉토리가 아닙니다: {dir_path}")
        
        combined_cpg = CPG()
        files_processed = 0
        
        # 파일 수집
        if recursive:
            file_iter = Path(dir_path).rglob('*')
        else:
            file_iter = Path(dir_path).glob('*')
        
        for file_path in file_iter:
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                try:
                    file_cpg = self.build_from_file(str(file_path))
                    combined_cpg.merge(file_cpg)
                    files_processed += 1
                except Exception as e:
                    print(f"경고: {file_path} 처리 중 오류 - {e}")
        
        # 헤더 의존성 그래프 구축 (파일 간 연결)
        # 이미 개별 파일 처리 시 추가됨
        
        combined_cpg.files.add(dir_path)
        print(f"총 {files_processed}개 파일 처리 완료")
        
        return combined_cpg
    
    def export_json(self, cpg: CPG, output_path: str, indent: int = 2):
        """
        CPG를 JSON 파일로 내보냅니다.
        
        Args:
            cpg: CPG 객체
            output_path: 출력 파일 경로
            indent: 들여쓰기 수준
        """
        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(cpg.to_dict(), f, ensure_ascii=False, indent=indent)
        
        print(f"JSON 출력 완료: {output_path}")
    
    def export_jsonl(self, cpg: CPG, output_path: str):
        """
        CPG를 JSONL 파일로 내보냅니다 (노드/엣지 각 라인).
        
        Args:
            cpg: CPG 객체
            output_path: 출력 파일 경로
        """
        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            # 노드 출력
            for node in cpg.nodes.values():
                f.write(json.dumps({"record_type": "node", **node.to_dict()}, 
                                  ensure_ascii=False) + '\n')
            # 엣지 출력
            for edge in cpg.edges:
                f.write(json.dumps({"record_type": "edge", **edge.to_dict()}, 
                                  ensure_ascii=False) + '\n')
        
        print(f"JSONL 출력 완료: {output_path}")
    
    def export_dot(self, cpg: CPG, output_path: str, title: str = "CPG"):
        """
        CPG를 Graphviz DOT 파일로 내보냅니다.
        
        Args:
            cpg: CPG 객체
            output_path: 출력 파일 경로
            title: 그래프 제목
        """
        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        dot_content = cpg.to_dot(title)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(dot_content)
        
        print(f"DOT 출력 완료: {output_path}")
        print(f"시각화: dot -Tpng {output_path} -o output.png")
    
    def get_file_dependencies(self, header_name: str) -> List[str]:
        """
        특정 헤더를 사용하는 파일 목록을 반환합니다.
        
        Args:
            header_name: 헤더 파일명
            
        Returns:
            헤더를 포함하는 파일 경로 목록
        """
        return self.header_analyzer.get_dependents(header_name)
    
    def get_call_chain(self, func_name: str, max_depth: int = 10) -> Dict:
        """
        함수의 호출 체인을 반환합니다.
        
        Args:
            func_name: 시작 함수명
            max_depth: 최대 탐색 깊이
            
        Returns:
            호출 체인 트리 구조
        """
        return self.call_graph_extractor.get_call_chain(func_name, max_depth)
    
    def get_variable_flow(self, var_name: str) -> Dict:
        """
        변수의 데이터 흐름을 반환합니다.
        
        Args:
            var_name: 변수명
            
        Returns:
            def-use 체인 정보
        """
        return self.data_flow_analyzer.get_def_use_chains(var_name)
    
    def summary(self, cpg: CPG) -> str:
        """CPG 요약 정보 반환"""
        from .models import NodeType, EdgeType
        
        lines = ["=" * 50]
        lines.append("CPG Summary")
        lines.append("=" * 50)
        lines.append(f"총 노드 수: {len(cpg.nodes)}")
        lines.append(f"총 엣지 수: {len(cpg.edges)}")
        lines.append(f"파일 수: {len(cpg.files)}")
        lines.append("")
        
        # 노드 타입별 통계
        lines.append("노드 타입별:")
        for nt in NodeType:
            count = len(cpg.get_nodes_by_type(nt))
            if count > 0:
                lines.append(f"  - {nt.value}: {count}")
        
        lines.append("")
        lines.append("엣지 타입별:")
        for et in EdgeType:
            count = len(cpg.get_edges_by_type(et))
            if count > 0:
                lines.append(f"  - {et.value}: {count}")
        
        lines.append("=" * 50)
        return "\n".join(lines)
