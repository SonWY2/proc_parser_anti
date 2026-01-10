from abc import ABC, abstractmethod
import re
from typing import List, Optional


class NamingConventionPlugin(ABC):
    """
    네이밍 컨벤션 플러그인을 위한 추상 기본 클래스입니다.
    호스트 변수 이름을 대상 형식(예: snake_case에서 camelCase)으로 변환하는 데 사용됩니다.
    """
    
    @abstractmethod
    def convert(self, name: str) -> str:
        """
        변수 이름을 대상 컨벤션으로 변환합니다.
        
        Args:
            name: 원래 변수 이름 (예: "my_var").
            
        Returns:
            변환된 이름 (예: "myVar").
        """
        pass


class SnakeToCamelPlugin(NamingConventionPlugin):
    """
    snake_case를 camelCase로 변환합니다.
    예: user_id -> userId, my_long_var -> myLongVar
    """
    
    def convert(self, name: str) -> str:
        # 선행 콜론이 있으면 제거 (대개 없이 전달되지만 안전을 위해)
        clean_name = name.lstrip(':')
        
        components = clean_name.split('_')
        if not components:
            return name
            
        # 첫 번째 요소를 제외한 각 요소의 첫 글자를 대문자로 변환하고
        # 'title' 메서드를 사용하여 결합합니다.
        return components[0] + ''.join(x.title() for x in components[1:])


class HostVariableNamingPlugin(NamingConventionPlugin):
    """
    호스트 변수명 변환 플러그인
    
    Pro*C 호스트 변수에서 흔히 사용되는 prefix를 제거하고 camelCase로 변환합니다.
    
    Args:
        prefixes: 제거할 prefix 리스트 (기본: ['H_', 'H_o', 'H_i', 'W_'])
        remove_prefix: prefix 제거 여부 (기본: True)
        to_camel_case: camelCase 변환 여부 (기본: True)
    
    Example:
        plugin = HostVariableNamingPlugin()
        
        plugin.convert("H_user_id")       # -> "userId"
        plugin.convert("H_o_result_code") # -> "resultCode"
        plugin.convert("H_i_input_param") # -> "inputParam"
        plugin.convert("W_work_buffer")   # -> "workBuffer"
    """
    
    # 기본 prefix 목록 (순서 중요: 더 긴 것 먼저)
    DEFAULT_PREFIXES = ['H_o_', 'H_i_', 'H_', 'W_']
    
    def __init__(self, 
                 prefixes: Optional[List[str]] = None,
                 remove_prefix: bool = True,
                 to_camel_case: bool = True):
        self._prefixes = prefixes if prefixes is not None else self.DEFAULT_PREFIXES.copy()
        self._remove_prefix = remove_prefix
        self._to_camel_case = to_camel_case
        
        # prefix를 길이 역순으로 정렬 (더 긴 것 먼저 매칭)
        self._prefixes.sort(key=len, reverse=True)
    
    @property
    def prefixes(self) -> List[str]:
        """현재 설정된 prefix 목록"""
        return self._prefixes.copy()
    
    def add_prefix(self, prefix: str) -> None:
        """prefix 추가"""
        if prefix not in self._prefixes:
            self._prefixes.append(prefix)
            self._prefixes.sort(key=len, reverse=True)
    
    def remove_prefix_from_list(self, prefix: str) -> None:
        """prefix 목록에서 제거"""
        if prefix in self._prefixes:
            self._prefixes.remove(prefix)
    
    def convert(self, name: str) -> str:
        """
        변수 이름을 변환합니다.
        
        1. 선행 콜론 제거
        2. prefix 제거 (설정된 경우)
        3. snake_case -> camelCase 변환 (설정된 경우)
        
        Args:
            name: 원래 변수 이름 (예: "H_user_id", ":H_o_result")
            
        Returns:
            변환된 이름 (예: "userId", "result")
        """
        # 선행 콜론 제거
        clean_name = name.lstrip(':')
        
        # prefix 제거
        if self._remove_prefix:
            clean_name = self._remove_known_prefix(clean_name)
        
        # camelCase 변환
        if self._to_camel_case:
            clean_name = self._snake_to_camel(clean_name)
        
        return clean_name
    
    def _remove_known_prefix(self, name: str) -> str:
        """알려진 prefix 제거"""
        for prefix in self._prefixes:
            if name.startswith(prefix):
                return name[len(prefix):]
        return name
    
    def _snake_to_camel(self, name: str) -> str:
        """snake_case를 camelCase로 변환"""
        components = name.split('_')
        if not components:
            return name
        
        # 첫 번째 요소는 소문자, 나머지는 첫 글자 대문자
        result = components[0].lower()
        for comp in components[1:]:
            if comp:  # 빈 문자열 건너뜀 (연속된 언더스코어 처리)
                result += comp.title()
        
        return result
    
    def convert_variable_list(self, variables: List[str]) -> List[str]:
        """변수 목록 일괄 변환"""
        return [self.convert(var) for var in variables]


# 편의 함수
def convert_host_variable(name: str, 
                         prefixes: Optional[List[str]] = None) -> str:
    """
    호스트 변수명 변환 편의 함수
    
    Args:
        name: 변환할 변수명
        prefixes: 제거할 prefix 목록 (None이면 기본값 사용)
        
    Returns:
        변환된 변수명
        
    Example:
        convert_host_variable("H_user_id")  # -> "userId"
        convert_host_variable(":H_o_result_code")  # -> "resultCode"
    """
    plugin = HostVariableNamingPlugin(prefixes=prefixes)
    return plugin.convert(name)
