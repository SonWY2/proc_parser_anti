"""
파서 플러그인 인터페이스를 정의하는 모듈입니다.
ParserPlugin: 사용자 정의 구문이나 프로젝트별 문법을 파싱하기 위한 플러그인 기본 클래스
SQLRelationshipPlugin: SQL 관계 감지 플러그인 기본 클래스
"""
import re
from typing import List, Dict, Optional
from abc import ABC, abstractmethod


class ParserPlugin(ABC):
    """
    Pro*C 파서 플러그인을 위한 추상 기본 클래스입니다.
    사용자 정의 구문이나 프로젝트별 문법을 파싱하는 데 사용됩니다.
    """
    
    @property
    @abstractmethod
    def pattern(self):
        """
        매칭할 정규식 패턴입니다.
        컴파일된 정규식 객체 또는 문자열이어야 합니다.
        """
        pass
    
    @property
    @abstractmethod
    def element_type(self):
        """
        추출된 요소의 'type' 문자열입니다 (예: 'bam_call').
        """
        pass

    @abstractmethod
    def parse(self, match, content):
        """
        정규식 매치 객체에서 데이터를 추출합니다.
        
        Args:
            match: 정규식 매치 객체.
            content: 파일의 전체 내용 (라인 수 계산에 유용).
            
        Returns:
            dict: 추출된 데이터를 포함하는 딕셔너리.
                  'type', 'line_start', 'line_end', 'raw_content'를 반드시 포함해야 합니다.
        """
        pass

    def get_line_range(self, match, content):
        """
        매치 객체로부터 시작 라인과 끝 라인을 계산하는 헬퍼 메서드입니다.
        """
        start_index = match.start()
        end_index = match.end()
        
        line_start = content.count('\n', 0, start_index) + 1
        line_end = content.count('\n', 0, end_index) + 1
        
        return line_start, line_end
    
    def get_marker(self, element: Dict) -> Optional[str]:
        """
        디버그 파일 생성 시 사용할 마커 주석을 반환합니다.
        
        Args:
            element: parse() 메서드가 반환한 요소 딕셔너리
            
        Returns:
            주석 문자열 (예: "/* @BAMCALL_EXTRACTED: args */")
            None을 반환하면 디버그 파일에서 이 요소를 마커로 치환하지 않습니다.
        """
        return None  # 기본값: 마커 생성 안함


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


class ElementEnricherPlugin(ABC):
    """
    추출된 요소를 후처리하여 추가 정보를 삽입하는 플러그인 기본 클래스입니다.
    
    이 플러그인은 파싱이 완료된 후 실행되며, 개별 요소에 메타데이터를 추가하거나
    요소의 내용을 보강하는 데 사용됩니다.
    """
    
    @abstractmethod
    def can_handle(self, element: Dict) -> bool:
        """
        이 플러그인이 주어진 요소를 처리할 수 있는지 확인합니다.
        
        Args:
            element: 파서에서 추출한 요소 딕셔너리
            
        Returns:
            처리할 수 있으면 True
        """
        pass
    
    @abstractmethod
    def enrich(self, element: Dict, all_elements: List[Dict], content: str) -> Dict:
        """
        요소에 추가 정보를 삽입합니다.
        
        Args:
            element: 보강할 요소 딕셔너리
            all_elements: 모든 추출된 요소 목록 (참조용)
            content: 원본 파일 내용
            
        Returns:
            보강된 요소 딕셔너리 (원본을 수정하거나 새 객체 반환)
        """
        pass

