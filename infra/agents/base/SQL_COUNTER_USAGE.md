# SQL Counter Multi-Agent System 사용 가이드

Pro*C 코드에서 SQL 구문 개수를 추출하는 멀티 에이전트 시스템입니다.

## 📋 개요

이 시스템은 다음 에이전트들로 구성됩니다:

| 에이전트 | 역할 |
|----------|------|
| `sql-counter-orchestrator` | 전체 작업 조율 |
| `code-chunker` | 긴 코드를 청크로 분할 |
| `sql-counter` | SQL 구문 개수 추출 |
| `result-aggregator` | 청크별 결과 통합 |

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# LLM API 설정 (필수)
export LLM_API_ENDPOINT=http://localhost:8000/v1
export LLM_API_KEY=your-api-key
```

### 2. CLI 사용

```bash
cd d:\workspace\proc_parser_antigravity\proc_parser

# 에이전트 목록 확인 (sql-counter 관련 에이전트 포함 확인)
python -m agent_system list

# SQL 카운팅 작업 실행
python -m agent_system run sql-counter "sample.pc 파일의 SQL 개수 세기"
```

---

## 🐍 Python API 사용

### 방법 1: 커스텀 도구 직접 사용 (권장)

LLM 호출 없이 도구를 직접 사용하는 가장 간단한 방법입니다.

```python
from agent_system.sql_counter_tools import (
    chunk_code_tool,
    count_sql_tool,
    aggregate_results_tool
)
import json

# 예제 Pro*C 코드
code = """
EXEC SQL BEGIN DECLARE SECTION;
    char emp_name[50];
    int emp_id;
EXEC SQL END DECLARE SECTION;

void fetch_employee(int id) {
    EXEC SQL SELECT name INTO :emp_name FROM employees WHERE id = :emp_id;
    EXEC SQL INSERT INTO log_table VALUES (:emp_id, SYSDATE);
    EXEC SQL UPDATE employees SET last_access = SYSDATE WHERE id = :emp_id;
    EXEC SQL COMMIT;
}

void process_all() {
    EXEC SQL DECLARE emp_cursor CURSOR FOR SELECT id, name FROM employees;
    EXEC SQL OPEN emp_cursor;
    EXEC SQL FETCH emp_cursor INTO :emp_id, :emp_name;
    EXEC SQL CLOSE emp_cursor;
}
"""

# 1. 짧은 코드: 직접 카운팅
result = count_sql_tool.execute(code=code, include_details=True)
print(result.output)

# 2. 긴 코드: 청킹 후 카운팅
if len(code) > 5000:
    # 코드 분할
    chunk_result = chunk_code_tool.execute(code=code, chunk_size=5000)
    chunks = json.loads(chunk_result.output)["chunks"]
    
    # 각 청크별 카운팅
    chunk_counts = []
    for chunk in chunks:
        count_result = count_sql_tool.execute(
            code=chunk["content"], 
            chunk_index=chunk["index"]
        )
        chunk_counts.append(json.loads(count_result.output))
    
    # 결과 통합
    final_result = aggregate_results_tool.execute(
        results=json.dumps(chunk_counts)
    )
    print(final_result.output)
```

### 방법 2: 오케스트레이터를 통한 에이전트 실행

LLM 기반 에이전트를 사용하는 방법입니다.

```python
from agent_system import Orchestrator
from agent_system.tools import ToolRegistry
from agent_system.sql_counter_tools import register_sql_counter_tools

# 오케스트레이터 생성
orchestrator = Orchestrator()

# SQL 카운터 도구 등록
register_sql_counter_tools(orchestrator.tool_registry)

# 에이전트 로드
orchestrator.load_agents()

