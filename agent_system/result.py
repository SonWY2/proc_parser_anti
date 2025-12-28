"""
결과 데이터 구조

서브에이전트 실행 결과 및 도구 호출 기록을 정의합니다.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class ToolCallRecord:
    """도구 호출 기록"""
    tool_name: str
    arguments: Dict[str, Any]
    result: str
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'tool_name': self.tool_name,
            'arguments': self.arguments,
            'result': self.result,
            'success': self.success,
            'timestamp': self.timestamp.isoformat(),
            'error': self.error
        }


@dataclass
class SubagentResult:
    """서브에이전트 실행 결과"""
    success: bool
    output: str
    agent_name: str
    execution_time: float
    tool_calls: List[ToolCallRecord] = field(default_factory=list)
    error: Optional[str] = None
    context_length: int = 0  # 사용된 컨텍스트 토큰 수
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'success': self.success,
            'output': self.output,
            'agent_name': self.agent_name,
            'execution_time': self.execution_time,
            'tool_calls': [tc.to_dict() for tc in self.tool_calls],
            'error': self.error,
            'context_length': self.context_length
        }
    
    def get_summary(self, max_length: int = 500) -> str:
        """압축된 요약 반환 (메인 컨텍스트 오염 방지)"""
        summary = self.output
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."
        return f"[{self.agent_name}] {'성공' if self.success else '실패'}: {summary}"
