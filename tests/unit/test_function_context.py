"""
Function Context 모듈 테스트
"""
import pytest
import json
from typing import Dict


# 테스트용 메타데이터 생성
def create_test_metadata() -> Dict:
    """테스트용 메타데이터 생성"""
    return {
        "source_file": "test.pc",
        "elements": {
            "functions": [
                {
                    "name": "main",
                    "return_type": "int",
                    "parameters": ["int argc", "char **argv"],
                    "line_start": 10,
                    "line_end": 50,
                    "raw_content": "int main(int argc, char **argv) { process_data(); MAX_SIZE; return 0; }"
                },
                {
                    "name": "process_data",
                    "return_type": "void",
                    "parameters": [],
                    "line_start": 55,
                    "line_end": 100,
                    "raw_content": "void process_data() { User user; g_user_id = 1; }"
                }
            ],
            "sql": [
                {
                    "sql_id": "select_0",
                    "sql_type": "select",
                    "function_name": "process_data",
                    "line_start": 60,
                    "standardized_sql": "SELECT name FROM users WHERE id = :id",
                    "mybatis_sql": "SELECT name FROM users WHERE id = #{id}",
                    "input_vars": [":id"],
                    "output_vars": [":name"]
                },
                {
                    "sql_id": "insert_0",
                    "sql_type": "insert",
                    "function_name": "process_data",
                    "line_start": 70,
                    "standardized_sql": "INSERT INTO logs VALUES (:msg)",
                    "mybatis_sql": "INSERT INTO logs VALUES (#{msg})",
                    "input_vars": [":msg"]
                },
                {
                    "sql_id": "select_1",
                    "sql_type": "select",
                    "function_name": "main",
                    "line_start": 20,
                    "standardized_sql": "SELECT COUNT(*) FROM users",
                    "mybatis_sql": "SELECT COUNT(*) FROM users"
                }
            ],
            "variables": [
                {
                    "name": "g_user_id",
                    "data_type": "int",
                    "scope": "global",
                    "line_start": 5
                },
                {
                    "name": "g_buffer",
                    "data_type": "char",
                    "scope": "global",
                    "line_start": 6
                },
                {
                    "name": "local_var",
                    "data_type": "int",
                    "scope": "local",
                    "line_start": 56
                },
                {
                    "name": "user",
                    "data_type": "User",
                    "scope": "local",
                    "line_start": 57
                }
            ],
            "macros": [
                {
                    "name": "MAX_SIZE",
                    "value": "1024",
                    "line_start": 1
                },
                {
                    "name": "DEBUG",
                    "value": "1",
                    "line_start": 2
                }
            ],
            "structs": [
                {
                    "name": "User",
                    "fields": ["int id", "char name[50]"],
                    "line_start": 3
                }
            ]
        }
    }