# sql-counter 에이전트에게 작업 위임
code = "... Pro*C 코드 ..."
result = orchestrator.delegate(
    "sql-counter", 
    f"다음 코드의 SQL 개수를 세어주세요:\n\n{code}"
)
print(result.output)
```

### 방법 3: 독립 Subagent 사용

특정 에이전트만 사용하고 싶을 때.

```python
from agent_system import Subagent, AgentLoader
from agent_system.llm_client import LLMClient, LLMConfig
from agent_system.tools import ToolRegistry
from agent_system.sql_counter_tools import register_sql_counter_tools
from pathlib import Path

# 에이전트 정의 로드
loader = AgentLoader()
loader.load_from_directory(Path(".agents"))
agent_def = loader.get_agent("sql-counter")

# LLM 클라이언트
config = LLMConfig.from_env()
llm_client = LLMClient(config)

# 도구 레지스트리
registry = ToolRegistry()
register_sql_counter_tools(registry)

# Subagent 생성 및 실행
subagent = Subagent(
    definition=agent_def,
    llm_client=llm_client,
    tool_registry=registry
)

code = "... Pro*C 코드 ..."
result = subagent.run(f"SQL 개수 세기:\n\n{code}")
print(result.output)
```

---

## 🔧 커스텀 도구 상세

### ChunkCodeTool

긴 코드를 SQL 구문이 잘리지 않도록 청크로 분할합니다.

```python
from agent_system.sql_counter_tools import chunk_code_tool

result = chunk_code_tool.execute(
    code="... 긴 Pro*C 코드 ...",
    chunk_size=5000,  # 청크 크기 (기본값: 5000)
    overlap=100       # 청크 간 중복 (기본값: 100)
)
```

**출력 예시:**
```json
{
  "total_length": 25000,
  "chunk_count": 5,
  "chunks": [
    {"index": 0, "content": "...", "start": 0, "end": 5120},
    {"index": 1, "content": "...", "start": 5020, "end": 10240}
  ]
}
```

### CountSQLTool

Pro*C 코드에서 SQL 구문을 찾아 타입별로 분류합니다.

```python
from agent_system.sql_counter_tools import count_sql_tool

result = count_sql_tool.execute(
    code="... Pro*C 코드 ...",
    chunk_index=0,         # 청크 인덱스 (기본값: 0)
    include_details=True   # 상세 정보 포함 (기본값: False)
)
```

**출력 예시:**
```json
{
  "chunk_index": 0,
  "sql_count": {
    "total": 8,
    "by_type": {
      "SELECT": 2,
      "INSERT": 1,
      "UPDATE": 1,
      "COMMIT": 1,
      "CURSOR": 1,
      "OPEN": 1,
      "FETCH": 1,
      "CLOSE": 1
    }
  },
  "details": [
    {"line": 45, "type": "SELECT", "snippet": "EXEC SQL SELECT name INTO :emp_name..."}
  ]
}
```

**지원되는 SQL 타입:**

| 타입 | 설명 |
|------|------|
| `SELECT` | SELECT 문 |
| `INSERT` | INSERT 문 |
| `UPDATE` | UPDATE 문 |
| `DELETE` | DELETE 문 |
| `CURSOR` | 커서 선언 |
| `FETCH` | FETCH 문 |
| `OPEN` | 커서 열기 |
| `CLOSE` | 커서 닫기 |
| `PREPARE` | PREPARE 문 |
| `EXECUTE` | EXECUTE 문 |
| `INCLUDE` | INCLUDE 문 |
| `CONNECT` | CONNECT 문 |
| `COMMIT` | COMMIT 문 |
| `ROLLBACK` | ROLLBACK 문 |
| `WHENEVER` | WHENEVER 문 |
| `CALL` | CALL 문 |

### AggregateResultsTool

여러 청크의 결과를 통합합니다.

```python
from agent_system.sql_counter_tools import aggregate_results_tool
import json

chunk_results = [
    {"chunk_index": 0, "sql_count": {"total": 5, "by_type": {"SELECT": 3, "INSERT": 2}}},
    {"chunk_index": 1, "sql_count": {"total": 3, "by_type": {"UPDATE": 2, "DELETE": 1}}}
]

