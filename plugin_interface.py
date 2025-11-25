"""
파서 플러그인 인터페이스를 정의하는 모듈입니다.
사용자 정의 구문이나 프로젝트별 문법을 파싱하기 위한 플러그인의 기본 클래스를 제공합니다.
"""
import re
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
