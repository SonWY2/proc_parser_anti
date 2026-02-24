"""
LangChain Multi-Agent System (lang_chain_agents)

LangGraph 기반 멀티 에이전트 시스템으로 Pro*C to Java 변환을 지원합니다.

세 가지 오케스트레이션 모드:
- Dynamic: Reflection + Self-Evolve 기반 동적 오케스트레이션
- Static: 미리 정의된 워크플로우 기반 실행
- Migration: 5개 Subagent 파이프라인 (Parser→Critic→Draftsman→Specialist→Designer)
"""

from .config import LLMConfig
from .state import AgentState, DynamicAgentState, MigrationState, create_migration_state
from .memory import EpisodicMemory, Episode
from .orchestrator import LangChainOrchestrator
from .agents.base import AgentConfig, AgentFactory

# 동적 오케스트레이션
from .orchestration.manager import DynamicManager
from .orchestration.planner import Planner
from .orchestration.reflector import Reflector
from .orchestration.router import Router

# 정적 워크플로우
from .workflows.base import BaseWorkflow, WorkflowStep
from .workflows.proc_to_java import PROC_TO_JAVA_WORKFLOW

# 마이그레이션 파이프라인
from .skills import BaseSkill, SkillResult, SkillsRegistry, get_tools_map
from .subagents import SubagentLoader, SubagentConfig

__version__ = "0.2.0"

__all__ = [
    # Core
    "LLMConfig",
    "AgentState",
    "DynamicAgentState",
    "MigrationState",
    "create_migration_state",
    "EpisodicMemory",
    "Episode",
    "LangChainOrchestrator",
    "AgentConfig",
    "AgentFactory",
    # Dynamic Orchestration
    "DynamicManager",
    "Planner",
    "Reflector",
    "Router",
    # Static Workflow
    "BaseWorkflow",
    "WorkflowStep",
    "PROC_TO_JAVA_WORKFLOW",
    # Migration Pipeline
    "BaseSkill",
    "SkillResult",
    "SkillsRegistry",
    "get_tools_map",
    "SubagentLoader",
    "SubagentConfig",
]
