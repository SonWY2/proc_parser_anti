"""
매크로 파서 플러그인

#define 매크로 상수를 추출하는 플러그인입니다.
다른 플러그인보다 먼저 실행되어 매크로 값을 컨텍스트에 제공합니다.
"""
import re
from typing import Dict, Any, Optional

from ..parser_interface import HeaderParserPlugin, HeaderFormatType, ParseContext


class MacroParserPlugin(HeaderParserPlugin):
    """
    매크로 추출 플러그인
    
    #define 문을 파싱하여 매크로 이름과 값을 추출합니다.
    우선순위가 가장 높아(5) 다른 플러그인에 매크로 값을 제공합니다.
    """
    
    # #define NAME VALUE 패턴 (단순 상수 매크로)
    DEFINE_PATTERN = re.compile(
        r'^\s*#\s*define\s+'
        r'(\w+)\s+'                   # 매크로 이름 + 공백
        r'([^\n]+)',                  # 값 (줄 끝까지)
        re.MULTILINE
    )
    
    # 함수형 매크로 패턴 (추출 제외 대상)
    FUNCTION_MACRO_PATTERN = re.compile(
        r'^\s*#\s*define\s+(\w+)\s*\([^)]*\)',
        re.MULTILINE
    )
    
    @property
    def format_type(self) -> HeaderFormatType:
        return HeaderFormatType.MACRO
    
    @property
    def priority(self) -> int:
        return 5  # 최우선 실행
    
    def can_parse(self, content: str) -> bool:
        return '#define' in content
    
    def parse(self, content: str, context: Optional[ParseContext] = None) -> Dict[str, Any]:
        """매크로 추출"""
        result = {}
        
        # 함수형 매크로 이름 수집 (제외 대상)
        function_macros = set(self.FUNCTION_MACRO_PATTERN.findall(content))
        
        for match in self.DEFINE_PATTERN.finditer(content):
            name = match.group(1)
            value_str = match.group(2).strip()
            
            # 함수형 매크로 제외
            if name in function_macros:
                continue
            
            # 빈 값 제외 (플래그 매크로)
            if not value_str:
                continue
            
            # 주석 제거
            value_str = self._remove_comments(value_str)
            if not value_str:
                continue
            
            # 값 파싱
            parsed_value = self._parse_value(value_str)
            if parsed_value is not None:
                result[name] = parsed_value
        
        return {"macros": result}
    
    def _remove_comments(self, value_str: str) -> str:
        """값에서 주석 제거"""
        # // 주석 제거
        if '//' in value_str:
            value_str = value_str.split('//')[0]
        # /* 주석 제거
        if '/*' in value_str:
            value_str = value_str.split('/*')[0]
        return value_str.strip()
    
    def _parse_value(self, value_str: str) -> Optional[Any]:
        """매크로 값 파싱"""
        value_str = value_str.strip()
        
        if not value_str:
            return None
        
        # 문자열 리터럴
        if value_str.startswith('"') and value_str.endswith('"'):
            return value_str[1:-1]
        
        # 문자 리터럴
        if value_str.startswith("'") and value_str.endswith("'"):
            return value_str[1:-1]
        
        # 16진수
        if value_str.startswith('0x') or value_str.startswith('0X'):
            try:
                return int(value_str, 16)
            except ValueError:
                return value_str
        
        # 정수
        try:
            # 접미사 제거 (L, U, LL 등)
            clean_value = re.sub(r'[LlUu]+$', '', value_str)
            return int(clean_value)
        except ValueError:
            pass
        
        # 부동소수점
        try:
            # 접미사 제거 (f, F 등)
            clean_value = re.sub(r'[fF]$', '', value_str)
            return float(clean_value)
        except ValueError:
            pass
        
        # 수식 평가 시도 (안전한 경우만)
        if self._is_safe_expression(value_str):
            try:
                return eval(value_str)
            except:
                pass
        
        # 그 외는 문자열로 반환
        return value_str
    
    def _is_safe_expression(self, expr: str) -> bool:
        """안전한 수식인지 확인 (eval 가능 여부)"""
        allowed = set('0123456789+-*/%() \t')
        return all(c in allowed for c in expr)
