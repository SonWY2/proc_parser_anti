"""
플러그인 베이스 클래스

모든 병합 플러그인이 상속해야 하는 베이스 클래스.
"""

from abc import ABC
from enum import Enum
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import ExtractedMethod


class PluginPhase(str, Enum):
    """플러그인 실행 시점."""
    PRE_MERGE = "pre_merge"    # 코드 조립 전 (메소드 리스트 처리)
    POST_MERGE = "post_merge"  # 코드 조립 후 (최종 코드 처리)
    BOTH = "both"              # 둘 다


class PluginTarget(str, Enum):
    """플러그인 처리 대상."""
    METHOD = "method"  # 개별 메소드 단위
    CODE = "code"      # 전체 코드 단위


class MergePlugin(ABC):
    """병합 플러그인 베이스 클래스.
    
    모든 플러그인은 이 클래스를 상속하고 다음 메소드 중 하나 이상을 구현:
    - process(): 단일 메소드 처리 (phase=PRE_MERGE, target=METHOD)
    - process_all(): 메소드 리스트 처리 (phase=PRE_MERGE, target=METHOD)
    - process_code(): 최종 병합 코드 처리 (phase=POST_MERGE, target=CODE)
    
    Attributes:
        name: 플러그인 이름 (유니크해야 함)
        priority: 실행 우선순위 (낮을수록 먼저 실행, 기본값 100)
        description: 플러그인 설명
        phase: 실행 시점 (PRE_MERGE, POST_MERGE, BOTH)
        target: 처리 대상 (METHOD, CODE)
    """
    
    name: str = "base"
    priority: int = 100
    description: str = ""
    phase: PluginPhase = PluginPhase.PRE_MERGE
    target: PluginTarget = PluginTarget.METHOD
    
    def process(self, method: 'ExtractedMethod') -> 'ExtractedMethod':
        """단일 메소드 후처리.
        
        기본 구현은 메소드를 그대로 반환.
        개별 메소드 수정이 필요한 플러그인은 이 메소드를 오버라이드.
        
        Args:
            method: 추출된 메소드
            
        Returns:
            처리된 메소드
        """
        return method
    
    def process_all(self, methods: List['ExtractedMethod']) -> List['ExtractedMethod']:
        """메소드 리스트 전체 후처리.
        
        기본 구현은 각 메소드에 process()를 적용.
        메소드 간 관계를 고려해야 하는 플러그인(예: 중복 제거)은 이 메소드를 오버라이드.
        
        Args:
            methods: 추출된 메소드 리스트
            
        Returns:
            처리된 메소드 리스트
        """
        return [self.process(m) for m in methods]
    
    def process_code(self, code: str) -> str:
        """최종 병합 코드 후처리.
        
        기본 구현은 코드를 그대로 반환.
        스켈레톤 + 메소드 전체를 고려해야 하는 플러그인은 이 메소드를 오버라이드.
        
        Args:
            code: 병합된 전체 Java 코드
            
        Returns:
            처리된 코드
        """
        return code
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name}, phase={self.phase.value}, target={self.target.value}, priority={self.priority})>"
