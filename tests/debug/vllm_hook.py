"""Debug hook for VLLM_HOOK_TARGET integration tests."""

from __future__ import annotations

from typing import Any, Dict


def fake_java_response(payload: Dict[str, Any]) -> str:
    model = payload.get("model", "unknown")
    return (
        "package com.example.service;\n\n"
        "import org.springframework.stereotype.Service;\n\n"
        "@Service\n"
        "public class HookedService {\n"
        f"    // hooked model={model}\n"
        "    public void execute() {}\n"
        "}\n"
    )
