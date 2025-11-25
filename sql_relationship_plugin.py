"""
SQL 관계 플러그인 인터페이스

이 모듈은 SQL 관계 플러그인의 기본 인터페이스를 제공합니다.
각 플러그인은 SQL 요소를 분석하여 여러 SQL 문 간의 논리적 관계
(예: 커서 작업, 동적 SQL, 트랜잭션)를 감지하고 추출합니다.
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
            sql_elements: SQL 요소 딕셔너리 목록, 각 요소는 다음을 포함:
                - sql_id: 고유 식별자
                - sql_type: SQL 문 유형 (SELECT, INSERT 등)
                - normalized_sql: 정규화된 SQL 텍스트
                - input_host_vars: 입력 호스트 변수 목록
                - output_host_vars: 출력 호스트 변수 목록
                - function: 이 SQL을 포함하는 함수 이름
                - line_start, line_end: 소스 위치
                
        Returns:
            관계 딕셔너리 목록, 각 관계는 다음을 포함:
                - relationship_id: 이 관계의 고유 식별자
                - relationship_type: 유형 (CURSOR, DYNAMIC_SQL, TRANSACTION 등)
                - sql_ids: 이 관계에 포함된 sql_id 값 목록
                - metadata: 관계별 메타데이터 딕셔너리
        """
        pass
    
    def _generate_relationship_id(self, relationship_type: str, identifier: str, counter: int) -> str:
        """
        고유한 관계 ID를 생성하는 헬퍼 메서드입니다.
        
        Args:
            relationship_type: 관계 유형 (cursor, dynamic_sql 등)
            identifier: 식별 이름 (커서 이름, 문 이름 등)
            counter: 이 유형에 대한 고유 카운터
            
        Returns:
            포맷된 관계 ID (예: "cursor_emp_cursor_001")
        """
        return f"{relationship_type.lower()}_{identifier}_{counter:03d}"
