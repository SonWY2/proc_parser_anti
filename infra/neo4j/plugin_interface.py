"""
Neo4j Export Plugin Interface

데이터 소스별 Neo4j 변환 플러그인을 위한 추상 인터페이스입니다.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Any, Optional


@dataclass
class Neo4jNode:
    """Neo4j 노드 표현"""
    id: str
    label: str
    properties: Dict[str, Any]


@dataclass  
class Neo4jRelationship:
    """Neo4j 관계 표현"""
    source_id: str
    target_id: str
    rel_type: str
    properties: Dict[str, Any]


class Neo4jExportPlugin(ABC):
    """
    Neo4j Export 플러그인 인터페이스
    
    각 데이터 소스(LineageGraph, CPG 등)는 이 인터페이스를 구현하여
    자신의 데이터를 Neo4j 노드/관계로 변환합니다.
    
    Example:
        class LineageNeo4jPlugin(Neo4jExportPlugin):
            def __init__(self, graph: LineageGraph):
                self.graph = graph
            
            def get_nodes(self) -> List[Neo4jNode]:
                return [Neo4jNode(...) for node in self.graph.nodes.values()]
    """
    
    @abstractmethod
    def name(self) -> str:
        """플러그인 이름 반환"""
        pass
    
    @abstractmethod
    def get_nodes(self) -> List[Neo4jNode]:
        """
        변환할 노드 목록 반환
        
        Returns:
            Neo4jNode 리스트
        """
        pass
    
    @abstractmethod
    def get_relationships(self) -> List[Neo4jRelationship]:
        """
        변환할 관계 목록 반환
        
        Returns:
            Neo4jRelationship 리스트
        """
        pass
    
    def get_labels(self) -> List[str]:
        """
        사용되는 모든 노드 라벨 반환 (인덱스 생성용)
        
        Returns:
            라벨 문자열 리스트
        """
        return list(set(node.label for node in self.get_nodes()))
    
    def get_relationship_types(self) -> List[str]:
        """
        사용되는 모든 관계 타입 반환
        
        Returns:
            관계 타입 문자열 리스트
        """
        return list(set(rel.rel_type for rel in self.get_relationships()))
