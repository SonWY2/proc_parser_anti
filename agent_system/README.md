# Agent System (서브에이전트 시스템)

Claude Code 스타일의 서브에이전트 시스템입니다. `.md` 파일로 에이전트를 정의하고, 독립 컨텍스트에서 실행됩니다.

## 📁 모듈 구조

```
agent_system/
├── __init__.py          # 모듈 진입점 및 public API 정의
├── __main__.py          # CLI 인터페이스
├── agent_loader.py      # 에이전트 정의 파일 로더
├── llm_client.py        # OpenAI 호환 LLM API 클라이언트
├── orchestrator.py      # 서브에이전트 오케스트레이터
├── result.py            # 결과 데이터 구조
├── subagent.py          # 서브에이전트 실행 엔진
└── tools.py             # 도구 시스템 (Read, Grep, Glob, Bash, Edit 등)
```

---

## 🚀 빠른 시작

### 1. 환경 변수 설정

```bash
# LLM API 설정 (필수)
export LLM_API_ENDPOINT=http://localhost:8000/v1
export LLM_API_KEY=your-api-key

# 또는 OpenAI 호환 형식
export OPENAI_API_KEY=your-openai-key
export VLLM_API_ENDPOINT=http://localhost:8000/v1
```

### 2. CLI로 실행

```bash
# 에이전트 목록 확인
python -m agent_system list

# 특정 에이전트로 작업 실행
python -m agent_system run proc-analyzer "main.py 파일의 SQL 패턴 분석"

# 자동 매칭으로 작업 실행
python -m agent_system auto "Pro*C 코드에서 커서 찾기"

# 사용 가능한 도구 목록
python -m agent_system tools
```

### 3. Python 코드로 사용

```python
from agent_system import Orchestrator

# 오케스트레이터 생성 및 에이전트 로드
orchestrator = Orchestrator()
orchestrator.load_agents()

# 특정 에이전트에게 작업 위임
result = orchestrator.delegate("proc-analyzer", "EXEC SQL 패턴 분석")
print(result.output)

# 자동 매칭으로 작업 위임
result = orchestrator.auto_delegate("Pro*C 커서 사용 분석")
if result:
    print(result.output)

# 병렬 실행
tasks = [
    {"agent": "proc-analyzer", "task": "SQL 패턴 분석"},
    {"agent": "file-explorer", "task": "*.pc 파일 탐색"}
]
results = orchestrator.delegate_parallel(tasks)
```

---

## 📝 에이전트 정의

에이전트는 `.agents/` 디렉토리에 `.md` 파일로 정의합니다.

### 에이전트 정의 파일 형식

```markdown
---
name: my-agent
description: 언제 이 에이전트를 사용해야 하는지 설명
tools: Read, Grep, Glob
model: inherit
---

여기에 시스템 프롬프트를 작성합니다.

## 역할
에이전트가 수행할 작업 설명...

## 출력 형식
결과 형식 정의...
```

#### Frontmatter 필드

| 필드 | 필수 | 설명 |
|------|------|------|
| `name` | ✅ | 에이전트 고유 이름 |
| `description` | ✅ | 에이전트 용도 설명 (자동 매칭에 사용) |
| `tools` | ❌ | 허용된 도구 목록 (쉼표 구분, 미지정시 모든 도구) |
| `model` | ❌ | 사용할 모델 (`inherit`: 시스템 기본값) |

### 오케스트레이터 정의

프로젝트 수준에서 요청 라우팅 규칙을 정의할 수 있습니다.

```markdown
---
name: main-orchestrator
type: orchestrator
description: 메인 조율 에이전트
default_agent: file-explorer
delegate_rules:
  - pattern: "분석|analyze|SQL"
    agent: proc-analyzer
    priority: 10
  - pattern: "리뷰|review"
    agent: code-reviewer
    priority: 10
---

시스템 프롬프트...
```

#### 오케스트레이터 Frontmatter 필드

| 필드 | 필수 | 설명 |
|------|------|------|
| `type` | ✅ | `orchestrator`로 설정 |
| `default_agent` | ❌ | 매칭되는 규칙이 없을 때 사용할 기본 에이전트 |
| `delegate_rules` | ❌ | 위임 규칙 목록 |

---

## 🔧 내장 도구

