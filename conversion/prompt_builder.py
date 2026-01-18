"""
프롬프트 빌더

메타데이터 JSON을 LLM 프롬프트로 변환합니다.
"""

import json
from typing import Dict, Any, List, Optional
from pathlib import Path

from .types import (
    ConversionConfig,
    PromptContext,
    SkeletonResult,
    FieldInfo,
    MethodSignature,
)


class PromptBuilder:
    """
    LLM 프롬프트 생성기
    
    메타데이터에서 스켈레톤/함수 변환용 프롬프트를 생성합니다.
    
    사용 예:
        builder = PromptBuilder(config)
        skeleton_prompt = builder.build_skeleton_prompt(metadata)
        function_prompt = builder.build_function_prompt(func_data, context)
    """
    
    def __init__(self, config: ConversionConfig):
        """
        Args:
            config: 변환 설정
        """
        self.config = config
        self.templates_dir = Path(__file__).parent / "templates"
    
    def build_skeleton_prompt(self, metadata: Dict[str, Any]) -> str:
        """
        클래스 스켈레톤 생성용 프롬프트 작성
        
        Args:
            metadata: UnifiedMetadataGenerator에서 생성된 메타데이터
            
        Returns:
            LLM에 전달할 프롬프트 문자열
        """
        source_file = metadata.get("metadata", {}).get("source_file", "unknown")
        source_analysis = metadata.get("source_analysis", {})
        elements = source_analysis.get("elements_by_type", {})
        
        # 전역 변수 추출
        variables = elements.get("variables", [])
        global_vars = [v for v in variables if v.get("function") is None]
        
        # 함수 프로토타입 추출
        prototypes = elements.get("function_prototypes", [])
        
        # 함수 목록 추출
        functions = elements.get("functions", [])
        
        # SQL 정보 추출
        sql_statements = elements.get("sql", [])
        
        # 헤더 정보
        header_tree = metadata.get("header_tree", {})
        
        prompt = self._build_skeleton_prompt_text(
            source_file=source_file,
            global_vars=global_vars,
            prototypes=prototypes,
            functions=functions,
            sql_statements=sql_statements,
            header_tree=header_tree,
        )
        
        return prompt
    
    def _build_skeleton_prompt_text(
        self,
        source_file: str,
        global_vars: List[Dict],
        prototypes: List[Dict],
        functions: List[Dict],
        sql_statements: List[Dict],
        header_tree: Dict,
    ) -> str:
        """스켈레톤 프롬프트 텍스트 생성"""
        
        # 클래스명 추론
        class_name = self._derive_class_name(source_file)
        
        lines = []
        lines.append("## Task: Pro*C to Java Class Skeleton Conversion\n")
        lines.append(f"Convert the following Pro*C source file structure to a Java class.\n")
        lines.append(f"### Source File: `{source_file}`")
        lines.append(f"### Target Class: `{self.config.package_name}.{class_name}`\n")
        
        # 설정 정보
        lines.append("### Conversion Settings:")
        lines.append(f"- Package: `{self.config.package_name}`")
        lines.append(f"- Use Spring Annotations: {self.config.use_spring_annotations}")
        lines.append(f"- MyBatis Mapper Package: `{self.config.mybatis_mapper_package}`")
        lines.append("")
        
        # 전역 변수 → 클래스 필드
        lines.append("### Global Variables (→ Class Fields):")
        if global_vars:
            lines.append("```c")
            for var in global_vars[:20]:  # 최대 20개
                var_type = var.get("var_type", "unknown")
                var_name = var.get("name", "unknown")
                lines.append(f"{var_type} {var_name};")
            if len(global_vars) > 20:
                lines.append(f"// ... and {len(global_vars) - 20} more variables")
            lines.append("```")
        else:
            lines.append("(No global variables)")
        lines.append("")
        
        # 함수 프로토타입 → 메서드 시그니처
        lines.append("### Function Prototypes (→ Method Signatures):")
        if prototypes:
            lines.append("```c")
            for proto in prototypes:
                lines.append(proto.get("raw_content", ""))
            lines.append("```")
        elif functions:
            lines.append("```c")
            for func in functions:
                name = func.get("name", "unknown")
                lines.append(f"// {name}")
            lines.append("```")
        else:
            lines.append("(No function prototypes)")
        lines.append("")
        
        # SQL 정보
        lines.append("### SQL Operations (→ MyBatis Mapper Dependencies):")
        if sql_statements:
            sql_types = {}
            for sql in sql_statements:
                sql_type = sql.get("sql_type", "UNKNOWN")
                sql_types[sql_type] = sql_types.get(sql_type, 0) + 1
            
            for sql_type, count in sql_types.items():
                lines.append(f"- {sql_type}: {count} statements")
        else:
            lines.append("(No SQL statements)")
        lines.append("")
        
        # 헤더 의존성
        lines.append("### Header Dependencies:")
        direct_includes = header_tree.get("direct_includes", [])
        if direct_includes:
            for inc in direct_includes:
                lines.append(f"- {inc.get('header_name', 'unknown')}")
        else:
            lines.append("(No external headers)")
        lines.append("")
        
        # 생성 요청
        lines.append("### Required Output:")
        lines.append("Generate a Java class skeleton with:")
        lines.append("1. Proper package declaration")
        lines.append("2. Required imports (Spring, MyBatis, etc.)")
        lines.append("3. Class-level annotations (@Service, @Slf4j if applicable)")
        lines.append("4. Private fields from global variables (with proper Java types)")
        lines.append("5. Method signatures only (no implementations, just method stubs)")
        lines.append("6. Constructor with dependency injection")
        lines.append("")
        lines.append("Output only the Java code, no explanations.")
        
        return "\n".join(lines)
    
    def build_function_prompt(
        self, 
        function_data: Dict[str, Any], 
        context: PromptContext
    ) -> str:
        """
        개별 함수 변환용 프롬프트 작성
        
        Args:
            function_data: 변환할 함수 메타데이터
            context: 변환 컨텍스트 (스켈레톤 결과 등)
            
        Returns:
            LLM에 전달할 프롬프트 문자열
        """
        func_name = function_data.get("name", "unknown")
        raw_content = function_data.get("raw_content", "")
        docstring = function_data.get("docstring", "")
        
        # 함수 내 SQL 추출
        source_analysis = context.metadata.get("source_analysis", {})
        elements = source_analysis.get("elements_by_type", {})
        all_sql = elements.get("sql", [])
        func_sql = [s for s in all_sql if s.get("function") == func_name]
        
        # 함수 내 변수 추출
        all_vars = elements.get("variables", [])
        func_vars = [v for v in all_vars if v.get("function") == func_name]
        
        # 함수 호출 추출
        all_calls = elements.get("function_calls", [])
        func_calls = [c for c in all_calls if c.get("function") == func_name]
        
        prompt = self._build_function_prompt_text(
            func_name=func_name,
            raw_content=raw_content,
            docstring=docstring,
            func_sql=func_sql,
            func_vars=func_vars,
            func_calls=func_calls,
            context=context,
        )
        
        return prompt
    
    def _build_function_prompt_text(
        self,
        func_name: str,
        raw_content: str,
        docstring: str,
        func_sql: List[Dict],
        func_vars: List[Dict],
        func_calls: List[Dict],
        context: PromptContext,
    ) -> str:
        """함수 변환 프롬프트 텍스트 생성"""
        
        java_method_name = self._to_camel_case(func_name)
        
        lines = []
        lines.append("## Task: Pro*C Function to Java Method Conversion\n")
        lines.append(f"Convert the following Pro*C function to a Java method.\n")
        lines.append(f"### Function: `{func_name}` → `{java_method_name}`\n")
        
        # 원본 주석
        if docstring:
            lines.append("### Original Documentation:")
            lines.append("```")
            lines.append(docstring)
            lines.append("```\n")
        
        # 원본 함수 코드
        lines.append("### Original Pro*C Code:")
        lines.append("```c")
        lines.append(raw_content)
        lines.append("```\n")
        
        # SQL 문
        if func_sql:
            lines.append("### SQL Statements in this function:")
            for i, sql in enumerate(func_sql, 1):
                sql_type = sql.get("sql_type", "UNKNOWN")
                sql_content = sql.get("raw_content", "")
                lines.append(f"#### SQL #{i} ({sql_type}):")
                lines.append("```sql")
                lines.append(sql_content[:500])  # 최대 500자
                if len(sql_content) > 500:
                    lines.append("... (truncated)")
                lines.append("```")
            lines.append("")
        
        # 로컬 변수
        if func_vars:
            lines.append("### Local Variables:")
            for var in func_vars[:10]:
                var_type = var.get("var_type", "unknown")
                var_name = var.get("name", "unknown")
                lines.append(f"- `{var_type} {var_name}`")
            if len(func_vars) > 10:
                lines.append(f"- ... and {len(func_vars) - 10} more")
            lines.append("")
        
        # 호출하는 함수들
        if func_calls:
            unique_calls = list(set(c.get("name", "") for c in func_calls))
            lines.append("### Called Functions:")
            for call in unique_calls[:15]:
                lines.append(f"- `{call}`")
            lines.append("")
        
        # 컨텍스트 (스켈레톤에서 이미 생성된 필드들)
        if context.skeleton_result:
            lines.append("### Available Class Fields (from skeleton):")
            for field in context.skeleton_result.fields[:10]:
                lines.append(f"- `{field.java_type} {field.name}`")
            lines.append("")
        
        # 변환 지침
        lines.append("### Conversion Instructions:")
        lines.append("1. Convert C types to Java types")
        lines.append("2. Replace embedded SQL with MyBatis mapper method calls")
        lines.append("3. Convert BAM calls to appropriate Spring service calls")
        lines.append("4. Handle SQLCODE checks with try-catch or return values")
        lines.append("5. Use SLF4J logging instead of ELOG/ILOG macros")
        lines.append("6. Keep business logic intact")
        lines.append("")
        lines.append("Output only the Java method code, no explanations.")
        
        return "\n".join(lines)
    
    def _derive_class_name(self, source_file: str) -> str:
        """소스 파일명에서 Java 클래스명 추론"""
        # 파일명에서 확장자 제거
        name = Path(source_file).stem
        
        # snake_case → PascalCase
        parts = name.split('_')
        class_name = ''.join(p.title() for p in parts)
        
        # 접미사 추가
        if self.config.class_name_suffix and not class_name.endswith(self.config.class_name_suffix):
            class_name += self.config.class_name_suffix
        
        return class_name
    
    def _to_camel_case(self, name: str) -> str:
        """snake_case → camelCase 변환"""
        components = name.split('_')
        return components[0].lower() + ''.join(x.title() for x in components[1:])
    
    def get_system_prompt(self) -> str:
        """시스템 프롬프트 반환"""
        return """You are an expert Pro*C to Java converter.
You specialize in converting Oracle Pro*C/ESQL code to modern Java with Spring and MyBatis.

Key conversion rules:
- Pro*C host variables → Java fields or local variables
- EXEC SQL statements → MyBatis mapper method calls
- BAM/BAMCALL macros → Spring service method calls
- SQLCODE/SQLMSG → Exception handling or return codes
- C types → Java types (char[N] → String, long → Long, etc.)
- ELOG/ILOG macros → SLF4J logger calls

Always generate clean, idiomatic Java code following best practices."""
