# Pro*C → Java 멀티에이전트 시스템 사용 가이드

## 📖 목차

1. [시스템 개요](#시스템-개요)
2. [사전 준비](#사전-준비)
3. [빠른 시작](#빠른-시작)
4. [에이전트 설명](#에이전트-설명)
5. [스킬 설명](#스킬-설명)
6. [실행 방법](#실행-방법)
7. [테스트 시나리오](#테스트-시나리오)
8. [설정 커스터마이징](#설정-커스터마이징)
9. [문제 해결](#문제-해결)

---

## 시스템 개요

### 🎯 목적
Pro*C 레거시 코드를 Java Spring Boot + MyBatis 기반 현대적 애플리케이션으로 자동 변환하는 멀티에이전트 시스템입니다.

### 🏗️ 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│               main-orchestrator                         │
│          (사용자 확인 및 전체 조율)                        │
└───────────────────┬─────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌───────────────┐      ┌────────────────┐
│  analysis-    │      │  report-       │
│  agent        │      │  agent         │
│  (코드 분석)   │      │  (리포트 생성)  │
└───────────────┘      └────────────────┘
        │
        └─────────┬─────────┐
                  │         │
                  ▼         ▼
        ┌────────────┐  ┌──────────────┐
        │ java-      │  │ mybatis-     │
        │ spring-    │  │ agent        │
        │ agent      │  │ (MyBatis     │
        │ (Java 생성) │  │  생성)        │
        └────────────┘  └──────────────┘
```

### 🔧 핵심 구성 요소

**5개 에이전트**:
- `main-orchestrator`: 전체 파이프라인 조율 및 사용자 확인
- `analysis-agent`: Pro*C 코드 분석 및 메타데이터 추출
- `java-spring-agent`: Java Spring 코드 생성
- `mybatis-agent`: MyBatis DTO/DAO/XML 생성
- `report-agent`: 마이그레이션 리포트 작성

**4개 스킬** (재사용 가능한 유틸리티):
- `file-reader-chunker`: 대용량 파일 청킹
- `macro-type-mapper`: C 타입 → Java 타입 매핑
- `sql-extractor`: SQL 추출 및 변환
- `file-writer`: 안전한 파일 쓰기

---

## 사전 준비

### 1. 환경 변수 설정

```bash
# .env.example을 복사하여 .env 생성
cp .env.example .env

# .env 파일 편집 (API 키 입력)
nano .env
```

**.env 파일 예시**:
```bash
# OpenAI API (권장)
OPENAI_API_KEY=sk-your-actual-openai-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1

# 또는 Anthropic API
ANTHROPIC_API_KEY=sk-ant-your-actual-anthropic-api-key-here

# 로그 레벨
LOG_LEVEL=INFO

# 출력 경로
OUTPUT_BASE_PATH=output/

# 병렬 처리 워커 수
MAX_PARALLEL_WORKERS=2
```

### 2. 필수 패키지 설치

```bash
# Python 3.8 이상 필요
python --version

# 프로젝트 의존성 설치
pip install -r requirements.txt
```

### 3. 입력 파일 준비

변환하려는 파일들을 준비합니다:
- **헤더 파일** (.h): 타입 정의, 구조체, 매크로
- **Pro*C 파일** (.pc, .sqc): 변환 대상 소스 코드

---

## 빠른 시작

### 최소 실행 예제

```bash
python run_multiagent_conversion.py \
  --headers tests/fixtures/sample_input_data/sample.h \
  --procs tests/fixtures/sample_input_data/cursor_sample.pc \
  --output output/quick_test/
```

### 실행 흐름

1. **사용자 확인 프롬프트** (자동 표시):
   ```
   코드 변환 시 '코드 리팩토링'을 포함하여 구조를 최적화할까요?
   아니면 원본 코드의 구조를 최대한 유지할까요?

   O: 리팩토링 포함 (OOP 원칙, Spring 표준 패턴)
   X: 구조 유지 (Pro*C 1:1 매핑)

   선택 (O/X):
   ```

2. **분석 단계**: 헤더 파싱, Pro*C 파싱, SQL 추출
3. **변환 단계**: Java 코드 생성, MyBatis 파일 생성 (병렬)
4. **리포트 생성**: 변환 결과 요약 및 체크리스트

### 출력 결과

```
output/quick_test/
├── java/
│   ├── service/
│   │   └── CursorSampleService.java
│   └── stub/
│       └── ConfigStub.java
├── mybatis/
│   ├── dto/
│   │   └── EmployeeDto.java
│   ├── mapper/
│   │   └── EmployeeMapper.java
│   └── mapper/
│       └── EmployeeMapper.xml
└── report/
    └── migration-report.md
```

---

## 에이전트 설명

### 1️⃣ main-orchestrator

**역할**: 최상위 조율자 - 전체 파이프라인 관리 및 사용자 확인

**주요 책임**:
- 사용자에게 변환 전략 질문 (O/X 블로킹)
- 각 에이전트 호출 순서 제어
- 에러 발생 시 워크플로우 중단/계속 결정

**사용 모델**: GPT-4 Turbo (sonnet)

**특징**:
- **블로킹 동작**: 사용자 응답 수신 전까지 다음 단계 진행 불가
- AskUserQuestion 도구 사용으로 명시적 확인

---

### 2️⃣ analysis-agent

**역할**: Pro*C 코드 분석 및 메타데이터 추출

**주요 작업**:
1. **헤더 파일 분석**: typedef, struct, #define 추출
2. **Pro*C 파일 파싱**: 함수, 변수, 제어 흐름 분석
3. **SQL 추출**: EXEC SQL 블록 식별 및 변환
4. **Extern 참조 식별**: 외부 의존성 탐지

**사용 기존 코드**:
```python
from parsing.header import IntegratedHeaderParser
from parsing.core import ProCParser
from parsing.sql import SQLExtractor

# 헤더 파싱
parser = IntegratedHeaderParser(include_paths=["./include"])
header_result = parser.parse_headers(header_paths)

# Pro*C 파싱
proc_parser = ProCParser()
proc_result = proc_parser.parse_file(proc_path)

# SQL 추출
sql_extractor = SQLExtractor()
sql_blocks = sql_extractor.extract_sql(proc_content)
```

**출력 형식**:
```json
{
  "type_map": {
    "CHAR_100": "String",
    "INT_T": "int"
  },
  "files": [
    {
      "source_file": "customer.pc",
      "loc": 1000,
      "chunked": false,
      "functions": [...]
    }
  ],
  "sql_blocks": [...],
  "extern_list": [...]
}
```

---

### 3️⃣ java-spring-agent

**역할**: Java Spring 코드 생성 및 Extern Stub 구현

**변환 전략**:

**Preserve 모드** (구조 유지):
- Pro*C 파일 1개 → Java Service 클래스 1개
- C 함수 1개 → Java 메서드 1개
- 최소한의 Controller (옵션)

**Refactor 모드** (리팩토링):
- OOP 원칙 적용 (단일 책임, 의존성 주입)
- Controller + Service 계층 분리
- Spring 표준 패턴 적용 (@Service, @Autowired)
- 도메인별 클래스 분리

**사용 기존 코드**:
```python
from conversion.core import ProcToJavaConverter
from conversion.plugins import SpringAnnotationPlugin

converter = ProcToJavaConverter(
    strategy="refactor",
    plugins=[SpringAnnotationPlugin()]
)
java_code = converter.convert(analysis_result)
```

**Extern Stub 생성**:
- 정의되지 않은 외부 함수/변수 → Stub 클래스 자동 생성
- 주석으로 원본 표시: `// STUB: extern from [헤더명]`
- 파이프라인 중단 없이 계속 진행

---

### 4️⃣ mybatis-agent

**역할**: MyBatis DTO/DAO/XML 생성

**생성 파일 세트** (SQL당 3개 파일):
1. **DTO** (Data Transfer Object): Java 클래스
2. **DAO** (Mapper Interface): MyBatis 인터페이스
3. **DBIO** (MyBatis XML): SQL 쿼리 정의

**주요 기능**:
- **커서 병합**: DECLARE/OPEN/FETCH/CLOSE → 단일 `<select>` 태그
- **동적 SQL 변환**: 조건문 → `<if>`, `<choose>` 태그
- **컬럼 별칭 매핑**: DB 컬럼명 → Java 필드명

**사용 기존 코드**:
```python
from parsing.sql import MyBatisConverter
from generation.artifacts import DAOGenerator, OMMGenerator, DBIOGenerator

# MyBatis SQL 변환
converter = MyBatisConverter()
mybatis_sql = converter.convert_sql(sql_block)

# DTO 생성
omm_gen = OMMGenerator()
dto_code = omm_gen.generate(sql_metadata)

# DAO 생성
dao_gen = DAOGenerator()
dao_code = dao_gen.generate(sql_metadata)

# XML 생성
dbio_gen = DBIOGenerator()
xml_content = dbio_gen.generate(sql_metadata, mybatis_sql)
```

---

### 5️⃣ report-agent

**역할**: 마이그레이션 리포트 작성

**리포트 구성**:
1. **변환 요약**: 생성 파일 통계
2. **파일 매핑 테이블**: Pro*C → Java 매핑 현황
3. **Extern Stub 목록**: 수동 구현 필요 항목
4. **검증 체크리스트**: 변환 후 확인 사항

**사용 모델**: GPT-3.5 Turbo (haiku) - 비용 절감

**출력 예시**:
```markdown
# Migration Report

생성일: 2026-02-24 10:30:00
전략: refactor

## 1. 변환 요약

| 항목 | 수량 |
|------|------|
| 생성 Java 파일 | 5개 |
| 생성 Stub 파일 | 2개 |
| 변환 SQL | 12개 |

## 2. 파일 매핑

| Pro*C 파일 | Java 파일 | 라인 수 |
|-----------|----------|---------|
| customer.pc | CustomerService.java | 1,200 LOC |

## 3. Extern Stub 목록

- `ConfigStub.java` (원본: config.h)
  - `get_config()` 함수 구현 필요

## 4. 검증 체크리스트

- [ ] 모든 EXEC SQL이 MyBatis XML로 추출되었는가
- [ ] Extern Stub이 실제 구현으로 교체되었는가
```

---

## 스킬 설명

### 🔧 file-reader-chunker

**목적**: 대용량 파일 (5,000 LOC 이상) 청킹

**청킹 전략**:
1. **함수 경계 기준**: 함수 단위로 분할 (우선)
2. **LOC 기준**: 함수 경계 실패 시 라인 수 기준 폴백
3. **블록 기준**: 재귀적 재청킹 (최악의 경우)

**컨텍스트 보존**:
- 글로벌 변수 정보 각 청크에 포함
- 이전 함수 요약 전달 (의존성 추적)

**사용 기존 코드**:
```python
from infra.agents.langchain.utils.chunking import chunk_by_function

chunks = chunk_by_function(
    content=proc_content,
    max_size=1000,
    include_context=True
)
```

**출력 형식**:
```json
{
  "chunked": true,
  "chunks": [
    {
      "chunk_id": 0,
      "content": "...",
      "context_header": "// 글로벌 변수: g_config, g_session\n..."
    }
  ]
}
```

---

### 🔧 macro-type-mapper

**목적**: C/Pro*C 타입을 Java 타입으로 매핑

**처리 항목**:
- **typedef**: `typedef char CHAR_100[100]` → `String`
- **#define**: `#define MAX_LEN 100` → Java 상수
- **struct**: 중첩 구조체 분석 (최대 깊이 3)

**복잡한 타입 처리**:
- 함수 포인터 → `TODO: 수동 구현 필요` 주석
- Union → 수동 검토 플래그 설정

**사용 기존 코드**:
```python
from parsing.header import IntegratedHeaderParser
from infra.config.type_mappings import TypeMapper

parser = IntegratedHeaderParser()
header_result = parser.parse_headers(header_paths)

type_mapper = TypeMapper()
java_type = type_mapper.map_type(c_type)
```

---

### 🔧 sql-extractor

**목적**: EXEC SQL 블록 추출 및 변환

**주요 기능**:

1. **Tree-sitter 기반 파싱**: 정확한 SQL 블록 식별
2. **커서 병합**:
   ```c
   EXEC SQL DECLARE emp_cursor CURSOR FOR ...;
   EXEC SQL OPEN emp_cursor;
   EXEC SQL FETCH emp_cursor INTO :var1, :var2;
   EXEC SQL CLOSE emp_cursor;

   ↓ 병합

   SELECT ... (단일 쿼리로 통합)
   ```

3. **바인드 변수 분류**:
   - `:in_var` → 입력 파라미터
   - `:out_var` → 출력 변수
   - `:inout_var` → 양방향 파라미터

4. **동적 SQL 탐지**:
   ```c
   sprintf(sql_buf, "SELECT * FROM %s WHERE ...", table_name);
   EXEC SQL EXECUTE IMMEDIATE :sql_buf;

   ↓ 플래그 설정

   is_dynamic: true (수동 검토 필요)
   ```

**사용 기존 코드**:
```python
from parsing.sql import SQLExtractor, CursorMerger, DynamicSQLExtractor

# SQL 추출
extractor = SQLExtractor()
sql_blocks = extractor._extract_with_tree_sitter(proc_content)

# 커서 병합
merger = CursorMerger()
merged_blocks = merger.merge_cursor_sequences(sql_blocks)

# 동적 SQL 탐지
dynamic_detector = DynamicSQLExtractor()
flagged_blocks = dynamic_detector.detect_dynamic_sql(sql_blocks)
```

---

### 🔧 file-writer

**목적**: 안전한 파일 쓰기

**기능**:
- UTF-8 인코딩 보장
- 디렉토리 자동 생성
- 충돌 시 타임스탬프 파일 생성 (`_20260224_103000`)

**사용 예시**:
```python
file_writer.write(
    path="output/java/CustomerService.java",
    content=java_code,
    overwrite=True
)
```

---

## 실행 방법

### 기본 실행

```bash
python run_multiagent_conversion.py \
  --headers include/types.h,include/customer.h \
  --procs src/customer.pc,src/order.pc \
  --output output/
```

### 옵션 설명

| 옵션 | 필수 여부 | 설명 | 예시 |
|------|----------|------|------|
| `--headers` | **필수** | 헤더 파일 경로 (쉼표 구분) | `types.h,common.h` |
| `--procs` | **필수** | Pro*C 파일 경로 (쉼표 구분) | `main.pc,sub.pc` |
| `--output` | 옵션 | 출력 디렉토리 | `output/` (기본값) |
| `--strategy` | 옵션 | 변환 전략 (`preserve`\|`refactor`) | 생략 시 대화형 질문 |
| `--knowledge` | 옵션 | 도메인 지식 문서 | `docs/rules.md` |
| `--config` | 옵션 | 설정 파일 경로 | `config/custom.yaml` |

### 전략 자동 지정

```bash
# 구조 유지 모드 (대화형 질문 생략)
python run_multiagent_conversion.py \
  --headers sample.h \
  --procs sample.pc \
  --output output/ \
  --strategy preserve

# 리팩토링 모드
python run_multiagent_conversion.py \
  --headers sample.h \
  --procs sample.pc \
  --output output/ \
  --strategy refactor
```

### 지식 문서 활용

도메인별 변환 규칙을 Markdown 파일로 제공:

```bash
python run_multiagent_conversion.py \
  --headers include/*.h \
  --procs src/*.pc \
  --output output/ \
  --knowledge docs/banking-domain-rules.md
```

**지식 문서 예시** (`docs/banking-domain-rules.md`):
```markdown
# 은행 도메인 변환 규칙

## 계좌번호 처리
- C 타입: `char account_no[20]`
- Java 타입: `String accountNo` (20자리 고정)
- 유효성 검사: 숫자만 허용

## 거래 금액
- C 타입: `long amount`
- Java 타입: `BigDecimal amount`
- 정밀도: 소수점 2자리
```

---

## 테스트 시나리오

### 시나리오 1: 단일 파일 변환 (LOC < 5,000)

**목적**: 소규모 파일의 기본 변환 검증

```bash
python run_multiagent_conversion.py \
  --headers tests/fixtures/sample_input_data/sample.h \
  --procs tests/fixtures/sample_input_data/cursor_sample.pc \
  --output output/scenario1/ \
  --strategy preserve
```

**검증 항목**:
- [ ] 청킹 없이 단일 분석 수행
- [ ] Java Service 클래스 1개 생성
- [ ] MyBatis DTO/DAO/XML 3종 생성
- [ ] 리포트에 파일 매핑 테이블 존재

---

### 시나리오 2: 대용량 파일 변환 (LOC > 5,000)

**목적**: 청킹 및 병합 처리 검증

```bash
python run_multiagent_conversion.py \
  --headers tests/fixtures/sample_input_data/sample.h \
  --procs tests/fixtures/sample_input_data/enterprise_complex_sql.pc \
  --output output/scenario2/ \
  --strategy refactor
```

**검증 항목**:
- [ ] 함수 경계 기준 청킹 수행
- [ ] 청크 개수 > 1
- [ ] Controller + Service 계층 분리
- [ ] Spring 어노테이션 적용

---

### 시나리오 3: Extern 참조 포함 파일

**목적**: Extern 처리 및 Stub 생성 검증

```bash
python run_multiagent_conversion.py \
  --headers tests/fixtures/sample_input_data/sample.h,tlfb000m.h \
  --procs original_source.sqc \
  --output output/scenario3/ \
  --strategy preserve
```

**검증 항목**:
- [ ] `extern_list`에 모든 extern 심볼 포함
- [ ] Stub 파일 생성 (예: `ConfigStub.java`)
- [ ] 리포트에 Extern 목록 섹션 존재
- [ ] 파이프라인 중단 없이 완료

---

### 시나리오 4: 커서 사용 파일

**목적**: 커서 병합 처리 검증

```bash
python run_multiagent_conversion.py \
  --headers tests/fixtures/sample_input_data/sample.h \
  --procs tests/fixtures/sample_input_data/cursor_sample.pc \
  --output output/scenario4/ \
  --strategy preserve
```

**검증 항목**:
- [ ] 커서 시퀀스 탐지 (DECLARE/OPEN/FETCH/CLOSE)
- [ ] MyBatis XML에 단일 `<select>` 태그로 병합
- [ ] Java 메서드 반환 타입이 `List<Dto>`
- [ ] 리포트에 커서 처리 현황 기록

---

### 전체 시나리오 일괄 실행

```bash
# 실행 권한 부여
chmod +x tests/multiagent/run_all_scenarios.sh

# 전체 시나리오 실행
bash tests/multiagent/run_all_scenarios.sh
```

**출력 예시**:
```
🧪 멀티에이전트 시스템 통합 테스트 시작
========================================

📋 시나리오 1: 단일 파일 변환 (LOC < 5,000)
-------------------------------------------
✅ 시나리오 1 완료

📋 시나리오 2: 대용량 파일 변환 (LOC > 5,000)
-----------------------------------------------
✅ 시나리오 2 완료

📋 시나리오 3: Extern 참조 포함 파일
-------------------------------------
✅ 시나리오 3 완료

📋 시나리오 4: 커서 사용 파일
-----------------------------
✅ 시나리오 4 완료

========================================
✅ 모든 시나리오 실행 완료
========================================
```

---

## 설정 커스터마이징

### config/multiagent_config.yaml 주요 설정

#### 1. Agent 모델 변경

```yaml
agents:
  analysis_agent:
    model: gpt-4-turbo  # 더 정확한 분석
    temperature: 0.1    # 낮을수록 일관성 향상
```

#### 2. 청킹 임계값 조정

```yaml
skills:
  file_reader_chunker:
    max_loc_threshold: 5000  # 기본값
    chunk_size: 1000         # 청크당 라인 수
    boundary_type: function  # function | loc | block
```

#### 3. 변환 전략 기본값

```yaml
conversion:
  default_strategy: preserve  # preserve | refactor

  preserve:
    one_to_one_mapping: true
    keep_function_names: true

  refactor:
    apply_oop_principles: true
    split_by_domain: true
```

#### 4. Extern 처리 설정

```yaml
validation:
  extern_handling:
    create_stubs: true       # Stub 자동 생성
    halt_on_extern: false    # Extern 발견 시 중단하지 않음
    report_all_externs: true # 리포트에 모두 기록
```

#### 5. 병렬 처리 성능

```yaml
performance:
  enable_parallel_agents: true
  max_parallel_workers: 2  # java-spring-agent + mybatis-agent
  agent_timeout_seconds: 300
```

---

## 문제 해결

### ❌ 문제: FileNotFoundError

**증상**:
```
❌ 다음 파일을 찾을 수 없습니다:
   - include/missing.h
```

**해결책**:
1. 파일 경로 확인 (절대 경로 또는 상대 경로)
2. 파일 존재 여부 확인: `ls -la include/`

---

### ❌ 문제: API Key 오류

**증상**:
```
OpenAI API Error: Invalid API key
```

**해결책**:
1. `.env` 파일에 API 키 정확히 입력했는지 확인
2. API 키 유효성 테스트:
   ```bash
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer $OPENAI_API_KEY"
   ```
3. 환경 변수 로드 확인:
   ```bash
   python -c "import os; print(os.getenv('OPENAI_API_KEY'))"
   ```

---

### ❌ 문제: 청킹 실패

**증상**:
```
[ERROR] 함수 경계를 찾을 수 없습니다. LOC 기준 폴백 실패.
```

**해결책**:
1. `config/multiagent_config.yaml`에서 폴백 전략 활성화 확인:
   ```yaml
   skills:
     file_reader_chunker:
       fallback_strategy: loc
   ```
2. 파일 형식 확인 (유효한 C/Pro*C 코드인지)
3. 로그 확인: `logs/multiagent_conversion.log`

---

### ❌ 문제: SQL 추출 실패

**증상**:
리포트에 SQL 개수가 0개로 표시됨

**해결책**:
1. Tree-sitter 활성화 확인:
   ```yaml
   skills:
     sql_extractor:
       use_tree_sitter: true
   ```
2. Pro*C 파일에 `EXEC SQL` 블록이 실제로 존재하는지 확인
3. 수동 확인:
   ```bash
   grep -n "EXEC SQL" your_file.pc
   ```

---

### ❌ 문제: 타임아웃 발생

**증상**:
```
[ERROR] Agent timeout after 300 seconds
```

**해결책**:
1. 타임아웃 연장:
   ```yaml
   performance:
     agent_timeout_seconds: 600  # 10분
   ```
2. 파일 크기 확인 (너무 큰 파일은 청킹 임계값 조정)
3. 네트워크 상태 확인

---

## 고급 사용법

### 1. 커스텀 플러그인 추가

새로운 타입 매핑 규칙 추가:

```python
# infra/config/custom_type_mappings.py
CUSTOM_TYPE_MAP = {
    "MY_CUSTOM_TYPE": "CustomJavaType",
    "LEGACY_STRUCT": "ModernDto"
}
```

설정 파일에 등록:
```yaml
skills:
  macro_type_mapper:
    type_mapping_file: infra/config/custom_type_mappings.py
```

---

### 2. 도메인별 명명 규칙

```yaml
output:
  naming:
    service_suffix: ServiceImpl    # 기본값: Service
    controller_suffix: RestController
    dto_suffix: Vo                 # 기본값: Dto
```

---

### 3. 체크포인트 활용 (중단된 작업 재개)

```yaml
advanced:
  enable_checkpoints: true
  checkpoint_dir: .checkpoints/
```

중단된 작업 재개:
```bash
python run_multiagent_conversion.py \
  --resume-from .checkpoints/20260224_103000/
```

---

### 4. 로그 레벨 조정

```yaml
logging:
  level: DEBUG  # DEBUG | INFO | WARNING | ERROR
  log_file: logs/debug_conversion.log
  log_agent_calls: true
  log_skill_calls: true
```

상세 로그 확인:
```bash
tail -f logs/debug_conversion.log
```

---

## 📚 추가 참고 자료

- **Enhanced Plan**: `multiagent_enhanced_plan.md`
- **Agent 정의**: `.claude/agents/*.md`
- **Skill 정의**: `.claude/skills/*/SKILL.md`
- **테스트 시나리오**: `tests/multiagent/test_scenarios.md`
- **설정 파일**: `config/multiagent_config.yaml`

---

## 🆘 지원

문제가 해결되지 않는 경우:

1. **로그 확인**: `logs/multiagent_conversion.log`
2. **상세 모드 실행**:
   ```bash
   LOG_LEVEL=DEBUG python run_multiagent_conversion.py ...
   ```
3. **이슈 리포트**: GitHub Issues에 다음 정보 포함
   - 에러 메시지 전문
   - 입력 파일 샘플
   - 사용한 명령어
   - 로그 파일

---

**마지막 업데이트**: 2026-02-24
**버전**: Enhanced Plan v2.0


## 최신 실행 가이드 (LangGraph)

- `langgraph_run_guide.md`를 참고하세요.
