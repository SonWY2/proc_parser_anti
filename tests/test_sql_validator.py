"""
sql_validator 패키지 테스트

모든 모듈에 대한 유닛 테스트를 포함합니다.
외부 의존성(API, 파일)은 목킹합니다.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 테스트 대상 모듈
from sql_validator.yaml_loader import load_yaml, validate_yaml_structure
from sql_validator.static_analyzer import StaticAnalyzer, CheckStatus, AnalysisResult
from sql_validator.diff_highlighter import DiffHighlighter, DiffType
from sql_validator.llm_client import LLMClient
from sql_validator.prompt import DEFAULT_PROMPT, load_custom_prompt, format_prompt, save_custom_prompt


# =============================================================================
# YAML Loader 테스트
# =============================================================================

class TestYamlLoader:
    """yaml_loader 모듈 테스트"""
    
    def test_load_valid_yaml(self, tmp_path):
        """유효한 YAML 파일 로드"""
        yaml_content = """
- sql: "EXEC SQL SELECT * FROM users;"
  parsed_sql: "SELECT * FROM users"
- sql: "EXEC SQL INSERT INTO orders VALUES (:id);"
  parsed_sql: "INSERT INTO orders VALUES (#{id})"
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content, encoding='utf-8')
        
        result = load_yaml(str(yaml_file))
        
        assert len(result) == 2
        assert result[0]['sql'] == "EXEC SQL SELECT * FROM users;"
        assert result[0]['parsed_sql'] == "SELECT * FROM users"
        assert result[1]['sql'] == "EXEC SQL INSERT INTO orders VALUES (:id);"
        assert result[1]['parsed_sql'] == "INSERT INTO orders VALUES (#{id})"
    
    def test_load_yaml_with_metadata(self, tmp_path):
        """메타데이터가 포함된 YAML 로드"""
        yaml_content = """
- sql: "SELECT * FROM test"
  parsed_sql: "SELECT * FROM test"
  description: "테스트 쿼리"
  author: "dev"
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content, encoding='utf-8')
        
        result = load_yaml(str(yaml_file))
        
        assert len(result) == 1
        assert result[0]['metadata']['description'] == "테스트 쿼리"
        assert result[0]['metadata']['author'] == "dev"
    
    def test_load_yaml_single_dict(self, tmp_path):
        """단일 딕셔너리 형태 YAML 로드"""
        yaml_content = """
sql: "SELECT 1"
parsed_sql: "SELECT 1"
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content, encoding='utf-8')
        
        result = load_yaml(str(yaml_file))
        
        assert len(result) == 1
        assert result[0]['sql'] == "SELECT 1"
    
    def test_load_yaml_file_not_found(self):
        """존재하지 않는 파일"""
        with pytest.raises(FileNotFoundError):
            load_yaml("nonexistent_file.yaml")
    
    def test_load_yaml_missing_keys(self, tmp_path):
        """필수 키가 없는 항목은 건너뜀"""
        yaml_content = """
- sql: "SELECT 1"
- parsed_sql: "SELECT 2"
- sql: "SELECT 3"
  parsed_sql: "SELECT 3"
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content, encoding='utf-8')
        
        result = load_yaml(str(yaml_file))
        
        # sql과 parsed_sql 모두 있는 항목만 로드
        assert len(result) == 1
        assert result[0]['sql'] == "SELECT 3"
    
    def test_load_empty_yaml(self, tmp_path):
        """빈 YAML 파일"""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("", encoding='utf-8')
        
        result = load_yaml(str(yaml_file))
        
        assert result == []
    
    def test_validate_yaml_structure_valid(self, tmp_path):
        """유효한 YAML 구조 검증"""
        yaml_content = """
- sql: "SELECT 1"
  parsed_sql: "SELECT 1"
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content, encoding='utf-8')
        
        result = validate_yaml_structure(str(yaml_file))
        
        assert result is None  # 오류 없음
    
    def test_validate_yaml_structure_invalid(self):
        """잘못된 YAML 경로 검증"""
        result = validate_yaml_structure("nonexistent.yaml")
        
        assert result is not None
        assert "찾을 수 없습니다" in result


# =============================================================================
# Static Analyzer 테스트
# =============================================================================

