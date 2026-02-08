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

### Q: LLM API가 없으면?
로컬 LLM (Ollama, vLLM 등)을 사용하세요:
```bash
export LLM_API_ENDPOINT=http://localhost:11434/v1  # Ollama
export LLM_MODEL=llama3
```

### Q: 동적 vs 정적 vs 마이그레이션?
- **동적**: 복잡한 작업, 예측 불가능한 상황, 학습 필요시
- **정적**: 단순 반복 작업, 명확한 단계, 빠른 실행
- **마이그레이션**: Pro*C → Java 변환에 최적화된 5단계 파이프라인

---

## 마이그레이션 모드 (Migration Mode)

Pro*C 파일을 Java로 변환하기 위한 5개 Subagent 파이프라인입니다.

```
Parser → Critic → Draftsman → SQL Specialist → BXM Designer
  (파싱)   (검증)   (초안작성)    (SQL 보정)      (Java 생성)
```

### 기본 사용법

```python
from infra.agents.langchain import LangChainOrchestrator

# 1. 마이그레이션 모드로 생성
orch = LangChainOrchestrator(mode="migration")

# 2. Pro*C 소스 코드 로드
with open("order.pc", "r", encoding="utf-8") as f:
    source_code = f.read()

# 3. 실행
result = orch.run_migration(
    source_code=source_code,
    filename="order.pc"
)

# 4. 결과 확인
print(result["java_code"])      # Java Service 코드
print(result["mapper_xml"])     # MyBatis Mapper XML
print(result["ast_data"])       # 파싱된 AST
print(result["validation_errors"])  # 검증 에러 (있다면)
```

---

## Subagent 관리

### Subagent 구조

각 Subagent는 `.md` 파일로 정의됩니다:

```
subagents/definitions/
├── parser_agent.md         # 분해자
├── critic_agent.md         # 검증자
├── draftsman_agent.md      # 초안 작성자
├── sql_specialist_agent.md # SQL 보정 전문가 (LLM)
└── bxm_designer_agent.md   # BXM 설계자 (LLM)
```

### Subagent MD 파일 형식

```markdown
---
name: my_custom_agent
persona: 커스텀 역할
description: 에이전트 설명
skills:
  - parse_proc_code
  - validate_ast
uses_llm: false
input_fields:
  - source_code
output_fields:
  - processed_data
---

# Agent Title

본문은 LLM 사용 시 system_prompt로 활용됩니다.

## 역할
- 무엇을 하는지 설명

## 처리 규칙
- 구체적인 규칙 명시
```

### 새 Subagent 추가하기

**Step 1: MD 파일 생성**

```markdown
# subagents/definitions/code_reviewer_agent.md
---
name: code_reviewer_agent
persona: 코드 리뷰어
description: 생성된 Java 코드 품질 검토
skills: []
uses_llm: true
input_fields:
  - java_code
output_fields:
  - review_result
  - suggestions
---

# Code Reviewer Agent

생성된 Java 코드의 품질을 검토하고 개선점을 제안합니다.

## 검토 항목
- 코드 스타일 준수
- 예외 처리 완전성
- 네이밍 규칙 준수
```

**Step 2: Graph에 노드 추가**

```python
# orchestration/migration_graph.py에 추가

def reviewer_node(state: MigrationState, llm: BaseChatModel) -> Dict[str, Any]:
    """Code Reviewer Agent 노드"""
    java_code = state.get("java_code", "")
    
    prompt = f"다음 Java 코드를 리뷰해주세요:\n```java\n{java_code}\n```"
    response = llm.invoke(prompt)
    
    return {
        "review_result": response.content,
        "current_agent": "code_reviewer_agent",
    }
```

**Step 3: Graph 연결 수정**

```python
def build_migration_graph(llm: BaseChatModel = None):
    workflow = StateGraph(MigrationState)
    
    # 기존 노드들...
    workflow.add_node("Designer", lambda s: designer_node(s, llm))
    
    # 새 노드 추가
    workflow.add_node("Reviewer", lambda s: reviewer_node(s, llm))
    
    # 엣지 수정: Designer → Reviewer → END
    workflow.add_edge("Designer", "Reviewer")
    workflow.add_edge("Reviewer", END)
    
    return workflow.compile()
```

### Subagent 제거하기

1. `.md` 파일 삭제: `definitions/` 디렉토리에서 제거
2. 노드 함수 제거: `migration_graph.py`에서 해당 함수 삭제
3. 엣지 수정: 연결된 엣지를 다음 노드로 변경

```python
# 예: Draftsman 제거 시
# Before: Critic → Draftsman → Specialist
# After:  Critic → Specialist

workflow.add_edge("Critic", "Specialist")  # Draftsman 건너뜀
```

