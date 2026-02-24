"""
에이전트 모니터링 시스템

에이전트 호출, 태스크 수행, 도구 사용을 추적하고 로깅합니다.
실시간 모니터링과 세션 분석 리포트를 제공합니다.
"""

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from .hooks import HookRegistry, HookEvent, HookContext


class EventType(Enum):
    """이벤트 타입"""
    INVOKE = "invoke"           # 에이전트 호출
    COMPLETE = "complete"       # 에이전트 완료
    ERROR = "error"            # 오류 발생
    TOOL_CALL = "tool_call"    # 도구 호출
    WORKFLOW_START = "workflow_start"
    WORKFLOW_END = "workflow_end"
    STEP_START = "step_start"
    STEP_END = "step_end"


@dataclass
class AgentEvent:
    """에이전트 이벤트 로그"""
    timestamp: str
    event_type: str
    agent_name: str
    task: str = ""
    execution_time_ms: float = 0.0
    tool_name: str = ""
    tool_calls: List[str] = field(default_factory=list)
    output_summary: str = ""
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'timestamp': self.timestamp,
            'event_type': self.event_type,
            'agent_name': self.agent_name,
            'task': self.task,
            'execution_time_ms': self.execution_time_ms,
            'tool_name': self.tool_name,
            'tool_calls': self.tool_calls,
            'output_summary': self.output_summary,
            'error': self.error,
            'metadata': self.metadata
        }


@dataclass 
class AgentStats:
    """에이전트별 통계"""
    agent_name: str
    total_invocations: int = 0
    total_completions: int = 0
    total_errors: int = 0
    total_tool_calls: int = 0
    total_execution_time_ms: float = 0.0
    avg_execution_time_ms: float = 0.0
    success_rate: float = 0.0
    
    def update(self):
        """통계 업데이트"""
        if self.total_completions > 0:
            self.avg_execution_time_ms = self.total_execution_time_ms / self.total_completions
        total_finished = self.total_completions + self.total_errors
        if total_finished > 0:
            self.success_rate = self.total_completions / total_finished * 100