class TestStaticAnalyzer:
    """static_analyzer 모듈 테스트"""
    
    @pytest.fixture
    def analyzer(self):
        return StaticAnalyzer()
    
    def test_exec_sql_removed(self, analyzer):
        """EXEC SQL 제거 검증"""
        asis = "EXEC SQL SELECT * FROM users;"
        tobe = "SELECT * FROM users"
        
        result = analyzer.analyze(asis, tobe)
        
        exec_check = next(c for c in result.checks if c.name == "EXEC SQL 제거")
        assert exec_check.status == CheckStatus.PASS
    
    def test_exec_sql_not_removed(self, analyzer):
        """EXEC SQL 미제거 감지"""
        asis = "EXEC SQL SELECT * FROM users;"
        tobe = "EXEC SQL SELECT * FROM users"
        
        result = analyzer.analyze(asis, tobe)
        
        exec_check = next(c for c in result.checks if c.name == "EXEC SQL 제거")
        assert exec_check.status == CheckStatus.FAIL
    
    def test_host_variable_converted(self, analyzer):
        """호스트 변수 변환 검증"""
        asis = "SELECT * FROM users WHERE id = :user_id"
        tobe = "SELECT * FROM users WHERE id = #{userId}"
        
        result = analyzer.analyze(asis, tobe)
        
        var_check = next(c for c in result.checks if c.name == "호스트 변수 변환")
        assert var_check.status == CheckStatus.PASS
    
    def test_host_variable_not_converted(self, analyzer):
        """변환되지 않은 호스트 변수 감지"""
        asis = "SELECT * FROM users WHERE id = :user_id"
        tobe = "SELECT * FROM users WHERE id = :user_id"
        
        result = analyzer.analyze(asis, tobe)
        
        var_check = next(c for c in result.checks if c.name == "호스트 변수 변환")
        assert var_check.status == CheckStatus.FAIL
    
    def test_semicolon_removed(self, analyzer):
        """세미콜론 제거 검증"""
        asis = "SELECT * FROM users;"
        tobe = "SELECT * FROM users"
        
        result = analyzer.analyze(asis, tobe)
        
        semi_check = next(c for c in result.checks if c.name == "세미콜론 처리")
        assert semi_check.status == CheckStatus.PASS
    
    def test_select_into_converted(self, analyzer):
        """SELECT INTO 변환 검증"""
        asis = "EXEC SQL SELECT id INTO :emp_id FROM employees;"
        tobe = "SELECT id FROM employees"
        
        result = analyzer.analyze(asis, tobe)
        
        into_check = next(c for c in result.checks if c.name == "SELECT INTO 변환")
        assert into_check.status == CheckStatus.PASS
    
    def test_keywords_preserved(self, analyzer):
        """SQL 키워드 보존 검증"""
        asis = "SELECT id, name FROM users WHERE status = 'active'"
        tobe = "SELECT id, name FROM users WHERE status = 'active'"
        
        result = analyzer.analyze(asis, tobe)
        
        kw_check = next(c for c in result.checks if c.name == "SQL 키워드 보존")
        assert kw_check.status == CheckStatus.PASS
    
    def test_analysis_result_counts(self, analyzer):
        """분석 결과 카운트 검증"""
        asis = "EXEC SQL SELECT * FROM users WHERE id = :id;"
        tobe = "SELECT * FROM users WHERE id = #{id}"
        
        result = analyzer.analyze(asis, tobe)
        
        assert result.pass_count >= 0
        assert result.fail_count >= 0
        assert result.warning_count >= 0
        assert len(result.checks) == 6  # 6개 검증 규칙
    
    def test_no_host_variables(self, analyzer):
        """호스트 변수 없는 경우"""
        asis = "SELECT * FROM users"
        tobe = "SELECT * FROM users"
        
        result = analyzer.analyze(asis, tobe)
        
        var_check = next(c for c in result.checks if c.name == "호스트 변수 변환")
        assert var_check.status == CheckStatus.INFO


# =============================================================================
# Diff Highlighter 테스트
# =============================================================================

