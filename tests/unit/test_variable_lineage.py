"""
Variable Lineage Tracker 테스트
"""
import pytest
import json
from analysis.lineage import (
    LineageNode, LineageLink, LineageGraph, 
    NodeType, LinkType, VariableLineageTracker,
    LineageConfig
)


class TestLineageTypes:
    """데이터 타입 테스트"""
    
    def test_node_creation(self):
        """LineageNode 생성 테스트"""
        node = LineageNode(
            id="proc_var_user_id",
            name="user_id",
            node_type=NodeType.PROC_VARIABLE,
            source_module="proc_parser",
            metadata={"data_type": "char", "size": 9}
        )
        
        assert node.id == "proc_var_user_id"
        assert node.name == "user_id"
        assert node.node_type == NodeType.PROC_VARIABLE
        
    def test_node_to_dict(self):
        """LineageNode JSON 변환 테스트"""
        node = LineageNode(
            id="test_node",
            name="test",
            node_type=NodeType.SQL_HOST_VAR,
            source_module="test"
        )
        
        d = node.to_dict()
        assert d['node_type'] == 'sql_host_var'
        
    def test_link_creation(self):
        """LineageLink 생성 테스트"""
        link = LineageLink(
            source_id="node_a",
            target_id="node_b",
            link_type=LinkType.TRANSFORMED_TO,
            confidence=0.9,
            transformations=["prefix_removed:H_", "snake_to_camel"]
        )
        
        assert link.source_id == "node_a"
        assert link.transformations == ["prefix_removed:H_", "snake_to_camel"]
        
    def test_graph_operations(self):
        """LineageGraph 조작 테스트"""
        graph = LineageGraph(source_file="test.pc")
        
        node1 = LineageNode("n1", "var1", NodeType.PROC_VARIABLE, "test")
        node2 = LineageNode("n2", "var2", NodeType.SQL_HOST_VAR, "test")
        
        graph.add_node(node1)
        graph.add_node(node2)
        
        link = LineageLink("n1", "n2", LinkType.USED_IN)
        graph.add_link(link)
        
        assert len(graph.nodes) == 2
        assert len(graph.links) == 1
        
        downstream = graph.get_downstream("n1")
        assert len(downstream) == 1
        assert downstream[0].id == "n2"


class TestVariableLineageTracker:
    """VariableLineageTracker 테스트"""
    
    def test_add_from_proc_parser(self):
        """proc_parser 결과로부터 노드 생성"""
        tracker = VariableLineageTracker()
        
        elements = [
            {
                "type": "variable",
                "name": "H_o_user_id",
                "data_type": "char",
                "line_start": 10
            },
            {
                "type": "sql",
                "sql_id": "sql_001",
                "sql_type": "SELECT",
                "input_host_vars": [":in_id"],
                "output_host_vars": [":out_name", ":out_age"]
            }
        ]
        
        count = tracker.add_from_proc_parser(elements)
        
        assert count == 4  # 1 variable + 1 input + 2 output
        assert "proc_var_H_o_user_id" in tracker.graph.nodes
        
    def test_add_from_header_parser(self):
        """header_parser 결과로부터 노드 생성"""
        tracker = VariableLineageTracker()
        
        db_vars_info = {
            "sampleStruct_t": {
                "userId": {
                    "dtype": "String",
                    "size": 9,
                    "name": "user_id",
                    "org_name": "user_id"
                },
                "userName": {
                    "dtype": "String",
                    "size": 50,
                    "name": "user_name",
                    "org_name": "user_name"
                }
            }
        }
        
        count = tracker.add_from_header_parser(db_vars_info)
        
        assert count == 2
        assert "struct_field_sampleStruct_t_userId" in tracker.graph.nodes
        
    def test_name_matching_exact(self):
        """정확한 이름 매칭 테스트"""
        tracker = VariableLineageTracker()
        
        result = tracker._match_names("user_id", "user_id")
        assert result['matched'] is True
        assert result['confidence'] == 1.0
        
    def test_name_matching_with_prefix(self):
        """Prefix 제거 매칭 테스트"""
        tracker = VariableLineageTracker()
        
        # H_ prefix
        result = tracker._match_names("H_user_id", "user_id")
        assert result['matched'] is True
        assert "prefix_removed:H_" in result['transformations']
        
        # H_o_ prefix
        result = tracker._match_names("H_o_result_code", "result_code")
        assert result['matched'] is True
        assert "prefix_removed:H_o_" in result['transformations']
        
    def test_name_matching_snake_to_camel(self):
        """snake_case → camelCase 매칭 테스트"""
        tracker = VariableLineageTracker()
        
        result = tracker._match_names("user_id", "userId")
        assert result['matched'] is True
        assert "snake_to_camel" in result['transformations']
        
    def test_name_matching_prefix_and_camel(self):
        """Prefix 제거 + camelCase 매칭 테스트"""
        tracker = VariableLineageTracker()
        
        result = tracker._match_names("H_o_result_code", "resultCode")
        assert result['matched'] is True
        assert "prefix_removed:H_o_" in result['transformations']
        assert "snake_to_camel" in result['transformations']
        
    def test_build_links(self):
        """연결 구축 테스트"""
        tracker = VariableLineageTracker()
        
        # 노드 추가
        elements = [
            {"type": "variable", "name": "H_user_id"},
            {"type": "sql", "sql_id": "sql_001", "sql_type": "SELECT",
             "input_host_vars": [":user_id"], "output_host_vars": []}
        ]
        tracker.add_from_proc_parser(elements)
        
        # 링크 구축
        link_count = tracker.build_links()
        
        assert link_count > 0
        
    def test_query_lineage(self):
        """변수 추적 쿼리 테스트"""
        tracker = VariableLineageTracker()
        
        # 노드 추가
        elements = [
            {"type": "variable", "name": "user_id"},
        ]
        tracker.add_from_proc_parser(elements)
        
        # 쿼리
        result = tracker.query_lineage("user")
        
        assert result['query'] == "user"
        assert len(result['matched_nodes']) > 0
        
    def test_to_json(self):
        """JSON 출력 테스트"""
        tracker = VariableLineageTracker(source_file="test.pc")
        
        elements = [
            {"type": "variable", "name": "H_o_user_id"},
        ]
        tracker.add_from_proc_parser(elements)
        
        json_str = tracker.to_json()
        data = json.loads(json_str)
        
        assert "nodes" in data
        assert "links" in data
        assert "summary" in data
        assert data['source_file'] == "test.pc"


class TestTransformationTracking:
    """변환 규칙 추적 테스트"""
    
    def test_all_prefix_types(self):
        """모든 prefix 타입 추적 테스트"""
        tracker = VariableLineageTracker()
        
        prefixes = [
            ("H_o_result", "result", "H_o_"),
            ("H_i_input", "input", "H_i_"),
            ("H_data", "data", "H_"),
            ("W_buffer", "buffer", "W_"),
        ]
        
        for source, target, expected_prefix in prefixes:
            result = tracker._match_names(source, target)
            assert result['matched'] is True, f"Failed: {source} -> {target}"
            assert f"prefix_removed:{expected_prefix}" in result['transformations']
            
    def test_custom_prefix_config(self):
        """커스텀 prefix 설정 테스트"""
        config = LineageConfig(prefixes=['CUSTOM_', 'MY_'])
        tracker = VariableLineageTracker(config=config)
        
        result = tracker._match_names("CUSTOM_field", "field")
        assert result['matched'] is True
        assert "prefix_removed:CUSTOM_" in result['transformations']
        
        # 기본 prefix는 매칭되지 않음
        result = tracker._match_names("H_field", "field")
        assert result['matched'] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
