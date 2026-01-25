"""
Verifier Module - 파싱 결과 검증 모듈

원본 소스 코드와 분석 결과를 비교하여 파싱이 올바르게 수행되었는지 검증합니다.

검증 플러그인:
- MacroVerifier: 매크로 정의 검증
- HeaderVerifier: 헤더 선언부 검증  
- VariableVerifier: 변수 선언 검증
- SQLExtractionVerifier: SQL 추출 검증
- SQLMetadataVerifier: SQL 메타데이터 검증
"""

from .core import ParsingVerifier
from .types import (
    VerificationType,
    VerificationStatus,
    VerificationInput,
    VerificationIssue,
    VerificationResult,
    VerificationContext,
    MacroInfo,
)
from .plugin_interface import VerifierPlugin

__all__ = [
    # Core
    'ParsingVerifier',
    
    # Types
    'VerificationType',
    'VerificationStatus', 
    'VerificationInput',
    'VerificationIssue',
    'VerificationResult',
    'VerificationContext',
    'MacroInfo',
    
    # Interface
    'VerifierPlugin',
]
