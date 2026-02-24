# Agent Monitoring System Usage Guide

에이전트 호출, 태스크 수행, 도구 사용을 추적하고 모니터링하는 시스템입니다.

## Quick Start

```python
from infra.agents.base import AgentMonitor, Orchestrator

# 모니터 생성
monitor = AgentMonitor(
    log_dir="./logs/agent_monitoring",
    enable_console_logging=True  # 콘솔에도 출력
)

# Orchestrator와 함께 사용
orchestrator = Orchestrator(monitor=monitor)
orchestrator.load_agents()

# 에이전트 실행 (자동으로 모니터링됨)
result = orchestrator.delegate("proc-analyzer", "분석 요청")

# 요약 확인
print(monitor.get_summary())
```

## Features

### 1. 이벤트 로깅

#### 자동 로깅 (Orchestrator 연동)
```python
# Orchestrator에 모니터 설정하면 delegate() 호출 시 자동 로깅
orchestrator = Orchestrator(monitor=monitor)
# 또는
orchestrator.set_monitor(monitor)
```

#### 수동 로깅
```python
# 에이전트 호출 기록
monitor.log_invoke("agent-name", "태스크 내용")

# 완료 기록
monitor.log_complete(
    "agent-name", 
    "태스크 내용",
    execution_time_ms=1500.0,
    output="결과 텍스트",
    tool_calls=["Read", "Grep"]
)

# 오류 기록
monitor.log_error("agent-name", "태스크 내용", "오류 메시지")

# 도구 호출 기록
monitor.log_tool_call("agent-name", "Read", arguments={"path": "/some/file"})
```

### 2. Hook 시스템 연동

워크플로우 엔진과 자동 연동:

```python
from infra.agents.base import WorkflowEngine

workflow_engine = WorkflowEngine(orchestrator)

# Hook 시스템에 모니터링 훅 등록
monitor.register_hooks(workflow_engine.hooks)

# 워크플로우 실행 시 자동으로 이벤트 기록됨
workflow_engine.execute("my-workflow")
```

### 3. 통계 및 분석

```python
# 세션 요약
summary = monitor.get_summary()
print(f"총 이벤트: {summary['total_events']}")
print(f"사용된 에이전트: {summary['agents_used']}")

# 에이전트별 통계
stats = monitor.get_agent_stats()
for name, stat in stats.items():
    print(f"{name}: 호출 {stat.total_invocations}, 성공률 {stat.success_rate:.1f}%")

# 특정 에이전트 통계
proc_stats = monitor.get_agent_stats("proc-analyzer")

# 오류 목록
errors = monitor.get_errors()
for err in errors:
    print(f"[{err.agent_name}] {err.error}")
```

### 4. 리포트 생성

#### JSON 리포트
```python
# 파일로 저장
monitor.export_report("report.json", format="json")

# 문자열로 받기
json_report = monitor.export_report(format="json")
```

#### Markdown 리포트
```python
# 파일로 저장
monitor.export_report("report.md", format="markdown")

# 문자열로 받기
md_report = monitor.export_report(format="markdown")
```

출력 예시:
```markdown
# Agent Monitoring Report

## Session Info
- **Session ID**: 20260124_124500
- **Duration**: 145.23 seconds
- **Total Events**: 42

## Agent Statistics

| Agent | Invocations | Completions | Errors | Avg Time (ms) | Success Rate |
|-------|-------------|-------------|--------|---------------|--------------|
| proc-analyzer | 10 | 9 | 1 | 1250 | 90.0% |
| code-reviewer | 5 | 5 | 0 | 2100 | 100.0% |
```

### 5. 로그 파일

로그는 JSONL 형식으로 저장됩니다:

```
./logs/agent_monitoring/
└── session_20260124_124500.jsonl
```

각 줄은 하나의 이벤트:
```json
{"timestamp":"2026-01-24T12:45:00","event_type":"invoke","agent_name":"proc-analyzer","task":"분석 요청..."}
{"timestamp":"2026-01-24T12:45:02","event_type":"complete","agent_name":"proc-analyzer","execution_time_ms":1523.5,...}
```

### 6. 세션 관리

```python
# 새 세션 시작
monitor.new_session()

# 이벤트 초기화
monitor.clear()

# 이전 세션 로드
loaded_count = monitor.load_session("./logs/agent_monitoring/session_20260124_100000.jsonl")
print(f"로드된 이벤트: {loaded_count}")
```

### 7. 실시간 콜백

```python
def on_event(event):
    if event.event_type == "error":
        print(f"⚠️ 오류 발생: {event.agent_name} - {event.error}")
        # 알림 전송, 슬랙 메시지 등

monitor.add_callback(on_event)

# 콜백 제거
monitor.remove_callback(on_event)
```

### 8. 전역 모니터

싱글톤 패턴으로 전역 모니터 사용:

```python
from infra.agents.base import get_global_monitor, set_global_monitor

# 전역 모니터 가져오기 (자동 생성)
monitor = get_global_monitor()

# 커스텀 모니터 설정
custom_monitor = AgentMonitor(log_dir="./custom_logs")
set_global_monitor(custom_monitor)
```

## Configuration Options

```python
monitor = AgentMonitor(
    log_dir="./logs/agent_monitoring",  # 로그 디렉토리
    enable_file_logging=True,            # 파일 로깅 활성화
    enable_console_logging=False,        # 콘솔 출력 활성화
    max_task_length=200,                 # 태스크 텍스트 최대 길이
    max_output_length=500                # 출력 텍스트 최대 길이
)
```

## Event Types

| EventType | 설명 |
|-----------|------|
| `INVOKE` | 에이전트 호출 |
| `COMPLETE` | 에이전트 완료 |
| `ERROR` | 오류 발생 |
| `TOOL_CALL` | 도구 호출 |
| `WORKFLOW_START` | 워크플로우 시작 |
| `WORKFLOW_END` | 워크플로우 종료 |
| `STEP_START` | 워크플로우 단계 시작 |
| `STEP_END` | 워크플로우 단계 종료 |

## Example: Complete Monitoring Setup

```python
from pathlib import Path
from infra.agents.base import (
    Orchestrator, 
    WorkflowEngine,
    AgentMonitor,
    get_global_monitor
)

# 1. 모니터 설정
monitor = AgentMonitor(
    log_dir="./logs/monitoring",
    enable_console_logging=True
)

# 2. Orchestrator 설정
orchestrator = Orchestrator(
    agent_dirs=[Path(".agents")],
    monitor=monitor
)
orchestrator.load_agents()

# 3. WorkflowEngine과 Hook 연동
workflow_engine = WorkflowEngine(orchestrator)
monitor.register_hooks(workflow_engine.hooks)

# 4. 에이전트 실행
result = orchestrator.delegate("proc-analyzer", "분석 요청")

# 5. 워크플로우 실행
workflow_result = workflow_engine.execute("my-workflow")

# 6. 리포트 생성
monitor.export_report("./reports/session_report.md", format="markdown")
print(monitor.get_summary())
```