class TestDiffHighlighter:
    """diff_highlighter 모듈 테스트"""
    
    @pytest.fixture
    def highlighter(self):
        return DiffHighlighter(ignore_whitespace=True)
    
    def test_identical_texts(self, highlighter):
        """동일한 텍스트"""
        text = "SELECT * FROM users"
        
        highlights = highlighter.get_highlight_ranges(text, text)
        
        assert len(highlights['asis']) == 0
        assert len(highlights['tobe']) == 0
    
    def test_whitespace_ignored(self, highlighter):
        """공백 차이 무시"""
        asis = "SELECT  *   FROM    users"
        tobe = "SELECT * FROM users"
        
        summary = highlighter.get_change_summary(asis, tobe)
        
        # 정규화 후 비교하면 동일
        assert summary['similarity'] > 0.9
    
    def test_detect_replacement(self, highlighter):
        """변경 감지"""
        asis = "SELECT * FROM old_table"
        tobe = "SELECT * FROM new_table"
        
        highlights = highlighter.get_highlight_ranges(asis, tobe)
        
        # 변경된 부분이 하이라이트됨
        assert len(highlights['asis']) > 0
        assert len(highlights['tobe']) > 0
    
    def test_detect_insertion(self, highlighter):
        """추가 감지"""
        asis = "SELECT id FROM users"
        tobe = "SELECT id, name FROM users"
        
        highlights = highlighter.get_highlight_ranges(asis, tobe)
        
        # tobe에 추가된 부분
        assert len(highlights['tobe']) > 0
    
    def test_detect_deletion(self, highlighter):
        """삭제 감지"""
        asis = "SELECT id, name FROM users"
        tobe = "SELECT id FROM users"
        
        highlights = highlighter.get_highlight_ranges(asis, tobe)
        
        # asis에서 삭제된 부분
        assert len(highlights['asis']) > 0
    
    def test_similarity_ratio(self, highlighter):
        """유사도 계산"""
        asis = "SELECT * FROM users"
        tobe = "SELECT * FROM users"
        
        similarity = highlighter.get_similarity_ratio(asis, tobe)
        
        assert similarity == 1.0
    
    def test_change_summary(self, highlighter):
        """변경 요약"""
        asis = "SELECT old_col FROM old_table"
        tobe = "SELECT new_col FROM new_table"
        
        summary = highlighter.get_change_summary(asis, tobe)
        
        assert 'total_blocks' in summary
        assert 'similarity' in summary
        assert summary['has_changes'] == True
    
    def test_compute_diff_returns_blocks(self, highlighter):
        """diff 블록 반환"""
        asis = "SELECT * FROM table_a"
        tobe = "SELECT * FROM table_b"
        
        blocks = highlighter.compute_diff(asis, tobe)
        
        assert len(blocks) > 0
        assert all(hasattr(b, 'diff_type') for b in blocks)


# =============================================================================
# LLM Client 테스트 (Mocked)
# =============================================================================