result = aggregate_results_tool.execute(
    results=json.dumps(chunk_results)
)
```

**출력 예시:**
```json
{
  "status": "success",
  "summary": {
    "total_sql_count": 8,
    "by_type": {"SELECT": 3, "INSERT": 2, "UPDATE": 2, "DELETE": 1},
    "chunks_processed": 2
  },
  "per_chunk": [
    {"index": 0, "count": 5},
    {"index": 1, "count": 3}
  ]
}
```

---

## 📊 워크플로우 다이어그램

```
┌─────────────────────────────────────────────────────────────┐
│                      입력 코드                               │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │         길이 확인              │
              │    len(code) > 5000?          │
              └───────────────┬───────────────┘
                    │                   │
                   YES                  NO
                    │                   │
                    ▼                   │
     ┌──────────────────────────┐       │
     │      code-chunker        │       │
     │   (ChunkCode 도구)       │       │
     └────────────┬─────────────┘       │
                  │                     │
                  ▼                     │
    ┌─────────────────────────────┐     │
    │ 각 청크별 sql-counter 실행  │     │
    │   (CountSQL 도구)          │◀────┘
    └────────────┬────────────────┘
                 │
                 ▼
    ┌─────────────────────────────┐
    │     result-aggregator       │
    │  (AggregateResults 도구)    │
    └────────────┬────────────────┘
                 │
                 ▼
    ┌─────────────────────────────┐
    │         최종 결과            │
    │  (total_sql_count, by_type) │
    └─────────────────────────────┘
```

---

## 🎯 전체 통합 예제

파일에서 Pro*C 코드를 읽어 SQL 개수를 세는 완전한 예제:

```python
from pathlib import Path
import json
from agent_system.sql_counter_tools import (
    chunk_code_tool,
    count_sql_tool,
    aggregate_results_tool
)

def count_sql_in_file(file_path: str, chunk_size: int = 5000) -> dict:
    """Pro*C 파일에서 SQL 개수 추출
    
    Args:
        file_path: Pro*C 파일 경로
        chunk_size: 청크 크기
        
    Returns:
        SQL 카운팅 결과 딕셔너리
    """
    # 파일 읽기
    code = Path(file_path).read_text(encoding='utf-8', errors='ignore')
    
    # 짧은 코드: 직접 카운팅
    if len(code) <= chunk_size:
        result = count_sql_tool.execute(code=code, include_details=True)
        return json.loads(result.output)
    
    # 긴 코드: 청킹 후 카운팅
    chunk_result = chunk_code_tool.execute(code=code, chunk_size=chunk_size)
    chunks = json.loads(chunk_result.output)["chunks"]
    
    chunk_counts = []
    for chunk in chunks:
        count_result = count_sql_tool.execute(
            code=chunk["content"], 
            chunk_index=chunk["index"]
        )
        chunk_counts.append(json.loads(count_result.output))
    
    # 결과 통합
    final_result = aggregate_results_tool.execute(results=json.dumps(chunk_counts))
    return json.loads(final_result.output)


# 사용 예
if __name__ == "__main__":
    result = count_sql_in_file("example.pc")
    print(f"총 SQL 개수: {result['summary']['total_sql_count']}")
    print(f"타입별: {result['summary']['by_type']}")
```

---

## ⚠️ 주의사항

1. **주석 처리**: 주석 내 `EXEC SQL`은 자동으로 제외됩니다
2. **문자열 리터럴**: 문자열 내 패턴도 제외됩니다
3. **여러 줄 SQL**: 여러 줄에 걸친 SQL 구문도 정상 처리됩니다
4. **청크 경계**: 청크 분할 시 SQL 구문이 잘리지 않도록 자동 조정됩니다
5. **인코딩**: 기본적으로 UTF-8 인코딩을 사용합니다
