# 기존 Python 모듈 통합 가이드

`lang_chain_agents` 모듈과 기존 Pro*C 파서 Python 코드를 통합하는 방법을 설명합니다.

---

## 통합 개요

```
┌─────────────────────────────────────────────────────────┐
│                 lang_chain_agents                        │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────┐ │
│  │  LLM Agent  │───▶│  Tool Call   │───▶│ 기존 Python │ │
│  │  (추론/판단) │    │  (도구 호출)  │    │   모듈      │ │
│  └─────────────┘    └──────────────┘    └────────────┘ │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │  기존 Pro*C 파서 모듈들         │
              │  - parser_core                │
              │  - sql_converter              │
              │  - sql_extractor              │
              │  - plugins/*                  │
              └───────────────────────────────┘
```

---

## 통합 방법

### 방법 1: 커스텀 도구로 래핑

기존 Python 함수를 `ToolDefinition`으로 래핑하여 에이전트가 호출할 수 있게 합니다.

```python
from lang_chain_agents.tools.base import ToolDefinition

# 기존 모듈 임포트
from your_module import your_function

# 도구 정의
your_tool = ToolDefinition(
    name="tool_name",
    description="에이전트가 이해할 수 있는 도구 설명",
    func=your_function,  # 기존 함수 직접 연결
)
```

#### 예시: parser_core 통합

```python
from parser_core import parse_proc_file
from lang_chain_agents.tools.base import ToolDefinition
import json

def _parse_proc_wrapper(file_path: str) -> str:
    """LLM 친화적 문자열 반환"""
    result = parse_proc_file(file_path)
    return json.dumps(result, ensure_ascii=False, indent=2)

proc_parser_tool = ToolDefinition(
    name="proc_parser",
    description="Pro*C 파일을 파싱하여 함수, 변수, SQL 블록 정보를 JSON으로 반환",
    func=_parse_proc_wrapper,
)
```

#### 예시: sql_extractor 통합

```python
from sql_extractor import SQLExtractor

def _extract_sql(file_path: str) -> str:
    extractor = SQLExtractor()
    sqls = extractor.extract(file_path)
    return json.dumps([
        {"type": s.sql_type, "content": s.content, "line": s.line}
        for s in sqls
    ])

sql_extractor_tool = ToolDefinition(
    name="sql_extractor",
    description="Pro*C 파일에서 EXEC SQL 블록을 추출하여 타입별로 분류",
    func=_extract_sql,
)
```

#### 예시: sql_converter 통합

```python
from sql_converter import SQLConverter

def _convert_sql(sql: str) -> str:
    converter = SQLConverter()
    normalized = converter.normalize_sql(sql)
    return normalized

sql_converter_tool = ToolDefinition(
    name="sql_converter",
    description="Pro*C SQL을 MyBatis 호환 형식으로 변환 (호스트 변수 → #{param})",
    func=_convert_sql,
)
```

---

### 방법 2: 오케스트레이터에 등록

```python
from lang_chain_agents import LangChainOrchestrator

orch = LangChainOrchestrator(mode="dynamic")

# 도구 등록
orch.tool_registry.register_tool(proc_parser_tool)
orch.tool_registry.register_tool(sql_extractor_tool)
orch.tool_registry.register_tool(sql_converter_tool)
```

또는 간단히:

```python
orch.register_tool(
    name="proc_parser",
    description="Pro*C 파일 파싱",
    func=parse_proc_file
)
```

---

### 방법 3: 에이전트가 도구 사용하도록 설정

```python
from lang_chain_agents import AgentConfig

# 기존 도구를 사용하는 에이전트 정의
parsing_agent = AgentConfig(
    name="parsing_agent",
    description="Pro*C 코드 구조 분석",
    tools=["proc_parser", "sql_extractor"],  # 래핑된 도구 이름
    system_prompt="""당신은 Pro*C 파싱 전문가입니다.

사용 가능한 도구:
- proc_parser: 파일 구조 분석
- sql_extractor: SQL 블록 추출

도구를 호출하여 정확한 파싱 결과를 기반으로 분석하세요.
"""
)

orch.register_agent(parsing_agent)
```