class TestLLMClient:
    """llm_client 모듈 테스트 (API 목킹)"""
    
    @pytest.fixture
    def mock_env(self, tmp_path):
        """목킹된 .env 환경"""
        env_file = tmp_path / ".env"
        env_file.write_text("VLLM_API_ENDPOINT=http://mock-api:8000/v1", encoding='utf-8')
        return str(env_file)
    
    def test_client_not_configured(self):
        """API 미설정 상태"""
        with patch.dict(os.environ, {}, clear=True):
            with patch('sql_validator.llm_client.load_dotenv'):
                client = LLMClient()
                client.endpoint = ""
                
                assert client.is_configured == False
    
    def test_client_configured(self, mock_env):
        """API 설정 상태"""
        with patch('sql_validator.llm_client.load_dotenv'):
            client = LLMClient()
            client.endpoint = "http://mock-api:8000/v1"
            
            assert client.is_configured == True
    
    @patch('sql_validator.llm_client.requests.get')
    def test_get_model_name_success(self, mock_get):
        """모델 이름 조회 성공"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [{'id': 'test-model'}]
        }
        mock_get.return_value = mock_response
        
        with patch('sql_validator.llm_client.load_dotenv'):
            client = LLMClient()
            client.endpoint = "http://mock-api:8000/v1"
            
            model_name = client.get_model_name()
            
            assert model_name == "test-model"
    
    @patch('sql_validator.llm_client.requests.get')
    def test_get_model_name_failure(self, mock_get):
        """모델 이름 조회 실패"""
        import requests
        mock_get.side_effect = requests.RequestException("Connection error")
        
        with patch('sql_validator.llm_client.load_dotenv'):
            client = LLMClient()
            client.endpoint = "http://mock-api:8000/v1"
            
            model_name = client.get_model_name()
            
            assert model_name is None
    
    @patch('sql_validator.llm_client.requests.post')
    @patch('sql_validator.llm_client.requests.get')
    def test_analyze_conversion_success(self, mock_get, mock_post):
        """변환 분석 성공"""
        # 모델 조회 목킹
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {'data': [{'id': 'test-model'}]}
        mock_get.return_value = mock_get_response
        
        # API 응답 목킹
        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {
            'choices': [{'message': {'content': '✅ 변환이 올바릅니다.'}}]
        }
        mock_post.return_value = mock_post_response
        
        with patch('sql_validator.llm_client.load_dotenv'):
            client = LLMClient()
            client.endpoint = "http://mock-api:8000/v1"
            
            # 간단한 프롬프트 사용 (중괄호 이슈 회피)
            simple_prompt = "원본: {asis}\n변환: {tobe}"
            result = client.analyze_conversion(
                "EXEC SQL SELECT * FROM users;",
                "SELECT * FROM users",
                prompt=simple_prompt
            )
            
            assert result['success'] == True
            assert "변환이 올바릅니다" in result['response']
    
    @patch('sql_validator.llm_client.requests.post')
    @patch('sql_validator.llm_client.requests.get')
    def test_analyze_conversion_timeout(self, mock_get, mock_post):
        """API 타임아웃"""
        import requests
        
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {'data': [{'id': 'test-model'}]}
        mock_get.return_value = mock_get_response
        
        mock_post.side_effect = requests.Timeout()
        
        with patch('sql_validator.llm_client.load_dotenv'):
            client = LLMClient()
            client.endpoint = "http://mock-api:8000/v1"
            
            # 간단한 프롬프트 사용
            simple_prompt = "원본: {asis}\n변환: {tobe}"
            result = client.analyze_conversion("SELECT 1", "SELECT 1", prompt=simple_prompt)
            
            assert result['success'] == False
            assert "시간이 초과" in result['error']
    
    def test_test_connection_not_configured(self):
        """연결 테스트 - 미설정"""
        with patch('sql_validator.llm_client.load_dotenv'):
            client = LLMClient()
            client.endpoint = ""
            
            result = client.test_connection()
            
            assert result['connected'] == False
            assert "설정되지 않았습니다" in result['error']


# =============================================================================
# Prompt 테스트
# =============================================================================

class TestPrompt:
    """prompt 모듈 테스트"""
    
    def test_default_prompt_exists(self):
        """기본 프롬프트 존재"""
        assert DEFAULT_PROMPT is not None
        assert len(DEFAULT_PROMPT) > 0
        assert '{asis}' in DEFAULT_PROMPT
        assert '{tobe}' in DEFAULT_PROMPT
    
    def test_format_prompt(self):
        """프롬프트 포맷팅"""
        template = "원본: {asis}\n변환: {tobe}"
        asis = "SELECT 1"
        tobe = "SELECT 1"
        
        result = format_prompt(template, asis, tobe)
        
        assert "원본: SELECT 1" in result
        assert "변환: SELECT 1" in result
    
    def test_load_custom_prompt_success(self, tmp_path):
        """커스텀 프롬프트 로드 성공"""
        prompt_content = "커스텀 프롬프트: {asis} vs {tobe}"
        prompt_file = tmp_path / "custom.txt"
        prompt_file.write_text(prompt_content, encoding='utf-8')
        
        result = load_custom_prompt(str(prompt_file))
        
        assert result == prompt_content
    
    def test_load_custom_prompt_missing_placeholders(self, tmp_path):
        """플레이스홀더 누락"""
        prompt_file = tmp_path / "invalid.txt"
        prompt_file.write_text("플레이스홀더 없음", encoding='utf-8')
        
        result = load_custom_prompt(str(prompt_file))
        
        assert result is None
    
    def test_load_custom_prompt_file_not_found(self):
        """파일 없음"""
        result = load_custom_prompt("nonexistent.txt")
        
        assert result is None
    
    def test_save_custom_prompt(self, tmp_path):
        """커스텀 프롬프트 저장"""
        prompt = "테스트 프롬프트: {asis} / {tobe}"
        save_path = tmp_path / "saved.txt"
        
        result = save_custom_prompt(str(save_path), prompt)
        
        assert result == True
        assert save_path.read_text(encoding='utf-8') == prompt


# =============================================================================
# 통합 테스트
# =============================================================================

class TestIntegration:
    """통합 테스트"""
    
    def test_full_workflow(self, tmp_path):
        """전체 워크플로우 테스트"""
        # 1. YAML 생성
        yaml_content = """
