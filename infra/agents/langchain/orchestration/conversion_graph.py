"""LangGraph orchestration for Pro*C -> Java conversion."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import importlib
from importlib import util as importlib_util
import os
import json
import time
from uuid import uuid4
from typing import Any, Dict, TypedDict, cast

from ..llm_trace import log_llm_trace, llm_trace_content_enabled, sanitize_url


class ConversionGraphState(TypedDict, total=False):
    header_paths: list[str]
    proc_paths: list[str]
    output_dir: str
    strategy: str
    knowledge_doc: str | None
    analysis_result: dict[str, Any]
    ast_by_file: dict[str, dict[str, Any]]
    source_by_file: dict[str, str]
    conversion_plan: dict[str, Any]
    java_result: dict[str, Any]
    mybatis_result: dict[str, Any]
    ast_validation_result: dict[str, Any]
    parser_validation_result: dict[str, Any]
    validation_result: dict[str, Any]
    supplement_result: dict[str, Any]
    validation_history: list[dict[str, Any]]
    planning_notes: list[str]
    report_path: str
    graph_mode: str
    iteration_count: int
    max_iterations: int
    errors: list[str]


class KnowledgeContext(TypedDict):
    loaded: bool
    path: str | None
    priorities: list[str]
    forbidden: list[str]
    rules: list[str]
    excerpt: str


try:
    from langgraph.graph import END as _GRAPH_END, StateGraph

    graph_end = _GRAPH_END
    has_langgraph = True
except ImportError:  # pragma: no cover
    graph_end = "END"
    StateGraph = None
    has_langgraph = False


def _env_true(name: str, default: bool = False) -> bool:
    fallback = "true" if default else "false"
    return os.getenv(name, fallback).strip().lower() in {"1", "true", "yes"}


def _resolve_graph_mode() -> str:
    mode = os.getenv("CONVERSION_GRAPH_MODE", "legacy").strip().lower()
    return "md" if mode == "md" else "legacy"


def _resolve_max_iterations(state: ConversionGraphState) -> int:
    explicit = state.get("max_iterations")
    if isinstance(explicit, int) and explicit >= 0:
        return explicit
    raw = os.getenv("CONVERSION_SUPPLEMENT_MAX_ITER", "1")
    try:
        return max(0, int(raw))
    except ValueError:
        return 1


def _strict_llm_validation(state: ConversionGraphState) -> bool:
    explicit = os.getenv("CONVERSION_VALIDATE_STRICT")
    if explicit is None:
        return state.get("graph_mode", _resolve_graph_mode()) == "md"
    return explicit.strip().lower() in {"1", "true", "yes"}


def _validator_debug_enabled() -> bool:
    return _env_true("CONVERSION_LLM_VALIDATOR_DEBUG", default=False)


def analysis_node(state: ConversionGraphState) -> Dict[str, Any]:
    try:
        run_analysis = importlib.import_module("agents.analysis_agent").run_analysis
        return run_analysis(state)
    except Exception as exc:
        return {"errors": state.get("errors", []) + [f"analysis node failed: {exc}"]}


def _append_unique(values: list[str], text: str) -> None:
    message = text.strip()
    if message and message not in values:
        values.append(message)


def _extract_knowledge_context(knowledge_doc: str | None) -> KnowledgeContext:
    context: KnowledgeContext = {
        "loaded": False,
        "path": knowledge_doc,
        "priorities": [],
        "forbidden": [],
        "rules": [],
        "excerpt": "",
    }
    if not knowledge_doc:
        return context

    try:
        text = Path(knowledge_doc).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return context

    context["loaded"] = True
    context["excerpt"] = text[:2000]

    section = "rules"
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#"):
            header = line.lstrip("#").strip().lower()
            if any(
                keyword in header
                for keyword in ["priority", "우선", "must", "필수", "중요"]
            ):
                section = "priorities"
            elif any(
                keyword in header
                for keyword in ["forbidden", "금지", "avoid", "금칙", "do not"]
            ):
                section = "forbidden"
            else:
                section = "rules"
            continue

        upper = line.upper()
        if upper.startswith(("P:", "PRIORITY:", "MUST:")):
            _append_unique(context["priorities"], line.split(":", 1)[1].strip())
            continue
        if upper.startswith(("F:", "FORBID:", "FORBIDDEN:", "DONT:", "DON'T:")):
            _append_unique(context["forbidden"], line.split(":", 1)[1].strip())
            continue
        if upper.startswith(("R:", "RULE:", "GUIDELINE:")):
            _append_unique(context["rules"], line.split(":", 1)[1].strip())
            continue

        content = line
        if line.startswith(("-", "*")):
            content = line[1:].strip()
        elif "." in line and line.split(".", 1)[0].isdigit():
            content = line.split(".", 1)[1].strip()

        _append_unique(context[section], content)

    context["priorities"] = context["priorities"][:20]
    context["forbidden"] = context["forbidden"][:20]
    context["rules"] = context["rules"][:30]
    return context


def _default_plan(
    state: ConversionGraphState, knowledge: KnowledgeContext
) -> Dict[str, Any]:
    analysis = state.get("analysis_result") or {}
    stats = analysis.get("stats", {})
    strategy = state.get("strategy", "preserve")
    knowledge_doc = state.get("knowledge_doc")
    steps = [
        "Pro*C를 파싱하고 메타데이터를 정규화한다",
        "파서 결과를 규칙 기반/LLM 기반으로 검증한다",
        "결정론적 Java/MyBatis 산출물을 생성한다",
        "LLM SQL 검증으로 변환 품질을 점검한다",
        "검증 실패 시 LLM 보완 후 재검증 루프를 수행한다",
        "검증 결과를 포함한 마이그레이션 리포트를 생성한다",
    ]
    if strategy == "refactor":
        steps.insert(3, "리팩터링 친화적인 네이밍과 컴포넌트 분리를 우선 적용한다")
    if knowledge_doc:
        steps.append("보완 단계에서 지식 문서의 도메인 규칙을 적용한다")
    if knowledge.get("priorities"):
        steps.insert(2, "생성 전에 우선순위 규칙을 먼저 적용한다")
    if knowledge.get("forbidden"):
        steps.insert(3, "금지 규칙을 하드 제약으로 강제한다")

    return {
        "mode": "deterministic",
        "strategy": strategy,
        "knowledge_doc": knowledge_doc,
        "knowledge": {
            "loaded": bool(knowledge.get("loaded")),
            "priority_count": len(knowledge.get("priorities", [])),
            "forbidden_count": len(knowledge.get("forbidden", [])),
            "rule_count": len(knowledge.get("rules", [])),
        },
        "stats": {
            "file_count": stats.get("file_count", 0),
            "sql_count": stats.get("sql_count", 0),
        },
        "steps": steps,
    }


def _llm_plan(
    state: ConversionGraphState,
    fallback_plan: Dict[str, Any],
    knowledge: KnowledgeContext,
) -> Dict[str, Any]:
    import requests

    if not _env_true("CONVERSION_PLAN_WITH_LLM", default=False):
        return {"plan": fallback_plan, "warning": "llm planner disabled"}
    if _env_true("VLLM_MOCK", default=True):
        return {"plan": fallback_plan, "warning": "llm planner skipped in mock mode"}

    endpoint = os.getenv("VLLM_API_ENDPOINT", "http://localhost:8000/v1").rstrip("/")
    endpoint_for_log = sanitize_url(endpoint)
    model = os.getenv("VLLM_MODEL", "mock-model")
    api_key = os.getenv("VLLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    analysis = state.get("analysis_result") or {}
    knowledge_payload = {
        "priorities": knowledge.get("priorities", []),
        "forbidden": knowledge.get("forbidden", []),
        "rules": knowledge.get("rules", []),
    }

    prompt = (
        "키가 'steps'인 JSON(문자열 배열)으로 간결한 마이그레이션 계획을 작성하세요.\n"
        "모든 steps는 한국어 문장으로 작성하세요.\n"
        "파서 우선 전환, 결정론적 생성 우선, LLM은 검증/보완에만 사용하세요.\n"
        "금지 규칙은 절대 위반하면 안 됩니다.\n"
        "우선순위 규칙을 일반 규칙보다 먼저 적용하세요.\n"
        f"Strategy: {state.get('strategy', 'preserve')}\n"
        f"Analysis stats: {analysis.get('stats', {})}\n"
        f"Structured knowledge: {json.dumps(knowledge_payload, ensure_ascii=False)}\n"
        f"Knowledge excerpt: {knowledge.get('excerpt', '')}"
    )

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 600,
    }

    started = time.perf_counter()
    include_content = llm_trace_content_enabled()
    trace_id = f"planner-{uuid4().hex[:10]}"
    planner_request_payload: dict[str, Any] = {
        "endpoint": endpoint_for_log,
        "model": model,
        "temperature": payload["temperature"],
        "max_tokens": payload["max_tokens"],
        "prompt_chars": len(prompt),
        "knowledge_loaded": bool(knowledge.get("loaded", False)),
        "stage": "planner",
        "trace_id": trace_id,
    }
    if include_content:
        planner_request_payload["prompt_preview"] = prompt
    log_llm_trace(
        component="planner",
        event="request",
        payload=planner_request_payload,
    )
    try:
        response = requests.post(
            f"{endpoint}/chat/completions",
            headers=headers,
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        log_llm_trace(
            component="planner",
            event="error",
            payload={
                "endpoint": endpoint_for_log,
                "model": model,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "error": str(exc),
                "stage": "planner",
                "trace_id": trace_id,
            },
        )
        raise
    planner_response_payload: dict[str, Any] = {
        "endpoint": endpoint_for_log,
        "model": model,
        "status_code": response.status_code,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "response_chars": len(str(content)),
        "stage": "planner",
        "trace_id": trace_id,
    }
    if include_content:
        planner_response_payload["response_preview"] = str(content)
    log_llm_trace(
        component="planner",
        event="response",
        payload=planner_response_payload,
    )

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            parsed = json.loads(content[start : end + 1])
        else:
            parsed = {}

    plan = dict(fallback_plan)
    llm_steps = parsed.get("steps") if isinstance(parsed, dict) else None
    if isinstance(llm_steps, list):
        normalized = [str(step).strip() for step in llm_steps if str(step).strip()]
        if normalized:
            plan["mode"] = "llm-assisted"
            plan["steps"] = normalized
    return {"plan": plan}


def planning_node(state: ConversionGraphState) -> Dict[str, Any]:
    knowledge = _extract_knowledge_context(state.get("knowledge_doc"))
    fallback_plan = _default_plan(state, knowledge)
    graph_mode = state.get("graph_mode", _resolve_graph_mode())
    max_iterations = _resolve_max_iterations(state)
    try:
        llm_result = _llm_plan(state, fallback_plan, knowledge)
        plan = llm_result.get("plan", fallback_plan)
        warning = llm_result.get("warning")
        notes = [f"planning note: {warning}"] if warning else []
    except Exception as exc:
        plan = fallback_plan
        notes = [f"planning fallback used: {exc}"]

    return {
        "conversion_plan": plan,
        "planning_notes": notes,
        "graph_mode": graph_mode,
        "max_iterations": max_iterations,
        "iteration_count": int(state.get("iteration_count", 0)),
    }


def ast_validation_node(state: ConversionGraphState) -> Dict[str, Any]:
    ast_by_file = state.get("ast_by_file") or {}
    errors_by_file: dict[str, list[str]] = {}
    all_errors: list[str] = []

    try:
        validator_cls = importlib.import_module(
            "infra.agents.langchain.skills.validate_ast"
        ).ValidateAstSkill
        validator = validator_cls()
    except Exception as exc:
        message = f"ast validator unavailable: {exc}"
        strict = _strict_llm_validation(state)
        return {
            "ast_validation_result": {
                "passed": not strict,
                "error_count": 1 if strict else 0,
                "errors": [message] if strict else [],
                "errors_by_file": {},
                "warnings": [message] if not strict else [],
            }
        }

    for file_path, ast_data in ast_by_file.items():
        file_errors: list[str] = []
        try:
            result = validator.invoke(ast_data)
            if result.data and isinstance(result.data, dict):
                for err in result.data.get("errors", []):
                    _append_unique(file_errors, str(err))
            if result.errors:
                for err in result.errors:
                    _append_unique(file_errors, str(err))
        except Exception as exc:
            _append_unique(file_errors, f"validator exception: {exc}")

        errors_by_file[file_path] = file_errors
        for err in file_errors:
            _append_unique(all_errors, f"{Path(file_path).name}: {err}")

    return {
        "ast_validation_result": {
            "passed": len(all_errors) == 0,
            "error_count": len(all_errors),
            "errors": all_errors,
            "errors_by_file": errors_by_file,
            "warnings": [],
        }
    }


def _flatten_ast_elements(ast_data: dict[str, Any]) -> list[dict[str, Any]]:
    elements: list[dict[str, Any]] = []
    for category in (
        "headers",
        "host_vars",
        "sql_blocks",
        "functions",
        "macros",
        "structs",
    ):
        values = ast_data.get(category, [])
        if not isinstance(values, list):
            continue
        for item in values:
            if isinstance(item, dict):
                enriched = dict(item)
                enriched.setdefault("category", category)
                elements.append(enriched)
    return elements


def _format_parser_issue(issue: dict[str, Any]) -> str:
    element_id = str(issue.get("element_id") or issue.get("element") or "unknown")
    issue_text = str(issue.get("issue") or "parser validation issue").strip()
    return f"{element_id}: {issue_text}"


def _extract_missing_text(ast_data: dict[str, Any]) -> str:
    unknown_segments = ast_data.get("unknown_segments") or []
    lines: list[str] = []
    for segment in unknown_segments:
        content = str(segment.get("content") or "").strip()
        if not content:
            continue
        start = segment.get("line_start")
        prefix = f"line {start}: " if start else ""
        lines.append(prefix + content)
    return "\n".join(lines)


def _build_parser_chunks(
    state: ConversionGraphState,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    chunks: list[dict[str, Any]] = []
    ast_by_file = state.get("ast_by_file") or {}
    source_by_file = state.get("source_by_file") or {}

    splitter = None
    splitter_error: str | None = None
    try:
        splitter_cls = importlib.import_module(
            "infra.agents.langchain.skills.scope_splitter"
        ).ScopeSplitterSkill
        splitter = splitter_cls()
    except Exception as exc:
        splitter_error = str(exc)

    for file_path in state.get("proc_paths", []):
        source = source_by_file.get(file_path)
        if source is None:
            try:
                source = Path(file_path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                source = ""

        ast_data = ast_by_file.get(file_path, {})
        missing_text = _extract_missing_text(ast_data)
        split_result = None
        if splitter is not None:
            try:
                split_result = splitter.invoke(
                    {
                        "source_code": source,
                        "metadata": ast_data,
                    }
                )
            except Exception as exc:
                _append_unique(
                    warnings,
                    f"scope split failed for {Path(file_path).name}: {exc}",
                )
        else:
            _append_unique(
                warnings,
                "scope splitter unavailable: " + (splitter_error or "unknown error"),
            )

        if split_result and split_result.success:
            payload = split_result.data or {}
            split_chunks = payload.get("chunks", [])
            for item in split_chunks:
                chunk = dict(item)
                chunk["source_file"] = file_path
                chunk["remaining_code"] = missing_text
                chunks.append(chunk)
            continue

        _append_unique(
            warnings, f"scope split fallback used for {Path(file_path).name}"
        )
        chunks.append(
            {
                "scope": f"file_{Path(file_path).stem}",
                "source_file": file_path,
                "code": source,
                "elements": _flatten_ast_elements(ast_data),
                "remaining_code": missing_text,
            }
        )

    return chunks, warnings


def parser_llm_validation_node(state: ConversionGraphState) -> Dict[str, Any]:
    enabled = _env_true("CONVERSION_VALIDATE_WITH_LLM", default=False)
    strict = _strict_llm_validation(state)
    warnings: list[str] = []
    issues: list[str] = []
    result: dict[str, Any] = {
        "enabled": enabled,
        "strict_mode": strict,
        "attempted": False,
        "success": False,
        "chunk_count": 0,
        "missing_count": 0,
        "wrong_count": 0,
        "reclassification_count": 0,
        "missing_issues": [],
        "wrong_issues": [],
        "reclassifications": [],
        "warnings": warnings,
        "issues": issues,
        "passed": True,
    }

    if not enabled:
        _append_unique(warnings, "parser llm validation disabled")
        log_llm_trace(
            component="validator",
            event="parser.skipped",
            payload={"reason": "disabled", "stage": "parser_validation"},
        )
        return {"parser_validation_result": result}

    chunks, chunk_warnings = _build_parser_chunks(state)
    result["chunk_count"] = len(chunks)
    for item in chunk_warnings:
        _append_unique(warnings, item)

    if not chunks:
        _append_unique(warnings, "parser llm validation enabled but no chunks")
        if strict:
            _append_unique(issues, "parser llm validation failed: no chunks")
            result["passed"] = False
        log_llm_trace(
            component="validator",
            event="parser.skipped",
            payload={
                "reason": "no_chunks",
                "strict_mode": strict,
                "stage": "parser_validation",
            },
        )
        return {"parser_validation_result": result}

    if importlib_util.find_spec("langchain_openai") is None:
        _append_unique(
            warnings, "parser llm validation skipped: langchain_openai not installed"
        )
        if strict:
            _append_unique(
                issues,
                "parser llm validation required but skipped (langchain_openai missing)",
            )
            result["passed"] = False
        log_llm_trace(
            component="validator",
            event="parser.skipped",
            payload={
                "reason": "langchain_openai_missing",
                "strict_mode": strict,
                "stage": "parser_validation",
            },
        )
        return {"parser_validation_result": result}

    result["attempted"] = True
    try:
        validator_cls = importlib.import_module(
            "infra.agents.langchain.skills.llm_validator"
        ).LLMValidatorSkill
        validator_debug = _validator_debug_enabled()
        validator_debug_file = os.getenv(
            "CONVERSION_LLM_VALIDATOR_DEBUG_LOG",
            "output/llm_trace/validator_parser.log",
        )
        validator = validator_cls(
            debug=validator_debug,
            debug_file=validator_debug_file if validator_debug else None,
        )
        batch_size_raw = os.getenv("CONVERSION_VALIDATE_LLM_BATCH_SIZE", "20")
        try:
            batch_size = max(1, int(batch_size_raw))
        except ValueError:
            batch_size = 20

        log_llm_trace(
            component="validator",
            event="parser.request",
            payload={
                "chunk_count": len(chunks),
                "batch_size": batch_size,
                "strict_mode": strict,
                "stage": "parser_validation",
            },
        )
        llm_result = validator.invoke(
            {
                "mode": "parser",
                "chunks": chunks,
                "batch_size": batch_size,
                "debug": validator_debug,
                "debug_file": validator_debug_file if validator_debug else None,
            }
        )

        if llm_result.success:
            payload = llm_result.data or {}
            result["success"] = True
            result["missing_count"] = int(payload.get("missing_count", 0))
            result["wrong_count"] = int(payload.get("wrong_count", 0))
            result["reclassification_count"] = int(
                payload.get("reclassification_count", 0)
            )
            result["missing_issues"] = list(payload.get("missing_issues", []))
            result["wrong_issues"] = list(payload.get("wrong_issues", []))
            result["reclassifications"] = list(payload.get("reclassifications", []))

            for issue in result["wrong_issues"]:
                _append_unique(issues, _format_parser_issue(issue))
            for missing in result["missing_issues"]:
                missing_type = str(missing.get("type", "UNKNOWN"))
                content = str(missing.get("content", "")).strip()
                _append_unique(issues, f"missing[{missing_type}] {content}")
            log_llm_trace(
                component="validator",
                event="parser.response",
                payload={
                    "success": True,
                    "missing_count": result["missing_count"],
                    "wrong_count": result["wrong_count"],
                    "reclassification_count": result["reclassification_count"],
                    "stage": "parser_validation",
                },
            )
        else:
            _append_unique(
                warnings,
                "parser llm validation invocation failed: "
                + "; ".join(str(err) for err in llm_result.errors),
            )
            if strict:
                _append_unique(issues, "parser llm validation invocation failed")
            log_llm_trace(
                component="validator",
                event="parser.response",
                payload={
                    "success": False,
                    "errors": [str(err) for err in llm_result.errors],
                    "stage": "parser_validation",
                },
            )
    except Exception as exc:
        _append_unique(warnings, f"parser llm validation exception: {exc}")
        if strict:
            _append_unique(issues, "parser llm validation exception")
        log_llm_trace(
            component="validator",
            event="parser.error",
            payload={"error": str(exc), "stage": "parser_validation"},
        )

    result["passed"] = len(issues) == 0
    if result["attempted"] and not result["success"] and not issues:
        result["passed"] = False
    return {"parser_validation_result": result}


def _build_llm_sql_candidates(
    analysis_result: dict[str, Any], mybatis_result: dict[str, Any]
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for block in analysis_result.get("sql_blocks", []):
        sql_id = str(block.get("id", "")).strip()
        sql_type = str(block.get("sql_type", "unknown")).lower()
        original = str(block.get("sql") or "")
        converted = str(block.get("parsed_sql") or block.get("sql") or "")
        if sql_type in {"begin", "end", "include", "declare"}:
            continue
        if not converted.strip() and not original.strip():
            continue
        candidates.append(
            {
                "sql_id": sql_id or f"sql_{len(candidates) + 1}",
                "sql_type": sql_type,
                "original": original,
                "converted": converted or original,
                "success": True,
            }
        )

    if candidates:
        return candidates

    for xml_path in mybatis_result.get("xml_files", []):
        path = Path(str(xml_path))
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")[:4000]
        except OSError:
            continue
        if not content.strip():
            continue
        candidates.append(
            {
                "sql_id": path.stem,
                "sql_type": "xml",
                "original": "generated mapper xml",
                "converted": content,
                "success": True,
                "note": "conversion_graph_xml_candidate",
            }
        )

    return candidates


def parallel_conversion_node(state: ConversionGraphState) -> Dict[str, Any]:
    base_errors = list(state.get("errors", []))
    run_java_conversion = importlib.import_module(
        "agents.java_spring_agent"
    ).run_java_conversion
    run_mybatis_generation = importlib.import_module(
        "agents.mybatis_agent"
    ).run_mybatis_generation

    with ThreadPoolExecutor(max_workers=2) as executor:
        java_future = executor.submit(run_java_conversion, state)
        mybatis_future = executor.submit(run_mybatis_generation, state)

        java_result = java_future.result()
        mybatis_result = mybatis_future.result()

    merged_errors: list[str] = []
    for item in (
        base_errors + java_result.get("errors", []) + mybatis_result.get("errors", [])
    ):
        text = str(item)
        if text and text not in merged_errors:
            merged_errors.append(text)

    return {
        "java_result": java_result.get("java_result", {}),
        "mybatis_result": mybatis_result.get("mybatis_result", {}),
        "errors": merged_errors,
    }


def validation_node(state: ConversionGraphState) -> Dict[str, Any]:
    analysis_result = state.get("analysis_result") or {}
    java_result = state.get("java_result") or {}
    mybatis_result = state.get("mybatis_result") or {}
    ast_validation = state.get("ast_validation_result") or {}
    parser_validation = state.get("parser_validation_result") or {}

    warnings: list[str] = []
    issues: list[str] = []

    for warning in parser_validation.get("warnings", []):
        _append_unique(warnings, f"[parser] {warning}")
    for issue in parser_validation.get("issues", []):
        _append_unique(issues, f"[parser] {issue}")
    for ast_issue in ast_validation.get("errors", []):
        _append_unique(issues, f"[ast] {ast_issue}")
    for ast_warning in ast_validation.get("warnings", []):
        _append_unique(warnings, f"[ast] {ast_warning}")

    expected_services = len(analysis_result.get("files", []))
    generated_services = len(java_result.get("java_files", []))
    expected_sql = len(analysis_result.get("sql_blocks", []))
    generated_xml = len(mybatis_result.get("xml_files", []))

    if generated_services < expected_services:
        _append_unique(
            issues,
            f"java services generated {generated_services}/{expected_services}",
        )
    if expected_sql > 0 and generated_xml == 0:
        _append_unique(issues, "sql blocks exist but no mybatis xml generated")

    if (
        java_result.get("llm_gap_fill_enabled")
        and java_result.get("llm_gap_fill_applied", 0) == 0
    ):
        _append_unique(warnings, "llm gap-fill enabled but no file applied")

    llm_validation_enabled = _env_true("CONVERSION_VALIDATE_WITH_LLM", default=False)
    strict_mode = _strict_llm_validation(state)
    llm_meta: dict[str, Any] = {
        "enabled": llm_validation_enabled,
        "strict_mode": strict_mode,
        "attempted": False,
        "success": False,
        "candidate_count": 0,
        "feedback_summary": "",
        "required_but_skipped": False,
    }

    if llm_validation_enabled:
        llm_meta["attempted"] = True
        candidates = _build_llm_sql_candidates(analysis_result, mybatis_result)
        llm_meta["candidate_count"] = len(candidates)

        if candidates:
            if importlib_util.find_spec("langchain_openai") is None:
                _append_unique(
                    warnings,
                    "llm validation skipped: langchain_openai not installed",
                )
                llm_meta["attempted"] = False
                llm_meta["required_but_skipped"] = bool(strict_mode)
                if strict_mode:
                    _append_unique(
                        issues,
                        "llm validation required but skipped (langchain_openai missing)",
                    )
                log_llm_trace(
                    component="validator",
                    event="sql.skipped",
                    payload={
                        "reason": "langchain_openai_missing",
                        "candidate_count": len(candidates),
                        "strict_mode": strict_mode,
                        "stage": "sql_validation",
                    },
                )
            else:
                try:
                    validator_cls = importlib.import_module(
                        "infra.agents.langchain.skills.llm_validator"
                    ).LLMValidatorSkill
                    validator_debug = _validator_debug_enabled()
                    validator_debug_file = os.getenv(
                        "CONVERSION_LLM_VALIDATOR_DEBUG_LOG",
                        "output/llm_trace/validator_sql.log",
                    )
                    validator = validator_cls(
                        debug=validator_debug,
                        debug_file=validator_debug_file if validator_debug else None,
                    )
                    batch_size_raw = os.getenv(
                        "CONVERSION_VALIDATE_LLM_BATCH_SIZE", "20"
                    )
                    try:
                        batch_size = max(1, int(batch_size_raw))
                    except ValueError:
                        batch_size = 20

                    log_llm_trace(
                        component="validator",
                        event="sql.request",
                        payload={
                            "candidate_count": len(candidates),
                            "batch_size": batch_size,
                            "strict_mode": strict_mode,
                            "stage": "sql_validation",
                        },
                    )
                    llm_result = validator.invoke(
                        {
                            "mode": "sql",
                            "mybatis_xmls": candidates,
                            "batch_size": batch_size,
                            "debug": validator_debug,
                            "debug_file": validator_debug_file
                            if validator_debug
                            else None,
                        }
                    )

                    if llm_result.success:
                        llm_meta["success"] = True
                        feedback = llm_result.data or {}
                        llm_meta["feedback_summary"] = str(feedback.get("summary", ""))

                        if not feedback.get("passed", True):
                            for item in feedback.get("issues", []):
                                issue_text = str(
                                    item.get("issue", "unspecified issue")
                                ).strip()
                                sql_id = str(item.get("sql_id", "unknown")).strip()
                                severity = str(item.get("severity", "warning")).lower()
                                message = f"[llm:{sql_id}] {issue_text}"
                                if severity == "error":
                                    _append_unique(issues, message)
                                else:
                                    _append_unique(warnings, message)
                        log_llm_trace(
                            component="validator",
                            event="sql.response",
                            payload={
                                "success": True,
                                "feedback_summary": llm_meta["feedback_summary"],
                                "issue_count": len(feedback.get("issues", [])),
                                "stage": "sql_validation",
                            },
                        )
                    else:
                        _append_unique(
                            warnings,
                            "llm validation invocation failed: "
                            + "; ".join(str(err) for err in llm_result.errors),
                        )
                        if strict_mode:
                            _append_unique(issues, "llm validation invocation failed")
                        log_llm_trace(
                            component="validator",
                            event="sql.response",
                            payload={
                                "success": False,
                                "errors": [str(err) for err in llm_result.errors],
                                "stage": "sql_validation",
                            },
                        )
                except Exception as exc:
                    _append_unique(warnings, f"llm validation exception: {exc}")
                    if strict_mode:
                        _append_unique(issues, "llm validation exception")
                    log_llm_trace(
                        component="validator",
                        event="sql.error",
                        payload={"error": str(exc), "stage": "sql_validation"},
                    )
        else:
            _append_unique(warnings, "llm validation enabled but no candidates")
            if strict_mode:
                _append_unique(issues, "llm validation enabled but no candidates")
            log_llm_trace(
                component="validator",
                event="sql.skipped",
                payload={
                    "reason": "no_candidates",
                    "strict_mode": strict_mode,
                    "stage": "sql_validation",
                },
            )
    else:
        log_llm_trace(
            component="validator",
            event="sql.skipped",
            payload={
                "reason": "disabled",
                "strict_mode": strict_mode,
                "stage": "sql_validation",
            },
        )

    validation_result = {
        "passed": len(issues) == 0,
        "summary": {
            "expected_services": expected_services,
            "generated_services": generated_services,
            "expected_sql": expected_sql,
            "generated_xml": generated_xml,
        },
        "ast": {
            "passed": bool(ast_validation.get("passed", True)),
            "error_count": int(ast_validation.get("error_count", 0)),
        },
        "parser": {
            "enabled": bool(parser_validation.get("enabled", False)),
            "passed": bool(parser_validation.get("passed", True)),
            "chunk_count": int(parser_validation.get("chunk_count", 0)),
            "missing_count": int(parser_validation.get("missing_count", 0)),
            "wrong_count": int(parser_validation.get("wrong_count", 0)),
            "reclassification_count": int(
                parser_validation.get("reclassification_count", 0)
            ),
        },
        "iteration": {
            "current": int(state.get("iteration_count", 0)),
            "max": _resolve_max_iterations(state),
        },
        "llm": llm_meta,
        "warnings": warnings,
        "issues": issues,
    }
    return {"validation_result": validation_result}


def supplement_node(state: ConversionGraphState) -> Dict[str, Any]:
    current_iteration = int(state.get("iteration_count", 0))
    next_iteration = current_iteration + 1
    validation = state.get("validation_result") or {}
    if validation.get("passed", False):
        return {
            "supplement_result": {
                "applied": False,
                "iteration": current_iteration,
                "reason": "validation already passed",
            }
        }

    run_java_conversion = importlib.import_module(
        "agents.java_spring_agent"
    ).run_java_conversion
    run_mybatis_generation = importlib.import_module(
        "agents.mybatis_agent"
    ).run_mybatis_generation

    supplement_state = dict(state)
    supplement_state["enable_llm_gap_fill"] = True

    java_payload = run_java_conversion(supplement_state)
    mybatis_payload = run_mybatis_generation(supplement_state)

    merged_errors: list[str] = []
    for item in (
        list(state.get("errors", []))
        + list(java_payload.get("errors", []))
        + list(mybatis_payload.get("errors", []))
    ):
        text = str(item)
        if text and text not in merged_errors:
            merged_errors.append(text)

    java_result = java_payload.get("java_result", {})
    mybatis_result = mybatis_payload.get("mybatis_result", {})
    supplement_result = {
        "applied": True,
        "iteration": next_iteration,
        "java_llm_gap_fill_applied": int(java_result.get("llm_gap_fill_applied", 0)),
        "java_llm_gap_fill_attempted": int(
            java_result.get("llm_gap_fill_attempted", 0)
        ),
        "note": "supplementation reran java/mybatis generation",
    }

    history = list(state.get("validation_history", []))
    history.append(
        {
            "iteration": int(
                validation.get("iteration", {}).get("current", current_iteration)
            ),
            "passed": bool(validation.get("passed", False)),
            "issue_count": len(validation.get("issues", [])),
        }
    )

    return {
        "java_result": java_result,
        "mybatis_result": mybatis_result,
        "supplement_result": supplement_result,
        "validation_history": history,
        "iteration_count": next_iteration,
        "errors": merged_errors,
    }


def _route_after_validate(state: ConversionGraphState) -> str:
    validation_result = state.get("validation_result") or {}
    if validation_result.get("passed", False):
        return "report"

    current_iteration = int(state.get("iteration_count", 0))
    max_iterations = _resolve_max_iterations(state)
    if current_iteration < max_iterations:
        return "supplement"
    return "report"


def report_node(state: ConversionGraphState) -> Dict[str, Any]:
    try:
        run_report = importlib.import_module("agents.report_agent").run_report
        return run_report(state)
    except Exception as exc:
        return {"errors": state.get("errors", []) + [f"report node failed: {exc}"]}


class _FallbackCompiledGraph:
    """langgraph 미설치 환경을 위한 순차 실행 fallback."""

    def __init__(self, mode: str):
        self.mode = mode

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(state)
        merged.setdefault("graph_mode", self.mode)
        merged.setdefault("iteration_count", 0)
        merged.setdefault(
            "max_iterations",
            _resolve_max_iterations(cast(ConversionGraphState, cast(object, merged))),
        )

        merged.update(analysis_node(cast(ConversionGraphState, cast(object, merged))))
        merged.update(planning_node(cast(ConversionGraphState, cast(object, merged))))

        if self.mode == "legacy":
            merged.update(
                parallel_conversion_node(
                    cast(ConversionGraphState, cast(object, merged))
                )
            )
            merged.update(
                validation_node(cast(ConversionGraphState, cast(object, merged)))
            )
            merged.update(report_node(cast(ConversionGraphState, cast(object, merged))))
            return merged

        merged.update(
            ast_validation_node(cast(ConversionGraphState, cast(object, merged)))
        )
        merged.update(
            parser_llm_validation_node(cast(ConversionGraphState, cast(object, merged)))
        )
        merged.update(
            parallel_conversion_node(cast(ConversionGraphState, cast(object, merged)))
        )

        safety_counter = 0
        while True:
            merged.update(
                validation_node(cast(ConversionGraphState, cast(object, merged)))
            )
            route = _route_after_validate(
                cast(ConversionGraphState, cast(object, merged))
            )
            if route == "report":
                break
            merged.update(
                supplement_node(cast(ConversionGraphState, cast(object, merged)))
            )
            safety_counter += 1
            if safety_counter > max(
                1,
                _resolve_max_iterations(
                    cast(ConversionGraphState, cast(object, merged))
                )
                + 1,
            ):
                break

        merged.update(report_node(cast(ConversionGraphState, cast(object, merged))))
        return merged


def build_conversion_graph():
    mode = _resolve_graph_mode()
    if not has_langgraph:
        return _FallbackCompiledGraph(mode)
    if StateGraph is None:
        return _FallbackCompiledGraph(mode)

    workflow = StateGraph(ConversionGraphState)
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("plan", planning_node)

    if mode == "legacy":
        workflow.add_node("conversion", parallel_conversion_node)
        workflow.add_node("validate", validation_node)
        workflow.add_node("report", report_node)

        workflow.set_entry_point("analysis")
        workflow.add_edge("analysis", "plan")
        workflow.add_edge("plan", "conversion")
        workflow.add_edge("conversion", "validate")
        workflow.add_edge("validate", "report")
        workflow.add_edge("report", graph_end)
        return workflow.compile()

    workflow.add_node("ast_critic", ast_validation_node)
    workflow.add_node("parser_validate", parser_llm_validation_node)
    workflow.add_node("conversion", parallel_conversion_node)
    workflow.add_node("validate", validation_node)
    workflow.add_node("supplement", supplement_node)
    workflow.add_node("report", report_node)

    workflow.set_entry_point("analysis")
    workflow.add_edge("analysis", "plan")
    workflow.add_edge("plan", "ast_critic")
    workflow.add_edge("ast_critic", "parser_validate")
    workflow.add_edge("parser_validate", "conversion")
    workflow.add_edge("conversion", "validate")
    workflow.add_conditional_edges(
        "validate",
        _route_after_validate,
        {
            "supplement": "supplement",
            "report": "report",
        },
    )
    workflow.add_edge("supplement", "validate")
    workflow.add_edge("report", graph_end)
    return workflow.compile()
