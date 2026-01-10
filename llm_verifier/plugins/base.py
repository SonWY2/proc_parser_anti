"""
플러그인 베이스 클래스

모든 검증 플러그인이 상속해야 하는 베이스 클래스.
"""

from abc import ABC
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import VerificationContext, VerificationResult


class PluginPhase(str, Enum):
    """플러그인 실행 시점"""
    PRE_VERIFY = "pre_verify"    # 사전 검증 (정적 체크, 샘플링)
    VERIFY = "verify"            # 메인 검증 (LLM 호출)
    POST_VERIFY = "post_verify"  # 후처리 (리포트 생성)


class VerifierPlugin(ABC):
    """검증 플러그인 베이스 클래스
    
    모든 플러그인은 이 클래스를 상속하고 다음 메소드 중 하나 이상을 구현:
    - process(): 컨텍스트 처리 (PRE_VERIFY, VERIFY)
    - process_result(): 결과 처리 (POST_VERIFY)
    
    Attributes:
        name: 플러그인 이름 (고유)
        stage: 처리 대상 단계 ("sql_extraction", "all" 등)
        phase: 실행 시점 (PRE_VERIFY, VERIFY, POST_VERIFY)
        priority: 실행 우선순위 (낮을수록 먼저)
        description: 플러그인 설명
    """
    
    name: str = "base"
    stage: str = "all"  # "all"이면 모든 단계에 적용
    phase: PluginPhase = PluginPhase.VERIFY
    priority: int = 100
    description: str = ""
    
    def process(self, context: 'VerificationContext') -> 'VerificationContext':
        """컨텍스트 처리 (PRE_VERIFY, VERIFY)
        
        기본 구현은 컨텍스트를 그대로 반환.
        
        Args:
            context: 검증 컨텍스트
            
        Returns:
            처리된 컨텍스트
        """
        return context
    
    def process_result(self, result: 'VerificationResult') -> 'VerificationResult':
        """결과 처리 (POST_VERIFY)
        
        기본 구현은 결과를 그대로 반환.
        
        Args:
            result: 검증 결과
            
        Returns:
            처리된 결과
        """
        return result
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name}, phase={self.phase.value}, stage={self.stage}, priority={self.priority})>"