- sql: |
    EXEC SQL SELECT emp_id, emp_name
    INTO :emp_id, :emp_name
    FROM employees
    WHERE dept_id = :dept_id;
  parsed_sql: |
    SELECT emp_id, emp_name
    FROM employees
    WHERE dept_id = #{deptId}
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content, encoding='utf-8')
        
        # 2. YAML 로드
        items = load_yaml(str(yaml_file))
        assert len(items) == 1
        
        # 3. 정적 분석
        analyzer = StaticAnalyzer()
        result = analyzer.analyze(items[0]['sql'], items[0]['parsed_sql'])
        
        # EXEC SQL 제거됨
        exec_check = next(c for c in result.checks if c.name == "EXEC SQL 제거")
        assert exec_check.status == CheckStatus.PASS
        
        # SELECT INTO 변환됨
        into_check = next(c for c in result.checks if c.name == "SELECT INTO 변환")
        assert into_check.status == CheckStatus.PASS
        
        # 4. Diff 분석
        highlighter = DiffHighlighter()
        summary = highlighter.get_change_summary(items[0]['sql'], items[0]['parsed_sql'])
        
        assert summary['has_changes'] == True
    
    def test_multiple_items(self, tmp_path):
        """여러 항목 처리"""
        yaml_content = """
- sql: "EXEC SQL SELECT 1;"
  parsed_sql: "SELECT 1"
- sql: "EXEC SQL SELECT 2;"
  parsed_sql: "SELECT 2"
- sql: "EXEC SQL SELECT 3;"
  parsed_sql: "SELECT 3"
"""
        yaml_file = tmp_path / "multi.yaml"
        yaml_file.write_text(yaml_content, encoding='utf-8')
        
        items = load_yaml(str(yaml_file))
        analyzer = StaticAnalyzer()
        
        for item in items:
            result = analyzer.analyze(item['sql'], item['parsed_sql'])
            assert result.fail_count == 0


# =============================================================================
# Exporter 테스트
# =============================================================================

class TestExporter:
    """exporter 모듈 테스트"""
    
    def test_export_approved_items(self, tmp_path):
        """승인된 항목 내보내기"""
        from sql_validator.exporter import export_approved
        
        items = [
            {'sql': 'SELECT 1', 'parsed_sql': 'SELECT 1'},
            {'sql': 'SELECT 2', 'parsed_sql': 'SELECT 2'},
            {'sql': 'SELECT 3', 'parsed_sql': 'SELECT 3'},
        ]
        statuses = {0: 'approved', 2: 'approved'}
        
        output_file = tmp_path / "approved.yaml"
        count = export_approved(items, statuses, str(output_file))
        
        assert count == 2
        assert output_file.exists()
    
    def test_export_rejected_items(self, tmp_path):
        """거부된 항목 내보내기"""
        from sql_validator.exporter import export_rejected
        
        items = [
            {'sql': 'SELECT 1', 'parsed_sql': 'SELECT 1'},
            {'sql': 'SELECT 2', 'parsed_sql': 'SELECT 2'},
        ]
        statuses = {0: 'rejected'}
        
        output_file = tmp_path / "rejected.yaml"
        count = export_rejected(items, statuses, str(output_file))
        
        assert count == 1
    
    def test_export_empty_list(self, tmp_path):
        """빈 리스트 내보내기"""
        from sql_validator.exporter import export_approved
        
        items = [{'sql': 'SELECT 1', 'parsed_sql': 'SELECT 1'}]
        statuses = {0: 'rejected'}  # 승인된 항목 없음
        
        output_file = tmp_path / "empty.yaml"
        count = export_approved(items, statuses, str(output_file))
        
        assert count == 0


# =============================================================================
# Session 테스트
# =============================================================================

