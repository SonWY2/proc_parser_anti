"""
트레이싱 래퍼

LangGraph 노드를 자동으로 모니터링하도록 래핑합니다.
"""

import os
from typing import Any, Dict, Callable, Optional
from dataclasses import dataclass
import logging

from .pipeline_monitor import PipelineMonitor

logger = logging.getLogger(__name__)


@dataclass
class TracingConfig:
    """
    트레이싱 설정
    
    Attributes:
        enable_langsmith: LangSmith 트레이싱 활성화
        enable_local: 로컬 PipelineMonitor 활성화
        verbose: 실시간 로그 출력
        project_name: LangSmith 프로젝트 이름
    """
    enable_langsmith: bool = False
    enable_local: bool = True
    verbose: bool = True
    project_name: str = "migration-pipeline"
    
    @classmethod
    def from_env(cls) -> "TracingConfig":
        """환경 변수에서 설정 로드"""
        return cls(
            enable_langsmith=os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true",
            enable_local=os.getenv("LOCAL_TRACING", "true").lower() == "true",
            verbose=os.getenv("TRACING_VERBOSE", "true").lower() == "true",
            project_name=os.getenv("LANGCHAIN_PROJECT", "migration-pipeline"),
        )


def wrap_with_tracing(
    node_func: Callable,
    node_name: str,
    monitor: PipelineMonitor = None,
    config: TracingConfig = None,
) -> Callable:
    """
    노드 함수에 트레이싱 래핑
    
    Args:
        node_func: 원본 노드 함수
        node_name: 노드 이름 (로깅용)
        monitor: PipelineMonitor 인스턴스
        config: TracingConfig 설정
        
    Returns:
        래핑된 함수
        
    사용법:
        from .monitoring import wrap_with_tracing, PipelineMonitor
        
        monitor = PipelineMonitor()
        
        wrapped_parser = wrap_with_tracing(parser_node, "Parser", monitor)
        wrapped_critic = wrap_with_tracing(critic_node, "Critic", monitor)
        
        # Graph에 래핑된 함수 등록
        workflow.add_node("Parser", wrapped_parser)
    """
    if config is None:
        config = TracingConfig.from_env()
    
    if monitor is None and config.enable_local:
        monitor = PipelineMonitor(verbose=config.verbose)
    
    def wrapped(state: Dict[str, Any], *args, **kwargs) -> Dict[str, Any]:
        # 로컬 모니터링
        if monitor and config.enable_local:
            monitor._on_node_start(node_name, state, {})
            try:
                result = node_func(state, *args, **kwargs)
                monitor._on_node_end(node_name, state, result)
                return result
            except Exception as e:
                monitor._on_node_error(node_name, e)
                raise
        else:
            return node_func(state, *args, **kwargs)
    
    # 함수 이름 보존
    wrapped.__name__ = node_func.__name__
    wrapped.__doc__ = node_func.__doc__
    
    return wrapped


def create_monitored_graph(llm=None, monitor: PipelineMonitor = None):
    """
    모니터링이 적용된 마이그레이션 그래프 생성
    
    Args:
        llm: LLM 인스턴스
        monitor: PipelineMonitor 인스턴스 (없으면 새로 생성)
        
    Returns:
        tuple: (compiled_graph, monitor)
        
    사용법:
        from infra.agents.langchain.monitoring import create_monitored_graph
        
        graph, monitor = create_monitored_graph(llm)
        
        result = graph.invoke(initial_state)
        
        monitor.print_summary()
        monitor.export_html_report("report.html")
    """
    from langgraph.graph import StateGraph, END
    from ..state import MigrationState
    from ..orchestration.migration_graph import (
        parser_node,
        critic_node,
        draftsman_node,
        specialist_node,
        designer_node,
        check_validation,
    )
    
    if monitor is None:
        monitor = PipelineMonitor(verbose=True)
    
    # 노드 래핑
    wrapped_parser = wrap_with_tracing(parser_node, "Parser", monitor)
    wrapped_critic = wrap_with_tracing(critic_node, "Critic", monitor)
    wrapped_draftsman = wrap_with_tracing(draftsman_node, "Draftsman", monitor)
    
    # LLM 노드는 클로저로 처리
    def wrapped_specialist(state):
        monitor._on_node_start("Specialist", state, {"uses_llm": True})
        try:
            result = specialist_node(state, llm)
            monitor._on_node_end("Specialist", state, result)
            return result
        except Exception as e:
            monitor._on_node_error("Specialist", e)
            raise
    
    def wrapped_designer(state):
        monitor._on_node_start("Designer", state, {"uses_llm": True})
        try:
            result = designer_node(state, llm)
            monitor._on_node_end("Designer", state, result)
            return result
        except Exception as e:
            monitor._on_node_error("Designer", e)
            raise
    
    # Graph 구성
    workflow = StateGraph(MigrationState)
    
    workflow.add_node("Parser", wrapped_parser)
    workflow.add_node("Critic", wrapped_critic)
    workflow.add_node("Draftsman", wrapped_draftsman)
    workflow.add_node("Specialist", wrapped_specialist)
    workflow.add_node("Designer", wrapped_designer)
    
    workflow.add_edge("Parser", "Critic")
    workflow.add_conditional_edges(
        "Critic",
        check_validation,
        {"STOP": END, "CONTINUE": "Draftsman"}
    )
    workflow.add_edge("Draftsman", "Specialist")
    workflow.add_edge("Specialist", "Designer")
    workflow.add_edge("Designer", END)
    
    workflow.set_entry_point("Parser")
    
    return workflow.compile(), monitor


def setup_langsmith_tracing(project_name: str = "migration-pipeline"):
    """
    LangSmith 트레이싱 설정
    
    환경 변수를 설정하여 LangSmith 자동 트레이싱을 활성화합니다.
    
    Args:
        project_name: LangSmith 프로젝트 이름
        
    참고:
        다음 환경 변수가 필요합니다:
        - LANGCHAIN_API_KEY: LangSmith API 키
        - LANGCHAIN_ENDPOINT: (선택) LangSmith 엔드포인트
    """
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = project_name
    
    api_key = os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        logger.warning(
            "LANGCHAIN_API_KEY가 설정되지 않았습니다. "
            "LangSmith 트레이싱이 작동하지 않을 수 있습니다."
        )
    else:
        logger.info(f"LangSmith 트레이싱 활성화: 프로젝트={project_name}")
