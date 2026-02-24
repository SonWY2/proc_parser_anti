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

## 🛠️ 커스텀 도구 등록

### 방법 1: Tool 클래스 상속

자체 Python 함수를 도구로 사용하려면 `Tool` 클래스를 상속하여 구현합니다.

```python
from agent_system.tools import Tool, ToolResult, ToolRegistry
from typing import Dict, Any

class MyCustomTool(Tool):
    """내 커스텀 도구"""
    
    name = "MyTool"  # 도구 이름 (에이전트에서 사용)
    description = "커스텀 작업을 수행합니다."  # LLM이 참조하는 설명
    is_readonly = True  # 읽기 전용 여부 (파일 수정 등이 없으면 True)
    
    def execute(self, param1: str, param2: int = 10) -> ToolResult:
        """
        도구 실행 로직
        
        Args:
            param1: 필수 파라미터
            param2: 선택 파라미터 (기본값 10)
        """
        try:
            # 실제 로직 구현
            result = f"처리 완료: {param1}, {param2}"
            return ToolResult(success=True, output=result)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
    
    def _get_parameters(self) -> Dict[str, Any]:
        """LLM function calling을 위한 파라미터 스키마"""
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "필수 파라미터"},
                "param2": {"type": "integer", "description": "선택 파라미터", "default": 10}
            },
            "required": ["param1"]
        }
```

### 방법 2: 기존 함수를 래핑

이미 작성된 Python 함수를 도구로 래핑할 수 있습니다.

```python
from agent_system.tools import Tool, ToolResult, ToolRegistry
from typing import Dict, Any

# 기존에 작성한 함수
def my_existing_function(file_path: str, options: dict = None) -> dict:
    """기존 Pro*C 분석 함수"""
    # ... 기존 로직
    return {"status": "success", "data": [...]}

# Tool 클래스로 래핑
class MyExistingFunctionTool(Tool):
    name = "AnalyzeProC"
    description = "Pro*C 파일을 분석하여 SQL 패턴을 추출합니다."
    is_readonly = True
    
    def execute(self, file_path: str, use_cache: bool = True) -> ToolResult:
        try:
            # 기존 함수 호출
            result = my_existing_function(file_path, {"cache": use_cache})
            
            # 결과를 문자열로 변환 (LLM이 해석 가능하도록)
            import json
            output = json.dumps(result, ensure_ascii=False, indent=2)
            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "분석할 Pro*C 파일 경로"},
                "use_cache": {"type": "boolean", "description": "캐시 사용 여부", "default": True}
            },
            "required": ["file_path"]
        }
```

### ToolRegistry에 등록

커스텀 도구를 시스템에 등록합니다.

```python
from agent_system import Orchestrator
from agent_system.tools import ToolRegistry

# 레지스트리에 도구 등록
registry = ToolRegistry()
registry.register(MyCustomTool())
registry.register(MyExistingFunctionTool())

# 오케스트레이터에 전달
orchestrator = Orchestrator()
orchestrator.load_agents()
orchestrator.tool_registry = registry  # 커스텀 레지스트리 사용

# 또는 Subagent에 직접 전달
from agent_system import Subagent
subagent = Subagent(
    definition=agent_definition,
    llm_client=llm_client,
    tool_registry=registry  # 커스텀 도구 포함
)
```

### 에이전트 정의에서 도구 사용

등록된 커스텀 도구를 에이전트에서 사용하려면 `.md` 파일의 `tools` 필드에 추가합니다.

```markdown
---
name: proc-analyzer
description: Pro*C 코드 분석 전문 에이전트
tools: Read, Grep, MyTool, AnalyzeProC
---

시스템 프롬프트...
```

### 주의사항

| 항목 | 설명 |
|------|------|
| `name` | 영문 카멜케이스 권장, 에이전트 정의의 `tools` 필드와 일치해야 함 |
| `description` | LLM이 도구 선택 시 참조하므로 명확하게 작성 |
| `is_readonly` | 파일 수정, 외부 API 호출 등이 있으면 `False`로 설정 |
| `execute()` 반환값 | 반드시 `ToolResult` 객체 반환 |
| `_get_parameters()` | JSON Schema 형식으로 파라미터 정의, LLM function calling에 사용됨 |

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

---

## 🆕 v3 기능

### 추가된 모듈

| 파일 | 기능 |
|------|------|
| `hooks.py` | 워크플로우 훅 시스템 |
| `validator.py` | 품질 게이트, 완료 검증 |
| `checkpoint.py` | 상태 저장/복원, 사용자 승인 |
| `file_mediator.py` | 에이전트 간 파일 기반 통신 |
| `commands.py` | 슬래시 명령어 (`/convert`) |
| `cli.py` | Interactive CLI |
| `gui.py` | Tkinter GUI |
| `self_improve.py` | 자가개선 체크리스트 |

---

## 🔄 자가개선 체크리스트 시스템

반복 발생하는 실패를 자동으로 체크리스트로 변환하여 에이전트에 주입합니다.

### 활성화

```markdown
<!-- 에이전트 정의 -->
---
name: parsing-agent
self_improve: true
---
```

```yaml
# 워크플로우에서 오버라이드
steps:
  - name: parse
    agent: parsing-agent
    self_improve: false    # 이 단계에서는 비활성화
```

### Python 코드

```python
from agent_system import SelfImprovingChecklist, HookRegistry

si = SelfImprovingChecklist()
hooks = HookRegistry()
si.setup_hooks(hooks, loader)  # 자동 이슈 수집/체크리스트 주입
```

### 참고 문서

- [example.md](example.md) - Pro*C→Java 변환 가이드
- [context관리예시.md](context관리예시.md) - 메타데이터 구조

