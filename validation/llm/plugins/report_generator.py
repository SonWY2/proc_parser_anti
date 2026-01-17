"""
리포트 생성 플러그인

검증 결과를 Markdown/JSON 리포트로 생성 (POST_VERIFY phase).
"""

from typing import List, Dict, Any
from datetime import datetime
import json

from .base import VerifierPlugin, PluginPhase
from . import register_plugin
from ..types import VerificationResult, CheckStatus, FeedbackSeverity


@register_plugin
class ReportGeneratorPlugin(VerifierPlugin):
    """리포트 생성 플러그인
    
    검증 결과를 Markdown/JSON 리포트로 생성합니다.
    """
    
    name = "report_generator"
    stage = "all"
    phase = PluginPhase.POST_VERIFY
    priority = 100
    description = "검증 리포트 생성"
    
    def process_result(self, result: VerificationResult) -> VerificationResult:
        """리포트 생성"""
        
        # Markdown 리포트 생성
        result.report_markdown = self._generate_markdown(result)
        
        # JSON 리포트 생성
        result.report_json = self._generate_json(result)
        
        return result
    
    def _generate_markdown(self, result: VerificationResult) -> str:
        """Markdown 리포트 생성"""
        lines = []
        
        # 헤더
        lines.append("# 검증 리포트")
        lines.append("")
        lines.append(f"- **단계**: {result.stage}")
        lines.append(f"- **검증 시간**: {result.timestamp}")
        lines.append("")
        
        # 요약
        status_emoji = "✅" if result.failed_checks == 0 else "❌"
        lines.append(f"## {status_emoji} 요약")
        lines.append("")
        lines.append(f"| 항목 | 값 |")
        lines.append(f"|------|-----|")
        lines.append(f"| 총 체크 | {result.total_checks} |")
        lines.append(f"| 통과 | {result.passed_checks} |")
        lines.append(f"| 실패 | {result.failed_checks} |")
        lines.append(f"| 경고 | {result.warning_checks} |")
        lines.append("")
        
        # 정적 체크 결과
        if result.static_checks:
            lines.append("## 정적 체크")
            lines.append("")
            lines.append("| 체크 | 상태 | 메시지 |")
            lines.append("|------|------|--------|")
            for check in result.static_checks:
                status = self._status_emoji(check.status)
                lines.append(f"| {check.name} | {status} | {check.message} |")
            lines.append("")
        
        # LLM 체크 결과
        if result.llm_checks:
            lines.append("## LLM 체크")
            lines.append("")
            lines.append("| 체크 | 상태 | 메시지 |")
            lines.append("|------|------|--------|")
            for check in result.llm_checks:
                status = self._status_emoji(check.status)
                lines.append(f"| {check.name} | {status} | {check.message} |")
            lines.append("")
        
        # 피드백
        if result.feedbacks:
            lines.append("## 피드백")
            lines.append("")
            for fb in result.feedbacks:
                severity_emoji = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(fb.severity.value, "⚪")
                lines.append(f"### {severity_emoji} {fb.category}")
                lines.append("")
                lines.append(f"- **메시지**: {fb.message}")
                if fb.suggestion:
                    lines.append(f"- **제안**: {fb.suggestion}")
                if fb.affected_items:
                    lines.append(f"- **영향 항목**: {', '.join(fb.affected_items)}")
                lines.append("")
        
        return "\n".join(lines)
    
    def _generate_json(self, result: VerificationResult) -> Dict[str, Any]:
        """JSON 리포트 생성"""
        return {
            "stage": result.stage,
            "timestamp": result.timestamp,
            "summary": {
                "total_checks": result.total_checks,
                "passed": result.passed_checks,
                "failed": result.failed_checks,
                "warnings": result.warning_checks,
                "status": "pass" if result.failed_checks == 0 else "fail"
            },
            "static_checks": [
                {
                    "check_id": c.check_id,
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message
                }
                for c in result.static_checks
            ],
            "llm_checks": [
                {
                    "check_id": c.check_id,
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message
                }
                for c in result.llm_checks
            ],
            "feedbacks": [
                {
                    "feedback_id": fb.feedback_id,
                    "category": fb.category,
                    "severity": fb.severity.value,
                    "message": fb.message,
                    "suggestion": fb.suggestion,
                    "affected_items": fb.affected_items
                }
                for fb in result.feedbacks
            ]
        }
    
    def _status_emoji(self, status: CheckStatus) -> str:
        """상태별 이모지"""
        return {
            CheckStatus.PASS: "✅",
            CheckStatus.FAIL: "❌",
            CheckStatus.WARNING: "⚠️",
            CheckStatus.SKIPPED: "⏭️"
        }.get(status, "❓")
