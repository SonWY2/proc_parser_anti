#!/usr/bin/env python3
"""Hardcoded runner for LangGraph-based Pro*C -> Java conversion.

이 스크립트는 CLI 인자를 받지 않습니다.
아래 "EDIT HERE" 영역의 값만 수정해서 바로 테스트할 수 있습니다.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Protocol, cast

from infra.agents.langchain.orchestration.conversion_graph import (
    ConversionGraphState,
    build_conversion_graph,
)


PROJECT_ROOT = Path(__file__).resolve().parent

HEADER_PATHS = [
    # "tests/fixtures/sample_input_data/sample.h",
    "/mnt/d/workspace/proc_parser_antigravity/proc_parser_claude_multiagent/tlfb000m.h"
]

PROC_PATHS = [
    # "tests/fixtures/sample_input_data/cursor_sample.pc",
    "/mnt/d/workspace/proc_parser_antigravity/proc_parser_claude_multiagent/original_source_dup_comment.sqc"
]

OUTPUT_DIR = "output/manual_run_py_hardcoded"
STRATEGY = "preserve"
KNOWLEDGE_DOC: str | None = None

MODE = "real"  # mock
REAL_PROVIDER = "openrouter"
VLLM_API_ENDPOINT = "http://localhost:8000/v1"
VLLM_MODEL = "mock-model"
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "")
OPENROUTER_API_ENDPOINT = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "qwen/qwen3.5-flash-02-23"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
VLLM_HOOK_TARGET = "tests.debug.vllm_hook:fake_java_response"
VLLM_HOOK_LOG = "output/hook_debug/hook_log.jsonl"

CONVERSION_GRAPH_MODE = "md"
CONVERSION_PLAN_WITH_LLM = True
CONVERSION_VALIDATE_WITH_LLM = True
CONVERSION_VALIDATE_STRICT = True
CONVERSION_VALIDATE_LLM_BATCH_SIZE = 5
CONVERSION_SUPPLEMENT_MAX_ITER = 1
CONVERSION_LLM_TRACE = True
CONVERSION_LLM_TRACE_CONTENT = True
CONVERSION_LLM_TRACE_STDOUT = True
CONVERSION_LLM_TRACE_LOG = "output/llm_trace/llm_trace.jsonl"
CONVERSION_LLM_TRACE_PREVIEW = 500
CONVERSION_LLM_VALIDATOR_DEBUG = False
CONVERSION_LLM_VALIDATOR_DEBUG_LOG = "output/llm_trace/validator.log"


class InvokableGraph(Protocol):
    def invoke(self, input: ConversionGraphState | None) -> dict[str, object]: ...


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _validate_input_paths() -> tuple[list[str], list[str], str | None]:
    resolved_headers = [_resolve_path(p) for p in HEADER_PATHS]
    resolved_procs = [_resolve_path(p) for p in PROC_PATHS]
    missing = [str(p) for p in [*resolved_headers, *resolved_procs] if not p.exists()]
    if missing:
        raise FileNotFoundError(f"입력 파일이 없습니다: {missing}")

    resolved_knowledge: str | None = None
    if KNOWLEDGE_DOC:
        knowledge_path = _resolve_path(KNOWLEDGE_DOC)
        if not knowledge_path.exists():
            raise FileNotFoundError(f"knowledge_doc 파일이 없습니다: {knowledge_path}")
        resolved_knowledge = str(knowledge_path)

    return (
        [str(p) for p in resolved_headers],
        [str(p) for p in resolved_procs],
        resolved_knowledge,
    )


def _set_runtime_env() -> None:
    mode = MODE.strip().lower()
    if mode not in {"mock", "real", "hook"}:
        raise ValueError("MODE는 mock, real, hook 중 하나여야 합니다.")

    os.environ["CONVERSION_PLAN_WITH_LLM"] = (
        "true" if CONVERSION_PLAN_WITH_LLM else "false"
    )
    os.environ["CONVERSION_VALIDATE_WITH_LLM"] = (
        "true" if CONVERSION_VALIDATE_WITH_LLM else "false"
    )
    os.environ["CONVERSION_VALIDATE_LLM_BATCH_SIZE"] = str(
        CONVERSION_VALIDATE_LLM_BATCH_SIZE
    )
    os.environ["CONVERSION_GRAPH_MODE"] = CONVERSION_GRAPH_MODE
    os.environ["CONVERSION_VALIDATE_STRICT"] = (
        "true" if CONVERSION_VALIDATE_STRICT else "false"
    )
    os.environ["CONVERSION_SUPPLEMENT_MAX_ITER"] = str(CONVERSION_SUPPLEMENT_MAX_ITER)
    os.environ["CONVERSION_LLM_TRACE"] = "true" if CONVERSION_LLM_TRACE else "false"
    os.environ["CONVERSION_LLM_TRACE_CONTENT"] = (
        "true" if CONVERSION_LLM_TRACE_CONTENT else "false"
    )
    os.environ["CONVERSION_LLM_TRACE_STDOUT"] = (
        "true" if CONVERSION_LLM_TRACE_STDOUT else "false"
    )
    os.environ["CONVERSION_LLM_TRACE_LOG"] = CONVERSION_LLM_TRACE_LOG
    os.environ["CONVERSION_LLM_TRACE_PREVIEW"] = str(CONVERSION_LLM_TRACE_PREVIEW)
    os.environ["CONVERSION_LLM_VALIDATOR_DEBUG"] = (
        "true" if CONVERSION_LLM_VALIDATOR_DEBUG else "false"
    )
    os.environ["CONVERSION_LLM_VALIDATOR_DEBUG_LOG"] = (
        CONVERSION_LLM_VALIDATOR_DEBUG_LOG
    )

    provider = REAL_PROVIDER.strip().lower()

    def set_provider_env(endpoint: str, model: str, api_key: str) -> None:
        os.environ["VLLM_API_ENDPOINT"] = endpoint
        os.environ["VLLM_MODEL"] = model
        os.environ["LLM_API_ENDPOINT"] = endpoint
        os.environ["LLM_MODEL"] = model
        if api_key:
            os.environ["VLLM_API_KEY"] = api_key
            os.environ["LLM_API_KEY"] = api_key
            os.environ["OPENAI_API_KEY"] = api_key

    if mode == "mock":
        os.environ["VLLM_MOCK"] = "true"
        os.environ["VLLM_MODEL"] = VLLM_MODEL
        _ = os.environ.pop("VLLM_HOOK_TARGET", None)
        _ = os.environ.pop("VLLM_HOOK_LOG", None)
        return

    os.environ["VLLM_MOCK"] = "false"

    if mode == "real":
        if provider == "vllm":
            set_provider_env(VLLM_API_ENDPOINT, VLLM_MODEL, VLLM_API_KEY)
        elif provider == "openrouter":
            set_provider_env(
                OPENROUTER_API_ENDPOINT,
                OPENROUTER_MODEL,
                OPENROUTER_API_KEY,
            )
        else:
            raise ValueError("REAL_PROVIDER는 vllm 또는 openrouter 여야 합니다.")
        _ = os.environ.pop("VLLM_HOOK_TARGET", None)
        _ = os.environ.pop("VLLM_HOOK_LOG", None)
        return

    os.environ["VLLM_HOOK_TARGET"] = VLLM_HOOK_TARGET
    os.environ["VLLM_HOOK_LOG"] = VLLM_HOOK_LOG


def main() -> int:
    header_paths, proc_paths, knowledge_doc = _validate_input_paths()
    _set_runtime_env()

    output_dir = _resolve_path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[run] mode={MODE}")
    print(f"[run] headers={header_paths}")
    print(f"[run] procs={proc_paths}")
    print(f"[run] output={output_dir}")
    print(f"[run] strategy={STRATEGY}")
    print(f"[run] llm_trace={CONVERSION_LLM_TRACE}")
    print(f"[run] llm_trace_content={CONVERSION_LLM_TRACE_CONTENT}")
    print(f"[run] llm_trace_stdout={CONVERSION_LLM_TRACE_STDOUT}")
    print(f"[run] llm_trace_log={CONVERSION_LLM_TRACE_LOG}")
    print(f"[run] validator_debug={CONVERSION_LLM_VALIDATOR_DEBUG}")
    print(f"[run] validator_log={CONVERSION_LLM_VALIDATOR_DEBUG_LOG}")
    if knowledge_doc:
        print(f"[run] knowledge_doc={knowledge_doc}")

    graph = cast(InvokableGraph, build_conversion_graph())
    initial_state: ConversionGraphState = {
        "header_paths": header_paths,
        "proc_paths": proc_paths,
        "output_dir": str(output_dir),
        "strategy": STRATEGY,
        "knowledge_doc": knowledge_doc,
        "errors": [],
    }

    result = graph.invoke(initial_state)

    result_path = output_dir / "conversion_result.json"
    _ = result_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"report: {result.get('report_path', 'N/A')}")
    print(f"result json: {result_path}")

    raw_errors_obj = result.get("errors", [])
    errors: list[str] = []
    if isinstance(raw_errors_obj, list):
        for item in cast(list[object], raw_errors_obj):
            errors.append(str(item))
    if errors:
        for err in errors:
            print(f"WARN: {err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
