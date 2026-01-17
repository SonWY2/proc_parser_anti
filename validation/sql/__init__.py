"""
Pro*C to MyBatis SQL 변환 검증 도구

YAML 파일에서 원본(sql)과 변환된(parsed_sql) SQL을 로드하여
변환이 올바르게 되었는지 검증하는 GUI 도구입니다.
"""

from .yaml_loader import load_yaml
from .static_analyzer import StaticAnalyzer
from .diff_highlighter import DiffHighlighter
from .llm_client import LLMClient
from .prompt import DEFAULT_PROMPT, load_custom_prompt
from .exporter import export_approved, export_rejected, export_all_with_status
from .session import SessionData, save_session, load_session
from .host_var_mapper import extract_variable_mapping, analyze_variable_mapping
from .batch_processor import process_batch, BatchResult, generate_markdown_report, generate_html_report

__all__ = [
    # 기존 모듈
    'load_yaml',
    'StaticAnalyzer',
    'DiffHighlighter',
    'LLMClient',
    'DEFAULT_PROMPT',
    'load_custom_prompt',
    # 내보내기
    'export_approved',
    'export_rejected',
    'export_all_with_status',
    # 세션
    'SessionData',
    'save_session',
    'load_session',
    # 호스트 변수 매핑
    'extract_variable_mapping',
    'analyze_variable_mapping',
    # 일괄 처리
    'process_batch',
    'BatchResult',
    'generate_markdown_report',
    'generate_html_report',
]