---

## Workflow 커스터마이징

### 특정 시점에 Subagent 개입시키기

#### 방법 1: 조건부 엣지 (Conditional Edge)

특정 조건에서만 에이전트가 개입하도록 설정:

```python
def should_run_optimizer(state: MigrationState) -> str:
    """SQL 복잡도가 높으면 Optimizer 실행"""
    draft_xmls = state.get("draft_xmls", [])
    
    # low confidence가 있으면 Optimizer 실행
    has_complex_sql = any(
        d.get("confidence") == "low" 
        for d in draft_xmls
    )
    
    if has_complex_sql:
        return "RUN_OPTIMIZER"
    return "SKIP_OPTIMIZER"

# Graph에 조건부 엣지 추가
workflow.add_conditional_edges(
    "Draftsman",
    should_run_optimizer,
    {
        "RUN_OPTIMIZER": "SQLOptimizer",  # Optimizer 실행
        "SKIP_OPTIMIZER": "Specialist",    # 건너뜀
    }
)
```

#### 방법 2: 병렬 실행 (Parallel Execution)

여러 에이전트를 동시에 실행:

```python
from langgraph.graph import StateGraph
from typing import Sequence

def parallel_node(state: MigrationState) -> Dict[str, Any]:
    """병렬로 여러 검증 수행"""
    results = {}
    
    # 동시 실행할 작업들
    results["security_check"] = security_checker(state)
    results["performance_check"] = performance_checker(state)
    
    return {"parallel_results": results}
```

#### 방법 3: 반복 루프 (Loop)

품질이 충족될 때까지 반복:

```python
def quality_check(state: MigrationState) -> str:
    """품질 점수에 따라 반복 또는 종료"""
    score = state.get("quality_score", 0)
    iterations = state.get("iteration_count", 0)
    
    if score >= 0.8 or iterations >= 3:
        return "DONE"
    return "RETRY"

workflow.add_conditional_edges(
    "Reviewer",
    quality_check,
    {
        "RETRY": "Specialist",  # 다시 보정
        "DONE": END,
    }
)
```

---

## Skills 시스템

### Skills 개요

Skills는 Python 모듈을 래핑하여 Subagent에서 호출할 수 있게 합니다.

```
skills/
├── skill_interface.py     # BaseSkill, SkillResult
├── skills_registry.py     # 레지스트리 (Mock/Real 스위칭)
├── parse_proc_code.py     # ProCParser 래핑
├── validate_ast.py        # AST 검증
└── convert_sql_draft.py   # MyBatisConverter 래핑
```

### Skills와 Subagent 연결 관계

```
┌─────────────────────────────────────────────────────────────┐
│  Subagent (MD 정의)                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  skills:                                              │   │
│  │    - parse_proc_code  ──────┐                        │   │
│  │    - validate_ast     ──────┼───► SkillsRegistry    │   │
│  │    - convert_sql_draft ─────┘           │            │   │
│  └─────────────────────────────────────────────────────┘   │
│                                              ↓              │
│                                    ┌───────────────────┐   │
│                                    │  Python Module    │   │
│                                    │  (ProCParser 등)  │   │
│                                    └───────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Skill 직접 호출

```python
from infra.agents.langchain.skills import get_registry

# 레지스트리 가져오기
registry = get_registry()

# Skill 가져오기
parser_skill = registry.get("parse_proc_code")

# 실행
result = parser_skill.invoke("EXEC SQL SELECT * FROM users; END-EXEC;")

if result.success:
    print("Headers:", result.data["headers"])
    print("SQL Blocks:", result.data["sql_blocks"])
else:
    print("Errors:", result.errors)
```

### 새 Skill 만들기

**Step 1: Skill 클래스 생성**

```python
# skills/extract_functions.py
from .skill_interface import BaseSkill, SkillResult
from typing import Any

class ExtractFunctionsSkill(BaseSkill):
    """함수 추출 Skill"""
    
    @property
    def name(self) -> str:
        return "extract_functions"
    
    def invoke(self, input_data: Any) -> SkillResult:
        try:
            # 실제 로직 구현
            functions = self._extract(input_data)
            
            return SkillResult(
                success=True,
                data={"functions": functions}
            )
        except Exception as e:
            return SkillResult(
                success=False,
                data={},
                errors=[str(e)]
            )
    
    def _extract(self, code: str) -> list:
        # 함수 추출 로직
        pass
```

**Step 2: 레지스트리에 등록**

```python
# skills/__init__.py에 추가
from .extract_functions import ExtractFunctionsSkill

# 또는 런타임에 등록
from infra.agents.langchain.skills import get_registry

