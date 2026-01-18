"""
네이밍 컨벤션 플러그인

Pro*C의 snake_case를 Java의 camelCase/PascalCase로 변환합니다.
"""

import re
from typing import Dict, Any

from ..plugin_interface import ConversionPlugin
from ..types import (
    ConversionConfig,
    SkeletonResult,
    FunctionConversionResult,
    PromptContext,
)


class NamingConventionPlugin(ConversionPlugin):
    """
    Java 네이밍 컨벤션 적용 플러그인
    
    - 함수명: snake_case → camelCase
    - 클래스명: snake_case → PascalCase
    - 변수명: 접두사 제거 및 camelCase 변환
    """
    
    # 제거할 변수 접두사
    PREFIXES_TO_REMOVE = ["H_", "p_", "s_", "g_"]
    
    def _to_camel_case(self, name: str) -> str:
        """snake_case → camelCase 변환"""
        # 접두사 제거
        for prefix in self.PREFIXES_TO_REMOVE:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
        
        components = name.split('_')
        return components[0].lower() + ''.join(x.title() for x in components[1:])
    
    def _to_pascal_case(self, name: str) -> str:
        """snake_case → PascalCase 변환"""
        components = name.split('_')
        return ''.join(x.title() for x in components)
    
    def post_skeleton(self, result: SkeletonResult, config: ConversionConfig) -> SkeletonResult:
        """메서드 시그니처와 필드명을 Java 컨벤션으로 변환"""
        
        # 메서드명 변환
        for sig in result.method_signatures:
            sig.java_name = self._to_camel_case(sig.name)
        
        # 필드명 변환
        for field in result.fields:
            field.name = self._to_camel_case(field.name)
        
        return result
    
    def post_function(
        self, 
        result: FunctionConversionResult, 
        config: ConversionConfig
    ) -> FunctionConversionResult:
        """변환된 함수명을 camelCase로 변환"""
        result.java_method_name = self._to_camel_case(result.original_name)
        return result
