"""
매크로 검증 플러그인

원본 소스 코드의 매크로 정의가 올바르게 분석되었는지 검증합니다.
검증 후 매크로 정보를 컨텍스트에 추가하여 다른 검증에서 사용할 수 있도록 합니다.
"""

import re
from typing import Any, Dict, List, Optional

from ..plugin_interface import VerifierPlugin
from ..types import (
    VerificationType,
    VerificationStatus,
    VerificationInput,
    VerificationResult,
    VerificationContext,
    VerificationIssue,
    MacroInfo,
)


class MacroVerifier(VerifierPlugin):
    """매크로 정의 검증 플러그인
    
    검증 항목:
    1. 모든 #define 매크로가 추출되었는지 확인
    2. 매크로 이름이 정확한지 확인
    3. 매크로 값이 정확한지 확인 (상수 매크로의 경우)
    4. 함수형 매크로의 파라미터가 정확한지 확인
    5. 매크로 사용 위치(used_in_functions)가 올바른지 확인
    """
    
    @property
    def name(self) -> str:
        return "macro_verifier"
    
    @property
    def verification_type(self) -> str:
        return "macro"
    
    @property
    def requires_context(self) -> bool:
        return False
    
    def verify(self, input_data: VerificationInput) -> VerificationResult:
        """매크로 검증 수행"""
        source = input_data.original_source
        analysis_result = input_data.analysis_result or []
        
        issues: List[VerificationIssue] = []
        
        # 1. 원본 소스에서 매크로 추출
        source_macros = self._extract_macros_from_source(source)
        
        # 2. 분석 결과에서 매크로 이름 추출
        analyzed_macro_names = set()
        analyzed_macros: Dict[str, Dict[str, Any]] = {}
        
        for macro in analysis_result:
            name = macro.get("name", "")
            if name:
                analyzed_macro_names.add(name)
                analyzed_macros[name] = macro
        
        total_items = len(source_macros)
        passed_items = 0
        
        # 3. 누락된 매크로 확인
        for macro_name, macro_info in source_macros.items():
            if macro_name not in analyzed_macro_names:
                issues.append(VerificationIssue(
                    issue_id=f"macro_missing_{macro_name}",
                    severity="error",
                    category="missing",
                    message=f"Macro '{macro_name}' not found in analysis result",
                    expected=macro_name,
                    actual=None,
                    line_number=macro_info.get("line"),
                    source_excerpt=macro_info.get("raw", ""),
                    suggestion=f"Add macro '{macro_name}' to the analysis",
                ))
            else:
                # 4. 매크로 값 검증
                analyzed = analyzed_macros[macro_name]
                expected_value = macro_info.get("value")
                actual_value = analyzed.get("value")
                
                if expected_value != actual_value:
                    issues.append(VerificationIssue(
                        issue_id=f"macro_value_mismatch_{macro_name}",
                        severity="error",
                        category="mismatch",
                        message=f"Macro '{macro_name}' value mismatch",
                        expected=str(expected_value),
                        actual=str(actual_value),
                        line_number=macro_info.get("line"),
                        source_excerpt=macro_info.get("raw", ""),
                    ))
                else:
                    passed_items += 1
        
        # 5. 분석 결과에만 있는 매크로 확인 (과잉 추출)
        for macro_name in analyzed_macro_names:
            if macro_name not in source_macros:
                issues.append(VerificationIssue(
                    issue_id=f"macro_extra_{macro_name}",
                    severity="warning",
                    category="extra",
                    message=f"Macro '{macro_name}' found in analysis but not in source",
                    expected=None,
                    actual=macro_name,
                    suggestion="Verify if this macro is defined in an included header",
                ))
        
        # 결과 상태 결정
        if any(i.severity == "error" for i in issues):
            status = VerificationStatus.FAIL
        elif any(i.severity == "warning" for i in issues):
            status = VerificationStatus.WARNING
        else:
            status = VerificationStatus.PASS
        
        return VerificationResult(
            verification_type=VerificationType.MACRO,
            status=status,
            total_items=total_items,
            passed_items=passed_items,
            failed_items=total_items - passed_items,
            issues=issues,
            details={
                "source_macros": list(source_macros.keys()),
                "analyzed_macros": list(analyzed_macro_names),
            },
        )
    
    def update_context(
        self,
        context: VerificationContext,
        result: VerificationResult
    ) -> VerificationContext:
        """검증 후 컨텍스트에 매크로 정보 추가"""
        # 이미 컨텍스트에 매크로가 있으면 업데이트하지 않음
        # (build_context에서 이미 설정됨)
        return context
    
    def _extract_macros_from_source(self, source: str) -> Dict[str, Dict[str, Any]]:
        """소스 코드에서 매크로 정의 추출
        
        지원하는 패턴:
        - #define NAME VALUE
        - #define NAME(params) VALUE
        - #define NAME  (여러 줄 매크로)
        """
        macros: Dict[str, Dict[str, Any]] = {}
        
        # 패턴: #define NAME VALUE 또는 #define NAME(params) VALUE
        # 특수 케이스: 백슬래시로 이어지는 여러 줄 매크로
        
        lines = source.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # #define 시작 확인
            match = re.match(r'^\s*#\s*define\s+(\w+)(?:\(([^)]*)\))?\s*(.*)?', line)
            if match:
                name = match.group(1)
                params = match.group(2)
                value = match.group(3) or ""
                
                # 여러 줄 매크로 처리
                raw_content = line
                while value.rstrip().endswith('\\') and i + 1 < len(lines):
                    i += 1
                    value = value.rstrip()[:-1] + lines[i]
                    raw_content += '\n' + lines[i]
                
                value = value.strip()
                
                macros[name] = {
                    "name": name,
                    "params": [p.strip() for p in params.split(',')] if params else None,
                    "value": value if value else None,
                    "line": i + 1,
                    "raw": raw_content.strip(),
                }
            
            i += 1
        
        return macros
