"""
정적 분석 검증 모듈

Pro*C SQL에서 MyBatis SQL로의 변환이 올바른지 규칙 기반으로 검증합니다.
"""

import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class CheckStatus(Enum):
    """검증 결과 상태"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    INFO = "info"


@dataclass
class CheckResult:
    """개별 검증 결과"""
    name: str
    status: CheckStatus
    message: str
    details: str = ""


@dataclass
class AnalysisResult:
    """전체 분석 결과"""
    checks: List[CheckResult] = field(default_factory=list)
    
    @property
    def passed(self) -> bool:
        """모든 검증이 통과했는지"""
        return all(c.status in (CheckStatus.PASS, CheckStatus.INFO) for c in self.checks)
    
    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.PASS)
    
    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.FAIL)
    
    @property
    def warning_count(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.WARNING)


class StaticAnalyzer:
    """Pro*C to MyBatis 변환 정적 분석기"""
    
    # Pro*C 호스트 변수 패턴 (:variable 또는 :variable:indicator)
    PROC_HOST_VAR_PATTERN = re.compile(r':([a-zA-Z_][a-zA-Z0-9_]*)(?::([a-zA-Z_][a-zA-Z0-9_]*))?')
    
    # MyBatis 파라미터 패턴 (#{variable} 또는 ${variable})
    MYBATIS_PARAM_PATTERN = re.compile(r'[#$]\{([a-zA-Z_][a-zA-Z0-9_]*)\}')
    
    # EXEC SQL 패턴
    EXEC_SQL_PATTERN = re.compile(r'\bEXEC\s+SQL\b', re.IGNORECASE)
    
    # SQL 키워드들
    SQL_KEYWORDS = {
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'FROM', 'WHERE', 
        'INTO', 'VALUES', 'SET', 'JOIN', 'LEFT', 'RIGHT', 'INNER',
        'OUTER', 'ON', 'AND', 'OR', 'NOT', 'IN', 'LIKE', 'BETWEEN',
        'ORDER', 'BY', 'GROUP', 'HAVING', 'LIMIT', 'OFFSET', 'AS',
        'DISTINCT', 'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'CREATE',
        'ALTER', 'DROP', 'TABLE', 'INDEX', 'VIEW', 'UNION', 'ALL'
    }
    
    def __init__(self):
        logger.debug("StaticAnalyzer 초기화됨")
    
    def analyze(self, asis: str, tobe: str) -> AnalysisResult:
        """
        asis(Pro*C)와 tobe(MyBatis) SQL을 비교 분석합니다.
        
        Args:
            asis: 원본 Pro*C SQL
            tobe: 변환된 MyBatis SQL
            
        Returns:
            AnalysisResult 객체
        """
        result = AnalysisResult()
        
        # 1. EXEC SQL 제거 여부 검증
        result.checks.append(self._check_exec_sql_removed(asis, tobe))
        
        # 2. 호스트 변수 변환 검증
        result.checks.append(self._check_host_variables(asis, tobe))
        
        # 3. 세미콜론 처리 검증
        result.checks.append(self._check_semicolon(asis, tobe))
        
        # 4. SQL 키워드 보존 검증
        result.checks.append(self._check_keywords_preserved(asis, tobe))
        
        # 5. INTO 절 처리 검증 (SELECT INTO)
        result.checks.append(self._check_into_clause(asis, tobe))
        
        # 6. 테이블/컬럼명 보존 검증
        result.checks.append(self._check_identifiers_preserved(asis, tobe))
        
        logger.info(f"분석 완료: {result.pass_count} 통과, {result.fail_count} 실패, {result.warning_count} 경고")
        return result
    
    def _check_exec_sql_removed(self, asis: str, tobe: str) -> CheckResult:
        """EXEC SQL 키워드 제거 여부 확인"""
        has_exec_in_asis = bool(self.EXEC_SQL_PATTERN.search(asis))
        has_exec_in_tobe = bool(self.EXEC_SQL_PATTERN.search(tobe))
        
        if has_exec_in_tobe:
            return CheckResult(
                name="EXEC SQL 제거",
                status=CheckStatus.FAIL,
                message="tobe에 EXEC SQL이 남아있습니다",
                details="MyBatis SQL에서는 EXEC SQL 키워드를 제거해야 합니다"
            )
        elif has_exec_in_asis:
            return CheckResult(
                name="EXEC SQL 제거",
                status=CheckStatus.PASS,
                message="EXEC SQL이 올바르게 제거됨"
            )
        else:
            return CheckResult(
                name="EXEC SQL 제거",
                status=CheckStatus.INFO,
                message="원본에 EXEC SQL이 없음"
            )
    
    def _check_host_variables(self, asis: str, tobe: str) -> CheckResult:
        """호스트 변수 변환 검증"""
        # asis에서 호스트 변수 추출 (문자열 리터럴 내부 제외)
        asis_vars = self._extract_host_variables(asis)
        
        # tobe에서 MyBatis 파라미터 추출
        tobe_params = set(self.MYBATIS_PARAM_PATTERN.findall(tobe))
        
        # 남아있는 :var 패턴 확인
        remaining_host_vars = self._extract_host_variables(tobe)
        
        if remaining_host_vars:
            return CheckResult(
                name="호스트 변수 변환",
                status=CheckStatus.FAIL,
                message=f"변환되지 않은 호스트 변수: {', '.join(remaining_host_vars)}",
                details="모든 :var 형태는 #{var} 또는 ${var}로 변환되어야 합니다"
            )
        
        if not asis_vars and not tobe_params:
            return CheckResult(
                name="호스트 변수 변환",
                status=CheckStatus.INFO,
                message="호스트 변수 없음"
            )
        
        # 변수 개수 비교 (이름 변환 허용)
        if len(asis_vars) != len(tobe_params):
            return CheckResult(
                name="호스트 변수 변환",
                status=CheckStatus.WARNING,
                message=f"변수 개수 불일치: asis {len(asis_vars)}개, tobe {len(tobe_params)}개",
                details=f"asis: {', '.join(asis_vars)}\ntobe: {', '.join(tobe_params)}"
            )
        
        return CheckResult(
            name="호스트 변수 변환",
            status=CheckStatus.PASS,
            message=f"호스트 변수 {len(asis_vars)}개 모두 변환됨",
            details=f"asis: {', '.join(asis_vars)}\ntobe: {', '.join(tobe_params)}"
        )
    
    def _extract_host_variables(self, sql: str) -> set:
        """SQL에서 호스트 변수 추출 (문자열 리터럴 제외)"""
        # 문자열 리터럴 제거
        sql_no_strings = re.sub(r"'[^']*'", '', sql)
        sql_no_strings = re.sub(r'"[^"]*"', '', sql_no_strings)
        
        matches = self.PROC_HOST_VAR_PATTERN.findall(sql_no_strings)
        # 첫 번째 그룹만 추출 (indicator 변수 제외)
        return {m[0] for m in matches if m[0]}
    
    def _check_semicolon(self, asis: str, tobe: str) -> CheckResult:
        """세미콜론 처리 검증"""
        asis_has_semi = asis.rstrip().endswith(';')
        tobe_has_semi = tobe.rstrip().endswith(';')
        
        if asis_has_semi and tobe_has_semi:
            return CheckResult(
                name="세미콜론 처리",
                status=CheckStatus.WARNING,
                message="tobe에 세미콜론이 남아있음",
                details="일반적으로 MyBatis에서는 세미콜론을 제거하지만 필수는 아닙니다"
            )
        elif asis_has_semi and not tobe_has_semi:
            return CheckResult(
                name="세미콜론 처리",
                status=CheckStatus.PASS,
                message="세미콜론이 올바르게 제거됨"
            )
        else:
            return CheckResult(
                name="세미콜론 처리",
                status=CheckStatus.INFO,
                message="세미콜론 변경 없음"
            )
    
    def _check_keywords_preserved(self, asis: str, tobe: str) -> CheckResult:
        """SQL 키워드 보존 검증"""
        def extract_keywords(sql: str) -> set:
            # EXEC SQL 제거
            sql = self.EXEC_SQL_PATTERN.sub('', sql)
            words = re.findall(r'\b[A-Z]+\b', sql.upper())
            return {w for w in words if w in self.SQL_KEYWORDS}
        
        asis_keywords = extract_keywords(asis)
        tobe_keywords = extract_keywords(tobe)
        
        # INTO 절은 별도 검증하므로 제외
        asis_keywords.discard('INTO')
        tobe_keywords.discard('INTO')
        
        missing = asis_keywords - tobe_keywords
        added = tobe_keywords - asis_keywords
        
        if missing:
            return CheckResult(
                name="SQL 키워드 보존",
                status=CheckStatus.WARNING,
                message=f"누락된 키워드: {', '.join(missing)}",
                details=f"추가된 키워드: {', '.join(added)}" if added else ""
            )
        
        return CheckResult(
            name="SQL 키워드 보존",
            status=CheckStatus.PASS,
            message="모든 SQL 키워드가 보존됨"
        )
    
    def _check_into_clause(self, asis: str, tobe: str) -> CheckResult:
        """SELECT INTO 절 처리 검증"""
        # Pro*C의 SELECT INTO 패턴
        into_pattern = re.compile(r'\bSELECT\b.*?\bINTO\b.*?\bFROM\b', re.IGNORECASE | re.DOTALL)
        
        has_select_into_asis = bool(into_pattern.search(asis))
        has_select_into_tobe = bool(into_pattern.search(tobe))
        
        if has_select_into_asis and has_select_into_tobe:
            return CheckResult(
                name="SELECT INTO 변환",
                status=CheckStatus.WARNING,
                message="tobe에 SELECT INTO가 남아있음",
                details="MyBatis에서는 일반적으로 SELECT INTO 대신 resultType/resultMap을 사용합니다"
            )
        elif has_select_into_asis and not has_select_into_tobe:
            return CheckResult(
                name="SELECT INTO 변환",
                status=CheckStatus.PASS,
                message="SELECT INTO가 올바르게 변환됨"
            )
        else:
            return CheckResult(
                name="SELECT INTO 변환",
                status=CheckStatus.INFO,
                message="SELECT INTO 없음"
            )
    
    def _check_identifiers_preserved(self, asis: str, tobe: str) -> CheckResult:
        """테이블/컬럼 식별자 보존 검증"""
        def extract_identifiers(sql: str) -> set:
            # EXEC SQL, 호스트 변수, MyBatis 파라미터 제거
            sql = self.EXEC_SQL_PATTERN.sub('', sql)
            sql = self.PROC_HOST_VAR_PATTERN.sub('', sql)
            sql = self.MYBATIS_PARAM_PATTERN.sub('', sql)
            # 문자열 리터럴 제거
            sql = re.sub(r"'[^']*'", '', sql)
            
            # 식별자 추출 (소문자 변환하여 비교)
            words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', sql)
            return {w.lower() for w in words if w.upper() not in self.SQL_KEYWORDS}
        
        asis_ids = extract_identifiers(asis)
        tobe_ids = extract_identifiers(tobe)
        
        missing = asis_ids - tobe_ids
        
        if missing and len(missing) > 3:  # 너무 많으면 오탐 가능성
            return CheckResult(
                name="식별자 보존",
                status=CheckStatus.WARNING,
                message=f"일부 식별자가 변경됨: {', '.join(list(missing)[:5])}...",
                details="변수명 변환 또는 실제 누락일 수 있습니다"
            )
        elif missing:
            return CheckResult(
                name="식별자 보존",
                status=CheckStatus.INFO,
                message=f"변경된 식별자: {', '.join(missing)}",
                details="변수명 변환(예: snake_case → camelCase)일 수 있습니다"
            )
        
        return CheckResult(
            name="식별자 보존",
            status=CheckStatus.PASS,
            message="모든 식별자가 보존됨"
        )
