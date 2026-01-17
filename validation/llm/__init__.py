"""
LLM Verifier 모듈

Pro*C 파싱 결과의 정확성을 LLM을 활용하여 검증합니다.

주요 클래스:
- LLMVerifier: 메인 검증 오케스트레이터
- VerificationContext: 검증 컨텍스트
- VerificationResult: 검증 결과

Example:
    from llm_verifier import LLMVerifier
    
    verifier = LLMVerifier()
    result = verifier.verify(
        stage="sql_extraction",
        source=proc_code,
        result=extracted_elements
    )
    
    print(result.summary())
"""

from .types import (
    VerificationContext,
    VerificationResult,
    Feedback,
    FeedbackSeverity,
    CheckResult,
)
from .verifier import LLMVerifier
from .llm_client import LLMClient
from .prompts import VERIFICATION_PROMPT, format_verification_prompt
from .plugins import (
    VerifierPlugin,
    PluginPhase,
    register_plugin,
    load_plugins,
    load_plugins_by_phase,
    list_plugins,
)

__all__ = [
    # 메인 클래스
    "LLMVerifier",
    
    # 타입
    "VerificationContext",
    "VerificationResult",
    "Feedback",
    "FeedbackSeverity",
    "CheckResult",
    
    # LLM
    "LLMClient",
    "VERIFICATION_PROMPT",
    "format_verification_prompt",
    
    # 플러그인 시스템
    "VerifierPlugin",
    "PluginPhase",
    "register_plugin",
    "load_plugins",
    "load_plugins_by_phase",
    "list_plugins",
]
