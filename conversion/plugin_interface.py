"""
변환 플러그인 인터페이스

Main Logic + Plugin 아키텍처에 따른 플러그인 인터페이스 정의.
플러그인은 변환 프로세스의 각 단계에서 개입하여 결과를 수정할 수 있습니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from .types import (
    SkeletonResult,
    FunctionConversionResult,
    ConversionConfig,
    PromptContext,
)


class ConversionPlugin(ABC):
    """
    변환 플러그인 추상 기본 클래스
    
    모든 변환 플러그인은 이 클래스를 상속받아야 합니다.
    각 hook 메서드는 선택적으로 구현할 수 있습니다.
    
    Hook 실행 순서:
        1. pre_skeleton → 스켈레톤 생성 전
        2. modify_skeleton_prompt → 스켈레톤 프롬프트 수정
        3. post_skeleton → 스켈레톤 생성 후
        4. pre_function → 각 함수 변환 전
        5. modify_function_prompt → 함수 프롬프트 수정
        6. post_function → 각 함수 변환 후
        7. finalize → 최종 결과 생성 전
    """
    
    @property
    def name(self) -> str:
        """플러그인 이름"""
        return self.__class__.__name__
    
    @property
    def description(self) -> str:
        """플러그인 설명"""
        return self.__doc__ or ""
    
    def pre_skeleton(self, metadata: Dict[str, Any], config: ConversionConfig) -> Dict[str, Any]:
        """
        스켈레톤 생성 전 메타데이터 수정
        
        Args:
            metadata: 원본 메타데이터
            config: 변환 설정
            
        Returns:
            수정된 메타데이터
        """
        return metadata
    
    def modify_skeleton_prompt(self, prompt: str, context: PromptContext) -> str:
        """
        스켈레톤 프롬프트 수정
        
        Args:
            prompt: 원본 프롬프트
            context: 프롬프트 컨텍스트
            
        Returns:
            수정된 프롬프트
        """
        return prompt
    
    def post_skeleton(self, result: SkeletonResult, config: ConversionConfig) -> SkeletonResult:
        """
        스켈레톤 생성 후 결과 수정
        
        Args:
            result: 스켈레톤 생성 결과
            config: 변환 설정
            
        Returns:
            수정된 스켈레톤 결과
        """
        return result
    
    def pre_function(
        self, 
        func_data: Dict[str, Any], 
        context: PromptContext
    ) -> Dict[str, Any]:
        """
        함수 변환 전 함수 데이터 수정
        
        Args:
            func_data: 함수 메타데이터
            context: 변환 컨텍스트
            
        Returns:
            수정된 함수 데이터
        """
        return func_data
    
    def modify_function_prompt(self, prompt: str, context: PromptContext) -> str:
        """
        함수 프롬프트 수정
        
        Args:
            prompt: 원본 프롬프트
            context: 프롬프트 컨텍스트
            
        Returns:
            수정된 프롬프트
        """
        return prompt
    
    def post_function(
        self, 
        result: FunctionConversionResult, 
        config: ConversionConfig
    ) -> FunctionConversionResult:
        """
        함수 변환 후 결과 수정
        
        Args:
            result: 함수 변환 결과
            config: 변환 설정
            
        Returns:
            수정된 함수 변환 결과
        """
        return result
    
    def finalize(
        self, 
        skeleton: SkeletonResult, 
        functions: list, 
        config: ConversionConfig
    ) -> str:
        """
        최종 Java 코드 생성
        
        기본 구현은 None을 반환하며, 이 경우 core.py에서 기본 조합을 수행합니다.
        
        Args:
            skeleton: 스켈레톤 결과
            functions: 함수 변환 결과 리스트
            config: 변환 설정
            
        Returns:
            최종 Java 코드 (None이면 기본 조합 사용)
        """
        return None


class NamingConventionPlugin(ConversionPlugin):
    """
    Java 네이밍 컨벤션 적용 플러그인 (예시)
    
    Pro*C의 snake_case 함수명을 Java의 camelCase로 변환합니다.
    """
    
    def _to_camel_case(self, name: str) -> str:
        """snake_case → camelCase 변환"""
        components = name.split('_')
        return components[0].lower() + ''.join(x.title() for x in components[1:])
    
    def post_skeleton(self, result: SkeletonResult, config: ConversionConfig) -> SkeletonResult:
        """메서드 시그니처의 이름을 camelCase로 변환"""
        for sig in result.method_signatures:
            sig.java_name = self._to_camel_case(sig.name)
        return result
    
    def post_function(
        self, 
        result: FunctionConversionResult, 
        config: ConversionConfig
    ) -> FunctionConversionResult:
        """변환된 함수명을 camelCase로 변환"""
        result.java_method_name = self._to_camel_case(result.original_name)
        return result