class TestSession:
    """session 모듈 테스트"""
    
    def test_save_and_load_session(self, tmp_path):
        """세션 저장 및 로드"""
        from sql_validator.session import SessionData, save_session, load_session
        
        session = SessionData(
            yaml_path="/path/to/data.yaml",
            current_index=5,
            validation_statuses={0: 'approved', 1: 'rejected'},
            comments={0: 'LGTM', 1: '수정 필요'},
            custom_prompt="Test prompt {asis} {tobe}"
        )
        
        session_file = tmp_path / "session.json"
        result = save_session(session, str(session_file))
        
        assert result == True
        assert session_file.exists()
        
        # 로드
        loaded = load_session(str(session_file))
        
        assert loaded is not None
        assert loaded.yaml_path == "/path/to/data.yaml"
        assert loaded.current_index == 5
        assert loaded.validation_statuses == {0: 'approved', 1: 'rejected'}
        assert loaded.comments == {0: 'LGTM', 1: '수정 필요'}
    
    def test_load_nonexistent_session(self):
        """존재하지 않는 세션 로드"""
        from sql_validator.session import load_session
        
        result = load_session("nonexistent.json")
        assert result is None


# =============================================================================
# Host Variable Mapper 테스트
# =============================================================================

class TestHostVarMapper:
    """host_var_mapper 모듈 테스트"""
    
    def test_extract_simple_mapping(self):
        """단순 매핑 추출"""
        from sql_validator.host_var_mapper import extract_variable_mapping
        
        asis = "SELECT * FROM users WHERE id = :user_id"
        tobe = "SELECT * FROM users WHERE id = #{userId}"
        
        mappings = extract_variable_mapping(asis, tobe)
        
        assert len(mappings) == 1
        assert mappings[0] == (':user_id', '#{userId}')
    
    def test_extract_multiple_vars(self):
        """여러 변수 매핑"""
        from sql_validator.host_var_mapper import extract_variable_mapping
        
        asis = "SELECT * FROM users WHERE id = :id AND status = :status"
        tobe = "SELECT * FROM users WHERE id = #{id} AND status = #{status}"
        
        mappings = extract_variable_mapping(asis, tobe)
        
        assert len(mappings) == 2
    
    def test_no_mapping(self):
        """변수 없는 경우"""
        from sql_validator.host_var_mapper import extract_variable_mapping
        
        asis = "SELECT * FROM users"
        tobe = "SELECT * FROM users"
        
        mappings = extract_variable_mapping(asis, tobe)
        
        assert len(mappings) == 0
    
    def test_snake_to_camel_detection(self):
        """snake_case to camelCase 변환 감지"""
        from sql_validator.host_var_mapper import get_naming_transformation
        
        result = get_naming_transformation("user_id", "userId")
        assert result == "snake_case → camelCase"


# =============================================================================
# Batch Processor 테스트
# =============================================================================

class TestBatchProcessor:
    """batch_processor 모듈 테스트"""
    
    def test_process_single_file(self, tmp_path):
        """단일 파일 처리"""
        from sql_validator.batch_processor import process_batch
        
        yaml_content = """
- sql: "EXEC SQL SELECT 1;"
  parsed_sql: "SELECT 1"
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content, encoding='utf-8')
        
        result = process_batch([str(yaml_file)])
        
        assert result.total_files == 1
        assert result.successful_files == 1
        assert result.total_items == 1
    
    def test_process_multiple_files(self, tmp_path):
        """여러 파일 처리"""
        from sql_validator.batch_processor import process_batch
        
        for i in range(3):
            yaml_content = f"""
- sql: "EXEC SQL SELECT {i};"
  parsed_sql: "SELECT {i}"
"""
            yaml_file = tmp_path / f"test_{i}.yaml"
            yaml_file.write_text(yaml_content, encoding='utf-8')
        
        files = [str(tmp_path / f"test_{i}.yaml") for i in range(3)]
        result = process_batch(files)
        
        assert result.total_files == 3
        assert result.total_items == 3
    
    def test_generate_markdown_report(self, tmp_path):
        """Markdown 리포트 생성"""
        from sql_validator.batch_processor import process_batch, generate_markdown_report
        
        yaml_content = """
- sql: "EXEC SQL SELECT 1;"
  parsed_sql: "SELECT 1"
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content, encoding='utf-8')
        
        result = process_batch([str(yaml_file)])
        report = generate_markdown_report(result)
        
        assert "SQL 변환 검증 리포트" in report
        assert "요약" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
