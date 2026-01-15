# Pro*C 파싱 및 변환 단계별 가이드

Pro*C 파일을 분석하여 Java/MyBatis로 변환하는 전체 파이프라인의 단계별 사용법입니다.

---

## 📋 목차

1. [변수 추출](#1-변수-추출)
2. [SQL 추출](#2-sql-추출)
3. [함수 추출 및 호출 관계 분석](#3-함수-추출-및-호출-관계-분석)
4. [매크로 추출](#4-매크로-추출)
5. [헤더 파일 추출](#5-헤더-파일-추출)
6. [SQL → MyBatis 변환](#6-sql--mybatis-변환)
7. [SQL 변환 검증](#7-sql-변환-검증)
8. [변수 Lineage 추적](#8-변수-lineage-추적)
9. [Java 코드 병합](#9-java-코드-병합)
10. [LLM 기반 검증](#10-llm-기반-검증)
11. [OMM/DBIO/DAO 아티팩트 생성](#11-ommdbio-아티팩트-생성)
12. [Neo4j 그래프 내보내기](#12-neo4j-그래프-내보내기)
13. [통합 메타데이터 생성](#13-통합-메타데이터-생성)

---

## 1. 변수 추출

Pro*C 파일에서 변수 선언을 추출합니다.

### 기본 사용법

```python
from parser_core import ProCParser

parser = ProCParser()
elements = parser.parse_file("sample.pc")

# 변수만 필터링
variables = [e for e in elements if e.get("type") == "variable"]

for var in variables:
    print(f"이름: {var['name']}")
    print(f"  타입: {var['data_type']}")
    print(f"  범위: {var.get('scope', 'global')}")  # global/local
    print(f"  static: {var.get('is_static', False)}")
    print(f"  라인: {var['line_start']}-{var['line_end']}")
```

### 매크로 상수로 정의된 배열 크기 해석

```python
# 외부 매크로 주입
external_macros = {
    "MAX_SIZE": "100",
    "BUFFER_LEN": "256"
}

elements = parser.parse_file("sample.pc", external_macros=external_macros)

for var in elements:
    if var.get("type") == "variable" and "resolved_array_sizes" in var:
        print(f"{var['name']}: {var['resolved_array_sizes']}")
        # 예: user_id: ['100'] (MAX_SIZE가 100으로 치환됨)
```

### 출력 예시

```json
{
  "type": "variable",
  "name": "H_o_user_id",
  "data_type": "char",
  "array_sizes": ["MAX_SIZE"],
  "resolved_array_sizes": ["100"],
  "scope": "global",
  "is_static": false,
  "line_start": 10,
  "line_end": 10
}
```

---

## 2. SQL 추출

Pro*C 파일에서 임베디드 SQL(`EXEC SQL ... ;`)을 추출합니다.

### 기본 사용법 (tree-sitter 기반)

```python
from sql_extractor import TreeSitterSQLExtractor

extractor = TreeSitterSQLExtractor()

with open("sample.pc", "r", encoding="utf-8") as f:
    code = f.read()

# SQL 블록 추출
sql_blocks = extractor.extract_sql_blocks(code)

for block in sql_blocks:
    print(f"SQL: {block.text}")
    print(f"  타입: {block.sql_type}")  # select, insert, declare_cursor 등
    print(f"  라인: {block.start_line}-{block.end_line}")
    print(f"  함수: {block.containing_function}")
```

### proc_parser를 통한 추출

```python
from parser_core import ProCParser

parser = ProCParser()
elements = parser.parse_file("sample.pc")

# SQL만 필터링
sql_elements = [e for e in elements if e.get("type") == "sql"]

for sql in sql_elements:
    print(f"원본: {sql['raw_content']}")
    print(f"표준화: {sql['standardized_sql']}")
    print(f"입력 변수: {sql['input_vars']}")
    print(f"출력 변수: {sql['output_vars']}")
```

### YAML 파일로 저장

```python
from sql_extractor import SQLExtractor

extractor = SQLExtractor()
extractor.decompose_sql(
    input_path="sample.pc",
    output_dir="./output",
    file_key="sample"
)
# 결과: output/sql_calls.yaml
```

---

## 3. 함수 추출 및 호출 관계 분석

함수를 추출하고 호출 그래프(Call Graph)로 정렬합니다.

### 함수 추출

```python
from parser_core import ProCParser

parser = ProCParser()
elements = parser.parse_file("sample.pc")

# 함수 정의만 필터링
functions = [e for e in elements if e.get("type") == "function"]

for func in functions:
    print(f"함수명: {func['name']}")
    print(f"  반환타입: {func['return_type']}")
    print(f"  매개변수: {func['parameters']}")
    print(f"  라인: {func['line_start']}-{func['line_end']}")
```

### 호출 관계 분석 (CPG 모듈)

```python
from CPG import CPGBuilder

builder = CPGBuilder()
cpg = builder.build_from_file("sample.pc")

# 모든 함수 노드
from CPG import NodeType, EdgeType
functions = cpg.get_nodes_by_type(NodeType.FUNCTION)

# 호출 관계 (엣지)
calls = cpg.get_edges_by_type(EdgeType.CALL)
for call in calls:
    print(f"{call.source_id} → {call.target_id}")
```

### 호출 순서대로 정렬 (위상 정렬)

```python
from CPG import CPGBuilder

builder = CPGBuilder()
cpg = builder.build_from_file("sample.pc")

# main 함수부터 호출 체인 추적 (5단계 깊이)
call_chain = builder.get_call_chain("main", max_depth=5)

# 결과 예시:
# {
#   "main": ["init_db", "process_data", "cleanup"],
#   "init_db": ["connect_db", "load_config"],
#   "process_data": ["fetch_users", "save_result"]
# }
```

### 특정 함수의 호출자/피호출자

```python
# 이 함수를 호출하는 함수들
callers = builder.call_graph_extractor.get_callers("process_data")

# 이 함수가 호출하는 함수들
callees = builder.call_graph_extractor.get_callees("main")
```

---

## 4. 매크로 추출

`#define` 매크로 정의를 추출합니다.

### 기본 사용법

```python
from parser_core import ProCParser

parser = ProCParser()
elements = parser.parse_file("sample.pc")

# 매크로만 필터링
macros = [e for e in elements if e.get("type") == "macro"]

for macro in macros:
    print(f"이름: {macro['name']}")
    print(f"  값: {macro.get('value', '')}")
    print(f"  매개변수: {macro.get('parameters', [])}")
```

### 전처리기 지시문 추출

```python
# 조건부 컴파일 지시문도 추출
preprocessors = [e for e in elements if e.get("type") == "preprocessor"]

for pp in preprocessors:
    print(f"지시문: {pp['directive']}")  # ifdef, ifndef, endif 등
    print(f"  조건: {pp.get('condition', '')}")
```

### 출력 예시

```json
{
  "type": "macro",
  "name": "MAX_BUFFER_SIZE",
  "value": "1024",
  "line_start": 5,
  "line_end": 5
}
```

---

## 5. 헤더 파일 추출

`#include`로 포함된 모든 헤더를 재귀적으로 추출합니다.

### 기본 사용법

```python
from CPG import CPGBuilder

# 헤더 검색 경로 지정
builder = CPGBuilder(
    include_paths=["d:/project/include", "d:/project/common"],
    verbose=True  # 검색 로그 출력
)

# 재귀적 헤더 분석 활성화
cpg = builder.build_from_file("main.pc", follow_includes=True)
```

### 헤더 의존성 확인

```python
# 분석된 모든 헤더 목록
all_headers = builder.header_analyzer.get_all_analyzed_headers()

# 특정 소스 파일이 포함하는 헤더
dependencies = builder.header_analyzer.get_dependencies("main.pc")

# 특정 헤더를 사용하는 파일들
users = builder.get_file_dependencies("common.h")
```

### 해결된 경로 매핑

```python
# 헤더 이름 → 실제 경로 매핑
for header_name, resolved_path in builder.header_analyzer.resolved_paths.items():
    print(f"{header_name} → {resolved_path}")
```

### 검색 순서

1. 현재 소스/헤더 파일의 디렉토리
2. `include_paths[0]` (첫 번째 지정 경로)
3. `include_paths[1]` (두 번째 지정 경로)
4. ...

> **참고**: 시스템 헤더 (`#include <stdio.h>`)는 재귀 분석하지 않고 이름만 기록합니다.

---

## 6. SQL → MyBatis 변환

추출한 SQL을 MyBatis XML 형식으로 변환하고, 컬럼에 alias를 추가합니다.

### 전체 워크플로우

```python
from sql_extractor import SQLExtractor

extractor = SQLExtractor()

with open("sample.pc", "r", encoding="utf-8") as f:
    code = f.read()

# SQL 추출 + MyBatis 변환 + 주석 삽입
result_code, mybatis_sqls = extractor.extract_with_mybatis_conversion(
    code=code,
    file_key="sample"
)

# 변환된 코드 (원본 SQL이 주석으로 대체됨)
print(result_code)

# MyBatis SQL 목록
for sql in mybatis_sqls:
    print(f"ID: {sql.id}")
    print(f"  타입: {sql.mybatis_type}")  # select, insert, update, delete
    print(f"  변환 SQL: {sql.sql}")
    print(f"  입력 파라미터: {sql.input_params}")
    print(f"  출력 필드: {sql.output_fields}")
```

### 변환 예시

**입력 (Pro*C)**:
```sql
EXEC SQL SELECT emp_name, emp_age INTO :out_name, :out_age 
         FROM employees WHERE id = :in_id;
```

**출력 (MyBatis)**:
```sql
SELECT emp_name AS outName, emp_age AS outAge 
FROM employees WHERE id = #{inId}
```

### 커스텀 포맷터 사용

```python
# 호스트 변수 포맷 커스터마이징
def my_input_formatter(var_name: str) -> str:
    return f"${{param.{var_name}}}"

result_code, sqls = extractor.extract_with_mybatis_conversion(
    code=code,
    file_key="sample",
    input_formatter=my_input_formatter,  # :var → ${param.var}
    comment_template="/* @SQL: {sql_id} ({sql_type}) */"
)
```

### 커서 SQL 병합

DECLARE CURSOR + OPEN + FETCH + CLOSE 패턴을 단일 SELECT로 병합:

```python
from sql_extractor import CursorMerger

merger = CursorMerger()

# 커서 그룹 찾기
groups = merger.find_cursor_groups(sql_blocks)

for group in groups:
    merged = merger.merge(group)
    print(f"커서명: {merged.cursor_name}")
    print(f"병합된 SQL: {merged.merged_sql}")
    print(f"입력 변수: {merged.input_vars}")
    print(f"출력 변수: {merged.output_vars}")
```

### 호스트 변수 블랙리스트 설정

시간 포맷(`:MI`, `:SS`) 등이 호스트 변수로 오인되는 것을 방지:

```python
from sql_extractor import SQLExtractorConfig
from sql_extractor.pyparsing_parser import PyparsingProCParser

config = SQLExtractorConfig(
    CUSTOM_HOST_VAR_BLACKLIST={'MY_CONSTANT', 'STATUS_ACTIVE'},
    USE_DB2_SPECIAL_REGISTERS_BLACKLIST=True,
    IGNORE_VARS_IN_STRING_LITERALS=True
)

parser = PyparsingProCParser(config=config)
```

---

## 7. SQL 변환 검증

Pro*C → MyBatis 변환 결과가 올바른지 검증합니다.

### GUI 도구 실행

```bash
python -m sql_validator
```

### 주요 기능

| 기능 | 설명 |
|------|------|
| A/B 비교 | 원본 SQL과 변환된 SQL의 차이점을 시각적으로 확인 |
| 정적 분석 | 기본 변환 규칙 준수 여부 자동 확인 |
| AI 피드백 | LLM을 통해 논리적 결함이나 개선점 제안 |
| 검증 마킹 | ✅ 승인 / ❌ 거절 표시 |
| 세션 저장 | 작업 상태 저장 및 불러오기 |

### 키보드 단축키

| 단축키 | 기능 |
|--------|------|
| `←` / `→` | 이전/다음 항목 |
| `A` | 승인 (Approved) |
| `R` | 거절 (Rejected) |
| `Ctrl+S` | 세션 저장 |
| `Ctrl+E` | 승인된 항목만 내보내기 |

### 프로그래밍 API

```python
from sql_validator import load_yaml, StaticAnalyzer

# YAML 파일 로드
items = load_yaml("converted_sql.yaml")

# 정적 분석
analyzer = StaticAnalyzer()
for item in items:
    result = analyzer.analyze(item['sql'], item['parsed_sql'])
    if not result.is_valid:
        print(f"검증 실패: {result.errors}")
```

### 일괄 처리

```python
from sql_validator import process_batch, generate_markdown_report

results = process_batch(["file1.yaml", "file2.yaml"])
report = generate_markdown_report(results)

with open("validation_report.md", "w", encoding="utf-8") as f:
    f.write(report)
```

---

## 8. 변수 Lineage 추적

Pro*C 변수가 MyBatis/Java로 변환되는 과정의 연결관계를 추적합니다.

### 기본 사용법

```python
from variable_lineage import VariableLineageTracker

tracker = VariableLineageTracker(source_file="sample.pc")

# 1. proc_parser 결과 추가
from parser_core import ProCParser
parser = ProCParser()
elements = parser.parse_file("sample.pc")
tracker.add_from_proc_parser(elements)

# 2. header_parser 결과 추가 (선택)
# tracker.add_from_header_parser(db_vars_info)

# 3. 연결관계 자동 구축
tracker.build_links()

# 4. JSON 출력
print(tracker.to_json())
```

### 추적되는 변환 규칙

| 변환 | 예시 | 기록 |
|------|------|------|
| Prefix 제거 | `H_o_result` → `result` | `prefix_removed:H_o_` |
| snake → camelCase | `user_id` → `userId` | `snake_to_camel` |

### 특정 변수 추적

```python
# 특정 변수의 상위/하위 노드 추적
result = tracker.query_lineage("user_id")
print(result['upstream'])    # 상위 노드들
print(result['downstream'])  # 하위 노드들
```

### 노드 타입

| 타입 | 설명 |
|------|------|
| `proc_variable` | Pro*C 변수 선언 |
| `struct_field` | 구조체 필드 |
| `sql_host_var` | SQL 호스트 변수 |
| `java_variable` | Java 변수 (camelCase) |
| `mybatis_param` | MyBatis 파라미터 |

---

## 9. Java 코드 병합

LLM이 생성한 메소드들을 하나의 완전한 Java 클래스로 병합합니다.

### 기본 사용법

```python
from translation_merge import TranslationMerger, MethodTranslation

merger = TranslationMerger()

# 클래스 스켈레톤 (LLM 생성)
class_skeleton = """
package com.example;

public class MyProgram {
}
"""

# 메소드 변환 결과들 (LLM 생성)
method_translations = [
    MethodTranslation(
        name="processData",
        llm_response='''
import java.util.ArrayList;

public void processData() {
    List<String> data = new ArrayList<>();
    // 비즈니스 로직
}
'''
    ),
]

# 병합 실행
result = merger.merge(class_skeleton, method_translations)

print(result.merged_code)    # 병합된 Java 코드
print(result.imports)        # 수집된 import 목록
print(result.methods)        # 병합된 메소드 이름들
print(result.warnings)       # 경고 메시지
```

### 플러그인 시스템

| 플러그인 | 설명 |
|----------|------|
| `visibility` | public → private 변환 (main 제외) |
| `bxmcategory` | @bxmcategory 어노테이션 자동 추가 |
| `main_deduplicator` | 중복 main 함수 제거 |

```python
# 특정 플러그인만 적용
result = merger.merge(
    skeleton, 
    translations,
    plugin_names=["bxmcategory"]
)

# 모든 플러그인 비활성화
merger = TranslationMerger(use_plugins=False)
```

---

## 10. LLM 기반 검증

Pro*C 파싱 결과의 정확성을 LLM으로 검증합니다.

### 환경 설정

```bash
# .env 파일
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=o1-mini
```

### 기본 사용법

```python
from llm_verifier import LLMVerifier

verifier = LLMVerifier()

# SQL 추출 결과 검증
result = verifier.verify(
    stage="sql_extraction",
    source=proc_code,
    result=extracted_elements
)

# 결과 확인
print(result.summary())
# ✅ PASS | Stage: sql_extraction | Passed: 5/5 | Failed: 0 | Warnings: 0

if result.has_errors():
    for err in result.get_errors():
        print(f"Error: {err.message}")
```

### 검증 단계 (Stages)

| Stage | 설명 |
|-------|------|
| `sql_extraction` | Pro*C → SQL 추출 검증 |
| `function_parsing` | Pro*C → 함수 파싱 검증 |
| `header_parsing` | .h → 구조체 파싱 검증 |
| `translation_merge` | Java 코드 병합 검증 |

### LLM 없이 정적 체크만

```python
verifier = LLMVerifier()
result = verifier.verify(
    stage="sql_extraction",
    source=source,
    result=result
)

# 정적 체크 결과만 확인 (LLM API 없어도 동작)
for check in result.static_checks:
    print(f"{check.name}: {check.status.value}")
```

---

## 11. OMM/DBIO/DAO 아티팩트 생성

Pro*C에서 Java 아티팩트를 자동 생성합니다.

### 개별 생성

```python
# OMM (Object Mapping Model) - Java VO/DTO
from omm_generator import OMMGenerator
omm_gen = OMMGenerator()
omm_code = omm_gen.generate(struct_elements)

# DBIO (Database I/O)
from dbio_generator import DBIOGenerator
dbio_gen = DBIOGenerator()
dbio_code = dbio_gen.generate(sql_elements)

# DAO (MyBatis Mapper Interface)
from dao_generator import DAOGenerator
dao_gen = DAOGenerator()
dao_code = dao_gen.generate(sql_elements)
```

### 통합 생성 (권장)

```bash
python generate_metadata.py sample.pc output.json
```

출력 JSON에 `generated_artifacts` 섹션으로 포함:

```json
{
  "generated_artifacts": {
    "omm": "public class UserVO { ... }",
    "dbio": "public class UserDBIO { ... }",
    "dao": "public interface UserMapper { ... }"
  }
}
```

---

## 12. Neo4j 그래프 내보내기

분석 결과를 Neo4j 그래프 데이터베이스로 내보냅니다.

### Variable Lineage 내보내기

```python
from variable_lineage import VariableLineageTracker, Neo4jExporter

tracker = VariableLineageTracker(source_file="sample.pc")
tracker.add_from_proc_parser(elements)
tracker.build_links()

# Cypher 파일 생성
exporter = Neo4jExporter(program_name="my_program")
exporter.save_cypher(tracker.graph, "output.cypher")

# Neo4j 직접 연결
from neo4j import GraphDatabase
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
result = exporter.export_to_driver(tracker.graph, driver)
print(f"노드: {result['nodes_created']}, 관계: {result['relationships_created']}")
```

### CPG 내보내기

```python
from CPG import CPGBuilder

builder = CPGBuilder()
cpg = builder.build_from_file("sample.pc")

# 다양한 형식으로 내보내기
builder.export_json(cpg, "cpg.json")
builder.export_jsonl(cpg, "cpg.jsonl")
builder.export_dot(cpg, "cpg.dot")

# Graphviz로 시각화
# dot -Tpng cpg.dot -o cpg.png
```

---

## 13. 통합 메타데이터 생성

Pro*C 파일을 분석하여 모든 정보를 포함한 메타데이터 JSON을 생성합니다.

### 단일 파일 분석

```bash
python generate_metadata.py sample.pc output.json
```

### 디렉토리 일괄 분석

```bash
python generate_metadata.py ./proc_files ./output_dir
```

### 출력 구조

```json
{
  "source_file": "sample.pc",
  "elements": {
    "functions": [...],
    "variables": [...],
    "sql": [...],
    "structs": [...],
    "macros": [...],
    "includes": [...]
  },
  "generated_artifacts": {
    "omm": "...",
    "dbio": "...",
    "dao": "..."
  },
  "analysis_metadata": {
    "total_lines": 500,
    "parse_time_ms": 120
  }
}
```

---

## 📊 전체 파이프라인 예시

```python
from parser_core import ProCParser
from sql_extractor import SQLExtractor
from CPG import CPGBuilder
from variable_lineage import VariableLineageTracker

# 1. Pro*C 파싱
parser = ProCParser()
elements = parser.parse_file("sample.pc")

# 2. SQL 추출 및 MyBatis 변환
sql_extractor = SQLExtractor()
with open("sample.pc", "r") as f:
    code = f.read()
result_code, mybatis_sqls = sql_extractor.extract_with_mybatis_conversion(code, "sample")

# 3. 함수 호출 그래프 생성
cpg_builder = CPGBuilder()
cpg = cpg_builder.build_from_file("sample.pc")

# 4. 변수 Lineage 추적
tracker = VariableLineageTracker(source_file="sample.pc")
tracker.add_from_proc_parser(elements)
tracker.build_links()

# 5. 결과 저장
cpg_builder.export_json(cpg, "cpg.json")
with open("lineage.json", "w") as f:
    f.write(tracker.to_json())
```

---

## 🔧 환경 설정 요약

### 필수 패키지

```bash
pip install tree-sitter tree-sitter-c pyparsing pyyaml
```

### 옵션별 추가 패키지

```bash
# LLM 검증용
pip install openai python-dotenv loguru

# Neo4j 내보내기용
pip install neo4j

# GUI 도구
# tkinter (Python 기본 포함)
```

### 환경 변수 (.env)

```bash
# LLM API
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=o1-mini

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

---

## 📚 관련 문서

| 모듈 | 상세 문서 |
|------|----------|
| SQL 추출 | [sql_extractor/USAGE.md](sql_extractor/USAGE.md) |
| SQL 검증 | [sql_validator/USAGE.md](sql_validator/USAGE.md) |
| CPG | [CPG/USAGE.md](CPG/USAGE.md) |
| 변수 추적 | [variable_lineage/USAGE.md](variable_lineage/USAGE.md) |
| 코드 병합 | [translation_merge/USAGE.md](translation_merge/USAGE.md) |
| LLM 검증 | [llm_verifier/USAGE.md](llm_verifier/USAGE.md) |
