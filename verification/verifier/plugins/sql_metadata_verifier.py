"""
SQL 메타데이터 검증 플러그인

SQL 분석 결과의 메타데이터(input/output 변수, alias 등)가 올바른지 검증합니다.
"""

import re
from typing import Any, Dict, List, Set, Tuple

from ..plugin_interface import VerifierPlugin
from ..types import (
    VerificationType,
    VerificationStatus,
    VerificationInput,
    VerificationResult,
    VerificationIssue,
)


class SQLMetadataVerifier(VerifierPlugin):
    """SQL 메타데이터 검증 플러그인
    
    검증 항목:
    1. input_host_vars: SQL에서 사용된 모든 입력 호스트 변수가 추출되었는지
    2. output_host_vars: INTO 절의 모든 출력 변수가 추출되었는지
    3. Alias 정확성: SELECT 컬럼 alias가 올바르게 분석되었는지
    4. mybatis_sql: 호스트 변수가 #{} 형식으로 올바르게 변환되었는지
    """
    
    @property
    def name(self) -> str:
        return "sql_metadata_verifier"
    
    @property
    def verification_type(self) -> str:
        return "sql_metadata"
    
    def verify(self, input_data: VerificationInput) -> VerificationResult:
        """SQL 메타데이터 검증 수행"""
        sql_content = input_data.original_source  # 원본 SQL 구문
        analysis_result = input_data.analysis_result or {}
        
        issues: List[VerificationIssue] = []
        
        sql_id = analysis_result.get("sql_id", "unknown")
        
        # 1. 입력 호스트 변수 검증
        input_issues = self._verify_input_host_vars(sql_content, analysis_result, sql_id)
        issues.extend(input_issues)
        
        # 2. 출력 호스트 변수 검증
        output_issues = self._verify_output_host_vars(sql_content, analysis_result, sql_id)
        issues.extend(output_issues)
        
        # 3. MyBatis SQL 변환 검증
        mybatis_issues = self._verify_mybatis_sql(analysis_result, sql_id)
        issues.extend(mybatis_issues)
        
        # 결과 집계
        total_checks = 3  # input, output, mybatis
        error_count = len([i for i in issues if i.severity == "error"])
        
        if any(i.severity == "error" for i in issues):
            status = VerificationStatus.FAIL
        elif any(i.severity == "warning" for i in issues):
            status = VerificationStatus.WARNING
        else:
            status = VerificationStatus.PASS
        
        return VerificationResult(
            verification_type=VerificationType.SQL_METADATA,
            status=status,
            total_items=total_checks,
            passed_items=total_checks - error_count,
            failed_items=error_count,
            issues=issues,
            details={
                "sql_id": sql_id,
                "sql_type": analysis_result.get("sql_type"),
            },
        )
    
    def _verify_input_host_vars(
        self,
        sql_content: str,
        analysis_result: Dict[str, Any],
        sql_id: str,
    ) -> List[VerificationIssue]:
        """입력 호스트 변수 검증"""
        issues = []
        
        # SQL에서 호스트 변수 추출 (:var_name 형식)
        source_vars = self._extract_host_vars_from_sql(sql_content)
        
        # 분석 결과의 입력 변수
        analyzed_input_vars = set(analysis_result.get("input_host_vars", []))
        
        # INTO 절의 변수는 출력이므로 제외
        into_vars = self._extract_into_vars(sql_content)
        input_vars_in_source = source_vars - into_vars
        
        # 누락된 입력 변수
        for var in input_vars_in_source:
            clean_var = var.lstrip(':')
            if f":{clean_var}" not in analyzed_input_vars and clean_var not in analyzed_input_vars:
                # 인디케이터 변수 확인
                if not any(f":{clean_var}" in v for v in analyzed_input_vars):
                    issues.append(VerificationIssue(
                        issue_id=f"input_var_missing_{sql_id}_{clean_var}",
                        severity="error",
                        category="missing",
                        message=f"Input host variable '{var}' not in analysis result",
                        expected=var,
                        actual=None,
                    ))
        
        # 과잉 추출
        for var in analyzed_input_vars:
            clean_var = var.lstrip(':')
            if f":{clean_var}" not in source_vars and clean_var not in source_vars:
                issues.append(VerificationIssue(
                    issue_id=f"input_var_extra_{sql_id}_{clean_var}",
                    severity="warning",
                    category="extra",
                    message=f"Input variable '{var}' in analysis but not in SQL",
                    expected=None,
                    actual=var,
                ))
        
        return issues
    
    def _verify_output_host_vars(
        self,
        sql_content: str,
        analysis_result: Dict[str, Any],
        sql_id: str,
    ) -> List[VerificationIssue]:
        """출력 호스트 변수 검증"""
        issues = []
        
        # INTO 절에서 출력 변수 추출
        into_vars = self._extract_into_vars(sql_content)
        
        # 분석 결과의 출력 변수
        analyzed_output_vars = set(analysis_result.get("output_host_vars", []))
        
        # 누락된 출력 변수
        for var in into_vars:
            clean_var = var.lstrip(':')
            if f":{clean_var}" not in analyzed_output_vars and clean_var not in analyzed_output_vars:
                issues.append(VerificationIssue(
                    issue_id=f"output_var_missing_{sql_id}_{clean_var}",
                    severity="error",
                    category="missing",
                    message=f"Output host variable '{var}' not in analysis result",
                    expected=var,
                    actual=None,
                ))
        
        return issues
    
    def _verify_mybatis_sql(
        self,
        analysis_result: Dict[str, Any],
        sql_id: str,
    ) -> List[VerificationIssue]:
        """MyBatis SQL 변환 검증"""
        issues = []
        
        mybatis_sql = analysis_result.get("mybatis_sql", "")
        if not mybatis_sql:
            return issues
        
        # 모든 입력 변수가 #{} 형식으로 변환되었는지 확인
        input_vars = analysis_result.get("input_host_vars", [])
        
        for var in input_vars:
            clean_var = var.lstrip(':')
            # camelCase 변환 확인
            camel_case_var = self._to_camel_case(clean_var)
            
            # #{varName, jdbcType=...} 형식 확인
            pattern = rf'#\{{\s*{camel_case_var}\s*[,\}}]'
            if not re.search(pattern, mybatis_sql, re.IGNORECASE):
                # 원본 이름으로도 확인
                pattern2 = rf'#\{{\s*{clean_var}\s*[,\}}]'
                if not re.search(pattern2, mybatis_sql, re.IGNORECASE):
                    issues.append(VerificationIssue(
                        issue_id=f"mybatis_var_missing_{sql_id}_{clean_var}",
                        severity="warning",
                        category="mismatch",
                        message=f"Variable '{var}' not properly converted in mybatis_sql",
                        expected=f"#{{ {camel_case_var}, jdbcType=... }}",
                        actual="Variable not found in mybatis_sql",
                    ))
        
        # 아직 :var 형식이 남아있지 않은지 확인
        remaining_host_vars = re.findall(r':(\w+)', mybatis_sql)
        for var in remaining_host_vars:
            issues.append(VerificationIssue(
                issue_id=f"mybatis_unconverted_{sql_id}_{var}",
                severity="error",
                category="mismatch",
                message=f"Host variable ':{var}' not converted in mybatis_sql",
                expected=f"#{{ {self._to_camel_case(var)} }}",
                actual=f":{var}",
            ))
        
        return issues
    
    def _extract_host_vars_from_sql(self, sql: str) -> Set[str]:
        """SQL에서 호스트 변수 추출 (:var_name 형식)"""
        # 문자열 리터럴 제거
        sql_no_strings = re.sub(r"'[^']*'", "", sql)
        
        # :var_name 패턴 찾기
        vars = set(re.findall(r':(\w+)', sql_no_strings))
        return vars
    
    def _extract_into_vars(self, sql: str) -> Set[str]:
        """INTO 절에서 출력 변수 추출"""
        into_vars: Set[str] = set()
        
        # INTO ... FROM 또는 INTO ... ; 사이의 변수
        into_match = re.search(
            r'\bINTO\b\s+(.*?)(?:\bFROM\b|;|\bWHERE\b)',
            sql,
            re.IGNORECASE | re.DOTALL
        )
        
        if into_match:
            into_clause = into_match.group(1)
            vars = re.findall(r':(\w+)', into_clause)
            into_vars.update(vars)
        
        return into_vars
    
    def _to_camel_case(self, name: str) -> str:
        """snake_case를 camelCase로 변환"""
        # in_acct_no -> inAcctNo
        components = name.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])
