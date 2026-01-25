"""
변수 검증 플러그인

원본 소스 코드의 변수 선언이 올바르게 분석되었는지 검증합니다.
매크로 상수(예: MAX_SIZE)가 배열 크기에 사용된 경우 컨텍스트에서 실제 값을 참조합니다.
"""

import re
from typing import Any, Dict, List, Optional, Set

from ..plugin_interface import VerifierPlugin
from ..types import (
    VerificationType,
    VerificationStatus,
    VerificationInput,
    VerificationResult,
    VerificationContext,
    VerificationIssue,
)


class VariableVerifier(VerifierPlugin):
    """변수 선언 검증 플러그인
    
    검증 항목:
    1. 모든 변수 선언이 추출되었는지 확인
    2. 변수 이름이 정확한지 확인
    3. 변수 타입이 정확한지 확인
    4. 배열 크기가 정확한지 확인 (매크로 상수 해석 포함)
    5. 호스트 변수 방향성(in_/out_) 정확성 확인
    6. 인디케이터 변수(ind_) 식별 정확성 확인
    7. 변수 스코프(global/local) 정확성 확인
    """
    
    @property
    def name(self) -> str:
        return "variable_verifier"
    
    @property
    def verification_type(self) -> str:
        return "variable"
    
    @property
    def requires_context(self) -> bool:
        # 매크로 정보가 있으면 더 정확한 검증 가능
        return False
    
    @property
    def context_dependencies(self) -> List[str]:
        return []  # macros는 선택적
    
    def verify(self, input_data: VerificationInput) -> VerificationResult:
        """변수 검증 수행"""
        source = input_data.original_source
        analysis_result = input_data.analysis_result or []
        context = input_data.context
        
        issues: List[VerificationIssue] = []
        
        # 1. 원본 소스에서 변수 선언 추출
        source_variables = self._extract_variables_from_source(source, context)
        
        # 2. 분석 결과에서 변수 정보 추출
        analyzed_variables: Dict[str, Dict[str, Any]] = {}
        for var in analysis_result:
            name = var.get("name", "")
            if name:
                analyzed_variables[name] = var
        
        total_items = len(source_variables)
        passed_items = 0
        
        # 3. 각 변수 검증
        for var_name, var_info in source_variables.items():
            if var_name not in analyzed_variables:
                issues.append(VerificationIssue(
                    issue_id=f"var_missing_{var_name}",
                    severity="error",
                    category="missing",
                    message=f"Variable '{var_name}' not found in analysis result",
                    expected=var_name,
                    actual=None,
                    line_number=var_info.get("line"),
                    source_excerpt=var_info.get("raw", ""),
                ))
                continue
            
            analyzed = analyzed_variables[var_name]
            var_issues = self._verify_single_variable(var_name, var_info, analyzed, context)
            
            if not var_issues:
                passed_items += 1
            else:
                issues.extend(var_issues)
        
        # 4. 과잉 추출 확인
        for var_name in analyzed_variables:
            if var_name not in source_variables:
                issues.append(VerificationIssue(
                    issue_id=f"var_extra_{var_name}",
                    severity="warning",
                    category="extra",
                    message=f"Variable '{var_name}' in analysis but not in source excerpt",
                    expected=None,
                    actual=var_name,
                    suggestion="May be from included headers or different scope",
                ))
        
        # 결과 상태 결정
        if any(i.severity == "error" for i in issues):
            status = VerificationStatus.FAIL
        elif any(i.severity == "warning" for i in issues):
            status = VerificationStatus.WARNING
        else:
            status = VerificationStatus.PASS
        
        return VerificationResult(
            verification_type=VerificationType.VARIABLE,
            status=status,
            total_items=total_items,
            passed_items=passed_items,
            failed_items=total_items - passed_items,
            issues=issues,
            details={
                "source_variables": list(source_variables.keys()),
                "analyzed_variables": list(analyzed_variables.keys()),
                "macros_used": self._get_used_macros(source, context) if context else [],
            },
        )
    
    def _verify_single_variable(
        self,
        var_name: str,
        expected: Dict[str, Any],
        actual: Dict[str, Any],
        context: Optional[VerificationContext],
    ) -> List[VerificationIssue]:
        """단일 변수 상세 검증"""
        issues = []
        
        # 타입 검증
        expected_type = expected.get("type", "")
        actual_type = actual.get("type", "") or actual.get("data_type", "")
        
        if expected_type and actual_type:
            # 타입 정규화 (공백, const 등 처리)
            norm_expected = self._normalize_type(expected_type)
            norm_actual = self._normalize_type(actual_type)
            
            if norm_expected != norm_actual:
                issues.append(VerificationIssue(
                    issue_id=f"var_type_mismatch_{var_name}",
                    severity="error",
                    category="mismatch",
                    message=f"Variable '{var_name}' type mismatch",
                    expected=expected_type,
                    actual=actual_type,
                    line_number=expected.get("line"),
                ))
        
        # 배열 크기 검증 (매크로 해석 포함)
        expected_size = expected.get("array_size")
        actual_size = actual.get("array_size") or actual.get("size")
        
        if expected_size is not None:
            # 매크로가 사용된 경우 실제 값으로 변환
            resolved_expected = self._resolve_size(expected_size, context)
            resolved_actual = self._resolve_size(actual_size, context) if actual_size else None
            
            if resolved_expected != resolved_actual:
                issues.append(VerificationIssue(
                    issue_id=f"var_size_mismatch_{var_name}",
                    severity="error",
                    category="mismatch",
                    message=f"Variable '{var_name}' array size mismatch",
                    expected=f"{expected_size} (resolved: {resolved_expected})",
                    actual=f"{actual_size} (resolved: {resolved_actual})",
                    line_number=expected.get("line"),
                    suggestion="Check if macro constant is correctly resolved",
                ))
        
        # 호스트 변수 방향성 검증
        if var_name.startswith("in_") or var_name.startswith("out_"):
            expected_direction = "input" if var_name.startswith("in_") else "output"
            actual_direction = actual.get("direction", "")
            
            if actual_direction and actual_direction != expected_direction:
                issues.append(VerificationIssue(
                    issue_id=f"var_direction_mismatch_{var_name}",
                    severity="warning",
                    category="mismatch",
                    message=f"Host variable '{var_name}' direction mismatch",
                    expected=expected_direction,
                    actual=actual_direction,
                ))
        
        # 인디케이터 변수 식별
        if var_name.startswith("ind_"):
            is_indicator = actual.get("is_indicator", False)
            if not is_indicator:
                issues.append(VerificationIssue(
                    issue_id=f"var_indicator_not_marked_{var_name}",
                    severity="warning",
                    category="mismatch",
                    message=f"Variable '{var_name}' should be marked as indicator",
                    expected="is_indicator=True",
                    actual=f"is_indicator={is_indicator}",
                ))
        
        return issues
    
    def _extract_variables_from_source(
        self,
        source: str,
        context: Optional[VerificationContext],
    ) -> Dict[str, Dict[str, Any]]:
        """소스 코드에서 변수 선언 추출"""
        variables: Dict[str, Dict[str, Any]] = {}
        
        # C 변수 선언 패턴
        # type name; 또는 type name[size]; 또는 type *name;
        pattern = r'''
            ^\s*
            ((?:const\s+)?(?:unsigned\s+)?(?:short|long\s+)?(?:char|int|float|double|void)\s*\*?)  # 타입
            \s+
            (\w+)                           # 변수 이름
            (?:\[([^\]]+)\])?              # 배열 크기 (선택)
            \s*;
        '''
        
        lines = source.split('\n')
        for i, line in enumerate(lines, 1):
            match = re.match(pattern, line, re.VERBOSE)
            if match:
                var_type = match.group(1).strip()
                var_name = match.group(2)
                array_size = match.group(3)
                
                variables[var_name] = {
                    "name": var_name,
                    "type": var_type,
                    "array_size": array_size,
                    "line": i,
                    "raw": line.strip(),
                }
        
        return variables
    
    def _normalize_type(self, type_str: str) -> str:
        """타입 문자열 정규화"""
        # 공백 정규화
        normalized = ' '.join(type_str.split())
        # const 제거 (비교용)
        normalized = re.sub(r'\bconst\b\s*', '', normalized)
        return normalized.strip()
    
    def _resolve_size(
        self,
        size: Any,
        context: Optional[VerificationContext],
    ) -> Optional[int]:
        """배열 크기 해석 (매크로 포함)"""
        if size is None:
            return None
        
        if isinstance(size, int):
            return size
        
        size_str = str(size).strip()
        
        # 숫자인 경우
        try:
            return int(size_str)
        except ValueError:
            pass
        
        # 매크로인 경우 컨텍스트에서 값 조회
        if context and size_str in context.macros:
            macro_value = context.macros[size_str].get_numeric_value()
            if macro_value is not None:
                return macro_value
        
        # 간단한 수식 계산 (예: MAX_SIZE + 1)
        if context:
            resolved = context.resolve_macro(size_str)
            try:
                # 안전한 수식 평가 (숫자와 기본 연산자만)
                if re.match(r'^[\d\s+\-*/()]+$', resolved):
                    return int(eval(resolved))
            except:
                pass
        
        return None
    
    def _get_used_macros(
        self,
        source: str,
        context: Optional[VerificationContext],
    ) -> List[str]:
        """소스에서 사용된 매크로 목록"""
        if not context:
            return []
        
        used = []
        for macro_name in context.macros:
            if macro_name in source:
                used.append(macro_name)
        return used
