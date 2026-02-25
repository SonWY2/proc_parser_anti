from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.java_spring_agent import VLLMClient


def test_vllm_hook_target_injects_response(monkeypatch, tmp_path):
    log_path = tmp_path / "hook_log.jsonl"

    monkeypatch.setenv("VLLM_MOCK", "false")
    monkeypatch.setenv("VLLM_HOOK_TARGET", "tests.debug.vllm_hook:fake_java_response")
    monkeypatch.setenv("VLLM_HOOK_LOG", str(log_path))
    monkeypatch.setenv("VLLM_MODEL", "debug-model")

    client = VLLMClient()
    response = client.generate_java("SampleService", ["run_task"], "preserve")

    assert "HookedService" in response
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "debug-model" in content
