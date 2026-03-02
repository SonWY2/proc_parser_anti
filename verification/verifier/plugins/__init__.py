"""
검증 플러그인 모듈

사용 가능한 플러그인:
- MacroVerifier: 매크로 정의 검증
- HeaderVerifier: 헤더 선언부 검증
- VariableVerifier: 변수 선언 검증
- SQLExtractionVerifier: SQL 추출 검증
- SQLMetadataVerifier: SQL 메타데이터 검증 (규칙 기반)
- LLMHeaderVerifier: 헤더 섹션 검증 (LLM 기반)
- LLMSQLExtractionVerifier: SQL 추출 검증 (LLM 기반)
- LLMSQLMetadataVerifier: SQL 메타데이터 검증 (LLM 기반)
"""

from typing import List

from ..plugin_interface import VerifierPlugin

from .macro_verifier import MacroVerifier
from .header_verifier import HeaderVerifier
from .variable_verifier import VariableVerifier
from .sql_extraction_verifier import SQLExtractionVerifier
from .sql_metadata_verifier import SQLMetadataVerifier
from .llm_sql_metadata_verifier import LLMSQLMetadataVerifier
from .llm_header_verifier import LLMHeaderVerifier
from .llm_sql_extraction_verifier import LLMSQLExtractionVerifier


def get_all_plugins() -> List[VerifierPlugin]:
    """모든 플러그인 인스턴스 반환"""
    return [
        MacroVerifier(),
        HeaderVerifier(),
        VariableVerifier(),
        SQLExtractionVerifier(),
        SQLMetadataVerifier(),
        LLMSQLMetadataVerifier(),
    ]


def get_plugin_by_type(verification_type: str) -> VerifierPlugin:
    """검증 유형으로 플러그인 조회"""
    for plugin in get_all_plugins():
        if plugin.verification_type == verification_type:
            return plugin
    raise ValueError(f"No plugin found for verification type: {verification_type}")


__all__ = [
    'get_all_plugins',
    'get_plugin_by_type',
    'MacroVerifier',
    'HeaderVerifier',
    'VariableVerifier',
    'SQLExtractionVerifier',
    'SQLMetadataVerifier',
    'LLMHeaderVerifier',
    'LLMSQLExtractionVerifier',
    'LLMSQLMetadataVerifier',
]
