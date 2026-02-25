"""Java Spring conversion agent with vLLM-ready client."""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime
import importlib

import requests


class VLLMClient:
    """OpenAI-compatible vLLM client with mock-first mode for implementation phase."""

    def __init__(self) -> None:
        self.endpoint = os.getenv("VLLM_API_ENDPOINT", "http://localhost:8000/v1").rstrip("/")
        self.model = os.getenv("VLLM_MODEL", "mock-model")
        self.api_key = os.getenv("VLLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        # 구현 단계 기본값은 mock=true, 실제 연결 시 false로 전환
        self.mock_mode = os.getenv("VLLM_MOCK", "true").lower() in {"1", "true", "yes"}
        # 네트워크 호출 대신 훅 함수로 응답 생성 (디버깅 목적)
        self.hook_target = os.getenv("VLLM_HOOK_TARGET", "")
        self.hook_log_path = os.getenv("VLLM_HOOK_LOG", "")

    def generate_java(self, class_name: str, functions: List[str], strategy: str) -> str:
        if self.mock_mode:
            joined = "\n".join(
                f"    public void {fn}() {{ /* TODO: migrate */ }}" for fn in (functions or ["execute"]) 
            )
            return (
                "package com.example.service;\n\n"
                "import org.springframework.stereotype.Service;\n\n"
                "@Service\n"
                f"public class {class_name} {{\n"
                f"    // generated in mock mode (strategy={strategy})\n"
                f"{joined}\n"
                "}\n"
            )

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        prompt = (
            "Convert Pro*C function names into a Spring service class. "
            f"Class name: {class_name}, strategy: {strategy}, functions: {functions}."
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 1200,
        }

        if self.hook_target:
            return self._invoke_hook(payload)

        response = requests.post(
            f"{self.endpoint}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

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
                fp.write(
                    json.dumps(
                        {
                            "ts": datetime.now().isoformat(),
                            "payload": payload,
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


def run_java_conversion(state: Dict[str, Any]) -> Dict[str, Any]:
    analysis_result = state.get("analysis_result") or {}
    strategy = state.get("strategy", "preserve")
    output_dir = Path(state.get("output_dir", "output"))
    service_dir = output_dir / "java" / "service"
    stub_dir = output_dir / "java" / "stub"
    service_dir.mkdir(parents=True, exist_ok=True)
    stub_dir.mkdir(parents=True, exist_ok=True)

    client = VLLMClient()
    errors = list(state.get("errors", []))
    java_files: List[str] = []
    stub_files: List[str] = []

    for file_info in analysis_result.get("files", []):
        source_file = file_info.get("source_file", "unknown.pc")
        class_name = _to_class_name(source_file)
        try:
            java_code = client.generate_java(class_name, file_info.get("functions", []), strategy)
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
        },
        "errors": errors,
    }