class TestFunctionContextExtractor:
    """FunctionContextExtractor 테스트"""
    
    @pytest.fixture
    def extractor(self):
        """테스트용 추출기 생성"""
        from analysis.context import FunctionContextExtractor
        metadata = create_test_metadata()
        return FunctionContextExtractor(metadata)
    
    def test_list_functions(self, extractor):
        """함수 목록 반환 테스트"""
        functions = extractor.list_functions()
        assert "main" in functions
        assert "process_data" in functions
        assert len(functions) == 2
    
    def test_extract_sql(self, extractor):
        """SQL 추출 테스트"""
        ctx = extractor.extract("process_data", include_sql=True)
        assert len(ctx.sql) == 2
        assert ctx.sql[0]["sql_id"] == "select_0"
        assert ctx.sql[1]["sql_id"] == "insert_0"
    
    def test_extract_local_variables(self, extractor):
        """로컬 변수 추출 테스트"""
        ctx = extractor.extract("process_data", include_variables=True)
        assert len(ctx.local_variables) == 2
        var_names = [v["name"] for v in ctx.local_variables]
        assert "local_var" in var_names
        assert "user" in var_names
    
    def test_extract_used_global_variables(self, extractor):
        """사용된 전역 변수 추출 테스트"""
        ctx = extractor.extract("process_data", include_variables=True)
        assert len(ctx.used_global_variables) == 1
        assert ctx.used_global_variables[0]["name"] == "g_user_id"
    
    def test_extract_macros(self, extractor):
        """사용된 매크로 추출 테스트"""
        ctx = extractor.extract("main", include_macros=True)
        assert len(ctx.used_macros) == 1
        assert ctx.used_macros[0]["name"] == "MAX_SIZE"
    
    def test_extract_structs(self, extractor):
        """사용된 구조체 추출 테스트"""
        ctx = extractor.extract("process_data", include_structs=True)
        assert len(ctx.used_structs) == 1
        assert ctx.used_structs[0]["name"] == "User"
    
    def test_extract_mybatis_xml(self, extractor):
        """MyBatis XML 생성 테스트"""
        ctx = extractor.extract("process_data", include_sql=True, include_mybatis=True)
        assert ctx.mybatis_xml is not None
        assert "<mapper" in ctx.mybatis_xml
        assert 'id="select_0"' in ctx.mybatis_xml
        assert 'id="insert_0"' in ctx.mybatis_xml
    
    def test_extract_omm(self, extractor):
        """OMM VO 생성 테스트"""
        ctx = extractor.extract("process_data", include_variables=True, include_omm=True)
        assert ctx.omm_code is not None
        assert "ProcessDataVO" in ctx.omm_code
        assert "private" in ctx.omm_code
    
    def test_extract_dbio(self, extractor):
        """DBIO 생성 테스트"""
        ctx = extractor.extract("process_data", include_sql=True, include_dbio=True)
        assert ctx.dbio_code is not None
        assert "ProcessDataDBIO" in ctx.dbio_code
        assert "@Repository" in ctx.dbio_code
    
    def test_extract_dao(self, extractor):
        """DAO 인터페이스 생성 테스트"""
        ctx = extractor.extract("process_data", include_sql=True, include_dao=True)
        assert ctx.dao_code is not None
        assert "ProcessDataMapper" in ctx.dao_code
        assert "@Mapper" in ctx.dao_code
    
    def test_extract_all(self, extractor):
        """모든 함수 추출 테스트"""
        all_ctx = extractor.extract_all(include_sql=True)
        assert "main" in all_ctx
        assert "process_data" in all_ctx
        assert len(all_ctx["main"].sql) == 1
        assert len(all_ctx["process_data"].sql) == 2
    
    def test_function_not_found(self, extractor):
        """존재하지 않는 함수 테스트"""
        ctx = extractor.extract("nonexistent")
        assert ctx.name == "nonexistent"
        assert len(ctx.sql) == 0
        assert len(ctx.local_variables) == 0
    
    def test_to_dict(self, extractor):
        """to_dict 변환 테스트"""
        ctx = extractor.extract("process_data", include_sql=True)
        d = ctx.to_dict()
        assert d["name"] == "process_data"
        assert "sql" in d
        assert len(d["sql"]) == 2
    
    def test_to_json(self, extractor):
        """to_json 변환 테스트"""
        ctx = extractor.extract("process_data", include_sql=True)
        json_str = ctx.to_json()
        parsed = json.loads(json_str)
        assert parsed["name"] == "process_data"
    
    def test_summary(self, extractor):
        """summary 테스트"""
        ctx = extractor.extract("process_data")
        summary = ctx.summary()
        assert "process_data" in summary
        assert "SQL=2" in summary


class TestMetadataIndexer:
    """MetadataIndexer 테스트"""
    
    @pytest.fixture
    def indexer(self):
        """테스트용 인덱서 생성"""
        from analysis.context.indexer import MetadataIndexer
        metadata = create_test_metadata()
        return MetadataIndexer(metadata)
    
    def test_list_functions(self, indexer):
        """함수 목록 테스트"""
        functions = indexer.list_functions()
        assert len(functions) == 2
    
    def test_get_function_info(self, indexer):
        """함수 정보 조회 테스트"""
        info = indexer.get_function_info("main")
        assert info is not None
        assert info.name == "main"
        assert info.line_start == 10
        assert info.line_end == 50
    
    def test_find_function_for_line(self, indexer):
        """라인으로 함수 찾기 테스트"""
        func = indexer.find_function_for_line(30)
        assert func == "main"
        
        func = indexer.find_function_for_line(60)
        assert func == "process_data"
        
        func = indexer.find_function_for_line(5)
        assert func is None
    
    def test_get_sql_for_function(self, indexer):
        """함수별 SQL 조회 테스트"""
        sql = indexer.get_sql_for_function("process_data")
        assert len(sql) == 2
        
        sql = indexer.get_sql_for_function("main")
        assert len(sql) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