| 도구 | 설명 | 읽기 전용 |
|------|------|----------|
| `Read` | 파일 내용 읽기 (줄 범위 지정 가능) | ✅ |
| `Grep` | 정규식 패턴으로 파일 검색 | ✅ |
| `Glob` | glob 패턴으로 파일 탐색 | ✅ |
| `Bash` | 쉘 명령 실행 | ❌ |
| `Edit` | 파일 내용 수정 | ❌ |
| `Write` | 새 파일 생성 | ❌ |
| `Dispatch` | 다른 에이전트에게 작업 위임 | ✅ |
| `View` | 코드 요소 상세 보기 | ✅ |

---

## 📂 핵심 클래스

### Orchestrator

서브에이전트를 관리하고 작업을 위임합니다.

```python
from agent_system import Orchestrator

orchestrator = Orchestrator(
    agent_dirs=[Path("./.agents")],  # 에이전트 정의 디렉토리
    llm_config=None,                  # LLM 설정 (없으면 환경변수 사용)
    max_parallel=5                    # 최대 병렬 실행 수
)

# 에이전트 로드
orchestrator.load_agents(base_path=Path.cwd())

# 작업 위임
result = orchestrator.delegate("agent-name", "작업 설명")

# 자동 매칭 위임
result = orchestrator.auto_delegate("사용자 요청")

# 병렬 작업
results = orchestrator.delegate_parallel([
    {"agent": "agent1", "task": "task1"},
    {"agent": "agent2", "task": "task2"}
])
```

### Subagent

독립 컨텍스트에서 작업을 실행합니다.

```python
from agent_system import Subagent, AgentDefinition

subagent = Subagent(
    definition=agent_definition,  # AgentDefinition 인스턴스
    llm_client=llm_client,        # LLMClient 인스턴스
    tool_registry=registry        # ToolRegistry (선택)
)

result = subagent.run("작업 설명")
```

### SubagentResult

실행 결과를 담는 데이터 클래스입니다.

```python
@dataclass
class SubagentResult:
    success: bool              # 성공 여부
    output: str                # 최종 출력
    agent_name: str            # 에이전트 이름
    execution_time: float      # 실행 시간 (초)
    tool_calls: List[ToolCallRecord]  # 도구 호출 기록
    error: Optional[str]       # 에러 메시지
    context_length: int        # 사용된 컨텍스트 길이
```

### LLMConfig

LLM API 설정을 관리합니다.

```python
from agent_system.llm_client import LLMConfig

# 직접 설정
config = LLMConfig(
    endpoint="http://localhost:8000/v1",
    api_key="your-key",
    model="gpt-4",
    timeout=60
)

# 환경 변수에서 로드
config = LLMConfig.from_env()
```

---

## 🎯 자동 매칭 우선순위

`auto_delegate()` 호출 시 에이전트 선택 순서:

1. **오케스트레이터 `delegate_rules`**: 패턴 매칭 (priority 높은 순)
2. **에이전트 `description`**: 키워드 매칭
3. **`default_agent`**: 기본 에이전트

---

## 📁 디렉토리 검색 순서

에이전트 정의 파일은 다음 위치에서 검색됩니다:

1. `.agents/` - 프로젝트 수준
2. `.claude/agents/` - Claude Code 호환

---

## 예시: 에이전트 정의 파일

### proc-analyzer.md

```markdown
---
name: proc-analyzer
description: Pro*C 소스 코드 분석, SQL 패턴 식별, 호스트 변수 추적
tools: Read, Grep, Glob
model: inherit
---

You are a Pro*C code analysis expert.

## 전문 분야
- Pro*C 임베디드 SQL 분석
- 호스트 변수 및 타입 매핑
- 커서 선언 및 사용 추적

## 작업 방식
1. Grep으로 EXEC SQL 패턴 검색
2. Glob으로 .pc 파일 탐색
3. Read로 상세 분석
```

### file-explorer.md

```markdown
---
name: file-explorer
description: 파일 시스템 탐색, 파일 검색, 디렉토리 구조 분석
tools: Read, Grep, Glob
model: inherit
---

파일 탐색 전문 에이전트입니다.

## 역할
- 파일 및 디렉토리 검색
- 패턴 기반 파일 찾기
- 구조 분석 및 보고
```