registry = get_registry()
registry.register(ExtractFunctionsSkill())
```

**Step 3: Subagent에서 사용**

```markdown
# subagents/definitions/function_parser_agent.md
---
name: function_parser_agent
skills:
  - extract_functions    # 새로 만든 Skill
  - validate_ast
---
```

### Mock Skill 사용 (테스트용)

```python
from infra.agents.langchain.skills import get_registry

# Mock 모드로 레지스트리 생성
registry = get_registry(use_mock=True)

# Mock 데이터 등록
registry.register_mock("parse_proc_code", {
    "headers": [{"name": "sqlca.h"}],
    "sql_blocks": [{"id": "sql_0", "content": "SELECT 1"}],
    "host_vars": [],
    "functions": []
})

# Mock Skill 사용
result = registry.get("parse_proc_code").invoke("any input")
print(result.data)  # Mock 데이터 반환
```

### 기본 제공 Skills

| Skill 이름 | 래핑 대상 | 역할 |
|-----------|----------|------|
| `parse_proc_code` | `ProCParser` | Pro*C 파싱 → AST |
| `validate_ast` | (내장 로직) | AST 무결성 검증 |
| `convert_sql_draft` | `MyBatisConverter` | SQL → MyBatis XML |

---

## 전체 파이프라인 예제

```python
from infra.agents.langchain import (
    LangChainOrchestrator,
    SkillsRegistry,
    SubagentLoader,
)

# 1. Skills 확인
registry = SkillsRegistry()
print("사용 가능한 Skills:", registry.list_skills())

# 2. Subagents 확인
loader = SubagentLoader()
agents = loader.load_all()
print("로드된 Subagents:", list(agents.keys()))

# 3. 파이프라인 실행
orch = LangChainOrchestrator(mode="migration")

source = '''
EXEC SQL INCLUDE sqlca;

int process_order(int order_id) {
    EXEC SQL BEGIN DECLARE SECTION;
        int v_count;
    EXEC SQL END DECLARE SECTION;
    
    EXEC SQL SELECT COUNT(*) INTO :v_count FROM orders WHERE id = :order_id;
    return v_count;
}
'''

result = orch.run_migration(source_code=source, filename="order.pc")

# 4. 결과
print("=== 파싱 결과 ===")
print(result["ast_data"])

print("\n=== 검증 에러 ===")
print(result["validation_errors"])

print("\n=== Java 코드 ===")
print(result["java_code"])
```

---

## 트러블슈팅

### Skill이 등록되지 않음
```python
# 기본 Skills 수동 로드
registry = SkillsRegistry(use_mock=False)
registry.load_default_skills()
```

### Subagent MD 파일을 찾을 수 없음
```python
# 경로 직접 지정
from pathlib import Path
loader = SubagentLoader(agents_dir=Path("./custom/definitions"))
```

### 검증 실패로 파이프라인 중단
검증 에러 확인 후 수동 처리:
```python
result = orch.run_migration(source_code=code)

if result["validation_errors"]:
    print("검증 실패:", result["validation_errors"])
    # 수동 수정 후 재실행
```

---

## 모니터링 & 디버깅

### 로컬 모니터링 (PipelineMonitor)

```python
from infra.agents.langchain.monitoring import (
    PipelineMonitor,
    create_monitored_graph,
)
from infra.agents.langchain.state import create_migration_state

# 모니터링된 그래프 생성
graph, monitor = create_monitored_graph(llm)

# 실행
initial_state = create_migration_state(source_code, "order.pc")
result = graph.invoke(initial_state)

# 결과 확인
monitor.print_summary()
```

출력 예시:
```
📊 Pipeline Execution Summary
============================================================
✓ 1. Parser               45.2ms ██
✓ 2. Critic               12.1ms █
✓ 3. Draftsman           234.5ms ██████
✓ 4. Specialist         1520.3ms ████████████████████
✓ 5. Designer           2341.8ms ██████████████████████████
------------------------------------------------------------
Total: 4153.9ms (5 nodes)
```

### 리포트 내보내기

```python
# HTML 리포트 (Mermaid 다이어그램 포함)
monitor.export_html_report("pipeline_report.html")

# JSON 트레이스
monitor.export_json("pipeline_trace.json")

# Mermaid 다이어그램
print(monitor.export_mermaid())
```

### 실행 스크립트

```bash
# 모니터링 테스트 실행
python -m infra.agents.langchain.monitoring.run_monitored
```

### LangSmith 트레이싱

```bash
# 환경 변수 설정
set LANGCHAIN_TRACING_V2=true
set LANGCHAIN_API_KEY=<your-api-key>
set LANGCHAIN_PROJECT=migration-pipeline

# 실행하면 자동으로 LangSmith에 기록됨
python your_script.py
```

