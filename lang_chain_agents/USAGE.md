# lang_chain_agents 사용 가이드

## 설치

```bash
pip install langchain-core langgraph langchain-openai python-dotenv
```

## 환경 설정

### 환경 변수
```bash
# Windows (cmd)
set LLM_API_ENDPOINT=http://localhost:8000/v1
set LLM_API_KEY=your-api-key
set LLM_MODEL=gpt-4

# Windows (PowerShell)
$env:LLM_API_ENDPOINT = "http://localhost:8000/v1"
$env:LLM_API_KEY = "your-api-key"
$env:LLM_MODEL = "gpt-4"

# Linux/Mac
export LLM_API_ENDPOINT=http://localhost:8000/v1
export LLM_API_KEY=your-api-key
export LLM_MODEL=gpt-4
```

### .env 파일 사용
```
LLM_API_ENDPOINT=http://localhost:8000/v1
LLM_API_KEY=your-api-key
LLM_MODEL=gpt-4
LLM_TEMPERATURE=0.1
```

## 사용법

### 1. 동적 오케스트레이션 (Dynamic Mode)

Reflection + Self-Evolve 기반으로 동적으로 계획을 수립하고 실행합니다.

```python
from lang_chain_agents import LangChainOrchestrator

# 오케스트레이터 생성 (기본: 동적 모드)
orch = LangChainOrchestrator(mode="dynamic")

# 실행
result = orch.run(
    task="src/proc 디렉토리의 Pro*C 파일을 Java로 변환해주세요",
    context={
        "target_dir": "./src/proc",
        "output_dir": "./output/java"
    }
)

# 결과 확인
print("Artifacts:", list(result["artifacts"].keys()))
print("Executed:", result["executed_steps"])
print("Lessons:", result["lessons_applied"])
```

### 2. 정적 워크플로우 (Static Mode)

미리 정의된 6단계 파이프라인을 순차 실행합니다.

```python
from lang_chain_agents import LangChainOrchestrator, PROC_TO_JAVA_WORKFLOW

# 정적 모드로 생성
orch = LangChainOrchestrator(mode="static")
orch.set_workflow(PROC_TO_JAVA_WORKFLOW)

# 실행
result = orch.run(
    task="Pro*C 변환",
    context={"target_dir": "./src", "output_dir": "./output"}
)
```

### 3. 커스텀 에이전트 추가

```python
from lang_chain_agents import LangChainOrchestrator, AgentConfig

# 커스텀 에이전트 정의
my_agent = AgentConfig(
    name="my_custom_agent",
    description="특수 작업 처리",
    system_prompt="당신은 특수 작업 전문가입니다...",
    tools=["read_file", "write_file", "grep_search"]
)

# 등록
orch = LangChainOrchestrator()
orch.register_agent(my_agent)

# 에이전트 목록 확인
print(orch.list_agents())
```

### 4. 커스텀 워크플로우

```python
from lang_chain_agents import BaseWorkflow, WorkflowStep

# 워크플로우 정의
custom_workflow = BaseWorkflow(
    name="my_workflow",
    description="커스텀 변환 파이프라인",
    steps=[
        WorkflowStep(
            name="analyze",
            agent="dependency_analyst",
            task_template="${target_dir} 분석",
            next_step="convert"
        ),
        WorkflowStep(
            name="convert",
            agent="transformer",
            task_template="Java로 변환, 출력: ${output_dir}",
            next_step=None  # 종료
        ),
    ]
)

orch.set_mode("static")
orch.set_workflow(custom_workflow)
result = orch.run("시작", context={"target_dir": "./src", "output_dir": "./out"})
```

### 5. 메모리 관리 (Self-Evolve)

```python
# 메모리 통계
stats = orch.get_memory_stats()
print(f"총 에피소드: {stats['total_episodes']}")
print(f"성공률: {stats['success_rate']:.1%}")
print(f"교훈 수: {stats['lessons_count']}")

# 메모리 저장/로드
orch.save_memory("./memory.json")
orch.load_memory("./memory.json")

# 메모리 초기화
orch.clear_memory()
```

## 기본 제공 에이전트

| 이름 | 역할 | 도구 |
|-----|------|------|
| `dependency_analyst` | 종속성 분석 | read_file, glob_search, grep_search |
| `parsing_agent` | 코드 파싱 | read_file, grep_search |
| `sql_analyst` | SQL 추출/변환 | read_file, grep_search |
| `context_engineer` | 컨텍스트 생성 | read_file |
| `transformer` | Java 코드 생성 | read_file, write_file |
| `build_debug` | 빌드/디버그 | read_file, grep_search |
| `critic` | 품질 평가 | read_file |

## 기본 제공 도구

| 이름 | 설명 |
|-----|------|
| `read_file` | 파일 읽기 (줄 범위 지정 가능) |
| `write_file` | 파일 쓰기 |
| `glob_search` | glob 패턴으로 파일 검색 |
| `grep_search` | 정규식 패턴으로 내용 검색 |
| `list_dir` | 디렉토리 목록 |

## FAQ

### Q: LLM API가 없으면?
로컬 LLM (Ollama, vLLM 등)을 사용하세요:
```bash
export LLM_API_ENDPOINT=http://localhost:11434/v1  # Ollama
export LLM_MODEL=llama3
```

### Q: 동적 vs 정적 어떤 걸 써야 하나요?
- **동적**: 복잡한 작업, 예측 불가능한 상황, 학습 필요시
- **정적**: 단순 반복 작업, 명확한 단계, 빠른 실행
