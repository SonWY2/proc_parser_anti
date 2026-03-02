from __future__ import annotations

import json
import os
import re
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import logging

logger = logging.getLogger(__name__)
_TRACE_LOCK = threading.Lock()
_BEARER_PATTERN = re.compile(r"\b[Bb]earer\s+[A-Za-z0-9._\-]+")
_SK_PATTERN = re.compile(r"\bsk-[A-Za-z0-9._\-=]+")


def _env_true(name: str, default: bool = False) -> bool:
    fallback = "true" if default else "false"
    return os.getenv(name, fallback).strip().lower() in {"1", "true", "yes"}


def _preview_limit() -> int:
    raw = os.getenv("CONVERSION_LLM_TRACE_PREVIEW", "500")
    try:
        return max(80, int(raw))
    except ValueError:
        return 500


def _trace_log_path() -> Path:
    value = os.getenv("CONVERSION_LLM_TRACE_LOG", "output/llm_trace/llm_trace.jsonl")
    path = Path(value)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def llm_trace_enabled() -> bool:
    return _env_true("CONVERSION_LLM_TRACE", default=False)


def llm_trace_content_enabled() -> bool:
    return _env_true("CONVERSION_LLM_TRACE_CONTENT", default=False)


def llm_trace_stdout_enabled() -> bool:
    return _env_true("CONVERSION_LLM_TRACE_STDOUT", default=False)


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(
        token in lowered
        for token in [
            "api_key",
            "apikey",
            "token",
            "authorization",
            "password",
            "secret",
        ]
    )


def _truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value.replace("\n", "\\n")

    prefix = value[:limit]
    return prefix.replace("\n", "\\n") + f"...<truncated:{len(value) - limit}>"


def _redact_sensitive_text(value: str) -> str:
    redacted = _BEARER_PATTERN.sub("Bearer ***redacted***", value)
    redacted = _SK_PATTERN.sub("sk-***redacted***", redacted)
    return redacted


def sanitize_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return value

    netloc = parts.hostname or ""
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def _sanitize(value: Any, limit: int) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if _is_secret_key(str(key)):
                sanitized[str(key)] = "***redacted***"
            else:
                sanitized[str(key)] = _sanitize(item, limit)
        return sanitized

    if isinstance(value, list):
        return [_sanitize(item, limit) for item in value]

    if isinstance(value, str):
        return _truncate_text(_redact_sensitive_text(value), limit)

    return value


def _terminal_summary(component: str, event: str, payload: dict[str, Any]) -> str:
    tokens = [f"[llm] {component}.{event}"]

    stage = payload.get("stage")
    if isinstance(stage, str) and stage:
        tokens.append(f"stage={stage}")

    trace_id = payload.get("trace_id")
    if isinstance(trace_id, str) and trace_id:
        tokens.append(f"id={trace_id}")

    prompt_chars = payload.get("prompt_chars")
    if isinstance(prompt_chars, int):
        tokens.append(f"prompt={prompt_chars}")

    system_chars = payload.get("system_prompt_chars")
    user_chars = payload.get("user_prompt_chars")
    if isinstance(system_chars, int) and isinstance(user_chars, int):
        tokens.append(f"system={system_chars}")
        tokens.append(f"user={user_chars}")

    response_chars = payload.get("response_chars")
    if isinstance(response_chars, int):
        tokens.append(f"response={response_chars}")

    elapsed_ms = payload.get("elapsed_ms")
    if isinstance(elapsed_ms, (int, float)):
        tokens.append(f"ms={elapsed_ms}")

    reason = payload.get("reason")
    if isinstance(reason, str) and reason:
        tokens.append(f"reason={reason}")

    error = payload.get("error")
    if isinstance(error, str) and error:
        tokens.append(f"error={_truncate_text(error, 120)}")

    return " ".join(tokens)


def log_llm_trace(component: str, event: str, payload: dict[str, Any]) -> None:
    if not llm_trace_enabled():
        return

    limit = _preview_limit()
    record = {
        "ts": datetime.now().isoformat(),
        "component": component,
        "event": event,
        "payload": _sanitize(payload, limit),
    }

    try:
        log_path = _trace_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        sanitized_payload = _sanitize(payload, limit)
        with _TRACE_LOCK:
            with log_path.open("a", encoding="utf-8") as fp:
                fp.write(
                    json.dumps(
                        {
                            "ts": record["ts"],
                            "component": component,
                            "event": event,
                            "payload": sanitized_payload,
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                    + "\n"
                )
    except Exception as exc:
        logger.warning("llm trace file write failed: %s", exc)

    terminal_payload = record["payload"] if isinstance(record["payload"], dict) else {}

    if llm_trace_stdout_enabled():
        _ = sys.stderr.write(
            _terminal_summary(component, event, terminal_payload) + "\n"
        )
    else:
        logger.info("[llm-trace] %s.%s", component, event)
