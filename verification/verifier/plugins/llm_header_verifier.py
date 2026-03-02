"""
LLM 기반 헤더 섹션 검증 플러그인

함수 선언 윗부분(#include, #define, DECLARE SECTION)과 분석된 결과를 LLM에 전달하여
변수/매크로/헤더가 올바르게 파싱되었는지 검증합니다.
"""

import json
import re
from typing import Any, Dict, List

from ..plugin_interface import VerifierPlugin
from ..types import (
    VerificationType,
    VerificationStatus,
    VerificationInput,
    VerificationResult,
    VerificationIssue,
)
from ..llm_client import LLMClient


class LLMHeaderVerifier(VerifierPlugin):
    """LLM 기반 헤더 섹션 검증 플러그인
    
    검증 항목 (모두 LLM이 판단):
    1. macros: #define 매크로 추출 정확성
    2. includes: #include 헤더 추출 정확성
    3. variables: DECLARE SECTION 변수 추출 정확성
    """
    
    def __init__(self, llm_client: LLMClient = None):
        self._llm_client = llm_client
    
    @property
    def llm_client(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client
    
    @property
    def name(self) -> str:
        return "llm_header_verifier"
    
    @property
    def verification_type(self) -> str:
        return "header"
    
    def verify(self, input_data: VerificationInput) -> VerificationResult:
        """LLM을 사용한 헤더 섹션 검증"""
        header_source = input_data.original_source
        analysis_result = input_data.analysis_result or {}
        
        # LLM 호출
        llm_response = self.llm_client.chat(
            prompt=self._build_header_prompt(header_source, analysis_result)
        )
        
        if not llm_response.success:
            return VerificationResult(
                verification_type=VerificationType.HEADER,
                status=VerificationStatus.SKIPPED,
                details={"error": llm_response.error},
            )
        
        # LLM 응답 파싱
        issues = self._parse_llm_response(llm_response.content)
        
        error_count = len([i for i in issues if i.severity == "error"])
        
        if error_count > 0:
            status = VerificationStatus.FAIL
        elif issues:
            status = VerificationStatus.WARNING
        else:
            status = VerificationStatus.PASS
        
        total_checks = 3  # macros, includes, variables
        
        return VerificationResult(
            verification_type=VerificationType.HEADER,
            status=status,
            total_items=total_checks,
            passed_items=total_checks - error_count,
            failed_items=error_count,
            issues=issues,
            details={
                "llm_model": llm_response.model,
                "raw_response": llm_response.content,
            },
        )
    
    def _build_header_prompt(self, source: str, analysis: Dict[str, Any]) -> str:
        """헤더 섹션 검증 프롬프트 생성"""
        analysis_json = json.dumps(analysis, ensure_ascii=False, indent=2)
        
        return f"""당신은 Pro*C 코드 파싱 결과를 검증하는 전문가입니다.

## 원본 헤더 섹션 소스 코드
```c
{source}
```

## 분석된 결과
```json
{analysis_json}
```

## 검증 항목
다음 각 항목을 검증하고 PASS/FAIL로 판정해주세요:

1. **macros (매크로 정의)**
   - 모든 #define 매크로가 추출되었는지 확인
   - 매크로 이름과 값이 정확한지 확인
   - 함수형 매크로의 파라미터가 올바르게 파싱되었는지 확인

2. **includes (헤더 포함)**
   - 모든 #include 문이 추출되었는지 확인
   - system include(<>)와 user include("")가 구분되었는지 확인

3. **variables (변수 선언)**
   - EXEC SQL DECLARE SECTION 내의 모든 변수가 추출되었는지 확인
   - 변수 타입(char, int, long 등)이 정확한지 확인
   - 배열 크기가 정확하게 파싱되었는지 확인 (매크로 상수 포함)

## 응답 형식
반드시 다음 JSON 형식으로만 응답해주세요:
```json
{{
    "macros": {{
        "status": "PASS|FAIL",
        "missing": ["누락된 매크로"],
        "incorrect": ["잘못된 매크로"],
        "message": "판정 이유"
    }},
    "includes": {{
        "status": "PASS|FAIL",
        "missing": ["누락된 헤더"],
        "message": "판정 이유"
    }},
    "variables": {{
        "status": "PASS|FAIL",
        "missing": ["누락된 변수"],
        "incorrect": ["잘못된 타입/크기"],
        "message": "판정 이유"
    }},
    "overall": {{
        "status": "PASS|FAIL",
        "summary": "전체 검증 요약"
    }}
}}
```
"""
    
    def _parse_llm_response(self, response: str) -> List[VerificationIssue]:
        """LLM 응답에서 검증 이슈 추출"""
        issues = []
        
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response.strip()
        
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError:
            issues.append(VerificationIssue(
                issue_id="llm_parse_error",
                severity="warning",
                category="parse_error",
                message="LLM 응답 파싱 실패",
                actual=response[:200],
            ))
            return issues
        
        for check_name in ["macros", "includes", "variables"]:
            check_result = result.get(check_name, {})
            status = check_result.get("status", "PASS")
            
            if status == "FAIL":
                issues.append(VerificationIssue(
                    issue_id=f"{check_name}_fail",
                    severity="error",
                    category=check_name,
                    message=check_result.get("message", f"{check_name} 검증 실패"),
                    expected=str(check_result.get("missing", [])),
                    actual=str(check_result.get("incorrect", [])),
                ))
        
        return issues
