# CPG 모듈 사용법

Pro*C/.c 파일에서 Code Property Graph를 생성하는 모듈의 입출력 정의 및 사용법입니다.

---

## 빠른 시작

```python
from CPG import CPGBuilder

# CPG 빌더 생성
builder = CPGBuilder()

# 파일 분석 → CPG 생성
cpg = builder.build_from_file('sample.pc')

# 요약 출력
print(builder.summary(cpg))

# JSON 파일로 내보내기
builder.export_json(cpg, 'output.json')
```

---

## 헤더 재귀 분석 (신규)

소스 파일에서 `#include`된 헤더를 재귀적으로 추적하여 분석합니다.

### 기본 사용법

```python
from CPG import CPGBuilder

# 헤더 검색 경로 지정
builder = CPGBuilder(
    include_paths=['d:/project/include', 'd:/project/common'],
    verbose=True  # 헤더 검색 경로 로깅
)

# 재귀적 헤더 분석 활성화
cpg = builder.build_from_file('main.pc', follow_includes=True)
```

### 검색 순서

헤더 파일은 다음 순서로 검색됩니다:

1. 현재 소스/헤더 파일의 디렉토리
2. `include_paths[0]` (첫 번째 지정 경로)
3. `include_paths[1]` (두 번째 지정 경로)
4. ...

> **참고**: 시스템 헤더 (`#include <stdio.h>`)는 재귀 분석하지 않고 이름만 기록합니다.

### 런타임 경로 설정

```python
builder = CPGBuilder()

# 경로 설정
builder.set_include_paths(['d:/project/include'])

# 경로 추가
builder.add_include_path('d:/project/common')
```

### 해결된 경로 확인

```python
cpg = builder.build_from_file('main.c', follow_includes=True)

# 어떤 헤더가 어디서 찾아졌는지 확인
for header, path in builder.header_analyzer.resolved_paths.items():
    print(f"{header} -> {path}")
```

---

## 입력

### 지원 파일 형식

| 확장자 | 설명 |
|--------|------|
| `.c` | C 소스 파일 |
| `.pc` | Pro*C 소스 파일 |
| `.h` | C 헤더 파일 |
| `.cpp` | C++ 소스 파일 |
| `.hpp` | C++ 헤더 파일 |

### 입력 방식

#### 1. 단일 파일

```python
cpg = builder.build_from_file('sample.pc')
```

**매개변수**
- `file_path` (str): 소스 파일의 절대 또는 상대 경로

#### 2. 소스 코드 문자열

```python
source_code = """
#include <stdio.h>
void main() {
    printf("Hello");
}
"""
cpg = builder.build_from_source(source_code, file_path='test.c')
```

**매개변수**
- `source_code` (str): C/Pro*C 소스 코드 문자열
- `file_path` (str, optional): 파일 식별자 (기본값: `"<unknown>"`)

#### 3. 디렉토리

```python
# 하위 폴더 포함 전체 분석
cpg = builder.build_from_directory('d:/project/src', recursive=True)

# 현재 폴더만 분석
cpg = builder.build_from_directory('d:/project/src', recursive=False)
```

**매개변수**
- `dir_path` (str): 디렉토리 경로
- `recursive` (bool, optional): 하위 디렉토리 포함 여부 (기본값: `True`)

---

## 출력

### CPG 객체 구조

```python
cpg.nodes    # Dict[str, Node] - 노드 딕셔너리 (ID → Node)
cpg.edges    # List[Edge] - 엣지 리스트
cpg.files    # Set[str] - 분석된 파일 경로 집합
```

### 노드 타입 (NodeType)

| 타입 | 값 | 설명 |
|------|------|------|
| `FUNCTION` | `"function"` | 함수 정의 |
| `VARIABLE` | `"variable"` | 변수 선언 |
| `STRUCT` | `"struct"` | 구조체 정의 |
| `FILE` | `"file"` | 소스 파일 |
| `HEADER` | `"header"` | 헤더 파일 |
| `PARAMETER` | `"parameter"` | 함수 매개변수 |

### 엣지 타입 (EdgeType)

| 타입 | 값 | 설명 |
|------|------|------|
| `CALL` | `"call"` | 함수 호출 관계 |
| `INCLUDE` | `"include"` | 헤더 파일 포함 |
| `DATA_FLOW` | `"data_flow"` | 데이터 흐름 |
| `DEFINE` | `"define"` | 정의 관계 |
| `USE` | `"use"` | 사용 관계 |
| `FIELD_ACCESS` | `"field_access"` | 구조체 필드 접근 |

### 내보내기 형식

#### JSON

```python
builder.export_json(cpg, 'output.json', indent=2)
```

**출력 형식**
```json
{
  "nodes": [
    {
      "id": "func_main",
      "type": "function",
      "name": "main",
      "file_path": "sample.c",
      "line_start": 10,
      "line_end": 25,
      "attributes": {}
    }
  ],
  "edges": [
    {
      "source": "func_main",
      "target": "func_initialize",
      "type": "call",
      "attributes": {}
    }
  ],
  "files": ["sample.c"],
  "summary": {
    "total_nodes": 15,
    "total_edges": 8,
    "total_files": 1
  }
}
```

