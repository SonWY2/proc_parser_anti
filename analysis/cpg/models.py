"""
CPG 데이터 모델 정의

Node, Edge 및 CPG 그래프 클래스를 정의합니다.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set
from enum import Enum


class NodeType(Enum):
    """노드 타입 열거형"""
    FUNCTION = "function"
    VARIABLE = "variable"
    STRUCT = "struct"
    FILE = "file"
    HEADER = "header"
    PARAMETER = "parameter"


class EdgeType(Enum):
    """엣지 타입 열거형"""
    CALL = "call"              # 함수 호출
    INCLUDE = "include"        # 헤더 포함
    DATA_FLOW = "data_flow"    # 데이터 흐름
    DEFINE = "define"          # 정의 관계
    USE = "use"                # 사용 관계
    FIELD_ACCESS = "field_access"  # 구조체 필드 접근


@dataclass
class Node:
    """CPG 기본 노드"""
    id: str
    node_type: NodeType
    name: str
    file_path: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.node_type.value,
            "name": self.name,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "attributes": self.attributes
        }


@dataclass
class FunctionNode(Node):
    """함수 노드"""
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    is_static: bool = False
    
    def __post_init__(self):
        self.node_type = NodeType.FUNCTION
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "parameters": self.parameters,
            "return_type": self.return_type,
            "is_static": self.is_static
        })
        return d


@dataclass
class VariableNode(Node):
    """변수 노드"""
    data_type: Optional[str] = None
    is_global: bool = False
    is_host_variable: bool = False  # Pro*C 호스트 변수 여부
    
    def __post_init__(self):
        self.node_type = NodeType.VARIABLE
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "data_type": self.data_type,
            "is_global": self.is_global,
            "is_host_variable": self.is_host_variable
        })
        return d


@dataclass
class StructNode(Node):
    """구조체 노드"""
    fields: List[Dict[str, str]] = field(default_factory=list)
    
    def __post_init__(self):
        self.node_type = NodeType.STRUCT
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["fields"] = self.fields
        return d


@dataclass
class Edge:
    """CPG 기본 엣지"""
    source_id: str
    target_id: str
    edge_type: EdgeType = EdgeType.CALL  # 기본값 (하위 클래스에서 __post_init__으로 재설정)
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.edge_type.value,
            "attributes": self.attributes
        }


@dataclass
class CallEdge(Edge):
    """함수 호출 엣지"""
    call_site_line: Optional[int] = None
    arguments: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        self.edge_type = EdgeType.CALL
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "call_site_line": self.call_site_line,
            "arguments": self.arguments
        })
        return d


@dataclass
class DataFlowEdge(Edge):
    """데이터 흐름 엣지"""
    flow_type: str = "assignment"  # assignment, parameter, return
    
    def __post_init__(self):
        self.edge_type = EdgeType.DATA_FLOW
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["flow_type"] = self.flow_type
        return d


@dataclass
class IncludeEdge(Edge):
    """헤더 포함 엣지"""
    is_system_header: bool = False
    
    def __post_init__(self):
        self.edge_type = EdgeType.INCLUDE
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["is_system_header"] = self.is_system_header
        return d


@dataclass
class CPG:
    """Code Property Graph 전체 구조"""
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)
    files: Set[str] = field(default_factory=set)
    
    def add_node(self, node: Node):
        """노드 추가"""
        self.nodes[node.id] = node
        if node.file_path:
            self.files.add(node.file_path)
    
    def add_edge(self, edge: Edge):
        """엣지 추가"""
        self.edges.append(edge)
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """노드 조회"""
        return self.nodes.get(node_id)
    
    def get_nodes_by_type(self, node_type: NodeType) -> List[Node]:
        """타입별 노드 조회"""
        return [n for n in self.nodes.values() if n.node_type == node_type]
    
    def get_edges_by_type(self, edge_type: EdgeType) -> List[Edge]:
        """타입별 엣지 조회"""
        return [e for e in self.edges if e.edge_type == edge_type]
    
    def get_outgoing_edges(self, node_id: str) -> List[Edge]:
        """나가는 엣지 조회"""
        return [e for e in self.edges if e.source_id == node_id]
    
    def get_incoming_edges(self, node_id: str) -> List[Edge]:
        """들어오는 엣지 조회"""
        return [e for e in self.edges if e.target_id == node_id]
    
    def merge(self, other: 'CPG'):
        """다른 CPG와 병합"""
        for node in other.nodes.values():
            self.add_node(node)
        for edge in other.edges:
            self.add_edge(edge)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
            "files": list(self.files),
            "summary": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "total_files": len(self.files)
            }
        }
    
    def to_dot(self, title: str = "CPG") -> str:
        """Graphviz DOT 형식으로 변환"""
        lines = [f'digraph "{title}" {{']
        lines.append('  rankdir=LR;')
        lines.append('  node [shape=box];')
        
        # 노드 타입별 스타일
        type_styles = {
            NodeType.FUNCTION: 'style=filled,fillcolor=lightblue',
            NodeType.VARIABLE: 'style=filled,fillcolor=lightyellow',
            NodeType.STRUCT: 'style=filled,fillcolor=lightgreen',
            NodeType.FILE: 'shape=folder,style=filled,fillcolor=lightgray',
            NodeType.HEADER: 'shape=note,style=filled,fillcolor=wheat',
        }
        
        # 노드 출력
        for node in self.nodes.values():
            style = type_styles.get(node.node_type, '')
            label = f"{node.name}\\n({node.node_type.value})"
            lines.append(f'  "{node.id}" [label="{label}",{style}];')
        
        # 엣지 출력
        edge_styles = {
            EdgeType.CALL: 'color=blue',
            EdgeType.INCLUDE: 'color=gray,style=dashed',
            EdgeType.DATA_FLOW: 'color=red',
        }
        
        for edge in self.edges:
            style = edge_styles.get(edge.edge_type, '')
            lines.append(f'  "{edge.source_id}" -> "{edge.target_id}" [{style}];')
        
        lines.append('}')
        return '\n'.join(lines)
