"""
CPG (Code Property Graph) 모듈

Pro*C/.c 파일에서 코드 속성 그래프를 생성합니다.
- 함수 호출 관계
- 헤더 파일 의존성
- 변수/구조체 데이터 흐름
"""

from .models import (
    Node, Edge, CPG,
    FunctionNode, VariableNode, StructNode,
    CallEdge, DataFlowEdge, IncludeEdge
)
from .call_graph import CallGraphExtractor
from .header_analyzer import HeaderAnalyzer
from .data_flow import DataFlowAnalyzer
from .cpg_builder import CPGBuilder

__all__ = [
    'CPGBuilder',
    'CallGraphExtractor',
    'HeaderAnalyzer', 
    'DataFlowAnalyzer',
    'CPG',
    'Node', 'Edge',
    'FunctionNode', 'VariableNode', 'StructNode',
    'CallEdge', 'DataFlowEdge', 'IncludeEdge'
]
