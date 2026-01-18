"""
Lineage Neo4j Plugin

LineageGraph를 Neo4j 노드/관계로 변환하는 플러그인입니다.
"""

from typing import Dict, List, Any
from infra.neo4j.plugin_interface import Neo4jExportPlugin, Neo4jNode, Neo4jRelationship
from ..types import LineageGraph, LineageNode, LineageLink, NodeType, LinkType


# NodeType → Neo4j Label 매핑
NODE_TYPE_TO_LABEL: Dict[NodeType, str] = {
    # 변수 타입
    NodeType.PROC_VARIABLE: "ProCVariable",
    NodeType.STRUCT_FIELD: "FieldDefinition",
    NodeType.SQL_HOST_VAR: "SQLHostVariable",
    NodeType.OMM_FIELD: "OMMField",
    NodeType.MYBATIS_PARAM: "DBIOParam",
    NodeType.JAVA_VARIABLE: "JavaVariable",
    # 프로그램 구조 타입
    NodeType.HEADER_FILE: "HeaderFile",
    NodeType.MACRO: "Macro",
    NodeType.FUNCTION: "Function",
    NodeType.BAM_CALL: "BamCall",
    # SQL 관련 타입
    NodeType.CURSOR: "Cursor",
    NodeType.TRANSACTION: "Transaction",
}

# LinkType → Neo4j Relationship Type 매핑
LINK_TYPE_TO_REL: Dict[LinkType, str] = {
    # 변수 관계
    LinkType.DECLARED_AS: "DECLARES",
    LinkType.USED_IN: "USES_VARIABLE",
    LinkType.TRANSFORMED_TO: "MAPS_TO",
    LinkType.MAPPED_TO: "CORRESPONDS_TO",
    # 프로그램 구조 관계
    LinkType.INCLUDES: "INCLUDES",
    LinkType.DEFINES: "DEFINES",
    LinkType.CALLS: "CALLS",
    LinkType.CONTAINS: "CONTAINS",
    # 매크로 관계
    LinkType.SIZED_BY: "SIZED_BY",
    LinkType.RESOLVES_TO: "RESOLVES_TO",
}


class LineageNeo4jPlugin(Neo4jExportPlugin):
    """
    LineageGraph를 Neo4j로 변환하는 플러그인
    
    Usage:
        from analysis.lineage.exporters.neo4j_plugin import LineageNeo4jPlugin
        from infra.neo4j import Neo4jExporter
        
        plugin = LineageNeo4jPlugin(graph)
        exporter = Neo4jExporter(plugin, program_name="MyProgram")
        exporter.save_cypher("output.cypher")
    """
    
    def __init__(self, graph: LineageGraph):
        """
        Args:
            graph: LineageGraph 객체
        """
        self.graph = graph
    
    def name(self) -> str:
        """플러그인 이름"""
        return "LineageNeo4jPlugin"
    
    def get_nodes(self) -> List[Neo4jNode]:
        """LineageGraph 노드를 Neo4jNode로 변환"""
        result = []
        
        for node_id, node in self.graph.nodes.items():
            label = NODE_TYPE_TO_LABEL.get(node.node_type, "Variable")
            properties = {
                "name": node.name,
                "source_module": node.source_module,
            }
            
            # 주요 메타데이터 추가
            if 'data_type' in node.metadata:
                properties['data_type'] = node.metadata['data_type']
            if 'line_start' in node.metadata:
                properties['line_start'] = node.metadata['line_start']
            if 'direction' in node.metadata:
                properties['direction'] = node.metadata['direction']
            
            result.append(Neo4jNode(
                id=node_id,
                label=label,
                properties=properties
            ))
        
        return result
    
    def get_relationships(self) -> List[Neo4jRelationship]:
        """LineageGraph 링크를 Neo4jRelationship으로 변환"""
        result = []
        
        for link in self.graph.links:
            rel_type = LINK_TYPE_TO_REL.get(link.link_type, "RELATED_TO")
            properties = {
                "transformations": link.transformations,
                "confidence": link.confidence,
            }
            
            result.append(Neo4jRelationship(
                source_id=link.source_id,
                target_id=link.target_id,
                rel_type=rel_type,
                properties=properties
            ))
        
        return result
    
    def get_labels(self) -> List[str]:
        """사용되는 라벨 목록"""
        labels = set()
        for node in self.graph.nodes.values():
            labels.add(NODE_TYPE_TO_LABEL.get(node.node_type, "Variable"))
        return list(labels)
    
    def get_program_rel_type(self, node_type: NodeType) -> str:
        """노드 타입에 따른 Program 관계 타입"""
        mapping = {
            NodeType.PROC_VARIABLE: "DECLARES",
            NodeType.STRUCT_FIELD: "DEFINES",
            NodeType.SQL_HOST_VAR: "CONTAINS",
            NodeType.OMM_FIELD: "HAS_OMM",
            NodeType.MYBATIS_PARAM: "HAS_DBIO",
            NodeType.JAVA_VARIABLE: "DECLARES",
            NodeType.HEADER_FILE: "INCLUDES",
            NodeType.MACRO: "DEFINES",
            NodeType.FUNCTION: "CONTAINS",
            NodeType.BAM_CALL: "CONTAINS",
            NodeType.CURSOR: "CONTAINS",
            NodeType.TRANSACTION: "CONTAINS",
        }
        return mapping.get(node_type, "CONTAINS")
