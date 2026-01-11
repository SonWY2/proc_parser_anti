"""
Neo4j Exporter

LineageGraph를 Neo4j Cypher 쿼리로 변환하거나
Neo4j 드라이버를 통해 직접 export합니다.

기존 스키마와 매핑:
- proc_variable → ProCVariable
- struct_field → FieldDefinition  
- sql_host_var → SQLHostVariable
- java_variable → JavaVariable
- omm_field → OMMField
- mybatis_param → DBIOQuery 관계
"""

from typing import Dict, List, Optional, Any
from ..types import LineageGraph, LineageNode, LineageLink, NodeType, LinkType


# NodeType → Neo4j Label 매핑
NODE_TYPE_TO_LABEL = {
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
LINK_TYPE_TO_REL = {
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


class Neo4jExporter:
    """
    LineageGraph를 Neo4j로 export하는 클래스
    
    Usage:
        exporter = Neo4jExporter()
        
        # Cypher 쿼리 생성
        cypher = exporter.to_cypher(graph)
        
        # 파일로 저장
        exporter.save_cypher(graph, "output.cypher")
        
        # Neo4j driver로 직접 export (선택)
        exporter.export_to_driver(graph, driver)
    """
    
    def __init__(self, program_name: str = "UnknownProgram"):
        """
        Args:
            program_name: Program 노드 이름 (루트 노드)
        """
        self.program_name = program_name
    
    def to_cypher(self, graph: LineageGraph, include_program: bool = True) -> str:
        """
        LineageGraph를 Cypher CREATE 문으로 변환
        
        Args:
            graph: LineageGraph 객체
            include_program: Program 루트 노드 포함 여부
            
        Returns:
            Cypher 쿼리 문자열
        """
        lines = []
        
        # 헤더 주석
        lines.append(f"// Neo4j Export from VariableLineageTracker")
        lines.append(f"// Source: {graph.source_file}")
        lines.append(f"// Nodes: {len(graph.nodes)}, Links: {len(graph.links)}")
        lines.append("")
        
        # Program 노드 생성
        if include_program:
            lines.append(f"// Program Root Node")
            lines.append(f"CREATE (p:Program {{name: '{self.program_name}', source_file: '{graph.source_file}'}})")
            lines.append("")
        
        # 모든 노드 생성
        lines.append("// === Nodes ===")
        for node_id, node in graph.nodes.items():
            cypher_node = self._node_to_cypher(node)
            lines.append(cypher_node)
        
        lines.append("")
        
        # 모든 관계 생성
        lines.append("// === Relationships ===")
        for link in graph.links:
            cypher_rel = self._link_to_cypher(link)
            lines.append(cypher_rel)
        
        # Program 소유 관계
        if include_program:
            lines.append("")
            lines.append("// === Program Ownership ===")
            for node_id, node in graph.nodes.items():
                label = NODE_TYPE_TO_LABEL.get(node.node_type, "Variable")
                var_ref = self._safe_var_name(node_id)
                rel_type = self._get_program_rel_type(node.node_type)
                lines.append(
                    f"CREATE (p)-[:{rel_type}]->({var_ref})"
                )
        
        return "\n".join(lines)
    
    def to_cypher_merge(self, graph: LineageGraph) -> str:
        """
        MERGE를 사용하여 중복 없이 노드/관계 생성 (기존 데이터가 있을 때 사용)
        
        Args:
            graph: LineageGraph 객체
            
        Returns:
            Cypher MERGE 쿼리 문자열
        """
        lines = []
        
        lines.append(f"// Neo4j MERGE Export (idempotent)")
        lines.append(f"// Source: {graph.source_file}")
        lines.append("")
        
        # Program 노드
        lines.append(f"MERGE (p:Program {{name: '{self.program_name}'}})")
        lines.append(f"SET p.source_file = '{graph.source_file}'")
        lines.append("")
        
        # 노드 MERGE
        for node_id, node in graph.nodes.items():
            label = NODE_TYPE_TO_LABEL.get(node.node_type, "Variable")
            props = self._format_properties(node)
            lines.append(f"MERGE (:{label} {{id: '{node_id}'}})")
            lines.append(f"SET n += {props}")
        
        lines.append("")
        
        # 관계 MERGE
        for link in graph.links:
            rel_type = LINK_TYPE_TO_REL.get(link.link_type, "RELATED_TO")
            trans_str = str(link.transformations).replace("'", '"')
            lines.append(
                f"MATCH (a {{id: '{link.source_id}'}}), (b {{id: '{link.target_id}'}}) "
                f"MERGE (a)-[r:{rel_type}]->(b) "
                f"SET r.transformations = {trans_str}, r.confidence = {link.confidence}"
            )
        
        return "\n".join(lines)
    
    def save_cypher(self, graph: LineageGraph, file_path: str, use_merge: bool = False) -> str:
        """
        Cypher 쿼리를 파일로 저장
        
        Args:
            graph: LineageGraph 객체
            file_path: 출력 파일 경로
            use_merge: MERGE 문 사용 여부
            
        Returns:
            저장된 파일 경로
        """
        if use_merge:
            cypher = self.to_cypher_merge(graph)
        else:
            cypher = self.to_cypher(graph)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(cypher)
        
        return file_path
    
    def export_to_driver(self, graph: LineageGraph, driver, database: str = "neo4j") -> Dict[str, int]:
        """
        Neo4j Python 드라이버를 통해 직접 export
        
        Args:
            graph: LineageGraph 객체
            driver: neo4j.Driver 객체
            database: 데이터베이스 이름
            
        Returns:
            {'nodes_created': int, 'relationships_created': int}
        """
        nodes_created = 0
        rels_created = 0
        
        with driver.session(database=database) as session:
            # Program 노드
            session.run(
                "MERGE (p:Program {name: $name}) SET p.source_file = $source",
                name=self.program_name,
                source=graph.source_file
            )
            
            # 노드 생성
            for node_id, node in graph.nodes.items():
                label = NODE_TYPE_TO_LABEL.get(node.node_type, "Variable")
                result = session.run(
                    f"MERGE (n:{label} {{id: $id}}) "
                    f"SET n.name = $name, n.source_module = $source_module, n.metadata = $metadata "
                    f"RETURN n",
                    id=node_id,
                    name=node.name,
                    source_module=node.source_module,
                    metadata=str(node.metadata)
                )
                if result.single():
                    nodes_created += 1
            
            # 관계 생성
            for link in graph.links:
                rel_type = LINK_TYPE_TO_REL.get(link.link_type, "RELATED_TO")
                result = session.run(
                    f"MATCH (a {{id: $source}}), (b {{id: $target}}) "
                    f"MERGE (a)-[r:{rel_type}]->(b) "
                    f"SET r.transformations = $trans, r.confidence = $conf "
                    f"RETURN r",
                    source=link.source_id,
                    target=link.target_id,
                    trans=link.transformations,
                    conf=link.confidence
                )
                if result.single():
                    rels_created += 1
            
            # Program 소유 관계
            for node_id, node in graph.nodes.items():
                rel_type = self._get_program_rel_type(node.node_type)
                session.run(
                    f"MATCH (p:Program {{name: $prog}}), (n {{id: $node_id}}) "
                    f"MERGE (p)-[:{rel_type}]->(n)",
                    prog=self.program_name,
                    node_id=node_id
                )
        
        return {'nodes_created': nodes_created, 'relationships_created': rels_created}
    
    def _node_to_cypher(self, node: LineageNode) -> str:
        """단일 노드를 Cypher CREATE 문으로 변환"""
        label = NODE_TYPE_TO_LABEL.get(node.node_type, "Variable")
        var_name = self._safe_var_name(node.id)
        props = self._format_properties(node)
        
        return f"CREATE ({var_name}:{label} {props})"
    
    def _link_to_cypher(self, link: LineageLink) -> str:
        """단일 링크를 Cypher CREATE 문으로 변환"""
        source_var = self._safe_var_name(link.source_id)
        target_var = self._safe_var_name(link.target_id)
        rel_type = LINK_TYPE_TO_REL.get(link.link_type, "RELATED_TO")
        
        # 변환 규칙을 관계 속성으로
        trans_str = str(link.transformations).replace("'", '"')
        
        return (
            f"CREATE ({source_var})-[:{rel_type} "
            f"{{transformations: {trans_str}, confidence: {link.confidence}}}]"
            f"->({target_var})"
        )
    
    def _format_properties(self, node: LineageNode) -> str:
        """노드 속성을 Cypher 형식으로 변환"""
        props = {
            "id": node.id,
            "name": node.name,
            "source_module": node.source_module,
        }
        
        # 주요 메타데이터 추가
        if 'data_type' in node.metadata:
            props['data_type'] = node.metadata['data_type']
        if 'line_start' in node.metadata:
            props['line_start'] = node.metadata['line_start']
        if 'direction' in node.metadata:
            props['direction'] = node.metadata['direction']
        
        # Cypher 속성 문자열 생성
        prop_strs = []
        for k, v in props.items():
            if isinstance(v, str):
                prop_strs.append(f"{k}: '{self._escape_string(v)}'")
            elif isinstance(v, (int, float)):
                prop_strs.append(f"{k}: {v}")
            elif v is not None:
                prop_strs.append(f"{k}: '{self._escape_string(str(v))}'")
        
        return "{" + ", ".join(prop_strs) + "}"
    
    def _safe_var_name(self, node_id: str) -> str:
        """노드 ID를 Cypher 변수명으로 변환"""
        # 특수문자 제거, 언더스코어로 치환
        safe = node_id.replace("-", "_").replace(".", "_").replace(" ", "_")
        # 숫자로 시작하면 n_ 접두사
        if safe and safe[0].isdigit():
            safe = "n_" + safe
        return safe[:50]  # 길이 제한
    
    def _escape_string(self, s: str) -> str:
        """Cypher 문자열 이스케이프"""
        return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
    
    def _get_program_rel_type(self, node_type: NodeType) -> str:
        """노드 타입에 따른 Program 관계 타입"""
        mapping = {
            # 변수 타입
            NodeType.PROC_VARIABLE: "DECLARES",
            NodeType.STRUCT_FIELD: "DEFINES",
            NodeType.SQL_HOST_VAR: "CONTAINS",
            NodeType.OMM_FIELD: "HAS_OMM",
            NodeType.MYBATIS_PARAM: "HAS_DBIO",
            NodeType.JAVA_VARIABLE: "DECLARES",
            # 프로그램 구조 타입
            NodeType.HEADER_FILE: "INCLUDES",
            NodeType.MACRO: "DEFINES",
            NodeType.FUNCTION: "CONTAINS",
            NodeType.BAM_CALL: "CONTAINS",
            NodeType.CURSOR: "CONTAINS",
            NodeType.TRANSACTION: "CONTAINS",
        }
        return mapping.get(node_type, "CONTAINS")
