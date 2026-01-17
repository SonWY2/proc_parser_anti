# Pro*C Parser

Pro*C 파일(.pc, .sqc, .h)을 파싱하여 코드 요소별로 분해하고, Java/Spring 기반 모던 아키텍처로 자동 변환하는 통합 파이프라인입니다.

## 🎯 프로젝트 목표

레거시 Pro*C 코드를 분석하여:
1. **코드 요소 분해**: 함수, 변수, SQL, 구조체 등으로 분리
2. **SQL 추출 및 표준화**: 임베디드 SQL을 MyBatis XML로 변환
3. **Java 코드 생성**: OMM, DBIO, DAO 아티팩트 자동 생성
4. **LLM 기반 검증**: 변환 품질을 AI로 검증

---

## 📦 모듈 구조

```
proc_parser/
├── parsing/                        # 🔍 코드 파싱
│   ├── core/                       # 핵심 파서 + plugins/
│   ├── sql/                        # SQL 추출 + plugins/
│   └── header/                     # 헤더 파싱
│
├── analysis/                       # 📊 코드 분석
│   ├── cpg/                        # Code Property Graph
│   ├── lineage/                    # 변수 추적
│   └── context/                    # 함수 컨텍스트
│
├── generation/                     # 🏗️ 코드 생성
│   ├── artifacts/                  # OMM, DBIO, DAO 생성기
│   └── merge/                      # 번역 병합 + plugins/
│
├── validation/                     # ✅ 검증
│   ├── sql/                        # SQL 검증 (GUI 포함)
│   └── llm/                        # LLM 검증 + plugins/
│
├── infra/                          # 🔧 인프라
│   ├── agents/                     # 에이전트 시스템
│   ├── api/                        # API 로드밸런서
│   └── config/                     # 공유 설정
│
├── tests/
├── main.py
├── generate_metadata.py
└── README.md
```

---

## 🚀 빠른 시작

### 설치

```bash
pip install -r requirements.txt

# 또는 모듈별 설치
pip install -r sql_extractor/requirements.txt
pip install -r sql_validator/requirements.txt
pip install -r CPG/requirements.txt
```

### 기본 사용법

```bash
# 1. Pro*C 파일 파싱
python main.py <입력_디렉토리> <출력_디렉토리>

# 2. 통합 메타데이터 생성 (OMM, DBIO, DAO 포함)
python generate_metadata.py <입력_파일_또는_디렉토리> <출력_JSON_경로>

# 3. SQL 검증 GUI
python -m sql_validator
```

---

## 📚 주요 모듈

### 1. 핵심 파서 (`parsing/core/`)

Pro*C 파일을 파싱하여 코드 요소 추출:

- **Include**: `#include` 문
- **변수**: 전역/로컬, 호스트 변수, static 변수
- **함수**: 선언 및 정의, 프로토타입
- **구조체**: `struct` 및 `typedef`
- **매크로**: `#define`, 조건부 컴파일 (`#ifdef`, `#ifndef`)
- **SQL**: 임베디드 SQL (EXEC SQL)
- **Unknown**: 미분류 요소 (디버깅용)

```python
from parsing.core import ProCParser

parser = ProCParser()
elements = parser.parse_file("example.pc")
```

### 2. SQL 추출기 (`parsing/sql/`)

임베디드 SQL을 분석하고 MyBatis XML로 변환:

```python
from parsing.sql import SQLExtractor, MyBatisConverter

# SQL 추출
extractor = SQLExtractor()
sql_elements = extractor.extract("input.pc")

# MyBatis 변환
converter = MyBatisConverter()
mybatis_xml = converter.convert(sql_elements)
```

**지원 SQL 패턴:**
- Cursor (DECLARE, OPEN, FETCH, CLOSE)
- Dynamic SQL (PREPARE, EXECUTE)
- Transaction (COMMIT, ROLLBACK, SAVEPOINT)
- Array DML (BULK INSERT/UPDATE)

### 3. SQL 검증기 (`validation/sql/`)

LLM 기반 SQL 변환 검증 도구:

```bash
# GUI 실행
python -m validation.sql

# CLI 사용
python -m validation.sql --batch input_dir output_dir
```

**기능:**
- Pro*C → MyBatis 변환 검증
- 호스트 변수 매핑 검증
- Diff 하이라이팅
- 세션 저장/불러오기

### 4. CPG (Code Property Graph) (`analysis/cpg/`)

코드 분석을 위한 그래프 생성:

```python
from analysis.cpg import CPGBuilder

builder = CPGBuilder()
cpg = builder.build("input.pc")
cpg.export_to_neo4j("bolt://localhost:7687")
```

**분석 기능:**
- 함수 호출 그래프
- 데이터 흐름 분석
- 변수 의존성 추적
- 헤더 파일 분석

### 5. 통합 메타데이터 생성기 (`generate_metadata.py`)

Pro*C 파일을 분석하여 Java 아티팩트 생성:

```bash
python generate_metadata.py ./proc_files ./output.json
```

**생성 아티팩트:**
- **OMM**: Java VO/DTO 클래스
- **DBIO**: 데이터베이스 접근 클래스
- **DAO**: MyBatis Mapper 인터페이스

