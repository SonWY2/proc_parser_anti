"""
호스트 변수 추출 규칙 모듈

Pro*C SQL에서 호스트 변수 패턴을 추출하는 규칙들을 정의합니다.
규칙 순서가 중요합니다 (복잡한 패턴이 먼저 검사되어야 함).
"""

import re
from typing import Dict, Any
from .base import HostVariableRule


class StructIndicatorRule(HostVariableRule):
    """:struct.field:indicator 패턴
    
    예: :user.name:ind_name
    """
    
    @property
    def name(self) -> str:
        return "struct_indicator"
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(r':(\w+)\.(\w+):(\w+)')
    
    def extract(self, match: re.Match) -> Dict[str, Any]:
        return {
            'type': self.name,
            'var_name': match.group(1),
            'field_name': match.group(2),
            'indicator': match.group(3)
        }


class ArrayIndicatorRule(HostVariableRule):
    """:array[idx]:indicator 패턴
    
    예: :values[i]:ind_values
    """
    
    @property
    def name(self) -> str:
        return "array_indicator"
    
    @property
    def pattern(self) -> re.Pattern:
        return re.compile(r':(\w+)\[([^\]]+)\]:(\w+)')
    
    def extract(self, match: re.Match) -> Dict[str, Any]:
        return {
            'type': self.name,
            'var_name': match.group(1),
            'index': match.group(2),
            'indicator': match.group(3)
        }


class ArrayRule(HostVariableRule):
    """:array[idx] 패턴
    
    예: :values[i], :arr[0]
    """
    
    @property
    def name(self) -> str:
        return "array"
    
    @property
    def pattern(self) -> re.Pattern:
        # 뒤에 :가 없어야 함 (인디케이터와 구분)
        return re.compile(r':(\w+)\[([^\]]+)\](?!:)')
    
    def extract(self, match: re.Match) -> Dict[str, Any]:
        return {
            'type': self.name,
            'var_name': match.group(1),
            'index': match.group(2)
        }


class StructRule(HostVariableRule):
    """:struct.field 패턴
    
    예: :user.name, :record.id
    """
    
    @property
    def name(self) -> str:
        return "struct"
    
    @property
    def pattern(self) -> re.Pattern:
        # 뒤에 :가 없어야 함 (인디케이터와 구분)
        return re.compile(r':(\w+)\.(\w+)(?!:)')
    
    def extract(self, match: re.Match) -> Dict[str, Any]:
        return {
            'type': self.name,
            'var_name': match.group(1),
            'field_name': match.group(2)
        }


class IndicatorRule(HostVariableRule):
    """:var:indicator 패턴
    
    예: :value:ind_value
    """
    
    @property
    def name(self) -> str:
        return "indicator"
    
    @property
    def pattern(self) -> re.Pattern:
        # 앞에 .이나 ]가 없어야 함 (구조체/배열과 구분)
        return re.compile(r'(?<![.\]])(:(\w+):(\w+))')
    
    def extract(self, match: re.Match) -> Dict[str, Any]:
        return {
            'type': self.name,
            'var_name': match.group(2),
            'indicator': match.group(3)
        }


class BasicRule(HostVariableRule):
    """:var 기본 패턴
    
    예: :user_id, :name
    """
    
    @property
    def name(self) -> str:
        return "basic"
    
    @property
    def pattern(self) -> re.Pattern:
        # 뒤에 :, [, .이 없어야 함
        return re.compile(r':(\w+)(?![:\[.])')
    
    def extract(self, match: re.Match) -> Dict[str, Any]:
        return {
            'type': self.name,
            'var_name': match.group(1)
        }


# 기본 호스트 변수 규칙 목록
# 순서 중요: 복잡한 패턴이 먼저 검사되어야 함
DEFAULT_HOST_VARIABLE_RULES = [
    StructIndicatorRule(),  # :s.f:i
    ArrayIndicatorRule(),   # :a[x]:i
    ArrayRule(),            # :a[x]
    StructRule(),           # :s.f
    IndicatorRule(),        # :v:i
    BasicRule(),            # :v
]
