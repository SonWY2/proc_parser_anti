"""
Pro*C to Java 변환기 핵심 로직

Main Logic으로서 전체 변환 파이프라인을 오케스트레이션합니다.
Plugin을 통해 각 단계를 확장할 수 있습니다.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from .types import (
    ConversionConfig,
    ConversionResult,
    SkeletonResult,
    FunctionConversionResult,
    FieldInfo,
    MethodSignature,
    PromptContext,
    ConversionStage,
)
from .prompt_builder import PromptBuilder
from .plugin_interface import ConversionPlugin


class ProcToJavaConverter:
    """
    Pro*C to Java 변환기 (Main Logic)
    
    2단계 변환 프로세스를 수행합니다:
        1. Skeleton 생성: 클래스 구조 (패키지, 임포트, 필드, 메서드 시그니처)
        2. Function 변환: 각 함수를 Java 메서드로 변환
    
    Plugin을 통해 각 단계에서 확장 가능합니다.
    
    사용 예:
        from validation.llm import LLMClient
        
        llm_client = LLMClient()
        converter = ProcToJavaConverter(llm_client, config)
        converter.register_plugin(NamingConventionPlugin())
        
        result = converter.convert(metadata)
        print(result.full_java_code)
    """
    
    def __init__(
        self, 
        llm_client: Any, 
        config: Optional[ConversionConfig] = None
    ):
        """
        Args:
            llm_client: LLM API 클라이언트 (validation.llm.LLMClient)
            config: 변환 설정 (None이면 기본값 사용)
        """
        self.llm_client = llm_client
        self.config = config or ConversionConfig()
        self.prompt_builder = PromptBuilder(self.config)
        self.plugins: List[ConversionPlugin] = []
    
    def register_plugin(self, plugin: ConversionPlugin) -> None:
        """
        플러그인 등록
        
        Args:
            plugin: 등록할 플러그인 인스턴스
        """
        self.plugins.append(plugin)
    
    def convert(
        self, 
        metadata: Dict[str, Any],
        functions_to_convert: Optional[List[str]] = None,
    ) -> ConversionResult:
        """
        전체 변환 수행
        
        Args:
            metadata: UnifiedMetadataGenerator에서 생성된 메타데이터
            functions_to_convert: 변환할 함수 이름 리스트 (None이면 전체)
            
        Returns:
            변환 결과 (스켈레톤 + 함수들)
        """
        source_file = metadata.get("metadata", {}).get("source_file", "unknown")
        
        # 1. 스켈레톤 생성
        skeleton = self.convert_skeleton(metadata)
        
        # 2. 함수 변환
        source_analysis = metadata.get("source_analysis", {})
        elements = source_analysis.get("elements_by_type", {})
        all_functions = elements.get("functions", [])
        
        # 변환할 함수 필터링
        if functions_to_convert:
            target_functions = [
                f for f in all_functions 
                if f.get("name") in functions_to_convert
            ]
        else:
            target_functions = all_functions
        
        # 컨텍스트 생성
        context = PromptContext(
            source_file=source_file,
            metadata=metadata,
            config=self.config,
            skeleton_result=skeleton,
        )
        
        # 각 함수 변환
        function_results = []
        errors = []
        skipped = []
        
        for func_data in target_functions:
            try:
                func_result = self.convert_function(func_data, context)
                function_results.append(func_result)
                context.previous_functions.append(func_result)
            except Exception as e:
                func_name = func_data.get("name", "unknown")
                errors.append(f"Error converting {func_name}: {str(e)}")
                skipped.append(func_name)
        
        # 최종 Java 코드 조합
        full_code = self._combine_results(skeleton, function_results)
        
        # 결과 생성
        result = ConversionResult(
            skeleton=skeleton,
            functions=function_results,
            full_java_code=full_code,
            total_functions=len(target_functions),
            converted_functions=len(function_results),
            skipped_functions=skipped,
            errors=errors,
        )
        
        return result
    
    def convert_skeleton(self, metadata: Dict[str, Any]) -> SkeletonResult:
        """
        클래스 스켈레톤만 변환
        
        Args:
            metadata: 메타데이터
            
        Returns:
            스켈레톤 결과
        """
        # Plugin pre-hook
        processed_metadata = metadata
        for plugin in self.plugins:
            processed_metadata = plugin.pre_skeleton(processed_metadata, self.config)
        
        # 프롬프트 생성
        prompt = self.prompt_builder.build_skeleton_prompt(processed_metadata)
        
        # Plugin prompt modification
        context = PromptContext(
            source_file=metadata.get("metadata", {}).get("source_file", ""),
            metadata=processed_metadata,
            config=self.config,
        )
        for plugin in self.plugins:
            prompt = plugin.modify_skeleton_prompt(prompt, context)
        
        # LLM 호출
        java_code = self._call_llm(prompt)
        
        # 결과 파싱 및 생성
        source_file = metadata.get("metadata", {}).get("source_file", "unknown")
        class_name = self.prompt_builder._derive_class_name(source_file)
        
        result = SkeletonResult(
            class_name=class_name,
            package_name=self.config.package_name,
            java_code=java_code,
            source_file=source_file,
            generated_at=datetime.now().isoformat(),
        )
        
        # 메타데이터에서 필드/메서드 정보 추출
        result.fields = self._extract_fields(metadata)
        result.method_signatures = self._extract_method_signatures(metadata)
        
        # Plugin post-hook
        for plugin in self.plugins:
            result = plugin.post_skeleton(result, self.config)
        
        return result
    
    def convert_function(
        self, 
        function_data: Dict[str, Any], 
        context: PromptContext
    ) -> FunctionConversionResult:
        """
        개별 함수 변환
        
        Args:
            function_data: 함수 메타데이터
            context: 변환 컨텍스트
            
        Returns:
            함수 변환 결과
        """
        func_name = function_data.get("name", "unknown")
        
        # Plugin pre-hook
        processed_func = function_data
        for plugin in self.plugins:
            processed_func = plugin.pre_function(processed_func, context)
        
        # 프롬프트 생성
        prompt = self.prompt_builder.build_function_prompt(processed_func, context)
        
        # Plugin prompt modification
        for plugin in self.plugins:
            prompt = plugin.modify_function_prompt(prompt, context)
        
        # LLM 호출
        java_code = self._call_llm(prompt)
        
        # 결과 생성
        java_method_name = self.prompt_builder._to_camel_case(func_name)
        
        result = FunctionConversionResult(
            original_name=func_name,
            java_method_name=java_method_name,
            java_code=java_code,
        )
        
        # Plugin post-hook
        for plugin in self.plugins:
            result = plugin.post_function(result, self.config)
        
        return result
    
    def convert_skeleton_only(self, metadata: Dict[str, Any]) -> SkeletonResult:
        """
        스켈레톤만 생성 (함수 변환 없음)
        
        Args:
            metadata: 메타데이터
            
        Returns:
            스켈레톤 결과
        """
        return self.convert_skeleton(metadata)
    
    def convert_single_function(
        self, 
        metadata: Dict[str, Any], 
        function_name: str,
        skeleton: Optional[SkeletonResult] = None,
    ) -> FunctionConversionResult:
        """
        단일 함수만 변환
        
        Args:
            metadata: 메타데이터
            function_name: 변환할 함수 이름
            skeleton: 이미 생성된 스켈레톤 (None이면 새로 생성)
            
        Returns:
            함수 변환 결과
        """
        if skeleton is None:
            skeleton = self.convert_skeleton(metadata)
        
        # 함수 찾기
        source_analysis = metadata.get("source_analysis", {})
        elements = source_analysis.get("elements_by_type", {})
        functions = elements.get("functions", [])
        
        target_func = None
        for func in functions:
            if func.get("name") == function_name:
                target_func = func
                break
        
        if target_func is None:
            raise ValueError(f"Function '{function_name}' not found in metadata")
        
        # 컨텍스트 생성
        context = PromptContext(
            source_file=metadata.get("metadata", {}).get("source_file", ""),
            metadata=metadata,
            config=self.config,
            skeleton_result=skeleton,
        )
        
        return self.convert_function(target_func, context)
    
    def _call_llm(self, prompt: str) -> str:
        """
        LLM API 호출
        
        Args:
            prompt: 프롬프트
            
        Returns:
            LLM 응답 텍스트
        """
        system_prompt = self.prompt_builder.get_system_prompt()
        
        # LLMClient의 인터페이스에 맞춰 호출
        # 참고: validation/llm/llm_client.py의 verify 메서드와 유사한 방식
        try:
            # 직접 API 호출 (LLMClient가 chat completions를 지원한다고 가정)
            response = self._make_llm_request(system_prompt, prompt)
            return self._extract_code_from_response(response)
        except Exception as e:
            # 에러 시 빈 문자열 반환 (실제 구현에서는 적절히 처리)
            return f"// Error: {str(e)}"
    
    def _make_llm_request(self, system_prompt: str, user_prompt: str) -> str:
        """LLM API 요청 실행"""
        import requests
        
        # LLM 클라이언트 설정 확인
        if not self.llm_client.is_configured:
            return "// LLM not configured"
        
        headers = self.llm_client._get_headers()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        # o1 모델 확인
        if hasattr(self.llm_client, '_is_o1_model') and self.llm_client._is_o1_model():
            # o1 모델은 system 역할 지원 안함
            messages = [
                {"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}
            ]
        
        payload = {
            "model": self.llm_client.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        
        response = requests.post(
            f"{self.llm_client.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            return f"// API Error: {response.status_code}"
    
    def _extract_code_from_response(self, response: str) -> str:
        """LLM 응답에서 코드 블록 추출"""
        # 코드 블록 마커 제거
        if "```java" in response:
            start = response.find("```java") + 7
            end = response.find("```", start)
            if end > start:
                return response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            if end > start:
                return response[start:end].strip()
        
        return response.strip()
    
    def _extract_fields(self, metadata: Dict[str, Any]) -> List[FieldInfo]:
        """메타데이터에서 필드 정보 추출"""
        fields = []
        source_analysis = metadata.get("source_analysis", {})
        elements = source_analysis.get("elements_by_type", {})
        variables = elements.get("variables", [])
        
        for var in variables:
            if var.get("function") is None:  # 전역 변수만
                c_type = var.get("var_type", "unknown")
                java_type = self._c_to_java_type(c_type)
                
                fields.append(FieldInfo(
                    name=self._to_camel_case(var.get("name", "")),
                    java_type=java_type,
                    original_c_type=c_type,
                    is_host_variable=var.get("is_host_variable", False),
                ))
        
        return fields
    
    def _extract_method_signatures(self, metadata: Dict[str, Any]) -> List[MethodSignature]:
        """메타데이터에서 메서드 시그니처 추출"""
        signatures = []
        source_analysis = metadata.get("source_analysis", {})
        elements = source_analysis.get("elements_by_type", {})
        prototypes = elements.get("function_prototypes", [])
        
        for proto in prototypes:
            name = proto.get("name", "")
            signatures.append(MethodSignature(
                name=name,
                java_name=self._to_camel_case(name),
                return_type=self._c_to_java_type(proto.get("return_type", "int")),
                parameters=proto.get("parameters", []),
                original_prototype=proto.get("raw_content", ""),
                is_private=proto.get("storage_class") == "static",
            ))
        
        return signatures
    
    def _combine_results(
        self, 
        skeleton: SkeletonResult, 
        functions: List[FunctionConversionResult]
    ) -> str:
        """스켈레톤과 함수 결과를 하나의 Java 파일로 조합"""
        
        # 플러그인의 finalize 확인
        for plugin in self.plugins:
            final_code = plugin.finalize(skeleton, functions, self.config)
            if final_code:
                return final_code
        
        # 기본 조합 로직
        if not skeleton.java_code:
            return ""
        
        # 스켈레톤 코드에서 클래스 닫는 괄호 찾기
        code = skeleton.java_code.rstrip()
        if code.endswith("}"):
            # 마지막 } 앞에 함수들 삽입
            insert_pos = code.rfind("}")
            
            method_code = "\n\n".join(
                f.java_code for f in functions if f.java_code
            )
            
            if method_code:
                return code[:insert_pos] + "\n\n" + method_code + "\n" + code[insert_pos:]
        
        return code
    
    def _c_to_java_type(self, c_type: str) -> str:
        """C 타입을 Java 타입으로 변환"""
        type_mapping = {
            "int": "int",
            "long": "long",
            "float": "float",
            "double": "double",
            "char": "String",
            "short": "short",
            "void": "void",
        }
        
        # 포인터 및 배열 처리
        base_type = c_type.split()[0].replace("*", "").strip()
        
        if "char" in c_type and ("[" in c_type or "*" in c_type):
            return "String"
        
        return type_mapping.get(base_type, "Object")
    
    def _to_camel_case(self, name: str) -> str:
        """snake_case → camelCase 변환"""
        if not name:
            return name
        components = name.split('_')
        return components[0].lower() + ''.join(x.title() for x in components[1:])