class AgentMonitor:
    """
    에이전트 모니터링 시스템
    
    사용 예시:
        monitor = AgentMonitor(log_dir="./logs/monitoring")
        
        # 수동 로깅
        monitor.log_invoke("proc-analyzer", "분석 요청")
        monitor.log_complete("proc-analyzer", "분석 요청", 1500.0, "분석 완료", ["Read", "Grep"])
        
        # 요약 확인
        print(monitor.get_summary())
        
        # Hook 시스템 연동
        monitor.register_hooks(workflow_engine.hooks)
    """
    
    DEFAULT_LOG_DIR = "./logs/agent_monitoring"
    
    def __init__(
        self, 
        log_dir: Optional[str] = None,
        enable_file_logging: bool = True,
        enable_console_logging: bool = False,
        max_task_length: int = 200,
        max_output_length: int = 500
    ):
        """
        Args:
            log_dir: 로그 파일 저장 디렉토리
            enable_file_logging: 파일 로깅 활성화
            enable_console_logging: 콘솔 출력 활성화
            max_task_length: 태스크 텍스트 최대 길이
            max_output_length: 출력 텍스트 최대 길이
        """
        self.log_dir = Path(log_dir or self.DEFAULT_LOG_DIR)
        self.enable_file_logging = enable_file_logging
        self.enable_console_logging = enable_console_logging
        self.max_task_length = max_task_length
        self.max_output_length = max_output_length
        
        # 세션 정보
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._session_start = datetime.now()
        
        # 이벤트 저장
        self.events: List[AgentEvent] = []
        
        # 에이전트별 통계
        self._agent_stats: Dict[str, AgentStats] = {}
        
        # 진행 중인 태스크 추적 (execution_time 계산용)
        self._pending_tasks: Dict[str, float] = {}  # key: f"{agent_name}:{task_hash}"
        
        # 콜백
        self._callbacks: List[Callable[[AgentEvent], None]] = []
        
        # 로그 디렉토리 생성
        if self.enable_file_logging:
            self.log_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def session_id(self) -> str:
        """현재 세션 ID"""
        return self._session_id
    
    @property
    def log_file_path(self) -> Path:
        """현재 세션 로그 파일 경로"""
        return self.log_dir / f"session_{self._session_id}.jsonl"
    
    def _truncate(self, text: str, max_length: int) -> str:
        """텍스트 길이 제한"""
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text
    
    def _get_task_key(self, agent_name: str, task: str) -> str:
        """태스크 고유 키 생성"""
        return f"{agent_name}:{hash(task)}"
    
    def _get_or_create_stats(self, agent_name: str) -> AgentStats:
        """에이전트 통계 가져오기/생성"""
        if agent_name not in self._agent_stats:
            self._agent_stats[agent_name] = AgentStats(agent_name=agent_name)
        return self._agent_stats[agent_name]
    
    def _record(self, event: AgentEvent) -> None:
        """이벤트 기록"""
        self.events.append(event)
        
        # 파일 로깅
        if self.enable_file_logging:
            try:
                with open(self.log_file_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(event.to_dict(), ensure_ascii=False) + '\n')
            except Exception as e:
                print(f"[Monitor] 로그 파일 쓰기 실패: {e}")
        
        # 콘솔 로깅
        if self.enable_console_logging:
            self._print_event(event)
        
        # 콜백 실행
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"[Monitor] 콜백 실행 실패: {e}")
    
    def _print_event(self, event: AgentEvent) -> None:
        """이벤트 콘솔 출력"""
        time_str = event.timestamp.split('T')[1][:8] if 'T' in event.timestamp else event.timestamp
        
        if event.event_type == EventType.INVOKE.value:
            print(f"[{time_str}] 🚀 {event.agent_name} 호출: {event.task[:50]}")
        elif event.event_type == EventType.COMPLETE.value:
            print(f"[{time_str}] ✅ {event.agent_name} 완료 ({event.execution_time_ms:.0f}ms)")
        elif event.event_type == EventType.ERROR.value:
            print(f"[{time_str}] ❌ {event.agent_name} 오류: {event.error[:50]}")
        elif event.event_type == EventType.TOOL_CALL.value:
            print(f"[{time_str}] 🔧 {event.agent_name} -> {event.tool_name}")
    
    # ========== 로깅 메서드 ==========
    
    def log_invoke(self, agent_name: str, task: str, metadata: Optional[Dict] = None) -> None:
        """
        에이전트 호출 기록
        
        Args:
            agent_name: 에이전트 이름
            task: 수행할 태스크
            metadata: 추가 메타데이터
        """
        task_key = self._get_task_key(agent_name, task)
        self._pending_tasks[task_key] = time.time() * 1000  # ms
        
        stats = self._get_or_create_stats(agent_name)
        stats.total_invocations += 1
        
        event = AgentEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.INVOKE.value,
            agent_name=agent_name,
            task=self._truncate(task, self.max_task_length),
            metadata=metadata or {}
        )
        self._record(event)
    
    def log_complete(
        self, 
        agent_name: str, 
        task: str,
        execution_time_ms: Optional[float] = None,
        output: str = "",
        tool_calls: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        에이전트 완료 기록
        
        Args:
            agent_name: 에이전트 이름
            task: 수행한 태스크
            execution_time_ms: 실행 시간 (None이면 자동 계산)
            output: 출력 결과
            tool_calls: 사용된 도구 목록
            metadata: 추가 메타데이터
        """
        # 실행 시간 계산
        task_key = self._get_task_key(agent_name, task)
        if execution_time_ms is None:
            start_time = self._pending_tasks.pop(task_key, None)
            if start_time:
                execution_time_ms = time.time() * 1000 - start_time
            else:
                execution_time_ms = 0.0
        else:
            self._pending_tasks.pop(task_key, None)
        
        # 통계 업데이트
        stats = self._get_or_create_stats(agent_name)
        stats.total_completions += 1
        stats.total_execution_time_ms += execution_time_ms
        if tool_calls:
            stats.total_tool_calls += len(tool_calls)
        stats.update()
        
        event = AgentEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.COMPLETE.value,
            agent_name=agent_name,
            task=self._truncate(task, self.max_task_length),
            execution_time_ms=execution_time_ms,
            tool_calls=tool_calls or [],
            output_summary=self._truncate(output, self.max_output_length),
            metadata=metadata or {}
        )
        self._record(event)
    
    def log_error(
        self, 
        agent_name: str, 
        task: str, 
        error: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        에이전트 오류 기록
        
        Args:
            agent_name: 에이전트 이름
            task: 수행 중인 태스크
            error: 오류 메시지
            metadata: 추가 메타데이터
        """
        # 대기 중 태스크 제거
        task_key = self._get_task_key(agent_name, task)
        self._pending_tasks.pop(task_key, None)
        
        # 통계 업데이트
        stats = self._get_or_create_stats(agent_name)
        stats.total_errors += 1
        stats.update()
        
        event = AgentEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.ERROR.value,
            agent_name=agent_name,
            task=self._truncate(task, self.max_task_length),
            error=error,
            metadata=metadata or {}
        )
        self._record(event)
    
    def log_tool_call(
        self, 
        agent_name: str, 
        tool_name: str,
        arguments: Optional[Dict] = None,
        success: bool = True,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        도구 호출 기록
        
        Args:
            agent_name: 에이전트 이름
            tool_name: 도구 이름
            arguments: 도구 인자
            success: 성공 여부
            metadata: 추가 메타데이터
        """
        event = AgentEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.TOOL_CALL.value,
            agent_name=agent_name,
            tool_name=tool_name,
            metadata={
                'arguments': arguments or {},
                'success': success,
                **(metadata or {})
            }
        )
        self._record(event)
    
    def log_workflow_event(
        self,
        event_type: EventType,
        workflow_name: str,
        step_name: Optional[str] = None,
        agent_name: Optional[str] = None,
        output: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        워크플로우 이벤트 기록
        
        Args:
            event_type: 이벤트 타입
            workflow_name: 워크플로우 이름
            step_name: 단계 이름 (선택)
            agent_name: 에이전트 이름 (선택)
            output: 출력 (선택)
            error: 오류 (선택)
            metadata: 추가 메타데이터
        """
        event = AgentEvent(
            timestamp=datetime.now().isoformat(),
            event_type=event_type.value,
            agent_name=agent_name or "",
            task=f"{workflow_name}" + (f"/{step_name}" if step_name else ""),
            output_summary=self._truncate(output or "", self.max_output_length),
            error=error or "",
            metadata=metadata or {}
        )
        self._record(event)
    
    # ========== 분석 메서드 ==========
    
    def get_summary(self) -> Dict[str, Any]:
        """
        세션 요약
        
        Returns:
            세션 통계 딕셔너리
        """
        event_counts = {}
        for event in self.events:
            event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1
        
        total_exec_time = sum(e.execution_time_ms for e in self.events)
        
        return {
            "session_id": self._session_id,
            "session_start": self._session_start.isoformat(),
            "duration_seconds": (datetime.now() - self._session_start).total_seconds(),
            "total_events": len(self.events),
            "event_counts": event_counts,
            "agents_used": list(self._agent_stats.keys()),
            "total_execution_time_ms": total_exec_time,
            "avg_execution_time_ms": total_exec_time / max(1, event_counts.get(EventType.COMPLETE.value, 1))
        }
    
    def get_agent_stats(self, agent_name: Optional[str] = None) -> Dict[str, AgentStats]:
        """
        에이전트별 통계
        
        Args:
            agent_name: 특정 에이전트 이름 (None이면 전체)
            
        Returns:
            에이전트 통계 딕셔너리
        """
        if agent_name:
            if agent_name in self._agent_stats:
                return {agent_name: self._agent_stats[agent_name]}
            return {}
        return self._agent_stats.copy()
    
    def get_events_by_agent(self, agent_name: str) -> List[AgentEvent]:
        """특정 에이전트의 이벤트 목록"""
        return [e for e in self.events if e.agent_name == agent_name]
    
    def get_events_by_type(self, event_type: EventType) -> List[AgentEvent]:
        """특정 타입의 이벤트 목록"""
        return [e for e in self.events if e.event_type == event_type.value]
    
    def get_errors(self) -> List[AgentEvent]:
        """오류 이벤트 목록"""
        return self.get_events_by_type(EventType.ERROR)
    
    # ========== 리포트 생성 ==========
    
    def export_report(
        self, 
        output_path: Optional[str] = None,
        format: str = "json"  # "json" or "markdown"
    ) -> str:
        """
        세션 리포트 생성
        
        Args:
            output_path: 출력 파일 경로 (None이면 문자열 반환)
            format: 출력 형식 ("json" 또는 "markdown")
            
        Returns:
            리포트 문자열
        """
        if format == "markdown":
            report = self._generate_markdown_report()
        else:
            report = self._generate_json_report()
        
        if output_path:
            Path(output_path).write_text(report, encoding='utf-8')
        
        return report
    
    def _generate_json_report(self) -> str:
        """JSON 리포트 생성"""
        data = {
            "summary": self.get_summary(),
            "agent_stats": {
                name: asdict(stats) 
                for name, stats in self._agent_stats.items()
            },
            "events": [e.to_dict() for e in self.events]
        }
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def _generate_markdown_report(self) -> str:
        """Markdown 리포트 생성"""
        summary = self.get_summary()
        
        lines = [
            f"# Agent Monitoring Report",
            f"",
            f"## Session Info",
            f"- **Session ID**: {summary['session_id']}",
            f"- **Start**: {summary['session_start']}",
            f"- **Duration**: {summary['duration_seconds']:.2f} seconds",
            f"- **Total Events**: {summary['total_events']}",
            f"",
            f"## Event Summary",
        ]
        
        for event_type, count in summary.get('event_counts', {}).items():
            lines.append(f"- {event_type}: {count}")
        
        lines.extend([
            f"",
            f"## Agent Statistics",
            f"",
            f"| Agent | Invocations | Completions | Errors | Avg Time (ms) | Success Rate |",
            f"|-------|-------------|-------------|--------|---------------|--------------|",
        ])
        
        for name, stats in self._agent_stats.items():
            lines.append(
                f"| {name} | {stats.total_invocations} | {stats.total_completions} | "
                f"{stats.total_errors} | {stats.avg_execution_time_ms:.0f} | "
                f"{stats.success_rate:.1f}% |"
            )
        
        # 오류 목록
        errors = self.get_errors()
        if errors:
            lines.extend([
                f"",
                f"## Errors ({len(errors)})",
                f""
            ])
            for err in errors:
                lines.append(f"- **{err.agent_name}**: {err.error}")
        
        return '\n'.join(lines)
    
    # ========== Hook 시스템 연동 ==========
    
    def register_hooks(self, hook_registry: 'HookRegistry') -> None:
        """
        Hook 시스템에 모니터링 훅 등록
        
        Args:
            hook_registry: 훅 레지스트리
        """
        from .hooks import HookEvent as HE, HookContext
        
        @hook_registry.on(HE.WORKFLOW_START)
        def on_workflow_start(ctx: HookContext):
            self.log_workflow_event(
                EventType.WORKFLOW_START,
                ctx.workflow_name,
                metadata=ctx.data
            )
        
        @hook_registry.on(HE.WORKFLOW_END)
        def on_workflow_end(ctx: HookContext):
            self.log_workflow_event(
                EventType.WORKFLOW_END,
                ctx.workflow_name,
                output=ctx.output,
                metadata=ctx.data
            )
        
        @hook_registry.on(HE.STEP_START)
        def on_step_start(ctx: HookContext):
            if ctx.agent_name:
                self.log_invoke(ctx.agent_name, ctx.step_name or "")
        
        @hook_registry.on(HE.STEP_END)
        def on_step_end(ctx: HookContext):
            if ctx.agent_name:
                self.log_complete(
                    ctx.agent_name,
                    ctx.step_name or "",
                    output=ctx.output or ""
                )
        
        @hook_registry.on(HE.ERROR)
        def on_error(ctx: HookContext):
            if ctx.agent_name:
                self.log_error(
                    ctx.agent_name,
                    ctx.step_name or "",
                    ctx.error or "Unknown error"
                )
    
    # ========== 유틸리티 ==========
    
    def add_callback(self, callback: Callable[[AgentEvent], None]) -> None:
        """이벤트 콜백 추가"""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[AgentEvent], None]) -> None:
        """이벤트 콜백 제거"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def clear(self) -> None:
        """이벤트 초기화"""
        self.events.clear()
        self._agent_stats.clear()
        self._pending_tasks.clear()
    
    def new_session(self) -> None:
        """새 세션 시작"""
        self.clear()
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._session_start = datetime.now()
    
    def load_session(self, log_file_path: str) -> int:
        """
        저장된 세션 로드
        
        Args:
            log_file_path: JSONL 로그 파일 경로
            
        Returns:
            로드된 이벤트 수
        """
        path = Path(log_file_path)
        if not path.exists():
            return 0
        
        count = 0
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    event = AgentEvent(
                        timestamp=data.get('timestamp', ''),
                        event_type=data.get('event_type', ''),
                        agent_name=data.get('agent_name', ''),
                        task=data.get('task', ''),
                        execution_time_ms=data.get('execution_time_ms', 0),
                        tool_name=data.get('tool_name', ''),
                        tool_calls=data.get('tool_calls', []),
                        output_summary=data.get('output_summary', ''),
                        error=data.get('error', ''),
                        metadata=data.get('metadata', {})
                    )
                    self.events.append(event)
                    count += 1
                except json.JSONDecodeError:
                    continue
        
        return count


# 전역 모니터 인스턴스 (싱글톤 패턴)
_global_monitor: Optional[AgentMonitor] = None


def get_global_monitor() -> AgentMonitor:
    """전역 모니터 가져오기"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = AgentMonitor()
    return _global_monitor


def set_global_monitor(monitor: AgentMonitor) -> None:
    """전역 모니터 설정"""
    global _global_monitor
    _global_monitor = monitor
