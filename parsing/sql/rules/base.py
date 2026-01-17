"""
규칙 기본 클래스 모듈

SQL 타입 결정 및 호스트 변수 추출 규칙의 기본 인터페이스를 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
import re


@dataclass
class RuleMatch:
    """규칙 매칭 결과
    
    Attributes:
        matched: 매칭 성공 여부
        value: 매칭된 값 (예: SQL 타입 이름)
        confidence: 매칭 신뢰도 (0.0 ~ 1.0)
        metadata: 추가 메타데이터 (예: DB2의 isolation level)
    """
    matched: bool
    value: Any = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SQLTypeRule(ABC):
    """SQL 타입 결정 규칙 기본 클래스
    
    새로운 SQL 타입을 추가하려면:
    1. 이 클래스를 상속
    2. name, priority, pattern 속성 정의
    3. match() 메서드 구현 (선택적, 기본은 pattern 매칭)
    4. SQLTypeRegistry에 등록
    
    Example:
        class MergeRule(SQLTypeRule):
            name = "merge"
            priority = 50
            pattern = re.compile(r'EXEC\\s+SQL\\s+MERGE', re.IGNORECASE)
        
        registry.register(MergeRule())
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """규칙 이름 (예: 'select', 'insert')
        
        이 값이 SQL 타입으로 반환됩니다.
        """
        pass
    
    @property
    @abstractmethod
    def priority(self) -> int:
        """우선순위 (높을수록 먼저 검사)
        
        권장 범위:
        - 100: 최우선 (INCLUDE, DECLARE SECTION)
        - 90: 커서 관련 (DECLARE CURSOR)
        - 80: 커서 작업 (OPEN, CLOSE, FETCH)
        - 60: 트랜잭션 (COMMIT, ROLLBACK)
        - 50: DML (SELECT, INSERT, UPDATE, DELETE)
        - 40: 기타
        """
        pass
    
    @property
    @abstractmethod
    def pattern(self) -> re.Pattern:
        """매칭 패턴 (정규식)
        
        기본 match() 구현에서 사용됩니다.
        """
        pass
    
    def match(self, sql_text: str) -> RuleMatch:
        """SQL 텍스트에 규칙 적용
        
        기본 구현은 pattern을 사용합니다.
        복잡한 로직이 필요하면 오버라이드하세요.
        
        Args:
            sql_text: EXEC SQL 구문 전체 텍스트
        
        Returns:
            RuleMatch: 매칭 결과
        """
        if self.pattern.search(sql_text):
            return RuleMatch(matched=True, value=self.name)
        return RuleMatch(matched=False)


class HostVariableRule(ABC):
    """호스트 변수 추출 규칙 기본 클래스
    
    새로운 호스트 변수 패턴을 추가하려면:
    1. 이 클래스를 상속
    2. name, pattern 속성 정의
    3. extract() 메서드 구현
    4. HostVariableRegistry에 등록
    
    Example:
        class CustomVarRule(HostVariableRule):
            name = "custom"
            pattern = re.compile(r':@(\\w+)')
            
            def extract(self, match):
                return {'type': self.name, 'var_name': match.group(1)}
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """규칙 이름 (예: 'basic', 'array', 'indicator')"""
        pass
    
    @property
    @abstractmethod
    def pattern(self) -> re.Pattern:
        """매칭 패턴
        
        호스트 변수를 찾기 위한 정규식입니다.
        그룹을 사용하여 변수 정보를 캡처하세요.
        """
        pass
    
    @abstractmethod
    def extract(self, match: re.Match) -> Dict[str, Any]:
        """매칭에서 호스트 변수 정보 추출
        
        Args:
            match: 정규식 매칭 결과
        
        Returns:
            호스트 변수 정보 딕셔너리:
            - type: 변수 타입 (규칙 이름)
            - var_name: 변수명
            - indicator: 인디케이터 (있는 경우)
            - field_name: 필드명 (구조체인 경우)
            - index: 인덱스 (배열인 경우)
        """
        pass
