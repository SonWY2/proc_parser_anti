"""
Skill 기본 인터페이스

모든 Skill은 이 인터페이스를 구현해야 합니다.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field


@dataclass
class SkillResult:
    """Skill 실행 결과"""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "errors": self.errors,
        }


class BaseSkill(ABC):
    """
    Skill 기본 인터페이스
    
    모든 Skill은 이 클래스를 상속받아 구현합니다.
    Subagent에서 동적으로 호출됩니다.
    
    Example:
        class ParseProcCodeSkill(BaseSkill):
            @property
            def name(self) -> str:
                return "parse_proc_code"
            
            def invoke(self, source_code: str) -> SkillResult:
                # 파싱 로직
                return SkillResult(success=True, data={"ast": ...})
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Skill 이름 (고유 식별자)"""
        pass
    
    @property
    def description(self) -> str:
        """Skill 설명 (옵션)"""
        return ""
    
    @abstractmethod
    def invoke(self, input_data: Any) -> SkillResult:
        """
        Skill 실행
        
        Args:
            input_data: 입력 데이터 (Skill마다 다름)
            
        Returns:
            SkillResult: 실행 결과
        """
        pass
    
    def validate_input(self, input_data: Any) -> Optional[str]:
        """
        입력 데이터 검증 (옵션)
        
        Args:
            input_data: 검증할 입력 데이터
            
        Returns:
            None이면 유효, 문자열이면 에러 메시지
        """
        return None


class MockSkill(BaseSkill):
    """
    Mock Skill 기본 구현
    
    테스트나 개발 중 실제 Skill 대신 사용합니다.
    """
    
    def __init__(self, skill_name: str, mock_response: Dict[str, Any] = None):
        self._name = skill_name
        self._mock_response = mock_response or {}
    
    @property
    def name(self) -> str:
        return self._name
    
    def invoke(self, input_data: Any) -> SkillResult:
        return SkillResult(
            success=True,
            data=self._mock_response,
        )
