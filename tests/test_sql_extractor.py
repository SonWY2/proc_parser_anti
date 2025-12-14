"""
sql_extractor 패키지 테스트

Tree-sitter 기반 SQL 추출과 규칙 기반 타입 결정을 테스트합니다.
"""

import os
import sys
import tempfile
import shutil
import re

# 상위 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# pytest 가용성 확인
try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

from sql_extractor import (
    SQLExtractor,
    SQLExtractorConfig,
    SQLTypeRegistry,
    HostVariableRegistry,
    SQLTypeRule,
    RuleMatch,
)
from sql_extractor.rules.sql_type_rules import DEFAULT_SQL_TYPE_RULES
from sql_extractor.rules.host_variable_rules import DEFAULT_HOST_VARIABLE_RULES


class TestSQLTypeRegistry:
    """SQLTypeRegistry 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.registry = SQLTypeRegistry()
        self.registry.load_defaults()
    
    def test_rule_count(self):
        """규칙 수 확인"""
        assert self.registry.rule_count == len(DEFAULT_SQL_TYPE_RULES)
    
    def test_priority_order(self):
        """규칙 우선순위 정렬 확인"""
        rules = self.registry.list_rules()
        priorities = [r['priority'] for r in rules]
        assert priorities == sorted(priorities, reverse=True)
    
    def test_determine_type_select(self):
        """SELECT 타입 결정"""
        result = self.registry.determine_type("EXEC SQL SELECT * FROM users;")
        assert result.matched
        assert result.value == "select"
    
    def test_determine_type_insert(self):
        """INSERT 타입 결정"""
        result = self.registry.determine_type("EXEC SQL INSERT INTO users VALUES (:id);")
        assert result.matched
        assert result.value == "insert"
    
    def test_determine_type_declare_cursor(self):
        """DECLARE CURSOR 타입 결정"""
        result = self.registry.determine_type(
            "EXEC SQL DECLARE cur CURSOR FOR SELECT * FROM users;"
        )
        assert result.matched
        assert result.value == "declare_cursor"
    
    def test_determine_type_fetch_into(self):
        """FETCH INTO 타입 결정"""
        result = self.registry.determine_type(
            "EXEC SQL FETCH cur INTO :id, :name;"
        )
        assert result.matched
        assert result.value == "fetch_into"
    
    def test_determine_type_include(self):
        """INCLUDE 타입 결정"""
        result = self.registry.determine_type("EXEC SQL INCLUDE SQLCA;")
        assert result.matched
        assert result.value == "include"
    
    def test_custom_rule_registration(self):
        """커스텀 규칙 등록"""
        class MergeRule(SQLTypeRule):
            @property
            def name(self):
                return "merge"
            
            @property
            def priority(self):
                return 55
            
            @property
            def pattern(self):
                return re.compile(r'EXEC\s+SQL\s+MERGE', re.IGNORECASE)
        
        self.registry.register(MergeRule())
        result = self.registry.determine_type("EXEC SQL MERGE INTO users;")
        assert result.matched
        assert result.value == "merge"


class TestHostVariableRegistry:
    """HostVariableRegistry 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.registry = HostVariableRegistry()
        self.registry.load_defaults()
    
    def test_rule_count(self):
        """규칙 수 확인"""
        assert self.registry.rule_count == len(DEFAULT_HOST_VARIABLE_RULES)
    
    def test_extract_basic_variable(self):
        """기본 변수 추출"""
        result = self.registry.extract_all(":user_id")
        assert len(result) == 1
        assert result[0]['var_name'] == 'user_id'
        assert result[0]['type'] == 'basic'
    
    def test_extract_array_variable(self):
        """배열 변수 추출"""
        result = self.registry.extract_all(":arr[10]")
        assert len(result) == 1
        assert result[0]['var_name'] == 'arr'
        assert result[0]['type'] == 'array'
        assert result[0]['index'] == '10'
    
    def test_extract_struct_variable(self):
        """구조체 변수 추출"""
        result = self.registry.extract_all(":user.name")
        assert len(result) == 1
        assert result[0]['var_name'] == 'user'
        assert result[0]['type'] == 'struct'
        assert result[0]['field_name'] == 'name'
    
    def test_extract_indicator_variable(self):
        """인디케이터 변수 추출"""
        result = self.registry.extract_all(":value:ind")
        assert len(result) == 1
        assert result[0]['var_name'] == 'value'
        assert result[0]['type'] == 'indicator'
        assert result[0]['indicator'] == 'ind'
    
    def test_extract_multiple_variables(self):
        """여러 변수 추출"""
        sql = "SELECT * INTO :out_id, :out_name FROM users WHERE id = :in_id"
        result = self.registry.extract_all(sql)
        var_names = [v['var_name'] for v in result]
        assert 'out_id' in var_names
        assert 'out_name' in var_names
        assert 'in_id' in var_names
    
    def test_classify_by_direction(self):
        """입출력 분류"""
        sql = "SELECT id INTO :out_id FROM users WHERE name = :in_name"
        input_vars, output_vars = self.registry.classify_by_direction(sql, 'select')
        
        input_names = [v['var_name'] for v in input_vars]
        output_names = [v['var_name'] for v in output_vars]
        
        assert 'in_name' in input_names
        assert 'out_id' in output_names


