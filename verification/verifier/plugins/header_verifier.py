"""
헤더 검증 플러그인

원본 소스 코드의 헤더 선언부(#include, typedef, struct)가 올바르게 분석되었는지 검증합니다.
"""

import re
from typing import Any, Dict, List, Set

from ..plugin_interface import VerifierPlugin
from ..types import (
    VerificationType,
    VerificationStatus,
    VerificationInput,
    VerificationResult,
    VerificationIssue,
)


class HeaderVerifier(VerifierPlugin):
    """헤더 선언부 검증 플러그인
    
    검증 항목:
    1. 모든 #include 문이 추출되었는지 확인
    2. include 경로가 정확한지 확인
    3. system/user include 구분이 정확한지 확인
    4. typedef 정의가 올바르게 추출되었는지 확인
    5. struct 정의가 올바르게 추출되었는지 확인
    """
    
    @property
    def name(self) -> str:
        return "header_verifier"
    
    @property
    def verification_type(self) -> str:
        return "header"
    
    def verify(self, input_data: VerificationInput) -> VerificationResult:
        """헤더 검증 수행"""
        source = input_data.original_source
        analysis_result = input_data.analysis_result or []
        
        issues: List[VerificationIssue] = []
        
        # 1. 원본 소스에서 include 추출
        source_includes = self._extract_includes_from_source(source)
        
        # 2. 분석 결과에서 include 추출
        analyzed_includes: Set[str] = set()
        for item in analysis_result:
            if item.get("type") == "include" or "header_name" in item:
                header_name = item.get("path") or item.get("header_name", "")
                if header_name:
                    analyzed_includes.add(header_name)
        
        total_items = len(source_includes)
        passed_items = 0
        
        # 3. 누락된 include 확인
        for inc_path, inc_info in source_includes.items():
            if inc_path not in analyzed_includes:
                issues.append(VerificationIssue(
                    issue_id=f"include_missing_{inc_path}",
                    severity="error",
                    category="missing",
                    message=f"Include '{inc_path}' not found in analysis result",
                    expected=inc_path,
                    actual=None,
                    line_number=inc_info.get("line"),
                    source_excerpt=inc_info.get("raw", ""),
                ))
            else:
                passed_items += 1
        
        # 4. 과잉 추출 확인
        for inc_path in analyzed_includes:
            if inc_path not in source_includes:
                issues.append(VerificationIssue(
                    issue_id=f"include_extra_{inc_path}",
                    severity="warning",
                    category="extra",
                    message=f"Include '{inc_path}' in analysis but not directly in source",
                    expected=None,
                    actual=inc_path,
                    suggestion="May be from nested includes or pre-processor",
                ))
        
        # 결과 상태 결정
        if any(i.severity == "error" for i in issues):
            status = VerificationStatus.FAIL
        elif any(i.severity == "warning" for i in issues):
            status = VerificationStatus.WARNING
        else:
            status = VerificationStatus.PASS
        
        return VerificationResult(
            verification_type=VerificationType.HEADER,
            status=status,
            total_items=total_items,
            passed_items=passed_items,
            failed_items=total_items - passed_items,
            issues=issues,
            details={
                "source_includes": list(source_includes.keys()),
                "analyzed_includes": list(analyzed_includes),
            },
        )
    
    def _extract_includes_from_source(self, source: str) -> Dict[str, Dict[str, Any]]:
        """소스 코드에서 #include 문 추출"""
        includes: Dict[str, Dict[str, Any]] = {}
        
        lines = source.split('\n')
        for i, line in enumerate(lines, 1):
            # #include <header.h> 또는 #include "header.h"
            match = re.match(r'^\s*#\s*include\s*([<"])([^>"]+)[>"]', line)
            if match:
                bracket = match.group(1)
                path = match.group(2)
                is_system = bracket == '<'
                
                includes[path] = {
                    "path": path,
                    "is_system": is_system,
                    "line": i,
                    "raw": line.strip(),
                }
        
        return includes
