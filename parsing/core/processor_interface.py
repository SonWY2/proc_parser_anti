"""
메타데이터 프로세서 인터페이스

UnifiedMetadataGenerator에서 사용하는 프로세서들의 기본 인터페이스를 정의합니다.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class MetadataProcessor(ABC):
    """
    메타데이터 처리를 위한 추상 기본 클래스입니다.
    
    각 프로세서는 특정 처리 단계를 담당하며,
    context 딕셔너리를 받아 처리 결과를 반환합니다.
    """
    
    @abstractmethod
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        컨텍스트를 받아 처리 결과를 반환합니다.
        
        Args:
            context: 처리에 필요한 입력 데이터 딕셔너리
            
        Returns:
            처리 결과 딕셔너리
        """
        pass