class TestDB2Rules:
    """DB2 규칙 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.registry = SQLTypeRegistry()
        self.registry.load_defaults()
        self.registry.load_db2_rules()
    
    def test_with_ur(self):
        """WITH UR 규칙"""
        result = self.registry.determine_type(
            "EXEC SQL SELECT * FROM users WITH UR;"
        )
        assert result.matched
        assert result.value == "select"
        assert result.metadata.get('isolation_level') == 'UR'
    
    def test_with_cs(self):
        """WITH CS 규칙"""
        result = self.registry.determine_type(
            "EXEC SQL SELECT * FROM users WITH CS;"
        )
        assert result.matched
        assert result.value == "select"
        assert result.metadata.get('isolation_level') == 'CS'
    
    def test_fetch_first(self):
        """FETCH FIRST 규칙"""
        result = self.registry.determine_type(
            "EXEC SQL SELECT * FROM users FETCH FIRST 10 ROWS ONLY;"
        )
        assert result.matched
        assert result.value == "select"
        assert result.metadata.get('fetch_first') == 10


class TestSQLExtractor:
    """SQLExtractor 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.config = SQLExtractorConfig()
        self.extractor = SQLExtractor(config=self.config)
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """테스트 정리"""
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """초기화 확인"""
        assert self.extractor.sql_type_registry.rule_count > 0
        assert self.extractor.host_var_registry.rule_count > 0
    
    def test_decompose_sql_basic(self):
        """기본 SQL 분해"""
        code = '''
int main() {
    EXEC SQL SELECT * FROM users INTO :id, :name;
    EXEC SQL INSERT INTO logs VALUES (:msg);
    return 0;
}
'''
        program_dict = {}
        self.config.OUTPUT_PATH = self.temp_dir
        
        result = self.extractor.decompose_sql(code, "test", program_dict)
        
        assert 'sql_call("sql_0"' in result
        assert 'sql_call("sql_1"' in result
        assert 'EXEC SQL SELECT' not in result
    
    def test_decompose_declare_section(self):
        """DECLARE SECTION 분해"""
        code = '''
EXEC SQL BEGIN DECLARE SECTION;
    int user_id;
    char user_name[100];
EXEC SQL END DECLARE SECTION;

int main() { return 0; }
'''
        program_dict = {}
        self.config.OUTPUT_PATH = self.temp_dir
        
        result = self.extractor.decompose_declare_section(code, "test", program_dict)
        
        assert 'EXEC SQL BEGIN DECLARE SECTION' not in result
        assert 'declare_section_files' in program_dict


class TestTreeSitterExtractor:
    """TreeSitterSQLExtractor 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        try:
            from sql_extractor.tree_sitter_extractor import TreeSitterSQLExtractor
            self.extractor = TreeSitterSQLExtractor()
            self.has_tree_sitter = True
        except ImportError:
            self.has_tree_sitter = False
    
    def test_extract_simple_sql(self):
        """단순 SQL 추출"""
        if not self.has_tree_sitter:
            return
        
        code = '''
int main() {
    EXEC SQL SELECT * FROM users;
    return 0;
}
'''
        blocks = self.extractor.extract_sql_blocks(code)
        assert len(blocks) >= 1
        assert 'SELECT' in blocks[0].text.upper()
    
    def test_function_scope_detection(self):
        """함수 스코프 감지"""
        if not self.has_tree_sitter:
            return
        
        code = '''
void func1() {
    EXEC SQL SELECT * FROM table1;
}

void func2() {
    EXEC SQL INSERT INTO table2 VALUES (:val);
}
'''
        functions = self.extractor.get_functions(code)
        blocks = self.extractor.extract_sql_blocks(code, functions)
        
        # 함수별 SQL 블록 확인
        func_names = [b.containing_function for b in blocks]
        assert 'func1' in func_names or 'func2' in func_names


def run_tests():
    """테스트 실행"""
    if HAS_PYTEST:
        import pytest
        pytest.main([__file__, "-v"])
    else:
        print("pytest not available, running basic tests...")
        
        # 기본 테스트 실행
        print("\n=== SQLTypeRegistry Tests ===")
        test = TestSQLTypeRegistry()
        test.setup_method()
        test.test_rule_count()
        test.test_priority_order()
        test.test_determine_type_select()
        test.test_determine_type_insert()
        test.test_custom_rule_registration()
        print("All SQLTypeRegistry tests passed!")
        
        print("\n=== HostVariableRegistry Tests ===")
        test = TestHostVariableRegistry()
        test.setup_method()
        test.test_rule_count()
        test.test_extract_basic_variable()
        test.test_extract_array_variable()
        test.test_extract_multiple_variables()
        print("All HostVariableRegistry tests passed!")
        
        print("\n=== All tests passed! ===")


if __name__ == "__main__":
    run_tests()
