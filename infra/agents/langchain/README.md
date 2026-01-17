# lang_chain_agents

LangGraph 기반 멀티 에이전트 시스템으로 Pro*C to Java 변환을 지원합니다.

## 두 가지 오케스트레이션 모드

### 🚀 Dynamic Mode (권장)
Reflection + Self-Evolve 기반 동적 오케스트레이션

- **Planner**: 현재 상태를 분석하여 동적으로 다음 계획 수립
- **Router**: 계획에 따라 적절한 전문 에이전트 선택
- **Reflector**: 결과 자기 비평, 품질 평가
- **Memory**: 과거 교훈 저장/참조 (Self-Evolve)

### 📋 Static Mode
미리 정의된 워크플로우 기반 실행

- 6단계 순차 실행 파이프라인
- 각 단계별 에이전트 고정
- 예측 가능한 실행 흐름

## 설치

```bash
pip install langchain-core langgraph langchain-openai python-dotenv
```

## 빠른 시작

### 동적 모드

```python
from lang_chain_agents import LangChainOrchestrator

# 환경 변수 설정 필요
# export LLM_API_ENDPOINT=http://localhost:8000/v1
# export LLM_API_KEY=your-api-key
# export LLM_MODEL=gpt-4

orch = LangChainOrchestrator(mode="dynamic")
result = orch.run(
    "Pro*C 파일을 Java로 변환",
    context={"target_dir": "./src/proc", "output_dir": "./output"}
)
print(result["artifacts"])
```

### 정적 모드

```python
from lang_chain_agents import LangChainOrchestrator, PROC_TO_JAVA_WORKFLOW

orch = LangChainOrchestrator(mode="static")
orch.set_workflow(PROC_TO_JAVA_WORKFLOW)
result = orch.run("Pro*C 변환", context={"target_dir": "./src"})
```

## 7개 전문 에이전트

| 에이전트 | 역할 |
|---------|------|
| `dependency_analyst` | 파일 종속성, 공유 헤더 분석 |
| `parsing_agent` | 함수, 변수, 구조체 파싱 |
| `sql_analyst` | EXEC SQL → MyBatis 변환 |
| `context_engineer` | 분석 결과 통합 |
| `transformer` | Java 코드 생성 |
| `build_debug` | 빌드/컴파일 검증 |
| `critic` | 품질 평가 |

## 커스텀 에이전트 추가

```python
from lang_chain_agents import LangChainOrchestrator, AgentConfig

my_agent = AgentConfig(
    name="my_agent",
    description="My custom agent",
    system_prompt="You are a specialized assistant...",
    tools=["read_file", "write_file"]
)

orch = LangChainOrchestrator()
orch.register_agent(my_agent)
```

## 커스텀 워크플로우 (정적 모드)

```python
from lang_chain_agents import BaseWorkflow, WorkflowStep

workflow = BaseWorkflow(
    name="custom",
    description="Custom workflow",
    steps=[
        WorkflowStep(name="step1", agent="dependency_analyst", 
                     task_template="분석...", next_step="step2"),
        WorkflowStep(name="step2", agent="transformer",
                     task_template="변환...", next_step=None),
    ]
)

orch.set_workflow(workflow)
```

## 환경 변수

| 변수 | 설명 | 기본값 |
|-----|------|--------|
| `LLM_API_ENDPOINT` | LLM API URL | - |
| `LLM_API_KEY` | API 키 | - |
| `LLM_MODEL` | 모델 이름 | gpt-4 |
| `LLM_TEMPERATURE` | 온도 | 0.1 |
| `LLM_MAX_TOKENS` | 최대 토큰 | 4096 |
