"""
Neo4j Exporter

플러그인 기반의 Neo4j Export 오케스트레이터입니다.
"""

from typing import Dict, List, Optional, Any
from .client import Neo4jClient, load_db_env
from .plugin_interface import Neo4jExportPlugin, Neo4jNode, Neo4jRelationship


class Neo4jExporter:
    """
    플러그인 기반 Neo4j Exporter
    
    Usage:
        # 1. Cypher 파일 생성
        plugin = LineageNeo4jPlugin(graph)
        exporter = Neo4jExporter(plugin)
        exporter.save_cypher("output.cypher")
        
        # 2. 직접 export
        exporter = Neo4jExporter.from_env(plugin)
        exporter.export()
    """
    
    def __init__(self, plugin: Neo4jExportPlugin, program_name: str = "UnknownProgram"):
        """
        Args:
            plugin: Neo4jExportPlugin 구현체
            program_name: Program 루트 노드 이름
        """
        self.plugin = plugin
        self.program_name = program_name
        self.client: Optional[Neo4jClient] = None
    
    @classmethod
    def from_env(
        cls, 
        plugin: Neo4jExportPlugin, 
        program_name: str = "UnknownProgram",
        env_file: str = None
    ) -> 'Neo4jExporter':
        """
        .db.env 파일에서 설정을 로드하여 연결된 인스턴스 생성
        """
        exporter = cls(plugin, program_name)
        exporter.client = Neo4jClient.from_env(env_file)
        return exporter
    
    def connect(self, uri: str, user: str, password: str, database: str = "neo4j") -> bool:
        """Neo4j 연결"""
        self.client = Neo4jClient()
        return self.client.connect(uri, user, password, database)
    
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self.client is not None and self.client.is_connected()
    
    def close(self):
        """연결 종료"""
        if self.client:
            self.client.close()
    
    def setup_schema(self) -> Dict[str, int]:
        """
        Neo4j 스키마 설정 (인덱스 + 제약조건)
        
        Returns:
            {'indexes': int, 'constraints': int}
        """
        if not self.is_connected():
            raise RuntimeError("Neo4j에 연결되지 않았습니다.")
        
        indexes = 0
        constraints = 0
        
        for label in self.plugin.get_labels():
            if self.client.create_index(label, "id"):
                indexes += 1
            if self.client.create_index(label, "name"):
                indexes += 1
            if self.client.create_constraint(label, "id"):
                constraints += 1
        
        # Program 노드
        if self.client.create_index("Program", "name"):
            indexes += 1
        if self.client.create_constraint("Program", "name"):
            constraints += 1
        
        return {'indexes': indexes, 'constraints': constraints}
    
    def export(self, source_file: str = "") -> Dict[str, int]:
        """
        Neo4j에 데이터 export
        
        Args:
            source_file: 소스 파일 경로 (Program 노드 속성용)
            
        Returns:
            {'nodes_created': int, 'relationships_created': int}
        """
        if not self.is_connected():
            raise RuntimeError("Neo4j에 연결되지 않았습니다.")
        
        nodes_created = 0
        rels_created = 0
        
        # Program 노드 생성
        self.client.run(
            "MERGE (p:Program {name: $name}) SET p.source_file = $source",
            name=self.program_name,
            source=source_file
        )
        
        # 노드 생성
        for node in self.plugin.get_nodes():
            props_str = ", ".join(f"n.{k} = ${k}" for k in node.properties.keys())
            query = f"MERGE (n:{node.label} {{id: $id}}) SET {props_str}" if props_str else f"MERGE (n:{node.label} {{id: $id}})"
            try:
                self.client.run(query, id=node.id, **node.properties)
                nodes_created += 1
            except Exception as e:
                print(f"노드 생성 실패 [{node.id}]: {e}")
        
        # 관계 생성
        for rel in self.plugin.get_relationships():
            props_str = ", ".join(f"r.{k} = ${k}" for k in rel.properties.keys())
            set_clause = f"SET {props_str}" if props_str else ""
            query = (
                f"MATCH (a {{id: $source}}), (b {{id: $target}}) "
                f"MERGE (a)-[r:{rel.rel_type}]->(b) {set_clause}"
            )
            try:
                self.client.run(query, source=rel.source_id, target=rel.target_id, **rel.properties)
                rels_created += 1
            except Exception as e:
                print(f"관계 생성 실패 [{rel.source_id}]->[{rel.target_id}]: {e}")
        
        # Program 소유 관계
        for node in self.plugin.get_nodes():
            self.client.run(
                f"MATCH (p:Program {{name: $prog}}), (n {{id: $node_id}}) "
                f"MERGE (p)-[:CONTAINS]->(n)",
                prog=self.program_name,
                node_id=node.id
            )
        
        return {'nodes_created': nodes_created, 'relationships_created': rels_created}
    
    def to_cypher(self, source_file: str = "", include_program: bool = True) -> str:
        """
        Cypher CREATE 문 생성
        
        Args:
            source_file: 소스 파일 경로
            include_program: Program 루트 노드 포함 여부
            
        Returns:
            Cypher 쿼리 문자열
        """
        lines = []
        
        # 헤더
        lines.append(f"// Neo4j Export via {self.plugin.name()}")
        lines.append(f"// Source: {source_file}")
        nodes = self.plugin.get_nodes()
        rels = self.plugin.get_relationships()
        lines.append(f"// Nodes: {len(nodes)}, Relationships: {len(rels)}")
        lines.append("")
        
        # Program 노드
        if include_program:
            lines.append("// Program Root Node")
            lines.append(f"CREATE (p:Program {{name: '{self.program_name}', source_file: '{source_file}'}})")
            lines.append("")
        
        # 노드 생성
        lines.append("// === Nodes ===")
        for node in nodes:
            props = self._format_properties(node.properties, node.id)
            var_name = self._safe_var_name(node.id)
            lines.append(f"CREATE ({var_name}:{node.label} {props})")
        
        lines.append("")
        
        # 관계 생성
        lines.append("// === Relationships ===")
        for rel in rels:
            src_var = self._safe_var_name(rel.source_id)
            tgt_var = self._safe_var_name(rel.target_id)
            props = self._format_properties(rel.properties)
            lines.append(f"CREATE ({src_var})-[:{rel.rel_type} {props}]->({tgt_var})")
        
        # Program 소유 관계
        if include_program:
            lines.append("")
            lines.append("// === Program Ownership ===")
            for node in nodes:
                var_name = self._safe_var_name(node.id)
                lines.append(f"CREATE (p)-[:CONTAINS]->({var_name})")
        
        return "\n".join(lines)
    
    def save_cypher(self, file_path: str, source_file: str = "") -> str:
        """
        Cypher 쿼리를 파일로 저장
        
        Args:
            file_path: 출력 파일 경로
            source_file: 소스 파일 경로
            
        Returns:
            저장된 파일 경로
        """
        cypher = self.to_cypher(source_file)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(cypher)
        return file_path
    
    def _format_properties(self, props: Dict[str, Any], node_id: str = None) -> str:
        """속성을 Cypher 형식으로 변환"""
        all_props = {}
        if node_id:
            all_props['id'] = node_id
        all_props.update(props)
        
        prop_strs = []
        for k, v in all_props.items():
            if isinstance(v, str):
                prop_strs.append(f"{k}: '{self._escape_string(v)}'")
            elif isinstance(v, (int, float)):
                prop_strs.append(f"{k}: {v}")
            elif isinstance(v, list):
                list_str = str(v).replace("'", '"')
                prop_strs.append(f"{k}: {list_str}")
            elif v is not None:
                prop_strs.append(f"{k}: '{self._escape_string(str(v))}'")
        
        return "{" + ", ".join(prop_strs) + "}"
    
    def _safe_var_name(self, node_id: str) -> str:
        """노드 ID를 Cypher 변수명으로 변환"""
        safe = node_id.replace("-", "_").replace(".", "_").replace(" ", "_")
        if safe and safe[0].isdigit():
            safe = "n_" + safe
        return safe[:50]
    
    def _escape_string(self, s: str) -> str:
        """Cypher 문자열 이스케이프"""
        return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
