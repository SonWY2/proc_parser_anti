"""
훅 시스템

워크플로우 생명주기 이벤트에 콜백을 등록합니다.
SubagentStop 훅은 BLOCK 시 reason을 에이전트에 전달하여 강제 재작업합니다.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, Any, List, Optional
from enum import Enum


class HookEvent(Enum):
    """훅 이벤트 타입"""
    WORKFLOW_START = "workflow_start"
    WORKFLOW_END = "workflow_end"
    STEP_START = "step_start"
    STEP_END = "step_end"
    STEP_RETRY = "step_retry"
    SUBAGENT_STOP = "subagent_stop"  # Claude Code의 SubagentStop
    VALIDATION_START = "validation_start"
    VALIDATION_END = "validation_end"
    PAUSE = "pause"
    RESUME = "resume"
    ERROR = "error"


class HookResult(Enum):
    """훅 반환 결과"""
    CONTINUE = 0      # 정상 진행
    RETRY = 1         # 재시도
    BLOCK = 2         # 차단 - reason 전달하여 강제 재작업
    ABORT = 3         # 워크플로우 중단


@dataclass
class HookContext:
    """훅 콜백에 전달되는 컨텍스트"""
    event: HookEvent
    workflow_name: str
    step_name: Optional[str] = None
    agent_name: Optional[str] = None
    output: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class HookResponse:
    """훅 응답"""
    result: HookResult
    reason: str = ""  # BLOCK 시 에이전트에 전달할 사유


# 훅 콜백 타입
HookCallback = Callable[[HookContext], Optional[HookResponse]]


class HookRegistry:
    """훅 레지스트리"""
    
    def __init__(self):
        self._hooks: Dict[HookEvent, List[HookCallback]] = {
            event: [] for event in HookEvent
        }
    
    def register(self, event: HookEvent, callback: HookCallback) -> None:
        """훅 등록"""
        self._hooks[event].append(callback)
    
    def unregister(self, event: HookEvent, callback: HookCallback) -> None:
        """훅 해제"""
        if callback in self._hooks[event]:
            self._hooks[event].remove(callback)
    
    def trigger(self, context: HookContext) -> HookResponse:
        """
        훅 트리거
        
        Returns:
            HookResponse - BLOCK 시 reason 포함
        """
        for callback in self._hooks[context.event]:
            try:
                response = callback(context)
                if response is None:
                    continue
                if isinstance(response, HookResponse):
                    if response.result in (HookResult.BLOCK, HookResult.ABORT):
                        return response
                # 하위 호환: bool 반환 지원
                elif response is False:
                    return HookResponse(HookResult.BLOCK, "훅에서 차단됨")
            except Exception as e:
                print(f"[Hook Error] {context.event}: {e}")
        
        return HookResponse(HookResult.CONTINUE)
    
    def on(self, event: HookEvent):
        """데코레이터 방식 훅 등록"""
        def decorator(func: HookCallback):
            self.register(event, func)
            return func
        return decorator
    
    def clear(self, event: Optional[HookEvent] = None) -> None:
        """훅 초기화"""
        if event:
            self._hooks[event] = []
        else:
            for e in HookEvent:
                self._hooks[e] = []
