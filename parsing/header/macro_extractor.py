"""
매크로 추출기
헤더 파일에서 #define 매크로 상수를 추출합니다.
"""
import re
import os
from typing import Dict, List, Any, Optional, Tuple


class MacroExtractor:
    """
    헤더 파일에서 매크로 상수 추출
    
    #define 문을 파싱하여 매크로 이름과 값을 추출합니다.
    숫자 상수와 문자열 상수를 지원합니다.
    
    사용 예:
        extractor = MacroExtractor()
        macros = extractor.extract_file("common.h")
        # {"MAX_SIZE": 30, "BUFFER_LEN": 256}
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
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def extract(self, content: str) -> Dict[str, Any]:
        """
        헤더 내용에서 매크로 추출
        
        Args:
            content: 헤더 파일 내용
            
        Returns:
            매크로 딕셔너리 {"NAME": value, ...}
        """
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
        
        return result
    
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
        """
        매크로 값 파싱
        
        Args:
            value_str: 값 문자열
            
        Returns:
            파싱된 값 (int, float, str) 또는 None
        """
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
        """
        안전한 수식인지 확인 (eval 가능 여부)
        
        숫자와 기본 연산자만 포함된 경우 안전
        """
        # 허용된 문자만 포함
        allowed = set('0123456789+-*/%() \t')
        return all(c in allowed for c in expr)
    
    def extract_file(self, file_path: str) -> Dict[str, Any]:
        """
        파일에서 매크로 추출
        
        Args:
            file_path: 헤더 파일 경로
            
        Returns:
            매크로 딕셔너리
        """
        abs_path = os.path.abspath(file_path)
        
        # 캐시 확인
        if abs_path in self._cache:
            return self._cache[abs_path]
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            macros = self.extract(content)
            self._cache[abs_path] = macros
            return macros
        except Exception as e:
            return {}
    
    def extract_from_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        여러 파일에서 매크로 추출 및 병합
        
        나중 파일이 이전 파일의 값을 덮어씁니다.
        
        Args:
            file_paths: 헤더 파일 경로 리스트
            
        Returns:
            병합된 매크로 딕셔너리
        """
        result = {}
        for path in file_paths:
            macros = self.extract_file(path)
            result.update(macros)
        return result
    
    def get_numeric_macros(self, macros: Dict[str, Any]) -> Dict[str, int]:
        """
        숫자 매크로만 필터링
        
        배열 크기 등에 사용되는 숫자 상수만 추출
        
        Args:
            macros: 전체 매크로 딕셔너리
            
        Returns:
            숫자 매크로만 포함된 딕셔너리
        """
        return {
            name: value
            for name, value in macros.items()
            if isinstance(value, (int, float))
        }
    
    def clear_cache(self):
        """캐시 초기화"""
        self._cache.clear()
