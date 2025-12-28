"""
SQL 관계 플러그인 기본 클래스

SQL 요소 간의 관계를 감지하는 플러그인의 추상 인터페이스입니다.
"""

from typing import List, Dict, Optional
from abc import ABC, abstractmethod


class SQLRelationshipPlugin(ABC):
    """
    SQL 관계 감지 플러그인을 위한 기본 클래스입니다.
    
    SQL 관계 플러그인은 SQL 요소 목록을 분석하여 논리적 그룹화 및 종속성을 식별합니다.
    이는 Pro*C 패턴을 MyBatis와 같은 최신 프레임워크로 변환하는 데 유용합니다.
    """
    
    @abstractmethod
    def can_handle(self, sql_elements: List[Dict]) -> bool:
        """
        이 플러그인이 SQL 요소 중 일부를 처리할 수 있는지 확인합니다.
        
        Args:
            sql_elements: 파서에서 추출한 SQL 요소 딕셔너리 목록
            
        Returns:
            처리할 수 있는 패턴이 감지되면 True
        """
        pass
    
    @abstractmethod
    def extract_relationships(self, sql_elements: List[Dict], all_elements: List[Dict] = None) -> List[Dict]:
        """
        SQL 요소에서 관계를 추출합니다.
        
        Args:
            sql_elements: SQL 요소 딕셔너리 목록
            all_elements: 모든 파싱된 요소 (C 코드 포함)
                
        Returns:
            관계 딕셔너리 목록
        """
        pass
    
    def _generate_relationship_id(self, relationship_type: str, identifier: str, counter: int) -> str:
        """고유한 관계 ID를 생성하는 헬퍼 메서드입니다."""
        return f"{relationship_type.lower()}_{identifier}_{counter:03d}"
