"""
Name Transform Plugin Interface

이름 변환 플러그인을 위한 추상 인터페이스입니다.
Prefix 제거, snake_case → camelCase 변환 등의 기능을 플러그인으로 구현합니다.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


@dataclass
class TransformationResult:
    """이름 변환 결과"""
    name: str                                  # 변환된 이름
    transformations: List[str] = field(default_factory=list)  # 적용된 변환 규칙


class NameTransformPlugin(ABC):
    """
    이름 변환 플러그인 추상 베이스 클래스
    
    변수명의 변환 규칙을 플러그인으로 정의합니다.
    예: Prefix 제거, snake_case → camelCase 변환 등
    """
    
    @abstractmethod
    def name(self) -> str:
        """플러그인 고유 이름 반환"""
        pass
    
    @abstractmethod
    def description(self) -> str:
        """플러그인 설명 반환"""
        pass
    
    @abstractmethod
    def transform(self, name: str) -> TransformationResult:
        """
        이름 변환 수행
        
        Args:
            name: 변환할 이름
            
        Returns:
            TransformationResult: 변환 결과 (변환된 이름 및 적용된 변환 규칙)
        """
        pass
