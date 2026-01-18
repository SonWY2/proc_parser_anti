"""
헤더 파서 플러그인 인터페이스

헤더 파일을 파싱하는 플러그인이 구현해야 할 표준 인터페이스를 정의합니다.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass, field


class HeaderFormatType(Enum):
    """지원하는 헤더 포맷 타입"""
    STP = "stp"              # STP 배열 포맷
    TYPEDEF = "typedef"      # typedef struct 포맷
    MACRO = "macro"          # #define 매크로
    # 향후 확장 가능:
    # PROTOBUF = "protobuf"
    # JSON_SCHEMA = "json_schema"
    # XML_SCHEMA = "xml_schema"


@dataclass
class ParseContext:
    """파싱 컨텍스트 - 플러그인 간 데이터 공유용"""
    macros: Dict[str, Any] = field(default_factory=dict)
    structs: Dict[str, Any] = field(default_factory=dict)
    db_vars_info: Dict[str, Any] = field(default_factory=dict)
    stp_data: Dict[str, Any] = field(default_factory=dict)
    source_file: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "macros": self.macros,
            "structs": self.structs,
            "db_vars_info": self.db_vars_info,
            "stp_data": self.stp_data,
            "source_file": self.source_file,
        }


class HeaderParserPlugin(ABC):
    """
    헤더 파서 플러그인 추상 기본 클래스
    
    모든 헤더 파서 플러그인은 이 인터페이스를 구현해야 합니다.
    
    사용 예:
        class MyCustomPlugin(HeaderParserPlugin):
            @property
            def format_type(self) -> HeaderFormatType:
                return HeaderFormatType.CUSTOM
            
            @property
            def priority(self) -> int:
                return 50
            
            def can_parse(self, content: str) -> bool:
                return "my_custom_marker" in content
            
            def parse(self, content: str, context: ParseContext) -> Dict[str, Any]:
                # 파싱 로직 구현
                return {"custom_data": {...}}
    """
    
    @property
    @abstractmethod
    def format_type(self) -> HeaderFormatType:
        """
        이 플러그인이 처리하는 포맷 타입
        
        Returns:
            HeaderFormatType: 플러그인이 담당하는 헤더 포맷 타입
        """
        pass
    
    @property
    @abstractmethod
    def priority(self) -> int:
        """
        실행 우선순위 (낮을수록 먼저 실행)
        
        권장 우선순위 범위:
        - 1-10: 매크로 추출 (다른 플러그인이 의존)
        - 11-20: 구조체 파싱
        - 21-30: STP/메타데이터 파싱
        - 31+: 후처리/변환
        
        Returns:
            int: 우선순위 값
        """
        pass
    
    @property
    def name(self) -> str:
        """플러그인 이름 (기본: 클래스명)"""
        return self.__class__.__name__
    
    @abstractmethod
    def can_parse(self, content: str) -> bool:
        """
        이 플러그인이 해당 콘텐츠를 파싱할 수 있는지 확인
        
        Args:
            content: 헤더 파일 내용
            
        Returns:
            bool: 파싱 가능 여부
        """
        pass
    
    @abstractmethod
    def parse(self, content: str, context: Optional[ParseContext] = None) -> Dict[str, Any]:
        """
        콘텐츠 파싱 수행
        
        Args:
            content: 헤더 파일 내용
            context: 이전 플러그인들의 결과가 담긴 컨텍스트
            
        Returns:
            파싱 결과 딕셔너리. 결과는 context에 병합됩니다.
            반환 키 예시:
            - "macros": 매크로 딕셔너리
            - "structs": 구조체 정보
            - "stp_data": STP 데이터
            - "db_vars_info": 변수 정보
        """
        pass
    
    def __repr__(self) -> str:
        return f"<{self.name}(type={self.format_type.value}, priority={self.priority})>"
