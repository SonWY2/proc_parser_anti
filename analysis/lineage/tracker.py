"""
Variable Lineage Tracker

Pro*C 변수의 변환 경로를 추적하는 메인 클래스입니다.
"""

import json
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .types import LineageNode, LineageLink, LineageGraph, NodeType, LinkType


@dataclass
class LineageConfig:
    """Lineage Tracker 설정"""
    # Prefix 제거 목록 (HostVariableNamingPlugin과 동일)
    prefixes: List[str] = field(default_factory=lambda: ['H_o_', 'H_i_', 'H_', 'W_'])
    # 대소문자 무시 매칭
    case_insensitive: bool = True
    # 최소 매칭 신뢰도
    min_confidence: float = 0.5


class VariableLineageTracker:
    """
    변수 연결관계 추적기
    
    Pro*C 코드에서 추출된 변수들이 MyBatis/Java로 변환되는 과정에서의
    연결관계를 추적합니다.
    
    Usage:
        tracker = VariableLineageTracker()
        
        # 각 모듈 결과 추가
        tracker.add_from_proc_parser(elements)
        tracker.add_from_header_parser(db_vars_info)
        tracker.add_from_sql_extractor(extracted_sqls)
        
        # 연결관계 구축
        tracker.build_links()
        
        # JSON 출력
        result = tracker.to_json()
    """
    
    def __init__(self, config: Optional[LineageConfig] = None, source_file: str = ""):
        self.config = config or LineageConfig()
        self.graph = LineageGraph(source_file=source_file)
        
        # prefix 정렬 (긴 것 먼저)
        self.config.prefixes.sort(key=len, reverse=True)
    
    # ===== 노드 추가 메서드 =====
    
    def add_from_proc_parser(self, elements: List[Dict]) -> int:
        """
        proc_parser 결과에서 노드 추가
        
        Args:
            elements: ProCParser.parse_file() 결과
            
        Returns:
            추가된 노드 수
        """
        added = 0
        for el in elements:
            el_type = el.get('type', '')
            
            if el_type == 'variable':
                node = LineageNode(
                    id=f"proc_var_{el.get('name', '')}",
                    name=el.get('name', ''),
                    node_type=NodeType.PROC_VARIABLE,
                    source_module="proc_parser",
                    metadata={
                        "data_type": el.get('data_type', ''),
                        "array_size": el.get('array_size'),
                        "line_start": el.get('line_start'),
                        "line_end": el.get('line_end'),
                        "function": el.get('function'),
                        "raw_content": el.get('raw_content', '')
                    }
                )
                self.graph.add_node(node)
                added += 1
                
            elif el_type == 'sql':
                # SQL 호스트 변수 추가
                for var in el.get('input_host_vars', []):
                    var_name = var.lstrip(':')
                    node = LineageNode(
                        id=f"sql_host_in_{el.get('sql_id', '')}_{var_name}",
                        name=var_name,
                        node_type=NodeType.SQL_HOST_VAR,
                        source_module="proc_parser",
                        metadata={
                            "direction": "input",
                            "sql_id": el.get('sql_id', ''),
                            "sql_type": el.get('sql_type', ''),
                            "function": el.get('function'),
                            "original_var": var
                        }
                    )
                    self.graph.add_node(node)
                    added += 1
                    
                for var in el.get('output_host_vars', []):
                    var_name = var.lstrip(':')
                    node = LineageNode(
                        id=f"sql_host_out_{el.get('sql_id', '')}_{var_name}",
                        name=var_name,
                        node_type=NodeType.SQL_HOST_VAR,
                        source_module="proc_parser",
                        metadata={
                            "direction": "output",
                            "sql_id": el.get('sql_id', ''),
                            "sql_type": el.get('sql_type', ''),
                            "function": el.get('function'),
                            "original_var": var
                        }
                    )
                    self.graph.add_node(node)
                    added += 1
                    
        return added
    
    def add_from_header_parser(self, db_vars_info: Dict[str, Dict]) -> int:
        """
        header_parser 결과에서 노드 추가
        
        Args:
            db_vars_info: HeaderParser.parse() 결과
            
        Returns:
            추가된 노드 수
        """
        added = 0
        for struct_name, fields in db_vars_info.items():
            for field_name, field_info in fields.items():
                node = LineageNode(
                    id=f"struct_field_{struct_name}_{field_name}",
                    name=field_name,
                    node_type=NodeType.STRUCT_FIELD,
                    source_module="header_parser",
                    metadata={
                        "struct_name": struct_name,
                        "dtype": field_info.get('dtype', ''),
                        "size": field_info.get('size'),
                        "original_name": field_info.get('name', ''),
                        "org_name": field_info.get('org_name', ''),
                        "description": field_info.get('description', ''),
                        "arraySize": field_info.get('arraySize'),
                        "arrayReference": field_info.get('arrayReference')
                    }
                )
                self.graph.add_node(node)
                added += 1
                
        return added
    
    def add_from_sql_extractor(self, extracted_sqls: List[Any]) -> int:
        """
        sql_extractor 결과에서 노드 추가
        
        Args:
            extracted_sqls: SQLExtractor 결과 (ExtractedSQL 또는 dict 리스트)
            
        Returns:
            추가된 노드 수
        """
        added = 0
        for sql in extracted_sqls:
            # ExtractedSQL 객체 또는 dict 처리
            if hasattr(sql, 'to_dict'):
                sql_dict = sql.to_dict()
            else:
                sql_dict = sql
                
            sql_id = sql_dict.get('sql_id', sql_dict.get('id', ''))
            
            for var in sql_dict.get('input_host_vars', sql_dict.get('input_vars', [])):
                var_name = var.lstrip(':')
                node_id = f"sql_host_in_{sql_id}_{var_name}"
                if node_id not in self.graph.nodes:
                    node = LineageNode(
                        id=node_id,
                        name=var_name,
                        node_type=NodeType.SQL_HOST_VAR,
                        source_module="sql_extractor",
                        metadata={
                            "direction": "input",
                            "sql_id": sql_id,
                            "sql_type": sql_dict.get('sql_type', ''),
                            "original_var": var
                        }
                    )
                    self.graph.add_node(node)
                    added += 1
                    
            for var in sql_dict.get('output_host_vars', sql_dict.get('output_vars', [])):
                var_name = var.lstrip(':')
                node_id = f"sql_host_out_{sql_id}_{var_name}"
                if node_id not in self.graph.nodes:
                    node = LineageNode(
                        id=node_id,
                        name=var_name,
                        node_type=NodeType.SQL_HOST_VAR,
                        source_module="sql_extractor",
                        metadata={
                            "direction": "output",
                            "sql_id": sql_id,
                            "sql_type": sql_dict.get('sql_type', ''),
                            "original_var": var
                        }
                    )
                    self.graph.add_node(node)
                    added += 1
                    
        return added
    
    def add_from_omm_generator(self, omm_data: Dict[str, Dict]) -> int:
        """
        omm_generator 결과에서 노드 추가
        
        Args:
            omm_data: OMMGenerator 입력 데이터 (db_vars_info 형식)
            
        Returns:
            추가된 노드 수
        """
        added = 0
        for struct_name, fields in omm_data.items():
            for field_name, field_info in fields.items():
                node = LineageNode(
                    id=f"omm_field_{struct_name}_{field_name}",
                    name=field_name,
                    node_type=NodeType.OMM_FIELD,
                    source_module="omm_generator",
                    metadata={
                        "struct_name": struct_name,
                        "dtype": field_info.get('dtype', ''),
                        "size": field_info.get('size'),
                        "description": field_info.get('description', '')
                    }
                )
                self.graph.add_node(node)
                added += 1
                
        return added
    
    def add_from_dbio_generator(self, sql_calls: List[Dict], dao_name: str = "") -> int:
        """
        dbio_generator 결과에서 노드 추가
        
        Args:
            sql_calls: DBIOGenerator 입력 데이터
            dao_name: DAO 이름
            
        Returns:
            추가된 노드 수
        """
        added = 0
        for sql_call in sql_calls:
            sql_name = sql_call.get('name', '')
            
            for var in sql_call.get('input_vars', []):
                var_name = var.lstrip(':')
                node = LineageNode(
                    id=f"mybatis_param_{dao_name}_{sql_name}_{var_name}",
                    name=var_name,
                    node_type=NodeType.MYBATIS_PARAM,
                    source_module="dbio_generator",
                    metadata={
                        "dao_name": dao_name,
                        "sql_name": sql_name,
                        "direction": "input",
                        "mybatis_format": f"#\u007b{var_name}\u007d"
                    }
                )
                self.graph.add_node(node)
                added += 1
                
            for var in sql_call.get('output_vars', []):
                var_name = var.lstrip(':')
                node = LineageNode(
                    id=f"mybatis_param_{dao_name}_{sql_name}_{var_name}",
                    name=var_name,
                    node_type=NodeType.MYBATIS_PARAM,
                    source_module="dbio_generator",
                    metadata={
                        "dao_name": dao_name,
                        "sql_name": sql_name,
                        "direction": "output"
                    }
                )
                self.graph.add_node(node)
                added += 1
                
        return added
    
    def add_headers(self, elements: List[Dict], source_file: str = None) -> int:
        """
        proc_parser 결과에서 Header 노드 추가 및 INCLUDES 관계 생성
        
        Args:
            elements: ProCParser.parse_file() 결과
            source_file: 소스 파일명 (Program 노드 ID용)
            
        Returns:
            추가된 노드 수
        """
        added = 0
        program_node_id = f"program_{source_file}" if source_file else None
        
        # 먼저 모든 헤더 노드 생성
        for el in elements:
            if el.get('type') != 'include':
                continue
            
            header_path = el.get('path', '')
            node_id = f"header_{header_path.replace('/', '_').replace('.', '_')}"
            
            if node_id not in self.graph.nodes:
                node = LineageNode(
                    id=node_id,
                    name=header_path,
                    node_type=NodeType.HEADER_FILE,
                    source_module="proc_parser",
                    metadata={
                        "is_system": el.get('is_system', False),
                        "line_start": el.get('line_start'),
                        "parent_header": el.get('parent_header'),
                        "raw_content": el.get('raw_content', '')
                    }
                )
                self.graph.add_node(node)
                added += 1
            
            # INCLUDES 관계 생성
            parent = el.get('parent_header')
            if parent:
                # Header → Header 중첩 관계
                parent_node_id = f"header_{parent.replace('/', '_').replace('.', '_')}"
                if parent_node_id in self.graph.nodes:
                    link = LineageLink(
                        source_id=parent_node_id,
                        target_id=node_id,
                        link_type=LinkType.INCLUDES,
                        confidence=1.0
                    )
                    self.graph.add_link(link)
            elif program_node_id:
                # Program → Header 관계 (루트 레벨 include)
                link = LineageLink(
                    source_id=program_node_id,
                    target_id=node_id,
                    link_type=LinkType.INCLUDES,
                    confidence=1.0
                )
                self.graph.add_link(link)
        
        return added
    
    def add_nested_header_includes(self, header_include_map: Dict[str, List[str]]) -> int:
        """
        중첩 헤더 인클루드 관계 수동 추가
        
        Args:
            header_include_map: {parent_header: [child_headers]} 형식
            예: {"main.h": ["types.h", "utils.h"]}
            
        Returns:
            생성된 링크 수
        """
        links_added = 0
        
        for parent, children in header_include_map.items():
            parent_id = f"header_{parent.replace('/', '_').replace('.', '_')}"
            
            if parent_id not in self.graph.nodes:
                node = LineageNode(
                    id=parent_id,
                    name=parent,
                    node_type=NodeType.HEADER_FILE,
                    source_module="manual",
                    metadata={}
                )
                self.graph.add_node(node)
            
            for child in children:
                child_id = f"header_{child.replace('/', '_').replace('.', '_')}"
                
                if child_id not in self.graph.nodes:
                    node = LineageNode(
                        id=child_id,
                        name=child,
                        node_type=NodeType.HEADER_FILE,
                        source_module="manual",
                        metadata={}
                    )
                    self.graph.add_node(node)
                
                link = LineageLink(
                    source_id=parent_id,
                    target_id=child_id,
                    link_type=LinkType.INCLUDES,
                    confidence=1.0
                )
                self.graph.add_link(link)
                links_added += 1
        
        return links_added
    
    def add_macros(self, elements: List[Dict]) -> int:
        """
        proc_parser 결과에서 Macro 노드 추가
        
        Args:
            elements: ProCParser.parse_file() 결과
            
        Returns:
            추가된 노드 수
        """
        added = 0
        for el in elements:
            if el.get('type') != 'macro':
                continue
            
            macro_name = el.get('name', '')
            node_id = f"macro_{macro_name}"
            
            if node_id not in self.graph.nodes:
                node = LineageNode(
                    id=node_id,
                    name=macro_name,
                    node_type=NodeType.MACRO,
                    source_module="proc_parser",
                    metadata={
                        "value": el.get('value'),
                        "line_start": el.get('line_start'),
                        "raw_content": el.get('raw_content', '')
                    }
                )
                self.graph.add_node(node)
                added += 1
        
        return added
    
    def add_functions(self, elements: List[Dict]) -> int:
        """
        proc_parser 결과에서 Function 노드 추가
        
        Args:
            elements: ProCParser.parse_file() 결과
            
        Returns:
            추가된 노드 수
        """
        added = 0
        for el in elements:
            if el.get('type') != 'function':
                continue
            
            func_name = el.get('name', '')
            node_id = f"function_{func_name}"
            
            if node_id not in self.graph.nodes:
                node = LineageNode(
                    id=node_id,
                    name=func_name,
                    node_type=NodeType.FUNCTION,
                    source_module="proc_parser",
                    metadata={
                        "return_type": el.get('return_type', ''),
                        "parameters": el.get('parameters', []),
                        "line_start": el.get('line_start'),
                        "line_end": el.get('line_end'),
                        "docstring": el.get('docstring')
                    }
                )
                self.graph.add_node(node)
                added += 1
        
        return added
    
    def add_bam_calls(self, elements: List[Dict]) -> int:
        """
        proc_parser 결과에서 BamCall 노드 추가
        
        Args:
            elements: ProCParser.parse_file() 결과
            
        Returns:
            추가된 노드 수
        """
        added = 0
        for el in elements:
            if el.get('type') != 'bam_call':
                continue
            
            bam_name = el.get('name', '')
            line_start = el.get('line_start', 0)
            node_id = f"bam_call_{bam_name}_{line_start}"
            
            node = LineageNode(
                id=node_id,
                name=bam_name,
                node_type=NodeType.BAM_CALL,
                source_module="proc_parser",
                metadata={
                    "function": el.get('function'),
                    "arguments": el.get('arguments', []),
                    "line_start": line_start,
                    "raw_content": el.get('raw_content', '')
                }
            )
            self.graph.add_node(node)
            added += 1
            
            # Function → BamCall CALLS 관계 생성
            if el.get('function'):
                func_node_id = f"function_{el['function']}"
                if func_node_id in self.graph.nodes:
                    link = LineageLink(
                        source_id=func_node_id,
                        target_id=node_id,
                        link_type=LinkType.CALLS,
                        confidence=1.0
                    )
                    self.graph.add_link(link)
        
        return added
    
    def add_all_program_elements(self, elements: List[Dict]) -> Dict[str, int]:
        """
        proc_parser 결과에서 모든 프로그램 요소 노드 추가
        
        Args:
            elements: ProCParser.parse_file() 결과
            
        Returns:
            타입별 추가된 노드 수
        """
        return {
            'headers': self.add_headers(elements),
            'macros': self.add_macros(elements),
            'functions': self.add_functions(elements),
            'bam_calls': self.add_bam_calls(elements),
            'variables': self.add_from_proc_parser(elements)
        }
    
    def add_java_variables(self) -> int:
        """
        ProCVariable 노드에서 JavaVariable 노드 자동 생성
        
        Prefix 제거 및 camelCase 변환을 적용하여 대응되는
        Java 변수 노드를 생성하고 MAPS_TO 관계로 연결합니다.
        
        Returns:
            추가된 노드 수
        """
        added = 0
        proc_vars = [n for n in self.graph.nodes.values() if n.node_type == NodeType.PROC_VARIABLE]
        
        for proc_var in proc_vars:
            # 변환 적용
            java_name = proc_var.name
            transformations = []
            
            # Prefix 제거
            for prefix in self.config.prefixes:
                if java_name.startswith(prefix):
                    java_name = java_name[len(prefix):]
                    transformations.append(f"prefix_removed:{prefix}")
                    break
            
            # snake_case → camelCase
            if '_' in java_name:
                java_name = self._snake_to_camel(java_name)
                transformations.append("snake_to_camel")
            
            # Java 변수 노드 생성 (없으면) 또는 기존 노드에 소스 추가
            java_node_id = f"java_var_{java_name}"
            
            if java_node_id not in self.graph.nodes:
                # 새 노드 생성
                java_node = LineageNode(
                    id=java_node_id,
                    name=java_name,
                    node_type=NodeType.JAVA_VARIABLE,
                    source_module="variable_lineage",
                    metadata={
                        "source_proc_vars": [proc_var.name],  # 다대일 지원
                        "transformations": transformations
                    }
                )
                self.graph.add_node(java_node)
                added += 1
            else:
                # 기존 노드에 소스 추가 (다대일)
                existing_node = self.graph.nodes[java_node_id]
                source_vars = existing_node.metadata.get('source_proc_vars', [])
                if proc_var.name not in source_vars:
                    source_vars.append(proc_var.name)
                    existing_node.metadata['source_proc_vars'] = source_vars
            
            # 링크는 항상 생성 (다대일 연결)
            link = LineageLink(
                source_id=proc_var.id,
                target_id=java_node_id,
                link_type=LinkType.TRANSFORMED_TO,
                confidence=1.0,
                transformations=transformations
            )
            self.graph.add_link(link)
        
        return added
    
    # ===== 연결 구축 =====
    
    def build_links(self) -> int:
        """
        노드 간 연결관계 자동 구축
        
        이름 기반 매칭 및 변환 규칙을 적용하여 연결을 생성합니다.
        
        Returns:
            생성된 링크 수
        """
        link_count = 0
        
        # 1. proc_variable → sql_host_var 연결
        link_count += self._link_proc_to_sql()
        
        # 2. struct_field → omm_field 연결
        link_count += self._link_struct_to_omm()
        
        # 3. sql_host_var → mybatis_param 연결
        link_count += self._link_sql_to_mybatis()
        
        return link_count
    
    def _link_proc_to_sql(self) -> int:
        """proc_variable과 sql_host_var 연결"""
        count = 0
        proc_vars = [n for n in self.graph.nodes.values() if n.node_type == NodeType.PROC_VARIABLE]
        sql_vars = [n for n in self.graph.nodes.values() if n.node_type == NodeType.SQL_HOST_VAR]
        
        for sql_var in sql_vars:
            # 호스트 변수명에서 구조체.필드 분리
            sql_name = sql_var.name
            if '.' in sql_name:
                parts = sql_name.split('.')
                base_name = parts[0]
            else:
                base_name = sql_name
            
            for proc_var in proc_vars:
                match_result = self._match_names(proc_var.name, base_name)
                if match_result['matched']:
                    link = LineageLink(
                        source_id=proc_var.id,
                        target_id=sql_var.id,
                        link_type=LinkType.USED_IN,
                        confidence=match_result['confidence'],
                        transformations=match_result['transformations']
                    )
                    self.graph.add_link(link)
                    count += 1
                    
        return count
    
    def _link_struct_to_omm(self) -> int:
        """struct_field와 omm_field 연결"""
        count = 0
        struct_fields = [n for n in self.graph.nodes.values() if n.node_type == NodeType.STRUCT_FIELD]
        omm_fields = [n for n in self.graph.nodes.values() if n.node_type == NodeType.OMM_FIELD]
        
        for struct_field in struct_fields:
            struct_name = struct_field.metadata.get('struct_name', '')
            org_name = struct_field.metadata.get('org_name', struct_field.name)
            
            for omm_field in omm_fields:
                omm_struct = omm_field.metadata.get('struct_name', '')
                
                # 같은 구조체 내 필드인지 확인
                if self._structs_match(struct_name, omm_struct):
                    match_result = self._match_names(org_name, omm_field.name)
                    if match_result['matched']:
                        link = LineageLink(
                            source_id=struct_field.id,
                            target_id=omm_field.id,
                            link_type=LinkType.MAPPED_TO,
                            confidence=match_result['confidence'],
                            transformations=match_result['transformations']
                        )
                        self.graph.add_link(link)
                        count += 1
                        
        return count
    
    def _link_sql_to_mybatis(self) -> int:
        """sql_host_var와 mybatis_param 연결"""
        count = 0
        sql_vars = [n for n in self.graph.nodes.values() if n.node_type == NodeType.SQL_HOST_VAR]
        mybatis_params = [n for n in self.graph.nodes.values() if n.node_type == NodeType.MYBATIS_PARAM]
        
        for sql_var in sql_vars:
            for mb_param in mybatis_params:
                match_result = self._match_names(sql_var.name, mb_param.name)
                if match_result['matched']:
                    link = LineageLink(
                        source_id=sql_var.id,
                        target_id=mb_param.id,
                        link_type=LinkType.TRANSFORMED_TO,
                        confidence=match_result['confidence'],
                        transformations=match_result['transformations']
                    )
                    self.graph.add_link(link)
                    count += 1
                    
        return count
    
    # ===== 이름 매칭 =====
    
    def _match_names(self, source_name: str, target_name: str) -> Dict[str, Any]:
        """
        두 이름이 매칭되는지 확인
        
        변환 규칙을 적용하여 매칭 여부와 적용된 변환을 반환합니다.
        
        Returns:
            {
                'matched': bool,
                'confidence': float,
                'transformations': List[str]
            }
        """
        transformations = []
        
        # 정확히 일치
        if source_name == target_name:
            return {'matched': True, 'confidence': 1.0, 'transformations': []}
        
        # 대소문자 무시 매칭
        if self.config.case_insensitive and source_name.lower() == target_name.lower():
            return {'matched': True, 'confidence': 0.95, 'transformations': ['case_normalized']}
        
        # Prefix 제거 후 매칭
        stripped_source = source_name
        for prefix in self.config.prefixes:
            if stripped_source.startswith(prefix):
                stripped_source = stripped_source[len(prefix):]
                transformations.append(f"prefix_removed:{prefix}")
                break
        
        # snake_case → camelCase 매칭
        source_camel = self._snake_to_camel(stripped_source)
        target_normalized = target_name
        
        if source_camel == target_normalized:
            transformations.append("snake_to_camel")
            return {'matched': True, 'confidence': 0.9, 'transformations': transformations}
        
        # 대소문자 무시로 camelCase 매칭
        if self.config.case_insensitive and source_camel.lower() == target_normalized.lower():
            transformations.append("snake_to_camel")
            transformations.append("case_normalized")
            return {'matched': True, 'confidence': 0.85, 'transformations': transformations}
        
        # Stripped source와 target 직접 비교
        if stripped_source == target_name:
            return {'matched': True, 'confidence': 0.9, 'transformations': transformations}
        
        if self.config.case_insensitive and stripped_source.lower() == target_name.lower():
            transformations.append("case_normalized")
            return {'matched': True, 'confidence': 0.85, 'transformations': transformations}
        
        return {'matched': False, 'confidence': 0.0, 'transformations': []}
    
    def _snake_to_camel(self, name: str) -> str:
        """snake_case를 camelCase로 변환"""
        components = name.split('_')
        if not components:
            return name
        return components[0].lower() + ''.join(x.title() for x in components[1:])
    
    def _structs_match(self, struct1: str, struct2: str) -> bool:
        """구조체 이름이 매칭되는지 확인"""
        # _t suffix 제거
        s1 = re.sub(r'_t$', '', struct1)
        s2 = re.sub(r'_t$', '', struct2)
        
        if self.config.case_insensitive:
            return s1.lower() == s2.lower()
        return s1 == s2
    
    # ===== 쿼리 =====
    
    def query_lineage(self, variable_name: str, direction: str = "both") -> Dict[str, Any]:
        """
        특정 변수의 lineage 추적
        
        Args:
            variable_name: 변수명 (부분 일치 지원)
            direction: 'upstream', 'downstream', 'both'
            
        Returns:
            {
                'query': str,
                'matched_nodes': List[Dict],
                'upstream': List[Dict],
                'downstream': List[Dict]
            }
        """
        # 이름으로 노드 검색
        matched = []
        for node in self.graph.nodes.values():
            if variable_name.lower() in node.name.lower():
                matched.append(node)
        
        result = {
            'query': variable_name,
            'matched_nodes': [n.to_dict() for n in matched],
            'upstream': [],
            'downstream': []
        }
        
        for node in matched:
            if direction in ('upstream', 'both'):
                upstream = self.graph.get_upstream(node.id)
                result['upstream'].extend([n.to_dict() for n in upstream])
                
            if direction in ('downstream', 'both'):
                downstream = self.graph.get_downstream(node.id)
                result['downstream'].extend([n.to_dict() for n in downstream])
        
        return result
    
    # ===== 출력 =====
    
    def to_json(self, indent: int = 2) -> str:
        """JSON 형식 출력"""
        return json.dumps(self.graph.to_dict(), indent=indent, ensure_ascii=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 형식 출력"""
        return self.graph.to_dict()
    
    def save_json(self, file_path: str, indent: int = 2) -> str:
        """JSON 파일로 저장"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.graph.to_dict(), f, indent=indent, ensure_ascii=False)
        return file_path
