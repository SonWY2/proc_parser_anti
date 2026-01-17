"""
정적 사전 검증 플러그인

수량 비교, 라인 범위, 필수 필드 등 코드 기반 빠른 검증.
"""

import re
from typing import List, Dict, Any

from .base import VerifierPlugin, PluginPhase
from . import register_plugin
from ..types import VerificationContext, CheckResult, CheckStatus, FeedbackSeverity


@register_plugin
class StaticPreCheckPlugin(VerifierPlugin):
    """정적 사전 검증 플러그인
    
    LLM 호출 전에 기본적인 정적 체크를 수행합니다.
    """
    
    name = "static_precheck"
    stage = "all"
    phase = PluginPhase.PRE_VERIFY
    priority = 10
    description = "정적 사전 검증 (수량, 라인 범위, 필수 필드)"
    
    def process(self, context: VerificationContext) -> VerificationContext:
        """정적 체크 수행"""
        
        if context.stage == "sql_extraction":
            context = self._check_sql_extraction(context)
        elif context.stage == "function_parsing":
            context = self._check_function_parsing(context)
        elif context.stage == "header_parsing":
            context = self._check_header_parsing(context)
        elif context.stage == "translation_merge":
            context = self._check_translation_merge(context)
        
        return context
    
    def _check_sql_extraction(self, context: VerificationContext) -> VerificationContext:
        """SQL 추출 정적 체크"""
        source = context.source
        result = context.result
        
        # EXEC SQL 개수 세기
        exec_sql_count = len(re.findall(r'EXEC\s+SQL', source, re.IGNORECASE))
        extracted_count = len(result) if isinstance(result, list) else 0
        
        # 수량 일치 체크
        if exec_sql_count == extracted_count:
            context.static_checks.append(CheckResult(
                check_id="count_match",
                name="SQL 수량 일치",
                status=CheckStatus.PASS,
                message=f"EXEC SQL {exec_sql_count}개 → 추출 {extracted_count}개",
                severity=FeedbackSeverity.INFO
            ))
        else:
            context.static_checks.append(CheckResult(
                check_id="count_match",
                name="SQL 수량 일치",
                status=CheckStatus.FAIL,
                message=f"EXEC SQL {exec_sql_count}개 vs 추출 {extracted_count}개 (차이: {abs(exec_sql_count - extracted_count)})",
                severity=FeedbackSeverity.ERROR
            ))
        
        # 라인 범위 유효성 체크
        if isinstance(result, list):
            invalid_lines = []
            for i, item in enumerate(result):
                if isinstance(item, dict):
                    start = item.get('line_start', 0)
                    end = item.get('line_end', 0)
                    if start > end or start < 1:
                        invalid_lines.append(i)
            
            if not invalid_lines:
                context.static_checks.append(CheckResult(
                    check_id="line_range_valid",
                    name="라인 범위 유효성",
                    status=CheckStatus.PASS,
                    message="모든 라인 범위가 유효함",
                    severity=FeedbackSeverity.INFO
                ))
            else:
                context.static_checks.append(CheckResult(
                    check_id="line_range_valid",
                    name="라인 범위 유효성",
                    status=CheckStatus.FAIL,
                    message=f"유효하지 않은 라인 범위: 인덱스 {invalid_lines}",
                    severity=FeedbackSeverity.ERROR
                ))
        
        return context
    
    def _check_function_parsing(self, context: VerificationContext) -> VerificationContext:
        """함수 파싱 정적 체크"""
        result = context.result
        
        if isinstance(result, list):
            # 필수 필드 체크
            missing_fields = []
            required = ['name', 'line_start', 'line_end']
            
            for i, item in enumerate(result):
                if isinstance(item, dict):
                    for field in required:
                        if field not in item:
                            missing_fields.append(f"[{i}].{field}")
            
            if not missing_fields:
                context.static_checks.append(CheckResult(
                    check_id="required_fields",
                    name="필수 필드 존재",
                    status=CheckStatus.PASS,
                    message="모든 필수 필드 존재",
                    severity=FeedbackSeverity.INFO
                ))
            else:
                context.static_checks.append(CheckResult(
                    check_id="required_fields",
                    name="필수 필드 존재",
                    status=CheckStatus.FAIL,
                    message=f"누락된 필드: {missing_fields[:5]}{'...' if len(missing_fields) > 5 else ''}",
                    severity=FeedbackSeverity.ERROR
                ))
        
        return context
    
    def _check_header_parsing(self, context: VerificationContext) -> VerificationContext:
        """헤더 파싱 정적 체크"""
        result = context.result
        
        if isinstance(result, dict):
            context.static_checks.append(CheckResult(
                check_id="struct_count",
                name="구조체 추출 수",
                status=CheckStatus.PASS,
                message=f"{len(result)}개 구조체 추출됨",
                severity=FeedbackSeverity.INFO
            ))
        
        return context
    
    def _check_translation_merge(self, context: VerificationContext) -> VerificationContext:
        """번역 병합 정적 체크"""
        result = context.result
        
        if isinstance(result, str):
            # Java 코드 기본 구문 체크
            has_class = 'class ' in result
            has_package = 'package ' in result
            
            if has_class:
                context.static_checks.append(CheckResult(
                    check_id="java_class_exists",
                    name="Java 클래스 존재",
                    status=CheckStatus.PASS,
                    message="클래스 정의 발견",
                    severity=FeedbackSeverity.INFO
                ))
            else:
                context.static_checks.append(CheckResult(
                    check_id="java_class_exists",
                    name="Java 클래스 존재",
                    status=CheckStatus.FAIL,
                    message="클래스 정의 없음",
                    severity=FeedbackSeverity.ERROR
                ))
        
        return context
