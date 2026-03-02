"""Java Spring conversion agent with vLLM-ready client."""

from __future__ import annotations

import os
import json
import time
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime
import importlib
from uuid import uuid4

import requests


def _trace_gap_fill(event: str, payload: Dict[str, Any]) -> None:
    try:
        trace_module = importlib.import_module("infra.agents.langchain.llm_trace")
        trace_module.log_llm_trace("gap_fill", event, payload)
    except Exception:
        return


def _trace_content_enabled() -> bool:
    try:
        trace_module = importlib.import_module("infra.agents.langchain.llm_trace")
        return bool(trace_module.llm_trace_content_enabled())
    except Exception:
        return False


def _sanitize_endpoint(endpoint: str) -> str:
    try:
        trace_module = importlib.import_module("infra.agents.langchain.llm_trace")
        return str(trace_module.sanitize_url(endpoint))
    except Exception:
        return endpoint


class VLLMClient:
    """OpenAI-compatible vLLM client with mock-first mode for implementation phase."""

    def __init__(self) -> None:
        self.endpoint = os.getenv(
            "VLLM_API_ENDPOINT", "http://localhost:8000/v1"
        ).rstrip("/")
        self.model = os.getenv("VLLM_MODEL", "mock-model")
        self.api_key = os.getenv("VLLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        # 구현 단계 기본값은 mock=true, 실제 연결 시 false로 전환
        self.mock_mode = os.getenv("VLLM_MOCK", "true").lower() in {"1", "true", "yes"}
        # 네트워크 호출 대신 훅 함수로 응답 생성 (디버깅 목적)
        self.hook_target = os.getenv("VLLM_HOOK_TARGET", "")
        self.hook_log_path = os.getenv("VLLM_HOOK_LOG", "")

    def generate_java(
        self,
        class_name: str,
        functions: List[str],
        strategy: str,
        base_code: str = "",
        plan_steps: List[str] | None = None,
    ) -> str:
        include_content = _trace_content_enabled()
        trace_id = f"gapfill-{uuid4().hex[:10]}"
        request_payload: Dict[str, Any] = {
            "mock_mode": self.mock_mode,
            "hook_enabled": bool(self.hook_target),
            "endpoint": _sanitize_endpoint(self.endpoint),
            "model": self.model,
            "class_name": class_name,
            "function_count": len(functions),
            "strategy": strategy,
            "plan_step_count": len(plan_steps or []),
            "base_code_chars": len(base_code),
            "stage": "gap_fill",
            "trace_id": trace_id,
        }
        if include_content:
            request_payload["base_code_preview"] = base_code
        _trace_gap_fill(
            "request",
            request_payload,
        )

        if self.mock_mode:
            if base_code.strip():
                _trace_gap_fill(
                    "response",
                    {
                        "mock_mode": True,
                        "class_name": class_name,
                        "reason": "base_code_passthrough",
                        "stage": "gap_fill",
                        "trace_id": trace_id,
                    },
                )
                return base_code
            joined = "\n".join(
                f"    public void {fn}() {{ /* TODO: migrate */ }}"
                for fn in (functions or ["execute"])
            )
            generated = (
                "package com.example.service;\n\n"
                "import org.springframework.stereotype.Service;\n\n"
                "@Service\n"
                f"public class {class_name} {{\n"
                f"    // generated in mock mode (strategy={strategy})\n"
                f"{joined}\n"
                "}\n"
            )
            _trace_gap_fill(
                "response",
                {
                    "mock_mode": True,
                    "class_name": class_name,
                    "generated_chars": len(generated),
                    "stage": "gap_fill",
                    "trace_id": trace_id,
                },
            )
            return generated

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        plan_text = "\n".join(f"- {step}" for step in (plan_steps or []))
        prompt = (
            "You are migrating Pro*C to Java Spring.\n"
            "Keep class name and existing method signatures exactly as-is.\n"
            "Fill TODO blocks with concise, compilable placeholder business logic only.\n"
            "Do not remove methods or add unrelated classes.\n"
            f"Strategy: {strategy}\n"
            f"Class name: {class_name}\n"
            f"Functions: {functions}\n"
            f"Plan:\n{plan_text}\n\n"
            f"Base code:\n{base_code}"
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 1200,
            "trace_id": trace_id,
            "stage": "gap_fill",
        }
        llm_request_payload: Dict[str, Any] = {
            "hook_enabled": bool(self.hook_target),
            "class_name": class_name,
            "model": self.model,
            "prompt_chars": len(prompt),
            "stage": "gap_fill",
            "trace_id": trace_id,
        }
        if include_content:
            llm_request_payload["prompt_preview"] = prompt
        _trace_gap_fill("llm.request", llm_request_payload)

        if self.hook_target:
            hooked = self._invoke_hook(payload)
            _trace_gap_fill(
                "response",
                {
                    "hook_enabled": True,
                    "class_name": class_name,
                    "generated_chars": len(hooked),
                    "stage": "gap_fill",
                    "trace_id": trace_id,
                },
            )
            return hooked

        started = time.perf_counter()
        try:
            response = requests.post(
                f"{self.endpoint}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            _trace_gap_fill(
                "response",
                {
                    "hook_enabled": False,
                    "class_name": class_name,
                    "status_code": response.status_code,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                    "generated_chars": len(str(content)),
                    "stage": "gap_fill",
                    "trace_id": trace_id,
                    **({"response_preview": str(content)} if include_content else {}),
                },
            )
            return content
        except Exception as exc:
            _trace_gap_fill(
                "error",
                {
                    "hook_enabled": False,
                    "class_name": class_name,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                    "error": str(exc),
                    "stage": "gap_fill",
                    "trace_id": trace_id,
                },
            )
            raise

    def _invoke_hook(self, payload: Dict[str, Any]) -> str:
        """VLLM_HOOK_TARGET(module:function) 호출로 응답을 주입합니다."""
        if ":" not in self.hook_target:
            raise ValueError("VLLM_HOOK_TARGET must be in 'module:function' format")

        module_name, function_name = self.hook_target.split(":", 1)
        module = importlib.import_module(module_name)
        hook_func = getattr(module, function_name)

        response = hook_func(payload)
        if not isinstance(response, str):
            raise TypeError("hook response must be str")

        if self.hook_log_path:
            log_path = Path(self.hook_log_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as fp:
                content = str(payload.get("messages", [{}])[0].get("content", ""))
                fp.write(
                    json.dumps(
                        {
                            "ts": datetime.now().isoformat(),
                            "payload_meta": {
                                "model": payload.get("model", ""),
                                "message_count": len(payload.get("messages", [])),
                                "prompt_chars": len(content),
                            },
                            **(
                                {"prompt_preview": content[:200]}
                                if _trace_content_enabled()
                                else {}
                            ),
                            "response_preview": response[:200],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

        return response


def _to_class_name(source_file: str) -> str:
    stem = Path(source_file).stem
    return "".join(part.capitalize() for part in stem.split("_")) + "Service"


def _sanitize_method_name(name: str, fallback_index: int) -> str:
    value = (name or "").strip()
    if not value:
        return f"execute{fallback_index}"
    value = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in value)
    if value[0].isdigit():
        value = f"m_{value}"
    return value


def _build_deterministic_service(
    class_name: str, functions: List[str], strategy: str
) -> str:
    method_defs: List[str] = []
    names = functions or ["execute"]
    for index, fn in enumerate(names, start=1):
        method_name = _sanitize_method_name(fn, index)
        method_defs.append(
            "    public void "
            + method_name
            + "() {\n"
            + "        // TODO: parser-driven migration body\n"
            + "        // strategy: "
            + strategy
            + "\n"
            + "    }"
        )

    body = "\n\n".join(method_defs)
    return (
        "package com.example.service;\n\n"
        "import org.springframework.stereotype.Service;\n\n"
        "@Service\n"
        f"public class {class_name} {{\n"
        f"{body}\n"
        "}\n"
    )


def run_java_conversion(state: Dict[str, Any]) -> Dict[str, Any]:
    analysis_result = state.get("analysis_result") or {}
    strategy = state.get("strategy", "preserve")
    output_dir = Path(state.get("output_dir", "output"))
    service_dir = output_dir / "java" / "service"
    stub_dir = output_dir / "java" / "stub"
    service_dir.mkdir(parents=True, exist_ok=True)
    stub_dir.mkdir(parents=True, exist_ok=True)

    client = VLLMClient()
    conversion_plan = state.get("conversion_plan") or {}
    plan_steps = conversion_plan.get("steps", [])
    default_gap_fill = os.getenv("JAVA_GAP_FILL_ENABLED", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    enable_llm_gap_fill = state.get("enable_llm_gap_fill", default_gap_fill)
    if client.mock_mode and not client.hook_target:
        enable_llm_gap_fill = False

    errors = list(state.get("errors", []))
    java_files: List[str] = []
    stub_files: List[str] = []
    llm_attempted = 0
    llm_applied = 0

    for file_info in analysis_result.get("files", []):
        source_file = file_info.get("source_file", "unknown.pc")
        class_name = _to_class_name(source_file)
        deterministic_code = _build_deterministic_service(
            class_name, file_info.get("functions", []), strategy
        )
        java_code = deterministic_code

        if enable_llm_gap_fill:
            llm_attempted += 1
            try:
                candidate = client.generate_java(
                    class_name,
                    file_info.get("functions", []),
                    strategy,
                    base_code=deterministic_code,
                    plan_steps=plan_steps,
                )
                if candidate.strip():
                    java_code = candidate
                    llm_applied += 1
            except Exception as exc:
                errors.append(f"llm gap-fill failed for {source_file}: {exc}")

        try:
            path = service_dir / f"{class_name}.java"
            path.write_text(java_code, encoding="utf-8")
            java_files.append(str(path))
        except Exception as exc:
            errors.append(f"java conversion failed for {source_file}: {exc}")

    for extern_name in analysis_result.get("extern_list", []):
        stub_name = f"{extern_name}Stub"
        content = (
            "package com.example.stub;\n\n"
            f"public class {stub_name} {{\n"
            "    // TODO: implement extern dependency\n"
            "}\n"
        )
        path = stub_dir / f"{stub_name}.java"
        path.write_text(content, encoding="utf-8")
        stub_files.append(str(path))

    return {
        "java_result": {
            "java_files": java_files,
            "stub_files": stub_files,
            "total_classes": len(java_files),
            "total_stubs": len(stub_files),
            "mocked_vllm": client.mock_mode,
            "vllm_endpoint": client.endpoint,
            "llm_gap_fill_enabled": bool(enable_llm_gap_fill),
            "llm_gap_fill_attempted": llm_attempted,
            "llm_gap_fill_applied": llm_applied,
        },
        "errors": errors,
    }
