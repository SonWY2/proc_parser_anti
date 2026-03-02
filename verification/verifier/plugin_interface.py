"""
검증 플러그인 인터페이스 정의

모든 검증 플러그인은 이 인터페이스를 구현해야 합니다.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .types import VerificationInput, VerificationResult, VerificationContext


class VerifierPlugin(ABC):
    """검증 플러그인 인터페이스
    
    모든 검증 플러그인은 이 추상 클래스를 상속받아 구현합니다.
    
    Example:
        class HeaderVerifier(VerifierPlugin):
            @property
            def name(self) -> str:
                return "header_verifier"
            
            @property
            def verification_type(self) -> str:
                return "header"
            
            def verify(self, input_data: VerificationInput) -> VerificationResult:
                # 검증 로직 구현
                ...
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """플러그인 이름"""
        pass
    
    @property
    @abstractmethod
    def verification_type(self) -> str:
        """검증 유형: macro, header, variable, sql_extraction, sql_metadata"""
        pass
    
    @property
    def requires_context(self) -> bool:
        """컨텍스트 필요 여부 (기본: False)
        
        True로 설정하면 verify() 호출 시 context가 반드시 제공되어야 합니다.
        변수/함수 검증처럼 매크로 정보가 필요한 경우 True로 설정합니다.
        """
        return False
    
    @property
    def context_dependencies(self) -> List[str]:
        """필요한 컨텍스트 항목들
        
        예: ["macros"] - 매크로 정보가 필요함
        """
        return []
    
    @abstractmethod
    def verify(self, input_data: VerificationInput) -> VerificationResult:
        """검증 수행
        
        Args:
            input_data: 검증 입력 데이터 (원본 소스, 분석 결과, 컨텍스트 등)
            
        Returns:
            VerificationResult: 검증 결과
        """
        pass
    
    def update_context(self, context: VerificationContext, result: VerificationResult) -> VerificationContext:
        """검증 후 컨텍스트 업데이트
        
        매크로 검증기가 매크로 정보를 컨텍스트에 추가하는 등의 용도로 사용.
        기본 구현은 아무것도 하지 않음.
        
        Args:
            context: 현재 컨텍스트
            result: 검증 결과
            
        Returns:
            VerificationContext: 업데이트된 컨텍스트
        """
        return context
    
    def validate_input(self, input_data: VerificationInput) -> Optional[str]:
        """입력 데이터 유효성 검사
        
        Args:
            input_data: 검증 입력 데이터
            
        Returns:
            None if valid, error message if invalid
        """
        if self.requires_context and input_data.context is None:
            return f"Plugin '{self.name}' requires context but none provided"
        
        for dep in self.context_dependencies:
            if input_data.context is None:
                return f"Plugin '{self.name}' requires context.{dep} but context is None"
            if not hasattr(input_data.context, dep):
                return f"Plugin '{self.name}' requires context.{dep} but it's not available"
        
        return None