#### JSONL (줄 단위)

```python
builder.export_jsonl(cpg, 'output.jsonl')
```

**출력 형식**
```jsonl
{"record_type": "node", "id": "func_main", "type": "function", ...}
{"record_type": "edge", "source": "func_main", "target": "func_init", ...}
{"record_type": "summary", "total_nodes": 15, ...}
```

#### Graphviz DOT

```python
builder.export_dot(cpg, 'graph.dot', title='MyProject CPG')
```

**시각화 (터미널)**
```bash
dot -Tpng graph.dot -o graph.png
```

---

## 주요 API

### CPGBuilder

| 메서드 | 입력 | 출력 | 설명 |
|--------|------|------|------|
| `build_from_file(path, follow_includes)` | 파일 경로, 헤더 추적 여부 | CPG | 단일 파일 분석 |
| `build_from_source(code, path, follow_includes)` | 소스 코드, 경로 | CPG | 문자열 분석 |
| `build_from_directory(path, recursive)` | 디렉토리 경로 | CPG | 디렉토리 분석 |
| `set_include_paths(paths)` | 경로 리스트 | None | 헤더 검색 경로 설정 |
| `add_include_path(path)` | 경로 | None | 헤더 검색 경로 추가 |
| `export_json(cpg, path)` | CPG, 출력 경로 | None | JSON 저장 |
| `export_jsonl(cpg, path)` | CPG, 출력 경로 | None | JSONL 저장 |
| `export_dot(cpg, path, title)` | CPG, 출력 경로 | None | DOT 저장 |
| `summary(cpg)` | CPG | str | 요약 문자열 |

### 분석 기능

| 메서드 | 입력 | 출력 | 설명 |
|--------|------|------|------|
| `get_call_chain(func, depth)` | 함수명, 깊이 | Dict | 함수 호출 체인 |
| `get_file_dependencies(header)` | 헤더명 | List[str] | 헤더 사용 파일 목록 |
| `get_variable_flow(var)` | 변수명 | Dict | def-use 체인 |

### CPG 객체

| 메서드 | 입력 | 출력 | 설명 |
|--------|------|------|------|
| `add_node(node)` | Node | None | 노드 추가 |
| `add_edge(edge)` | Edge | None | 엣지 추가 |
| `get_node(id)` | 노드 ID | Node | 노드 조회 |
| `get_nodes_by_type(type)` | NodeType | List[Node] | 타입별 노드 |
| `get_edges_by_type(type)` | EdgeType | List[Edge] | 타입별 엣지 |
| `merge(other)` | CPG | None | CPG 병합 |
| `to_dict()` | None | Dict | 딕셔너리 변환 |
| `to_dot(title)` | 제목 | str | DOT 문자열 |

---

## 사용 예제

### 함수 호출 분석

```python
from CPG import CPGBuilder

builder = CPGBuilder()
cpg = builder.build_from_file('sample.pc')

# main 함수의 호출 체인 (5단계)
chain = builder.get_call_chain('main', max_depth=5)
print(chain)

# 특정 함수를 호출하는 함수 목록
callers = builder.call_graph_extractor.get_callers('initialize_db')

# 특정 함수가 호출하는 함수 목록
callees = builder.call_graph_extractor.get_callees('main')
```

### 헤더 의존성 분석

```python
# stdio.h를 사용하는 모든 파일
files = builder.get_file_dependencies('stdio.h')

# 특정 파일이 포함하는 헤더 목록
headers = builder.header_analyzer.get_dependencies('main.c')

# 같은 헤더를 공유하는 파일들
shared = builder.header_analyzer.get_files_sharing_header('common.h')
```

### 데이터 흐름 분석

```python
# 변수의 def-use 체인
flow = builder.get_variable_flow('g_user_id')
# 결과:
# {
#   "definitions": [{"line": 10, "function": None}],
#   "reads": [{"line": 50, "function": "init"}],
#   "writes": [{"line": 30, "function": "main"}]
# }

# 구조체 필드 접근 목록
accesses = builder.data_flow_analyzer.get_struct_field_accesses('host_user')
```

### CPG 직접 조작

```python
from CPG import CPG, NodeType, EdgeType

# 함수 노드만 필터
functions = cpg.get_nodes_by_type(NodeType.FUNCTION)
for f in functions:
    print(f"함수: {f.name} ({f.line_start}-{f.line_end})")

# 호출 엣지만 필터
calls = cpg.get_edges_by_type(EdgeType.CALL)
for c in calls:
    print(f"호출: {c.source_id} → {c.target_id}")

# 여러 CPG 병합
cpg1 = builder.build_from_file('file1.c')
cpg2 = builder.build_from_file('file2.c')
cpg1.merge(cpg2)
```

---

## 의존성

- **tree-sitter**: C 코드 파싱
- **tree-sitter-c**: C 언어 문법

```bash
pip install tree-sitter tree-sitter-c
```
