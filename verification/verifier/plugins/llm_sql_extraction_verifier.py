"""
LLM 기반 SQL 추출 검증 플러그인

함수와 관련 메타데이터를 LLM에 전달하여
변수/SQL이 올바르게 추출되었는지 검증합니다.
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


class LLMSQLExtractionVerifier(VerifierPlugin):
    """LLM 기반 SQL 추출 검증 플러그인
    
    검증 항목 (모두 LLM이 판단):
    1. sql_extraction: 모든 EXEC SQL 문이 추출되었는지
    2. sql_replacement: SQL이 올바른 주석으로 대체되었는지
    3. local_variables: 로컬 변수가 올바르게 파싱되었는지
    4. function_mapping: SQL ID가 함수와 올바르게 연결되었는지
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
        return "llm_sql_extraction_verifier"
    
    @property
    def verification_type(self) -> str:
        return "sql_extraction"
    
    def verify(self, input_data: VerificationInput) -> VerificationResult:
        """LLM을 사용한 SQL 추출 검증"""
        extracted_code = input_data.original_source
        analysis_result = input_data.analysis_result or {}
        
        # LLM 호출
        llm_response = self.llm_client.chat(
            prompt=self._build_extraction_prompt(extracted_code, analysis_result)
        )
        
        if not llm_response.success:
            return VerificationResult(
                verification_type=VerificationType.SQL_EXTRACTION,
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
        
        total_checks = 4
        
        return VerificationResult(
            verification_type=VerificationType.SQL_EXTRACTION,
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
    
    def _build_extraction_prompt(self, extracted_code: str, analysis: Dict[str, Any]) -> str:
        """SQL 추출 검증 프롬프트 생성"""
        analysis_json = json.dumps(analysis, ensure_ascii=False, indent=2)
        
        return f"""당신은 Pro*C 코드 파싱 결과를 검증하는 전문가입니다.

## 추출된 코드 (_extracted.c)
SQL이 주석으로 대체된 후의 C 코드입니다:
```c
{extracted_code}
```

## 분석 결과 (functions, sql_ids, local_variables)
```json
{analysis_json}
```

## 검증 항목
다음 각 항목을 검증하고 PASS/FAIL로 판정해주세요:

1. **sql_extraction (SQL 추출)**
   - 원본에 있던 모든 EXEC SQL 문이 추출되었는지 확인
   - 추출된 코드에 미처리된 EXEC SQL 문이 남아있지 않은지 확인

2. **sql_replacement (SQL 대체)**
   - 각 SQL이 `/* SQL: sql_xxx */` 형식의 주석으로 올바르게 대체되었는지 확인
   - 주석 위치가 원본 EXEC SQL 위치와 일치하는지 확인

3. **local_variables (로컬 변수)**
   - 함수 내의 로컬 변수 선언이 올바르게 추출되었는지 확인
   - 변수 타입과 배열 크기가 정확한지 확인

4. **function_mapping (함수 매핑)**
   - 각 SQL ID가 올바른 함수와 연결되었는지 확인
   - sql_ids 목록이 실제 주석의 SQL ID와 일치하는지 확인

## 응답 형식
반드시 다음 JSON 형식으로만 응답해주세요:
```json
{{
    "sql_extraction": {{
        "status": "PASS|FAIL",
        "unextracted_sql": ["추출되지 않은 SQL 설명"],
        "message": "판정 이유"
    }},
    "sql_replacement": {{
        "status": "PASS|FAIL",
        "issues": ["발견된 문제점"],
        "message": "판정 이유"
    }},
    "local_variables": {{
        "status": "PASS|FAIL",
        "missing": ["누락된 변수"],
        "incorrect": ["잘못된 변수"],
        "message": "판정 이유"
    }},
    "function_mapping": {{
        "status": "PASS|FAIL",
        "issues": ["매핑 문제점"],
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
        
        for check_name in ["sql_extraction", "sql_replacement", "local_variables", "function_mapping"]:
            check_result = result.get(check_name, {})
            status = check_result.get("status", "PASS")
            
            if status == "FAIL":
                issues.append(VerificationIssue(
                    issue_id=f"{check_name}_fail",
                    severity="error",
                    category=check_name,
                    message=check_result.get("message", f"{check_name} 검증 실패"),
                    expected=str(check_result.get("missing", check_result.get("unextracted_sql", []))),
                    actual=str(check_result.get("issues", check_result.get("incorrect", []))),
                ))
        
        return issues
