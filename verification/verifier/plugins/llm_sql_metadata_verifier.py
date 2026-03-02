"""
LLM 기반 SQL 메타데이터 검증 플러그인

Pro*C SQL 구문과 분석된 메타데이터를 LLM에 전달하여
input/output 호스트 변수, alias, mybatis 변환이 올바른지 검증합니다.
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


class LLMSQLMetadataVerifier(VerifierPlugin):
    """LLM 기반 SQL 메타데이터 검증 플러그인
    
    검증 항목 (모두 LLM이 판단):
    1. input_host_vars: 입력 호스트 변수 추출 정확성
    2. output_host_vars: 출력 호스트 변수 추출 정확성
    3. alias: SELECT 컬럼 alias 분석 정확성
    4. mybatis_sql: MyBatis 형식 변환 정확성
    """
    
    def __init__(self, llm_client: LLMClient = None):
        """
        Args:
            llm_client: LLM 클라이언트 (None이면 새로 생성)
        """
        self._llm_client = llm_client
    
    @property
    def llm_client(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client
    
    @property
    def name(self) -> str:
        return "llm_sql_metadata_verifier"
    
    @property
    def verification_type(self) -> str:
        return "sql_metadata"
    
    def verify(self, input_data: VerificationInput) -> VerificationResult:
        """LLM을 사용한 SQL 메타데이터 검증"""
        raw_sql = input_data.original_source
        metadata = input_data.analysis_result or {}
        
        sql_id = metadata.get("sql_id", "unknown")
        
        # LLM 호출
        llm_response = self.llm_client.verify_sql_metadata(raw_sql, metadata)
        
        if not llm_response.success:
            return VerificationResult(
                verification_type=VerificationType.SQL_METADATA,
                status=VerificationStatus.SKIPPED,
                details={
                    "error": llm_response.error,
                    "sql_id": sql_id,
                },
            )
        
        # LLM 응답 파싱
        issues = self._parse_llm_response(llm_response.content, sql_id)
        
        # 결과 집계
        error_count = len([i for i in issues if i.severity == "error"])
        warning_count = len([i for i in issues if i.severity == "warning"])
        
        if error_count > 0:
            status = VerificationStatus.FAIL
        elif warning_count > 0:
            status = VerificationStatus.WARNING
        else:
            status = VerificationStatus.PASS
        
        total_checks = 4  # input, output, alias, mybatis
        
        return VerificationResult(
            verification_type=VerificationType.SQL_METADATA,
            status=status,
            total_items=total_checks,
            passed_items=total_checks - error_count,
            failed_items=error_count,
            issues=issues,
            details={
                "sql_id": sql_id,
                "llm_model": llm_response.model,
                "raw_response": llm_response.content,
            },
        )
    
    def _parse_llm_response(self, response: str, sql_id: str) -> List[VerificationIssue]:
        """LLM 응답에서 검증 이슈 추출"""
        issues = []
        
        # JSON 블록 추출
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response.strip()
        
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError:
            issues.append(VerificationIssue(
                issue_id=f"llm_parse_error_{sql_id}",
                severity="warning",
                category="parse_error",
                message="LLM 응답 파싱 실패",
                actual=response[:200],
            ))
            return issues
        
        # 각 검증 항목 처리
        for check_name in ["input_host_vars", "output_host_vars", "alias", "mybatis_sql"]:
            check_result = result.get(check_name, {})
            status = check_result.get("status", "PASS")
            
            if status == "FAIL":
                issues.append(VerificationIssue(
                    issue_id=f"{check_name}_fail_{sql_id}",
                    severity="error",
                    category=check_name,
                    message=check_result.get("message", f"{check_name} 검증 실패"),
                    expected=str(check_result.get("expected", "")),
                    actual=str(check_result.get("actual", "")),
                ))
            elif status == "WARNING":
                issues.append(VerificationIssue(
                    issue_id=f"{check_name}_warning_{sql_id}",
                    severity="warning",
                    category=check_name,
                    message=check_result.get("message", f"{check_name} 경고"),
                    expected=str(check_result.get("expected", "")),
                    actual=str(check_result.get("actual", "")),
                ))
        
        return issues


def get_llm_sql_metadata_verifier(llm_client: LLMClient = None) -> LLMSQLMetadataVerifier:
    """LLM SQL 메타데이터 검증기 팩토리 함수"""
    return LLMSQLMetadataVerifier(llm_client)
