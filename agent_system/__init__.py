"""
서브에이전트 시스템 (v3)

Claude Code 스타일의 서브에이전트를 구현합니다.
.md 파일로 에이전트를 정의하고, 독립 컨텍스트에서 실행됩니다.
"""

from .agent_loader import AgentLoader, AgentDefinition, OrchestratorDefinition, DelegateRule
from .tools import (
    ToolRegistry, Tool, ToolResult,
    ReadTool, GrepTool, GlobTool, BashTool, EditTool, WriteTool,
    TreeTool, DiffTool, ListDirTool, SearchReplaceTool
)
from .subagent import Subagent
from .orchestrator import Orchestrator
from .result import SubagentResult, ToolCallRecord
from .llm_client import LLMClient, LLMConfig

# v1 모듈
from .security import FileAccessControl, CommandSandbox, SecurityManager
from .workflow import (
    WorkflowEngine, WorkflowStep, WorkflowResult, WorkflowDefinition,
    ParallelGroup, MAX_PARALLEL_AGENTS
)
from .memory import SimpleMemory, MemoryEntry, ConversationMemory

# v3 모듈
from .hooks import HookRegistry, HookEvent, HookResult, HookContext, HookResponse
from .validator import (
    QualityGateValidator, QualityGate, ValidationResult,
    CompletionVerifier, VerificationRule, VerificationResult
)
from .checkpoint import (
    CheckpointManager, Checkpoint, CheckpointType,
    WorkflowState, ApprovalRequest, ApprovalResult
)
from .file_mediator import FileMediator, IntermediateArtifact
from .commands import CommandRegistry, SlashCommand
from .cli import InteractiveCLI, run_cli
from .gui import WorkflowGUI, run_gui
from .self_improve import SelfImprovingChecklist, Issue, ChecklistItem


__all__ = [
    # 에이전트 로더
    'AgentLoader', 'AgentDefinition', 'OrchestratorDefinition', 'DelegateRule',
    
    # 도구
    'ToolRegistry', 'Tool', 'ToolResult',
    'ReadTool', 'GrepTool', 'GlobTool', 'BashTool', 'EditTool', 'WriteTool',
    'TreeTool', 'DiffTool', 'ListDirTool', 'SearchReplaceTool',
    
    # 서브에이전트
    'Subagent', 'Orchestrator', 'SubagentResult', 'ToolCallRecord',
    
    # LLM
    'LLMClient', 'LLMConfig',
    
    # 보안
    'FileAccessControl', 'CommandSandbox', 'SecurityManager',
    
    # 워크플로우
    'WorkflowEngine', 'WorkflowStep', 'WorkflowResult', 'WorkflowDefinition',
    'ParallelGroup', 'MAX_PARALLEL_AGENTS',
    
    # 메모리
    'SimpleMemory', 'MemoryEntry', 'ConversationMemory',
    
    # v3: 훅
    'HookRegistry', 'HookEvent', 'HookResult', 'HookContext', 'HookResponse',
    
    # v3: 품질 게이트
    'QualityGateValidator', 'QualityGate', 'ValidationResult',
    'CompletionVerifier', 'VerificationRule', 'VerificationResult',
    
    # v3: 체크포인트
    'CheckpointManager', 'Checkpoint', 'CheckpointType',
    'WorkflowState', 'ApprovalRequest', 'ApprovalResult',
    
    # v3: 파일 매개체
    'FileMediator', 'IntermediateArtifact',
    
    # v3: 슬래시 명령어
    'CommandRegistry', 'SlashCommand',
    
    # v3: UI
    'InteractiveCLI', 'run_cli',
    'WorkflowGUI', 'run_gui',
    
    # v3: 자가개선
    'SelfImprovingChecklist', 'Issue', 'ChecklistItem',
]

