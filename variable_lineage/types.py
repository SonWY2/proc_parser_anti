"""
Variable Lineage 타입 정의

LineageNode, LineageLink, LineageGraph 등의 데이터 클래스를 정의합니다.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class NodeType(Enum):
    """노드 타입"""
    # 기본 변수 타입
    PROC_VARIABLE = "proc_variable"         # Pro*C 변수 선언
    STRUCT_FIELD = "struct_field"           # 구조체 필드
    SQL_HOST_VAR = "sql_host_var"           # SQL 호스트 변수
    OMM_FIELD = "omm_field"                 # OMM 파일 필드
    MYBATIS_PARAM = "mybatis_param"         # MyBatis 파라미터
    JAVA_VARIABLE = "java_variable"         # Java 변수 (camelCase 변환된)
    
    # 프로그램 구조 타입
    HEADER_FILE = "header_file"             # #include 헤더
    MACRO = "macro"                         # #define 매크로
    FUNCTION = "function"                   # C 함수 정의
    BAM_CALL = "bam_call"                   # BAMCALL 호출
    
    # SQL 관련 타입
    CURSOR = "cursor"                       # CURSOR 정의/사용
    TRANSACTION = "transaction"             # COMMIT/ROLLBACK


class LinkType(Enum):
    """연결 타입"""
    # 변수 관계
    DECLARED_AS = "declared_as"             # 변수 → 호스트변수로 선언됨
    USED_IN = "used_in"                     # SQL에서 사용됨
    TRANSFORMED_TO = "transformed_to"       # 변환됨 (네이밍 변환 등)
    MAPPED_TO = "mapped_to"                 # OMM/MyBatis로 매핑됨
    
    # 프로그램 구조 관계
    INCLUDES = "includes"                   # Program → HeaderFile
    DEFINES = "defines"                     # Program → Macro/Function
    CALLS = "calls"                         # Function → Function/BamCall
    CONTAINS = "contains"                   # Function → Variable/SQL
    
    # 매크로 관계
    SIZED_BY = "sized_by"                   # Variable → Macro (배열 크기)
    RESOLVES_TO = "resolves_to"             # Macro → Value


@dataclass
class LineageNode:
    """
    변수 노드
    
    각 변환 단계에서의 변수 상태를 나타냅니다.
    
    Attributes:
        id: 고유 ID (예: "proc_var_H_o_user_id")
        name: 변수명 (예: "H_o_user_id")
        node_type: 노드 타입 (NodeType enum)
        source_module: 출처 모듈 (proc_parser, header_parser, etc.)
        metadata: 추가 정보 (data_type, size, line_start 등)
    """
    id: str
    name: str
    node_type: NodeType
    source_module: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "id": self.id,
            "name": self.name,
            "node_type": self.node_type.value,
            "source_module": self.source_module,
            "metadata": self.metadata
        }


@dataclass
class LineageLink:
    """
    연결 관계
    
    두 노드 간의 변환/연결 관계를 나타냅니다.
    
    Attributes:
        source_id: 소스 노드 ID
        target_id: 타겟 노드 ID
        link_type: 연결 타입 (LinkType enum)
        confidence: 매칭 신뢰도 (0.0 ~ 1.0)
        transformations: 적용된 변환 규칙 리스트
        metadata: 추가 정보
        
    Example:
        transformations = ["prefix_removed:H_o_", "snake_to_camel"]
    """
    source_id: str
    target_id: str
    link_type: LinkType
    confidence: float = 1.0
    transformations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "link_type": self.link_type.value,
            "confidence": self.confidence,
            "transformations": self.transformations,
            "metadata": self.metadata
        }


@dataclass
class LineageGraph:
    """
    전체 연결 그래프
    
    모든 노드와 링크를 포함하는 그래프 구조입니다.
    
    Attributes:
        nodes: 노드 ID → LineageNode 매핑
        links: LineageLink 리스트
        source_file: 원본 파일 경로
        metadata: 그래프 메타데이터
    """
    nodes: Dict[str, LineageNode] = field(default_factory=dict)
    links: List[LineageLink] = field(default_factory=list)
    source_file: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_node(self, node: LineageNode) -> None:
        """노드 추가"""
        self.nodes[node.id] = node
    
    def add_link(self, link: LineageLink) -> None:
        """링크 추가"""
        self.links.append(link)
    
    def get_node(self, node_id: str) -> Optional[LineageNode]:
        """노드 조회"""
        return self.nodes.get(node_id)
    
    def get_upstream(self, node_id: str) -> List[LineageNode]:
        """상위 노드 조회 (이 노드를 타겟으로 하는 링크의 소스들)"""
        upstream_ids = [link.source_id for link in self.links if link.target_id == node_id]
        return [self.nodes[uid] for uid in upstream_ids if uid in self.nodes]
    
    def get_downstream(self, node_id: str) -> List[LineageNode]:
        """하위 노드 조회 (이 노드를 소스로 하는 링크의 타겟들)"""
        downstream_ids = [link.target_id for link in self.links if link.source_id == node_id]
        return [self.nodes[did] for did in downstream_ids if did in self.nodes]
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        return {
            "source_file": self.source_file,
            "metadata": self.metadata,
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
            "links": [link.to_dict() for link in self.links],
            "summary": {
                "total_nodes": len(self.nodes),
                "total_links": len(self.links),
                "nodes_by_type": self._count_nodes_by_type(),
                "links_by_type": self._count_links_by_type()
            }
        }
    
    def _count_nodes_by_type(self) -> Dict[str, int]:
        """타입별 노드 수"""
        counts = {}
        for node in self.nodes.values():
            type_name = node.node_type.value
            counts[type_name] = counts.get(type_name, 0) + 1
        return counts
    
    def _count_links_by_type(self) -> Dict[str, int]:
        """타입별 링크 수"""
        counts = {}
        for link in self.links:
            type_name = link.link_type.value
            counts[type_name] = counts.get(type_name, 0) + 1
        return counts