### 6. LLM 검증기 (`validation/llm/`)

변환 품질을 AI로 검증:

```python
from validation.llm import LLMVerifier

verifier = LLMVerifier()
result = verifier.verify_transformation(
    source_code="...",
    transformed_code="..."
)
```

### 7. 변수 추적 (`analysis/lineage/`)

변수 흐름 및 의존성 분석:

```python
from analysis.lineage import VariableLineageTracker

tracker = VariableLineageTracker()
lineage = tracker.trace("input.pc")
tracker.export_to_json(lineage, "output.json")
```

### 8. 에이전트 시스템 (`infra/agents/`)

멀티 에이전트 기반 자동화:

```bash
python -m infra.agents.base --mode gui
python -m infra.agents.base --mode cli --agent orchestrator
```

---

## 🔌 플러그인 시스템

### 코드 플러그인

특수 구조 파싱을 위한 확장:

```python
from parsing.core.interfaces import ParserPlugin

class CustomPlugin(ParserPlugin):
    def can_handle(self, text, start_pos):
        return text[start_pos:].startswith("CUSTOM_MACRO")
    
    def parse(self, text, start_pos):
        # 파싱 로직
        pass
```

**기본 제공 플러그인:**
- `bam_call.py`: BAMCALL() 패턴
- `docstring.py`: 주석 기반 문서화

### SQL 관계 플러그인

SQL 패턴 감지를 위한 확장 (위치: `parsing/sql/plugins/`):

```python
from parsing.sql.plugins import SQLRelationshipPlugin

class BulkCollectPlugin(SQLRelationshipPlugin):
    def can_handle(self, sql_elements):
        return any("BULK COLLECT" in e.text for e in sql_elements)
    
    def extract_relationships(self, sql_elements):
        # 관계 추출 로직
        pass
```

---

## 📊 출력 형식

### JSONL 출력

각 코드 요소는 별도의 JSONL 파일로 저장:

| 파일명 | 설명 |
|--------|------|
| `function.jsonl` | 함수 선언 및 정의 |
| `variable.jsonl` | 변수 선언 (global/local/static) |
| `struct.jsonl` | 구조체 정의 |
| `macro.jsonl` | 매크로 정의 |
| `sql.jsonl` | SQL 문 (표준화된 형식 + 관계 정보) |
| `comment.jsonl` | 주석 |
| `include.jsonl` | Include 문 |
| `preprocessor.jsonl` | 전처리기 지시문 |
| `prototype.jsonl` | 함수 프로토타입 |
| `unknown.jsonl` | 미분류 코드 조각 |

### SQL 관계 정보 (MyBatis 변환용)

```json
{
  "sql_id": "sql_001",
  "sql_type": "SELECT",
  "relationship": {
    "relationship_type": "CURSOR",
    "metadata": {
      "cursor_name": "emp_cursor",
      "cursor_query": "SELECT id, name FROM employees",
      "is_loop_based": true,
      "all_output_vars": [":emp_id", ":emp_name"]
    }
  }
}
```

---

## 🧪 테스트

```bash
# 전체 테스트
python -m pytest tests/

# 특정 모듈 테스트
python -m pytest tests/test_sql_extractor.py
python -m pytest tests/test_cpg.py

# 통합 테스트
python test_runner.py
```

---

## 📋 환경 설정

### 환경 변수

```bash
# .env 파일 생성
cp .env.example .env

# 주요 설정
OPENAI_API_KEY=sk-xxx          # LLM 검증용
NEO4J_URI=bolt://localhost:7687  # CPG 내보내기용
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

### 데이터베이스 설정 (선택)

```bash
cp .db.env.example .db.env
```

---

## 📖 상세 문서

각 모듈별 상세 문서:

- [`parsing/core/USAGE.md`](parsing/core/USAGE.md) - 핵심 파서 사용법
- [`parsing/sql/USAGE.md`](parsing/sql/USAGE.md) - SQL 추출기 사용법
- [`analysis/cpg/USAGE.md`](analysis/cpg/USAGE.md) - CPG 빌더 사용법
- [`analysis/context/USAGE.md`](analysis/context/USAGE.md) - 함수 컨텍스트 사용법
- [`analysis/lineage/USAGE.md`](analysis/lineage/USAGE.md) - 변수 추적 사용법
- [`generation/merge/USAGE.md`](generation/merge/USAGE.md) - 번역 병합 사용법
- [`validation/sql/USAGE.md`](validation/sql/USAGE.md) - SQL 검증기 사용법
- [`validation/llm/USAGE.md`](validation/llm/USAGE.md) - LLM 검증기 사용법
- [`infra/agents/base/README.md`](infra/agents/base/README.md) - 에이전트 시스템 가이드

---

## 🛠 기술 스택

| 구분 | 기술 |
|------|------|
| 언어 | Python 3.x |
| 파싱 | tree-sitter, pyparsing |
| LLM | OpenAI GPT-4, Claude |
| 그래프 DB | Neo4j |
| GUI | tkinter |
| 테스트 | pytest |

---

## 📄 라이선스

이 프로젝트는 내부 사용 목적으로 개발되었습니다.
