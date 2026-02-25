"""LangGraph orchestration for Pro*C -> Java conversion."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

try:
    from langgraph.graph import END, StateGraph
    HAS_LANGGRAPH = True
except ImportError:  # pragma: no cover
    END = "END"
    StateGraph = None
    HAS_LANGGRAPH = False

from agents.analysis_agent import run_analysis
from agents.java_spring_agent import run_java_conversion
from agents.mybatis_agent import run_mybatis_generation
from agents.report_agent import run_report
from infra.agents.langchain.state import ConversionState


def analysis_node(state: ConversionState) -> Dict[str, Any]:
    try:
        return run_analysis(state)
    except Exception as exc:
        return {"errors": state.get("errors", []) + [f"analysis node failed: {exc}"]}


def parallel_conversion_node(state: ConversionState) -> Dict[str, Any]:
    errors = list(state.get("errors", []))

    with ThreadPoolExecutor(max_workers=2) as executor:
        java_future = executor.submit(run_java_conversion, state)
        mybatis_future = executor.submit(run_mybatis_generation, state)

        java_result = java_future.result()
        mybatis_result = mybatis_future.result()

    errors.extend(java_result.get("errors", []))
    errors.extend(mybatis_result.get("errors", []))

    return {
        "java_result": java_result.get("java_result", {}),
        "mybatis_result": mybatis_result.get("mybatis_result", {}),
        "errors": errors,
    }


def report_node(state: ConversionState) -> Dict[str, Any]:
    try:
        return run_report(state)
    except Exception as exc:
        return {"errors": state.get("errors", []) + [f"report node failed: {exc}"]}


class _FallbackCompiledGraph:
    """langgraph 미설치 환경을 위한 순차 실행 fallback."""

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(state)
        merged.update(analysis_node(merged))
        merged.update(parallel_conversion_node(merged))
        merged.update(report_node(merged))
        return merged


def build_conversion_graph():
    if not HAS_LANGGRAPH:
        return _FallbackCompiledGraph()

    workflow = StateGraph(ConversionState)
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("conversion", parallel_conversion_node)
    workflow.add_node("report", report_node)

    workflow.set_entry_point("analysis")
    workflow.add_edge("analysis", "conversion")
    workflow.add_edge("conversion", "report")
    workflow.add_edge("report", END)
    return workflow.compile()
