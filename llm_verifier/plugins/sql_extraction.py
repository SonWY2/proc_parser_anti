"""
SQL 추출 검증 플러그인

Pro*C에서 SQL 추출 결과 검증 (VERIFY phase).
"""

from typing import List, Dict, Any
import yaml

from .base import VerifierPlugin, PluginPhase
from . import register_plugin
from ..types import VerificationContext, CheckResult, CheckStatus, FeedbackSeverity, Feedback
from ..llm_client import LLMClient
from ..prompts import format_verification_prompt, parse_llm_response, VERIFICATION_PROMPT


@register_plugin
class SQLExtractionVerifyPlugin(VerifierPlugin):
    """SQL 추출 검증 플러그인
    
    LLM을 사용하여 SQL 추출 결과의 정확성을 검증합니다.
    """
    
    name = "sql_extraction_verify"
    stage = "sql_extraction"
    phase = PluginPhase.VERIFY
    priority = 50
    description = "SQL 추출 결과 LLM 검증"
    
    def __init__(self):
        self.llm_client = LLMClient()
    
    def process(self, context: VerificationContext) -> VerificationContext:
        """LLM 검증 수행"""
        
        # LLM 클라이언트가 설정되지 않았으면 스킵
        if not self.llm_client.is_configured:
            context.llm_checks.append(CheckResult(
                check_id="llm_not_configured",
                name="LLM 설정",
                status=CheckStatus.SKIPPED,
                message="LLM API가 설정되지 않았습니다",
                severity=FeedbackSeverity.WARNING
            ))
            return context
        
        # 체크리스트 로드
        checklist = self._load_checklist(context.checklist_path)
        if not checklist:
            checklist = self._get_default_checklist()
        
        # 샘플만 검증 (또는 전체가 적으면 전체)
        samples = context.samples if context.samples else context.result
        if isinstance(samples, list) and len(samples) > 0:
            sample_str = self._format_samples(samples[:5])
        else:
            sample_str = str(samples)
        
        # LLM 호출
        result = self.llm_client.verify(
            source=context.source,
            result=sample_str,
            checklist=checklist
        )
        
        if result['success']:
            # 응답 파싱
            parsed = parse_llm_response(result['response'])
            
            # 체크 결과 추가
            for check in parsed.get('checks', []):
                context.llm_checks.append(CheckResult(
                    check_id=check.get('check_id', 'llm_check'),
                    name=check.get('check_id', 'LLM 체크'),
                    status=CheckStatus[check.get('status', 'PASS').upper()],
                    message=check.get('message', ''),
                    severity=FeedbackSeverity.INFO
                ))
            
            # 피드백 추가
            for fb in parsed.get('feedbacks', []):
                context.feedbacks.append(Feedback(
                    feedback_id=f"fb_{len(context.feedbacks)}",
                    category=fb.get('category', 'accuracy'),
                    severity=FeedbackSeverity(fb.get('severity', 'info')),
                    message=fb.get('message', ''),
                    suggestion=fb.get('suggestion', ''),
                    affected_items=fb.get('affected_items', [])
                ))
        else:
            context.llm_checks.append(CheckResult(
                check_id="llm_error",
                name="LLM 호출",
                status=CheckStatus.FAIL,
                message=f"LLM 오류: {result['error']}",
                severity=FeedbackSeverity.ERROR
            ))
        
        return context
    
    def _load_checklist(self, path: str) -> List[Dict[str, str]]:
        """체크리스트 YAML 로드"""
        if not path:
            return []
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            return data.get('llm_checks', [])
        except Exception:
            return []
    
    def _get_default_checklist(self) -> List[Dict[str, str]]:
        """기본 체크리스트"""
        return [
            {
                'id': 'all_exec_sql_found',
                'question': '모든 EXEC SQL이 추출되었나요?',
                'severity': 'error'
            },
            {
                'id': 'under_decomposition',
                'question': '하나에 여러 SQL이 합쳐져 있진 않나요?',
                'severity': 'error'
            },
            {
                'id': 'over_decomposition',
                'question': '하나의 SQL이 여러 개로 분리되진 않았나요?',
                'severity': 'error'
            },
            {
                'id': 'host_vars_complete',
                'question': '호스트 변수가 빠짐없이 추출되었나요?',
                'severity': 'warning'
            }
        ]
    
    def _format_samples(self, samples: List[Dict]) -> str:
        """샘플을 문자열로 포맷"""
        import json
        return json.dumps(samples, ensure_ascii=False, indent=2)
