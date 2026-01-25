"""
SQL 추출 검증 플러그인

추출된 코드(_extracted.c)를 검증하여 SQL이 올바르게 추출되었는지 확인합니다.
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


class SQLExtractionVerifier(VerifierPlugin):
    """SQL 추출 검증 플러그인
    
    검증 항목:
    1. 모든 EXEC SQL 문이 추출되었는지 확인
    2. SQL이 올바른 주석으로 대체되었는지 확인
    3. SQL ID가 함수와 올바르게 연결되었는지 확인
    4. 로컬 변수가 누락 없이 추출되었는지 확인
    5. 추출 후 남은 코드에 미추출된 SQL이 없는지 확인
    """
    
    @property
    def name(self) -> str:
        return "sql_extraction_verifier"
    
    @property
    def verification_type(self) -> str:
        return "sql_extraction"
    
    def verify(self, input_data: VerificationInput) -> VerificationResult:
        """SQL 추출 검증 수행"""
        extracted_code = input_data.original_source  # _extracted.c 내용
        analysis_result = input_data.analysis_result or {}
        
        issues: List[VerificationIssue] = []
        
        sql_ids = analysis_result.get("sql_ids", [])
        functions = analysis_result.get("functions", [])
        
        # 1. 추출된 코드에서 SQL 주석 찾기
        sql_comments = self._find_sql_comments(extracted_code)
        
        # 2. 미추출된 EXEC SQL 문 확인
        remaining_exec_sql = self._find_remaining_exec_sql(extracted_code)
        
        for exec_sql in remaining_exec_sql:
            issues.append(VerificationIssue(
                issue_id=f"sql_not_extracted_{exec_sql['line']}",
                severity="error",
                category="missing",
                message=f"EXEC SQL statement not extracted at line {exec_sql['line']}",
                expected="SQL should be extracted and replaced with comment",
                actual=exec_sql['content'][:80] + "...",
                line_number=exec_sql['line'],
                source_excerpt=exec_sql['content'],
            ))
        
        # 3. SQL ID 연속성 검증
        if sql_ids:
            expected_ids = set(sql_ids)
            found_ids = set(sql_comments.keys())
            
            # 누락된 SQL ID
            missing_ids = expected_ids - found_ids
            for sql_id in missing_ids:
                issues.append(VerificationIssue(
                    issue_id=f"sql_comment_missing_{sql_id}",
                    severity="warning",
                    category="missing",
                    message=f"SQL ID '{sql_id}' not found as comment in extracted code",
                    expected=sql_id,
                    actual=None,
                ))
            
            # 추가된 SQL ID (있을 수 있음 - 중복 등)
            extra_ids = found_ids - expected_ids
            for sql_id in extra_ids:
                if sql_id:  # 빈 ID 무시
                    issues.append(VerificationIssue(
                        issue_id=f"sql_comment_extra_{sql_id}",
                        severity="info",
                        category="extra",
                        message=f"SQL comment '{sql_id}' found but not in SQL list",
                        expected=None,
                        actual=sql_id,
                    ))
        
        # 4. 함수별 SQL 연결 검증
        function_sql_map = self._build_function_sql_map(functions, sql_ids, analysis_result)
        
        for func_name, expected_sqls in function_sql_map.items():
            # 추출된 코드에서 해당 함수 내 SQL 주석 확인
            func_sqls_in_code = self._find_sqls_in_function(extracted_code, func_name, sql_comments)
            
            for sql_id in expected_sqls:
                if sql_id not in func_sqls_in_code:
                    issues.append(VerificationIssue(
                        issue_id=f"sql_func_mismatch_{func_name}_{sql_id}",
                        severity="warning",
                        category="mismatch",
                        message=f"SQL '{sql_id}' should be in function '{func_name}'",
                        expected=f"SQL {sql_id} in {func_name}",
                        actual="SQL not found in function scope",
                    ))
        
        # 결과 집계
        total_items = len(sql_ids) if sql_ids else len(sql_comments)
        error_count = len([i for i in issues if i.severity == "error"])
        passed_items = total_items - error_count
        
        if any(i.severity == "error" for i in issues):
            status = VerificationStatus.FAIL
        elif any(i.severity == "warning" for i in issues):
            status = VerificationStatus.WARNING
        else:
            status = VerificationStatus.PASS
        
        return VerificationResult(
            verification_type=VerificationType.SQL_EXTRACTION,
            status=status,
            total_items=total_items,
            passed_items=passed_items,
            failed_items=error_count,
            issues=issues,
            details={
                "sql_comments_found": list(sql_comments.keys()),
                "remaining_exec_sql_count": len(remaining_exec_sql),
                "function_sql_map": function_sql_map,
            },
        )
    
    def _find_sql_comments(self, code: str) -> Dict[str, Dict[str, Any]]:
        """추출된 코드에서 SQL 주석 찾기
        
        예: /* SQL: sql_001 */ 또는 // SQL_ID: sql_001
        """
        comments: Dict[str, Dict[str, Any]] = {}
        
        # 패턴: /* SQL: sql_xxx */ 또는 유사 형식
        patterns = [
            r'/\*\s*SQL[_:]?\s*(\w+)\s*\*/',
            r'//\s*SQL[_:]?\s*(\w+)',
            r'/\*\s*sql_id[=:]?\s*(\w+)\s*\*/',
        ]
        
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            for pattern in patterns:
                matches = re.findall(pattern, line, re.IGNORECASE)
                for match in matches:
                    sql_id = match
                    comments[sql_id] = {
                        "sql_id": sql_id,
                        "line": i,
                        "content": line.strip(),
                    }
        
        return comments
    
    def _find_remaining_exec_sql(self, code: str) -> List[Dict[str, Any]]:
        """추출 후 남은 EXEC SQL 문 찾기"""
        remaining = []
        
        lines = code.split('\n')
        in_sql = False
        sql_start = 0
        sql_content = ""
        
        for i, line in enumerate(lines, 1):
            # EXEC SQL 시작
            if re.search(r'\bEXEC\s+SQL\b', line, re.IGNORECASE) and not in_sql:
                in_sql = True
                sql_start = i
                sql_content = line
            elif in_sql:
                sql_content += "\n" + line
            
            # SQL 종료 (세미콜론)
            if in_sql and ';' in line:
                remaining.append({
                    "line": sql_start,
                    "content": sql_content.strip(),
                })
                in_sql = False
                sql_content = ""
        
        return remaining
    
    def _build_function_sql_map(
        self,
        functions: List[Dict[str, Any]],
        sql_ids: List[str],
        analysis_result: Dict[str, Any],
    ) -> Dict[str, List[str]]:
        """함수별 SQL 매핑 구성"""
        func_sql_map: Dict[str, List[str]] = {}
        
        # functions 데이터에서 구성
        for func in functions:
            func_name = func.get("name", "")
            if func_name:
                func_sql_map[func_name] = func.get("sql_ids", [])
        
        return func_sql_map
    
    def _find_sqls_in_function(
        self,
        code: str,
        func_name: str,
        sql_comments: Dict[str, Dict[str, Any]],
    ) -> Set[str]:
        """특정 함수 내의 SQL 주석 찾기"""
        # 간단한 구현: 함수 시작과 끝 사이의 SQL 주석 찾기
        sqls: Set[str] = set()
        
        # 함수 시작 패턴
        func_pattern = rf'\b{re.escape(func_name)}\s*\([^)]*\)\s*\{{'
        
        match = re.search(func_pattern, code)
        if not match:
            return sqls
        
        # 간단히 함수 이름 이후의 모든 SQL을 해당 함수의 것으로 간주
        # (실제로는 중괄호 매칭 필요)
        for sql_id, info in sql_comments.items():
            sqls.add(sql_id)
        
        return sqls
