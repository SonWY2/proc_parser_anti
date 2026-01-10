"""
검증 관련 타입 정의

VerificationContext, VerificationResult, Feedback 등
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime


class FeedbackSeverity(str, Enum):
    """피드백 심각도"""
    ERROR = "error"      # 심각한 문제 (반드시 수정 필요)
    WARNING = "warning"  # 주의 필요
    INFO = "info"        # 참고 정보


class CheckStatus(str, Enum):
    """체크 결과 상태"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class CheckResult:
    """단일 체크 결과"""
    check_id: str
    name: str
    status: CheckStatus
    message: str = ""
    severity: FeedbackSeverity = FeedbackSeverity.INFO
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Feedback:
    """LLM 피드백 항목"""
    feedback_id: str
    category: str                          # "under_decomposition", "over_decomposition", "accuracy"
    severity: FeedbackSeverity
    message: str
    suggestion: str = ""
    affected_items: List[str] = field(default_factory=list)
    source_excerpt: str = ""
    result_excerpt: str = ""


@dataclass
class VerificationContext:
    """검증 컨텍스트
    
    플러그인 간에 전달되는 검증 정보를 담습니다.
    """
    stage: str                             # "sql_extraction", "function_parsing", etc.
    source: str                            # 원본 소스 코드
    result: Any                            # 변환 결과 (List[Dict] 등)
    
    # 플러그인에서 채워지는 필드
    static_checks: List[CheckResult] = field(default_factory=list)
    samples: List[Any] = field(default_factory=list)
    llm_checks: List[CheckResult] = field(default_factory=list)
    feedbacks: List[Feedback] = field(default_factory=list)
    
    # 메타데이터
    metadata: Dict[str, Any] = field(default_factory=dict)
    checklist_path: Optional[str] = None


@dataclass
class VerificationResult:
    """검증 결과"""
    stage: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 체크 결과
    static_checks: List[CheckResult] = field(default_factory=list)
    llm_checks: List[CheckResult] = field(default_factory=list)
    feedbacks: List[Feedback] = field(default_factory=list)
    
    # 집계
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    warning_checks: int = 0
    
    # 리포트
    report_markdown: str = ""
    report_json: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_context(cls, context: VerificationContext) -> 'VerificationResult':
        """컨텍스트에서 결과 생성"""
        all_checks = context.static_checks + context.llm_checks
        
        passed = sum(1 for c in all_checks if c.status == CheckStatus.PASS)
        failed = sum(1 for c in all_checks if c.status == CheckStatus.FAIL)
        warnings = sum(1 for c in all_checks if c.status == CheckStatus.WARNING)
        
        return cls(
            stage=context.stage,
            static_checks=context.static_checks,
            llm_checks=context.llm_checks,
            feedbacks=context.feedbacks,
            total_checks=len(all_checks),
            passed_checks=passed,
            failed_checks=failed,
            warning_checks=warnings,
        )
    
    def summary(self) -> str:
        """간단한 요약 문자열 반환"""
        status = "✅ PASS" if self.failed_checks == 0 else "❌ FAIL"
        return (
            f"{status} | Stage: {self.stage} | "
            f"Passed: {self.passed_checks}/{self.total_checks} | "
            f"Failed: {self.failed_checks} | Warnings: {self.warning_checks}"
        )
    
    def has_errors(self) -> bool:
        """에러가 있는지 확인"""
        return self.failed_checks > 0
    
    def get_errors(self) -> List[CheckResult]:
        """실패한 체크 목록"""
        return [c for c in self.static_checks + self.llm_checks if c.status == CheckStatus.FAIL]
    
    def get_warnings(self) -> List[CheckResult]:
        """경고 체크 목록"""
        return [c for c in self.static_checks + self.llm_checks if c.status == CheckStatus.WARNING]
