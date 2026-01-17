"""
품질 게이트 및 완료 검증 시스템

비평 에이전트 결과를 검증하고, 완료 허구(Hallucination)를 방지합니다.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, TYPE_CHECKING
from enum import Enum
from pathlib import Path
import re

if TYPE_CHECKING:
    from .orchestrator import Orchestrator


class ValidationResult(Enum):
    """검증 결과"""
    PASSED = "passed"       # 통과 - 다음 단계로
    FAILED = "failed"       # 실패 - on_failure로
    RETRY = "retry"         # 재시도 - 현재 단계 반복
    STOP = "stop"           # 중단 - 워크플로우 종료
    PAUSE = "pause"         # 일시정지 - 사용자 개입 대기


class VerificationResult(Enum):
    """완료 검증 결과"""
    VERIFIED = "verified"           # 실제 완료 확인
    UNVERIFIED = "unverified"       # 검증 실패 (재작업 필요)
    HALLUCINATION = "hallucination" # 거짓 완료 감지


@dataclass
class QualityGate:
    """품질 게이트 정의"""
    name: str
    validator_agent: str           # 검증 에이전트 이름
    validation_prompt: str         # 검증 요청 프롬프트
    pass_keywords: List[str] = field(default_factory=lambda: ["PASSED", "SUCCESS", "OK"])
    fail_keywords: List[str] = field(default_factory=lambda: ["FAILED", "ERROR", "REJECT"])
    max_retries: int = 2           # 실패 시 최대 재시도
    on_stop: Optional[str] = None  # 중단 시 실행할 단계


@dataclass
class VerificationRule:
    """완료 검증 규칙"""
    step_pattern: str                         # 적용할 단계 패턴 (regex)
    required_files: List[str] = None          # 이 파일들이 존재해야 함
    required_keywords: List[str] = None       # 출력에 이 키워드가 있어야 함
    forbidden_patterns: List[str] = None      # 이 패턴이 있으면 허구로 판단
    custom_verifier: Optional[Callable] = None  # 커스텀 검증 함수
    
    def applies_to(self, step_name: str) -> bool:
        """규칙이 해당 단계에 적용되는지 확인"""
        return bool(re.match(self.step_pattern, step_name))
    
    def verify(self, output: str, context: Dict[str, Any]) -> VerificationResult:
        """검증 수행"""
        # 필수 파일 확인
        if self.required_files:
            for file_pattern in self.required_files:
                matches = list(Path('.').glob(file_pattern))
                if not matches:
                    return VerificationResult.UNVERIFIED
        
        # 필수 키워드 확인
        if self.required_keywords:
            output_lower = output.lower()
            for keyword in self.required_keywords:
                if keyword.lower() not in output_lower:
                    return VerificationResult.UNVERIFIED
        
        # 금지 패턴 확인 (허구 감지)
        if self.forbidden_patterns:
            for pattern in self.forbidden_patterns:
                if re.search(pattern, output, re.IGNORECASE):
                    return VerificationResult.HALLUCINATION
        
        # 커스텀 검증
        if self.custom_verifier:
            try:
                if not self.custom_verifier(output, context):
                    return VerificationResult.UNVERIFIED
            except Exception:
                return VerificationResult.UNVERIFIED
        
        return VerificationResult.VERIFIED


class CompletionVerifier:
    """
    완료 검증기
    
    에이전트가 실제 작업을 완료했는지 검증하여
    거짓 완료 보고(Completion Hallucination)를 방지합니다.
    """
    
    def __init__(self):
        self.rules: List[VerificationRule] = []
    
    def add_rule(self, rule: VerificationRule) -> None:
        """검증 규칙 추가"""
        self.rules.append(rule)
    
    def verify(self, step_name: str, output: str, context: Dict[str, Any]) -> VerificationResult:
        """
        완료 검증
        
        Args:
            step_name: 단계 이름
            output: 에이전트 출력
            context: 현재 컨텍스트
            
        Returns:
            검증 결과
        """
        for rule in self.rules:
            if rule.applies_to(step_name):
                result = rule.verify(output, context)
                if result != VerificationResult.VERIFIED:
                    return result
        
        return VerificationResult.VERIFIED
    
    def clear(self) -> None:
        """규칙 초기화"""
        self.rules.clear()


class QualityGateValidator:
    """품질 게이트 검증기"""
    
    def __init__(self, orchestrator: 'Orchestrator'):
        self.orchestrator = orchestrator
        self.completion_verifier = CompletionVerifier()
        self.gates: Dict[str, QualityGate] = {}
    
    def register_gate(self, gate: QualityGate) -> None:
        """품질 게이트 등록"""
        self.gates[gate.name] = gate
    
    def get_gate(self, name: str) -> Optional[QualityGate]:
        """품질 게이트 조회"""
        return self.gates.get(name)
    
    def validate(
        self, 
        gate_name: str,
        step_output: str,
        context: Dict[str, Any]
    ) -> ValidationResult:
        """
        품질 게이트 검증 실행
        
        Args:
            gate_name: 품질 게이트 이름
            step_output: 이전 단계의 출력
            context: 현재 컨텍스트
            
        Returns:
            검증 결과
        """
        gate = self.gates.get(gate_name)
        if not gate:
            return ValidationResult.PASSED
        
        # 1. 완료 검증 먼저 수행
        verification = self.completion_verifier.verify(
            gate_name, step_output, context
        )
        if verification == VerificationResult.HALLUCINATION:
            return ValidationResult.FAILED
        if verification == VerificationResult.UNVERIFIED:
            return ValidationResult.RETRY
        
        # 2. 비평 에이전트 호출
        prompt = f"{gate.validation_prompt}\n\n[검증 대상]\n{step_output}"
        result = self.orchestrator.delegate(gate.validator_agent, prompt)
        
        if not result.success:
            return ValidationResult.STOP
        
        output_lower = result.output.lower()
        
        # 통과 키워드 확인
        for keyword in gate.pass_keywords:
            if keyword.lower() in output_lower:
                return ValidationResult.PASSED
        
        # 실패 키워드 확인
        for keyword in gate.fail_keywords:
            if keyword.lower() in output_lower:
                return ValidationResult.FAILED
        
        # 기본값: 통과
        return ValidationResult.PASSED
