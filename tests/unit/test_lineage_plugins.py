"""
Lineage Plugin Architecture Tests
"""
import pytest
from analysis.lineage import (
    VariableLineageTracker, 
    PrefixRemovalPlugin, 
    SnakeToCamelPlugin,
    NameTransformPlugin, 
    TransformationResult
)

class TestLineagePlugins:
    
    def test_default_plugins_loaded(self):
        """기본 플러그인이 로드되는지 테스트"""
        tracker = VariableLineageTracker()
        plugins = tracker.get_plugins()
        
        plugin_names = [p.name() for p in plugins]
        assert "prefix_removal" in plugin_names
        assert "snake_to_camel" in plugin_names
        
    def test_prefix_removal_plugin(self):
        """Prefix 제거 플러그인 동작 테스트"""
        plugin = PrefixRemovalPlugin()
        
        # 기본 prefix 테스트
        res1 = plugin.transform("H_o_user_id")
        assert res1.name == "user_id"
        assert "prefix_removed:H_o_" in res1.transformations
        
        res2 = plugin.transform("H_i_data")
        assert res2.name == "data"
        assert "prefix_removed:H_i_" in res2.transformations
        
        # 매칭되지 않는 경우
        res3 = plugin.transform("OrdinaryVar")
        assert res3.name == "OrdinaryVar"
        assert len(res3.transformations) == 0

    def test_custom_prefix_config(self):
        """커스텀 Prefix 설정 테스트"""
        plugin = PrefixRemovalPlugin(prefixes=["MY_", "APP_"])
        
        res = plugin.transform("MY_variable")
        assert res.name == "variable"
        assert "prefix_removed:MY_" in res.transformations
        
        # 기본 prefix는 동작하지 않아야 함
        res2 = plugin.transform("H_o_variable")
        assert res2.name == "H_o_variable"
        
    def test_snake_to_camel_plugin(self):
        """Snake to Camel 플러그인 동작 테스트"""
        plugin = SnakeToCamelPlugin()
        
        res = plugin.transform("user_id")
        assert res.name == "userId"
        assert "snake_to_camel" in res.transformations
        
        res2 = plugin.transform("my_long_variable_name")
        assert res2.name == "myLongVariableName"
        
        # 이미 camelCase거나 _가 없는 경우
        res3 = plugin.transform("simple")
        assert res3.name == "simple"
        assert len(res3.transformations) == 0

    def test_chained_execution(self):
        """플러그인 체인 실행 통합 테스트"""
        # 기본 트래커 사용 (PrefixRemoval -> SnakeToCamel)
        tracker = VariableLineageTracker()
        
        # H_o_user_id -> user_id -> userId
        r = tracker._match_names("H_o_user_id", "userId")
        assert r['matched'] is True
        assert "prefix_removed:H_o_" in r['transformations']
        assert "snake_to_camel" in r['transformations']

    def test_custom_plugin_implementation(self):
        """사용자 정의 플러그인 구현 테스트"""
        
        class UpperCasePlugin(NameTransformPlugin):
            def name(self): return "upper_case"
            def description(self): return "To Upper"
            def transform(self, name):
                return TransformationResult(name.upper(), ["to_upper"])
                
        tracker = VariableLineageTracker(plugins=[UpperCasePlugin()])
        
        # abc_def -> ABC_DEF
        r = tracker._match_names("abc_def", "ABC_DEF")
        assert r['matched'] is True
        assert "to_upper" in r['transformations']
