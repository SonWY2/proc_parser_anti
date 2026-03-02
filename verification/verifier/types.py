"""
검증 관련 타입 정의

VerificationInput, VerificationResult, VerificationContext 등
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class VerificationType(str, Enum):
    """검증 유형"""
    MACRO = "macro"
    HEADER = "header"
    VARIABLE = "variable"
    SQL_EXTRACTION = "sql_extraction"
    SQL_METADATA = "sql_metadata"


class VerificationStatus(str, Enum):
    """검증 결과 상태"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class MacroInfo:
    """매크로 정보 (컨텍스트 공유용)
    
    변수, 함수 검증 시 매크로 상수 값을 참조할 수 있도록 합니다.
    예: 배열 크기가 MAX_SIZE로 정의된 경우 실제 값(256)으로 검증
    """
    name: str
    value: Optional[str] = None
    params: Optional[List[str]] = None  # 함수형 매크로의 파라미터
    is_constant: bool = True  # 상수 매크로 여부
    used_in_functions: List[str] = field(default_factory=list)
    
    def get_numeric_value(self) -> Optional[int]:
        """숫자 값 반환 (상수 매크로인 경우)"""
        if self.value is None:
            return None
        try:
            return int(self.value)
        except ValueError:
            try:
                return int(float(self.value))
            except ValueError:
                return None


@dataclass
class VerificationContext:
    """검증 컨텍스트
    
    검증 플러그인 간에 공유되는 정보를 담습니다.
    특히 매크로 정보는 변수/함수 검증에 필수적입니다.
    """
    source_file: str = ""
    extracted_file: str = ""
    
    # 매크로 정보 (다른 검증에서 참조)
    macros: Dict[str, MacroInfo] = field(default_factory=dict)
    
    # 분석 결과 캐시
    headers: List[Dict[str, Any]] = field(default_factory=list)
    variables: List[Dict[str, Any]] = field(default_factory=list)
    functions: List[Dict[str, Any]] = field(default_factory=list)
    sql_statements: List[Dict[str, Any]] = field(default_factory=list)
    
    # 검증 결과 누적
    verification_results: Dict[str, 'VerificationResult'] = field(default_factory=dict)
    
    def get_macro_value(self, name: str) -> Optional[str]:
        """매크로 값 조회"""
        if name in self.macros:
            return self.macros[name].value
        return None
    
    def resolve_macro(self, text: str) -> str:
        """텍스트 내 매크로를 실제 값으로 치환
        
        예: "char buf[MAX_SIZE]" -> "char buf[256]"
        """
        result = text
        for macro_name, macro_info in self.macros.items():
            if macro_info.value and macro_name in result:
                result = result.replace(macro_name, macro_info.value)
        return result


@dataclass
class VerificationInput:
    """검증 입력 데이터"""
    verification_type: VerificationType
    original_source: str                    # 원본 소스 코드 (해당 부분)
    analysis_result: Any                    # 분석 결과 (Dict 또는 List)
    context: Optional[VerificationContext] = None  # 공유 컨텍스트 (매크로 정보 등)
    metadata: Dict[str, Any] = field(default_factory=dict)  # 추가 컨텍스트


@dataclass
class VerificationIssue:
    """단일 검증 이슈"""
    issue_id: str
    severity: str                           # error, warning, info
    category: str                           # missing, incorrect, extra, mismatch
    message: str
    expected: Optional[str] = None
    actual: Optional[str] = None
    line_number: Optional[int] = None
    source_excerpt: str = ""
    suggestion: str = ""


@dataclass
class VerificationResult:
    """검증 결과"""
    verification_type: VerificationType
    status: VerificationStatus
    total_items: int = 0
    passed_items: int = 0
    failed_items: int = 0
    warning_items: int = 0
    issues: List[VerificationIssue] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def has_errors(self) -> bool:
        """에러 여부 확인"""
        return any(i.severity == "error" for i in self.issues)
    
    def has_warnings(self) -> bool:
        """경고 여부 확인"""
        return any(i.severity == "warning" for i in self.issues)
    
    def get_errors(self) -> List[VerificationIssue]:
        """에러 목록 반환"""
        return [i for i in self.issues if i.severity == "error"]
    
    def get_warnings(self) -> List[VerificationIssue]:
        """경고 목록 반환"""
        return [i for i in self.issues if i.severity == "warning"]
    
    def summary(self) -> str:
        """간단한 요약 문자열 반환"""
        if self.status == VerificationStatus.PASS:
            status_icon = "✅"
        elif self.status == VerificationStatus.WARNING:
            status_icon = "⚠️"
        elif self.status == VerificationStatus.FAIL:
            status_icon = "❌"
        else:
            status_icon = "⏭️"
            
        return (
            f"{status_icon} {self.verification_type.value}: "
            f"{self.passed_items}/{self.total_items} passed, "
            f"{len(self.get_errors())} errors, "
            f"{len(self.get_warnings())} warnings"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "verification_type": self.verification_type.value,
            "status": self.status.value,
            "total_items": self.total_items,
            "passed_items": self.passed_items,
            "failed_items": self.failed_items,
            "warning_items": self.warning_items,
            "issues": [
                {
                    "issue_id": i.issue_id,
                    "severity": i.severity,
                    "category": i.category,
                    "message": i.message,
                    "expected": i.expected,
                    "actual": i.actual,
                    "line_number": i.line_number,
                    "suggestion": i.suggestion,
                }
                for i in self.issues
            ],
            "details": self.details,
        }
