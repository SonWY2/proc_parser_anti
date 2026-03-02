"""
메인 ParsingVerifier 클래스

검증 파이프라인을 관리하고 플러그인을 통해 검증을 수행합니다.
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
import json

from .types import (
    VerificationType,
    VerificationStatus,
    VerificationInput,
    VerificationResult,
    VerificationContext,
    MacroInfo,
)
from .plugin_interface import VerifierPlugin


class ParsingVerifier:
    """파싱 결과 검증기
    
    플러그인 시스템을 통해 다양한 검증을 수행합니다.
    매크로 정보는 컨텍스트를 통해 모든 검증 단계에서 공유됩니다.
    
    Example:
        verifier = ParsingVerifier()
        
        # 컨텍스트 생성 (매크로 정보 포함)
        context = verifier.build_context(
            source_file="test.sqc",
            macros_data=[{"name": "MAX_SIZE", "value": "256", ...}]
        )
        
        # 매크로 검증 (가장 먼저 수행 - 컨텍스트에 매크로 정보 추가)
        macro_result = verifier.verify_macro(
            original_source=source_code,
            analysis_result=macros_data,
            context=context
        )
        
        # 변수 검증 (매크로 정보를 컨텍스트에서 참조)
        var_result = verifier.verify_variable(
            original_declarations=declarations,
            analysis_result=variables_data,
            context=context  # 매크로 정보 포함
        )
    """
    
    def __init__(self, enabled_plugins: Optional[List[str]] = None):
        """
        Args:
            enabled_plugins: 활성화할 플러그인 이름들 (None이면 전체)
        """
        self.enabled_plugins = enabled_plugins
        self._plugins: Dict[str, VerifierPlugin] = {}
        self._load_plugins()
    
    def _load_plugins(self) -> None:
        """플러그인 로드"""
        from .plugins import get_all_plugins
        
        all_plugins = get_all_plugins()
        
        for plugin in all_plugins:
            if self.enabled_plugins is None or plugin.name in self.enabled_plugins:
                self._plugins[plugin.verification_type] = plugin
    
    def build_context(
        self,
        source_file: str = "",
        extracted_file: str = "",
        macros_data: Optional[List[Dict[str, Any]]] = None,
        headers_data: Optional[List[Dict[str, Any]]] = None,
        variables_data: Optional[List[Dict[str, Any]]] = None,
        functions_data: Optional[List[Dict[str, Any]]] = None,
        sql_data: Optional[List[Dict[str, Any]]] = None,
    ) -> VerificationContext:
        """검증 컨텍스트 생성
        
        Args:
            source_file: 원본 소스 파일 경로
            extracted_file: 추출된 코드 파일 경로
            macros_data: 매크로 분석 결과
            headers_data: 헤더 분석 결과
            variables_data: 변수 분석 결과
            functions_data: 함수 분석 결과
            sql_data: SQL 분석 결과
            
        Returns:
            VerificationContext: 검증 컨텍스트
        """
        context = VerificationContext(
            source_file=source_file,
            extracted_file=extracted_file,
        )
        
        # 매크로 정보 구성
        if macros_data:
            for macro in macros_data:
                macro_info = MacroInfo(
                    name=macro.get("name", ""),
                    value=macro.get("value"),
                    params=macro.get("params"),
                    is_constant=macro.get("params") is None,
                    used_in_functions=macro.get("used_in_functions", []),
                )
                context.macros[macro_info.name] = macro_info
        
        # 다른 분석 결과 저장
        if headers_data:
            context.headers = headers_data
        if variables_data:
            context.variables = variables_data
        if functions_data:
            context.functions = functions_data
        if sql_data:
            context.sql_statements = sql_data
        
        return context
    
    def load_context_from_directory(self, output_dir: str) -> VerificationContext:
        """출력 디렉토리에서 컨텍스트 로드
        
        Args:
            output_dir: 파싱 출력 디렉토리 (*.jsonl 파일들이 있는 곳)
            
        Returns:
            VerificationContext: 로드된 컨텍스트
        """
        output_path = Path(output_dir)
        
        def load_jsonl(filename: str) -> List[Dict[str, Any]]:
            filepath = output_path / filename
            if not filepath.exists():
                return []
            
            results = []
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        results.append(json.loads(line))
            return results
        
        return self.build_context(
            macros_data=load_jsonl("macros.jsonl"),
            headers_data=load_jsonl("headers.jsonl"),
            variables_data=load_jsonl("variables.jsonl"),
            functions_data=load_jsonl("functions.jsonl"),
            sql_data=load_jsonl("sql.jsonl"),
        )
    
    def verify_macro(
        self,
        original_source: str,
        analysis_result: List[Dict[str, Any]],
        context: Optional[VerificationContext] = None,
    ) -> VerificationResult:
        """매크로 정의 검증
        
        Args:
            original_source: 원본 소스 코드
            analysis_result: 매크로 분석 결과 (macros.jsonl 내용)
            context: 검증 컨텍스트
            
        Returns:
            VerificationResult: 검증 결과
        """
        return self._run_verification(
            verification_type=VerificationType.MACRO,
            original_source=original_source,
            analysis_result=analysis_result,
            context=context,
        )
    
    def verify_header(
        self,
        original_source: str,
        analysis_result: List[Dict[str, Any]],
        context: Optional[VerificationContext] = None,
    ) -> VerificationResult:
        """헤더 선언부 검증
        
        Args:
            original_source: 원본 소스 코드 (헤더 부분)
            analysis_result: 헤더 분석 결과 (headers.jsonl, includes.jsonl 내용)
            context: 검증 컨텍스트
            
        Returns:
            VerificationResult: 검증 결과
        """
        return self._run_verification(
            verification_type=VerificationType.HEADER,
            original_source=original_source,
            analysis_result=analysis_result,
            context=context,
        )
    
    def verify_variable(
        self,
        original_source: str,
        analysis_result: List[Dict[str, Any]],
        context: Optional[VerificationContext] = None,
    ) -> VerificationResult:
        """변수 선언 검증
        
        Args:
            original_source: 원본 소스 코드 (변수 선언 부분)
            analysis_result: 변수 분석 결과 (variables.jsonl 내용)
            context: 검증 컨텍스트 (매크로 정보 필요)
            
        Returns:
            VerificationResult: 검증 결과
        """
        return self._run_verification(
            verification_type=VerificationType.VARIABLE,
            original_source=original_source,
            analysis_result=analysis_result,
            context=context,
        )
    
    def verify_sql_extraction(
        self,
        extracted_code: str,
        analysis_result: Dict[str, Any],
        context: Optional[VerificationContext] = None,
    ) -> VerificationResult:
        """SQL 추출 검증
        
        Args:
            extracted_code: SQL이 주석으로 대체된 코드 (_extracted.c)
            analysis_result: {
                "local_variables": List[Dict],  # 로컬 변수 목록
                "sql_ids": List[str],           # 추출된 SQL ID 목록
                "functions": List[Dict],        # 함수 정보
            }
            context: 검증 컨텍스트
            
        Returns:
            VerificationResult: 검증 결과
        """
        return self._run_verification(
            verification_type=VerificationType.SQL_EXTRACTION,
            original_source=extracted_code,
            analysis_result=analysis_result,
            context=context,
        )
    
    def verify_sql_metadata(
        self,
        sql_content: str,
        analysis_result: Dict[str, Any],
        context: Optional[VerificationContext] = None,
    ) -> VerificationResult:
        """단일 SQL 메타데이터 검증
        
        Args:
            sql_content: 원본 SQL 구문
            analysis_result: SQL 분석 결과 (sql.jsonl의 개별 엔트리)
            context: 검증 컨텍스트
            
        Returns:
            VerificationResult: 검증 결과
        """
        return self._run_verification(
            verification_type=VerificationType.SQL_METADATA,
            original_source=sql_content,
            analysis_result=analysis_result,
            context=context,
        )
    
    def verify_function_sql_metadata(
        self,
        function_name: str,
        sql_list: List[Dict[str, Any]],
        context: Optional[VerificationContext] = None,
    ) -> VerificationResult:
        """함수 내 여러 SQL 메타데이터 일괄 검증
        
        하나의 함수 안에 있는 여러 SQL을 한번에 검증합니다.
        
        Args:
            function_name: 함수 이름
            sql_list: 해당 함수의 SQL 분석 결과 리스트
                [
                    {"sql_id": "sql_001", "raw_content": "...", "input_host_vars": [...], ...},
                    {"sql_id": "sql_002", "raw_content": "...", "input_host_vars": [...], ...},
                ]
            context: 검증 컨텍스트
            
        Returns:
            VerificationResult: 통합 검증 결과
        """
        all_issues = []
        passed_count = 0
        
        for sql_metadata in sql_list:
            sql_content = sql_metadata.get("raw_content", "")
            result = self.verify_sql_metadata(
                sql_content=sql_content,
                analysis_result=sql_metadata,
                context=context,
            )
            all_issues.extend(result.issues)
            if not result.has_errors():
                passed_count += 1
        
        total_items = len(sql_list)
        error_count = len([i for i in all_issues if i.severity == "error"])
        
        if any(i.severity == "error" for i in all_issues):
            status = VerificationStatus.FAIL
        elif any(i.severity == "warning" for i in all_issues):
            status = VerificationStatus.WARNING
        else:
            status = VerificationStatus.PASS
        
        return VerificationResult(
            verification_type=VerificationType.SQL_METADATA,
            status=status,
            total_items=total_items,
            passed_items=passed_count,
            failed_items=total_items - passed_count,
            issues=all_issues,
            details={
                "function": function_name,
                "sql_count": total_items,
            },
        )

    
    def verify_all(
        self,
        original_source: str,
        extracted_code: str,
        output_dir: str,
    ) -> Dict[str, VerificationResult]:
        """전체 검증 수행
        
        검증 순서:
        1. Macro (컨텍스트에 매크로 정보 추가)
        2. Header
        3. Variable (매크로 정보 사용)
        4. SQL Extraction
        5. SQL Metadata
        
        Args:
            original_source: 원본 소스 코드
            extracted_code: 추출된 코드
            output_dir: 분석 결과 디렉토리
            
        Returns:
            Dict[str, VerificationResult]: 검증 유형별 결과
        """
        # 컨텍스트 로드
        context = self.load_context_from_directory(output_dir)
        context.source_file = "source"
        context.extracted_file = "extracted"
        
        results: Dict[str, VerificationResult] = {}
        
        # 1. 매크로 검증 (가장 먼저 - 컨텍스트 업데이트)
        if context.macros or self._get_macros_from_source(original_source):
            macro_result = self.verify_macro(
                original_source=original_source,
                analysis_result=list(m.__dict__ for m in context.macros.values()) if context.macros else [],
                context=context,
            )
            results["macro"] = macro_result
            context.verification_results["macro"] = macro_result
        
        # 2. 헤더 검증
        if context.headers:
            header_result = self.verify_header(
                original_source=original_source,
                analysis_result=context.headers,
                context=context,
            )
            results["header"] = header_result
            context.verification_results["header"] = header_result
        
        # 3. 변수 검증 (매크로 정보 컨텍스트에서 사용)
        if context.variables:
            variable_result = self.verify_variable(
                original_source=original_source,
                analysis_result=context.variables,
                context=context,
            )
            results["variable"] = variable_result
            context.verification_results["variable"] = variable_result
        
        # 4. SQL 추출 검증
        if context.sql_statements:
            sql_extraction_result = self.verify_sql_extraction(
                extracted_code=extracted_code,
                analysis_result={
                    "sql_ids": [s.get("sql_id") for s in context.sql_statements],
                    "functions": context.functions,
                    "local_variables": [v for v in context.variables if v.get("scope") == "local"],
                },
                context=context,
            )
            results["sql_extraction"] = sql_extraction_result
            context.verification_results["sql_extraction"] = sql_extraction_result
        
        # 5. SQL 메타데이터 검증 (각 SQL에 대해)
        sql_metadata_issues = []
        for sql_stmt in context.sql_statements:
            sql_result = self.verify_sql_metadata(
                sql_content=sql_stmt.get("raw_content", ""),
                analysis_result=sql_stmt,
                context=context,
            )
            sql_metadata_issues.extend(sql_result.issues)
        
        if context.sql_statements:
            combined_sql_result = VerificationResult(
                verification_type=VerificationType.SQL_METADATA,
                status=VerificationStatus.FAIL if any(i.severity == "error" for i in sql_metadata_issues) else VerificationStatus.PASS,
                total_items=len(context.sql_statements),
                passed_items=len(context.sql_statements) - len([i for i in sql_metadata_issues if i.severity == "error"]),
                failed_items=len([i for i in sql_metadata_issues if i.severity == "error"]),
                issues=sql_metadata_issues,
            )
            results["sql_metadata"] = combined_sql_result
            context.verification_results["sql_metadata"] = combined_sql_result
        
        return results
    
    def _run_verification(
        self,
        verification_type: VerificationType,
        original_source: str,
        analysis_result: Any,
        context: Optional[VerificationContext] = None,
    ) -> VerificationResult:
        """검증 실행"""
        plugin = self._plugins.get(verification_type.value)
        
        if plugin is None:
            return VerificationResult(
                verification_type=verification_type,
                status=VerificationStatus.SKIPPED,
                details={"reason": f"No plugin found for {verification_type.value}"},
            )
        
        input_data = VerificationInput(
            verification_type=verification_type,
            original_source=original_source,
            analysis_result=analysis_result,
            context=context,
        )
        
        # 입력 유효성 검사
        validation_error = plugin.validate_input(input_data)
        if validation_error:
            return VerificationResult(
                verification_type=verification_type,
                status=VerificationStatus.SKIPPED,
                details={"reason": validation_error},
            )
        
        # 검증 수행
        result = plugin.verify(input_data)
        
        # 컨텍스트 업데이트 (매크로 등)
        if context:
            plugin.update_context(context, result)
        
        return result
    
    def _get_macros_from_source(self, source: str) -> List[str]:
        """소스에서 매크로 정의 추출 (간단한 정규식)"""
        import re
        pattern = r'#define\s+(\w+)'
        return re.findall(pattern, source)
    
    def get_available_verification_types(self) -> List[str]:
        """사용 가능한 검증 유형 목록"""
        return list(self._plugins.keys())
    
    def print_summary(self, results: Dict[str, VerificationResult]) -> None:
        """결과 요약 출력"""
        print("\n" + "=" * 60)
        print("Verification Summary")
        print("=" * 60)
        
        for vtype, result in results.items():
            print(result.summary())
        
        total_errors = sum(len(r.get_errors()) for r in results.values())
        total_warnings = sum(len(r.get_warnings()) for r in results.values())
        
        print("-" * 60)
        if total_errors == 0:
            print(f"✅ All verifications passed! ({total_warnings} warnings)")
        else:
            print(f"❌ {total_errors} errors, {total_warnings} warnings found")
        print("=" * 60 + "\n")
