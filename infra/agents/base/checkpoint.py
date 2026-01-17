"""
체크포인트 시스템

워크플로우 상태 저장/복원 및 사용자 승인을 관리합니다.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
from datetime import datetime
from enum import Enum
import json


class CheckpointType(Enum):
    """체크포인트 타입"""
    AUTO = "auto"              # 자동 저장 (재개용)
    APPROVAL = "approval"      # 사용자 승인 필요
    REVIEW = "review"          # 사용자 리뷰 요청 (중단 안함)
    DECISION = "decision"      # 사용자 선택 필요 (분기)


class ApprovalResult(Enum):
    """승인 결과"""
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    PENDING = "pending"


@dataclass
class Checkpoint:
    """체크포인트 정의"""
    name: str
    type: CheckpointType = CheckpointType.AUTO
    message: str = ""              # 사용자에게 표시할 메시지
    show_output: bool = True       # 이전 단계 출력 표시
    timeout_seconds: int = 0       # 0이면 무한 대기


@dataclass
class UserDecision:
    """사용자 결정 요청"""
    question: str
    options: List[str] = field(default_factory=lambda: ["continue", "retry", "abort", "skip"])
    default: str = "continue"
    timeout: int = 0


@dataclass
class WorkflowState:
    """워크플로우 실행 상태"""
    workflow_name: str
    current_step: str
    completed_steps: List[str] = field(default_factory=list)
    outputs: Dict[str, str] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    started_at: str = ""
    paused_at: Optional[str] = None
    status: str = "running"  # running, paused, completed, failed, rejected
    
    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.now().isoformat()
    
    def save(self, file_path: str) -> None:
        """상태 저장"""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
    
    @classmethod
    def load(cls, file_path: str) -> 'WorkflowState':
        """상태 로드"""
        data = json.loads(Path(file_path).read_text(encoding='utf-8'))
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return asdict(self)


@dataclass
class ApprovalRequest:
    """승인 요청"""
    workflow_name: str
    checkpoint: Checkpoint
    state: WorkflowState
    previous_output: str = ""
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class CheckpointManager:
    """체크포인트 관리자"""
    
    DEFAULT_STORAGE = ".workflow_state"
    
    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or self.DEFAULT_STORAGE)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.checkpoints: Dict[str, Checkpoint] = {}
        self.pending_approvals: Dict[str, ApprovalRequest] = {}
        self.approval_callback: Optional[Callable[[ApprovalRequest], ApprovalResult]] = None
        self._current_request: Optional[ApprovalRequest] = None
    
    def register_checkpoint(self, checkpoint: Checkpoint) -> None:
        """체크포인트 등록"""
        self.checkpoints[checkpoint.name] = checkpoint
    
    def get_checkpoint(self, name: str) -> Optional[Checkpoint]:
        """체크포인트 조회"""
        return self.checkpoints.get(name)
    
    def save_state(self, state: WorkflowState) -> str:
        """
        워크플로우 상태 저장
        
        Returns:
            저장된 파일 경로
        """
        safe_time = state.started_at.replace(':', '-').replace('.', '-')
        file_name = f"{state.workflow_name}_{safe_time}.json"
        file_path = self.storage_dir / file_name
        state.save(str(file_path))
        return str(file_path)
    
    def load_state(self, file_path: str) -> WorkflowState:
        """상태 로드"""
        return WorkflowState.load(file_path)
    
    def list_saved_states(self, workflow_name: Optional[str] = None) -> List[str]:
        """저장된 상태 목록"""
        pattern = f"{workflow_name}_*.json" if workflow_name else "*.json"
        return [str(p) for p in self.storage_dir.glob(pattern)]
    
    def pause_for_approval(
        self, 
        state: WorkflowState,
        checkpoint: Checkpoint,
        previous_output: str = ""
    ) -> ApprovalResult:
        """
        사용자 승인을 위해 일시정지
        
        Returns:
            승인 결과
        """
        state.status = "paused"
        state.paused_at = datetime.now().isoformat()
        
        request = ApprovalRequest(
            workflow_name=state.workflow_name,
            checkpoint=checkpoint,
            state=state,
            previous_output=previous_output
        )
        
        self.pending_approvals[state.workflow_name] = request
        self._current_request = request
        self.save_state(state)
        
        # 콜백이 설정되어 있으면 사용
        if self.approval_callback:
            return self.approval_callback(request)
        
        # CLI 대화형 모드
        return self._cli_approval(request)
    
    def _cli_approval(self, request: ApprovalRequest) -> ApprovalResult:
        """CLI 대화형 승인"""
        checkpoint = request.checkpoint
        
        print("\n" + "=" * 50)
        print(f"[체크포인트: {checkpoint.name}]")
        print(checkpoint.message or "승인이 필요합니다.")
        
        if checkpoint.show_output and request.previous_output:
            print("\n[이전 단계 결과]")
            print(request.previous_output[:1000])
            if len(request.previous_output) > 1000:
                print("... (생략)")
        
        print("=" * 50)
        
        if checkpoint.type == CheckpointType.REVIEW:
            print("[Enter]를 눌러 계속...")
            input()
            return ApprovalResult.APPROVED
        
        while True:
            response = input("계속하시겠습니까? (y/n): ").strip().lower()
            if response in ('y', 'yes', ''):
                return ApprovalResult.APPROVED
            elif response in ('n', 'no'):
                return ApprovalResult.REJECTED
    
    def approve(self, workflow_name: str) -> Optional[WorkflowState]:
        """워크플로우 승인 및 재개"""
        request = self.pending_approvals.pop(workflow_name, None)
        if request:
            request.state.status = "running"
            request.state.paused_at = None
            return request.state
        return None
    
    def reject(self, workflow_name: str, reason: str = "") -> Optional[WorkflowState]:
        """워크플로우 거부"""
        request = self.pending_approvals.pop(workflow_name, None)
        if request:
            request.state.status = "rejected"
            request.state.errors["_rejection"] = reason
            return request.state
        return None
    
    def approve_current(self) -> Optional[WorkflowState]:
        """현재 승인 요청 승인"""
        if self._current_request:
            return self.approve(self._current_request.workflow_name)
        return None
    
    def reject_current(self, reason: str = "") -> Optional[WorkflowState]:
        """현재 승인 요청 거부"""
        if self._current_request:
            return self.reject(self._current_request.workflow_name, reason)
        return None
    
    def list_pending(self) -> List[str]:
        """승인 대기 중인 워크플로우 목록"""
        return list(self.pending_approvals.keys())
    
    def get_pending_request(self, workflow_name: str) -> Optional[ApprovalRequest]:
        """승인 요청 조회"""
        return self.pending_approvals.get(workflow_name)
    
    def set_approval_callback(
        self, 
        callback: Callable[[ApprovalRequest], ApprovalResult]
    ) -> None:
        """승인 콜백 설정 (GUI/API 연동용)"""
        self.approval_callback = callback