---

## 플러그인 통합

기존 `plugins/` 디렉토리의 분석 플러그인들을 도구로 래핑:

```python
from plugins.cursor_relationship import CursorRelationshipPlugin
from plugins.dynamic_sql_relationship import DynamicSqlRelationshipPlugin
from plugins.transaction_relationship import TransactionRelationshipPlugin

def _analyze_cursors(source_code: str) -> str:
    plugin = CursorRelationshipPlugin()
    result = plugin.analyze(source_code)
    return json.dumps(result)

cursor_tool = ToolDefinition(
    name="cursor_analyzer",
    description="DECLARE/OPEN/FETCH/CLOSE 커서 관계 분석",
    func=_analyze_cursors,
)
```

---

## 하이브리드 워크플로우 예시

LLM 추론과 기존 Python 코드 실행을 결합:

```python
from lang_chain_agents import BaseWorkflow, WorkflowStep

hybrid_workflow = BaseWorkflow(
    name="hybrid_conversion",
    description="기존 파서 + LLM 변환",
    steps=[
        # 1단계: 기존 파서로 정확한 구조 추출
        WorkflowStep(
            name="parse",
            agent="parsing_agent",  # proc_parser 도구 사용
            task_template="proc_parser 도구로 ${target_dir}를 파싱하세요.",
            next_step="analyze",
        ),
        # 2단계: LLM이 파싱 결과 해석/보완
        WorkflowStep(
            name="analyze", 
            agent="context_engineer",
            task_template="파싱 결과를 분석하여 변환 컨텍스트를 생성하세요.",
            next_step="transform",
        ),
        # 3단계: LLM이 Java 코드 생성
        WorkflowStep(
            name="transform",
            agent="transformer",
            task_template="Java 코드를 생성하세요. 출력: ${output_dir}",
            next_step=None,
        ),
    ]
)
```

---

## 도구 래핑 규칙

### 함수 시그니처

```python
def tool_function(arg1: str, arg2: str = None) -> str:
    """
    반드시 문자열 반환 (LLM이 결과를 읽어야 함)
    복잡한 객체는 JSON 직렬화
    """
    result = your_existing_function(arg1, arg2)
    return json.dumps(result) if not isinstance(result, str) else result
```

### 에러 처리

```python
def safe_wrapper(file_path: str) -> str:
    try:
        result = risky_function(file_path)
        return json.dumps({"success": True, "data": result})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
```

### 설명 작성

```python
ToolDefinition(
    name="short_name",  # 짧고 명확한 이름
    description="""
    한 줄 요약: 무엇을 하는 도구인지
    
    입력: file_path (Pro*C 파일 경로)
    출력: JSON 형식의 파싱 결과
    
    사용 시점: SQL 블록을 추출해야 할 때
    """,
    func=your_function,
)
```

---

## 통합 후 실행

```python
from lang_chain_agents import LangChainOrchestrator

# 설정
orch = LangChainOrchestrator(mode="dynamic")

# 기존 모듈 통합 (위에서 정의한 도구들)
orch.tool_registry.register_tool(proc_parser_tool)
orch.tool_registry.register_tool(sql_extractor_tool)
orch.tool_registry.register_tool(sql_converter_tool)

# 실행 - LLM이 필요에 따라 도구 호출
result = orch.run(
    "Pro*C 파일을 분석하고 Java로 변환해주세요",
    context={"target_dir": "./src/proc", "output_dir": "./output"}
)

print("생성된 산출물:", list(result["artifacts"].keys()))
```

---

## 장점

| 기존 파서 | LLM 에이전트 | 통합 시 |
|-----------|-------------|--------|
| 정확한 구문 분석 | 유연한 해석 | 정확성 + 유연성 |
| 결정론적 결과 | 맥락 이해 | 예외 상황 대응 |
| 빠른 실행 | 자연어 처리 | 인터페이스 단순화 |

---

## 파일 위치 권장

```
lang_chain_agents/
├── tools/
│   ├── file_tools.py           # 기본 파일 도구
│   └── proc_parser_tools.py    # 기존 모듈 래핑 (신규 생성)
```
