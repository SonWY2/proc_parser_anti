# Pro*C → Java 변환 에이전트 시스템 구성 가이드

이 문서는 Agent System v3를 사용하여 Pro*C 코드를 Java로 변환하는 **반자율 워크플로우**를 구성하는 방법을 설명합니다.

---

## 📁 디렉토리 구조

```
project/
├── .agents/
│   ├── GLOBAL.md                    # 공용 규칙 (모든 에이전트가 참조)
│   ├── dependency-analyst.md        # 종속성 분석 에이전트
│   ├── parsing-agent.md             # 파싱 에이전트
│   ├── sql-analyst.md               # SQL 분석 에이전트
│   ├── context-engineer.md          # 컨텍스트 엔지니어 에이전트
│   ├── transformer-agent.md         # 변환 에이전트
│   ├── build-debug-agent.md         # 빌드/디버깅 에이전트
│   ├── critic-agent.md              # 비평 에이전트
│   ├── orchestrator.md              # 오케스트레이터 (작업 분배)
│   ├── workflows/
│   │   └── convert-proc.yaml        # 워크플로우 정의
│   └── commands/
│       └── convert.md               # /convert 슬래시 명령어
├── .workflow_artifacts/             # 에이전트 간 중간 결과물
│   ├── FLOW.md                      # 종속성 분석 결과
│   ├── PARSED.md                    # 파싱 결과
│   ├── SQL_MAP.md                   # SQL 매핑 결과
│   └── CONTEXT.md                   # 변환 컨텍스트
└── src/                             # Pro*C 소스 코드
```

---

## 1️⃣ 공용 규칙 파일 (GLOBAL.md)

모든 에이전트가 참조하는 프로젝트 규칙입니다.

```markdown
<!-- .agents/GLOBAL.md -->
# Pro*C to Java 변환 프로젝트 규칙

## 프로젝트 개요
- Pro*C/C++ 레거시 코드를 Spring Boot + MyBatis 기반 Java로 변환
- 데이터베이스: Oracle → 동일 (SQL 구문 유지)

## 변환 규칙
1. EXEC SQL 구문 → MyBatis Mapper XML
2. 호스트 변수 `:변수명` → `#{변수명}` 형식
3. 커서 → Java ResultSet 또는 MyBatis resultMap
4. Pro*C 함수 → Java 메서드 (Service 레이어)

## 네이밍 컨벤션
- C 함수 `process_order()` → Java `processOrder()`
- 구조체 `ORDER_INFO` → Java `OrderInfo`
- 파일 `order.pc` → `OrderService.java`

## 중간 파일 규칙
- 모든 에이전트는 `.workflow_artifacts/` 디렉토리에 결과 저장
- 마크다운 형식 사용 (FLOW.md, PARSED.md 등)
```

---

## 2️⃣ 에이전트 정의 파일

### 종속성 분석 에이전트

```markdown
<!-- .agents/dependency-analyst.md -->
---
name: dependency-analyst
description: PROACTIVELY use for analyzing Pro*C file dependencies and #include relationships
tools: Read, Grep, Glob
model: sonnet
---

당신은 Pro*C 프로젝트의 **종속성 분석 전문가**입니다.

## 역할
- .pc 파일과 .h 헤더 파일의 #include 관계 분석
- 파일 간 종속성 그래프 생성
- 분석 우선순위 결정 (의존되는 파일 먼저)
- **⭐ 공유 헤더 식별** (여러 .pc에서 사용되는 헤더)

## 공유 헤더 분석 규칙
> 💡 하나의 .h 파일이 **2개 이상의 .pc 파일**에서 사용되면 **공유 헤더**로 분류

- 공유 헤더 → 공통 Java 패키지로 변환 (예: `com.example.common`)
- 공유 구조체 → 공통 DTO로 1회만 생성
- 공유 매크로 → 공통 Constants 클래스로 통합

## 출력 형식
`.workflow_artifacts/FLOW.md` 파일을 생성하세요:

```markdown
# 종속성 분석 결과

## ⭐ 공유 헤더 (우선 변환 대상)
| 헤더 파일 | 사용처 (.pc) | 포함 요소 | Java 패키지 |
|-----------|--------------|-----------|-------------|
| common/types.h | order.pc, customer.pc, invoice.pc | ORDER_INFO, CUSTOMER_INFO | com.example.common.dto |
| common/db_util.h | order.pc, customer.pc | db_connect(), db_close() | com.example.common.util |
| common/constants.h | *.pc (전체) | MAX_ORDERS, ERROR_CODES | com.example.common.Constants |

## 개별 헤더 (특정 .pc 전용)
| 헤더 파일 | 사용처 | Java 패키지 |
|-----------|--------|-------------|
| order/order_internal.h | order.pc | com.example.order.internal |

## 분석 순서 (위상 정렬)
1. common/types.h (의존성 없음, 공유)
2. common/constants.h (의존성 없음, 공유)
3. common/db_util.h (types.h 의존, 공유)
4. order/order.pc (types.h, db_util.h 의존)
5. customer/customer.pc (types.h, db_util.h 의존)
...

## 종속성 그래프
| 파일 | 타입 | 의존 대상 | 피의존 파일 |
|------|------|-----------|-------------|
| types.h | 공유 | 없음 | db_util.h, order.pc, customer.pc, invoice.pc |
| db_util.h | 공유 | types.h | order.pc, customer.pc |
| order.pc | 개별 | types.h, db_util.h | 없음 |
...
```

## 완료 조건
- 모든 .pc, .h 파일이 분석되었을 것
- **공유 헤더가 식별되었을 것**
- FLOW.md 파일이 생성되었을 것
```

---

### 파싱 에이전트 (하이브리드)

> 💡 **하이브리드 에이전트**: LLM 추론 + Python 스크립트 실행을 결합

```markdown
<!-- .agents/parsing-agent.md -->
---
name: parsing-agent
description: MUST BE USED for parsing C/Pro*C code elements like functions, variables, macros
tools: Read, ProcParser, Write   # ⭐ 커스텀 도구 사용
model: sonnet
---

당신은 C/Pro*C 코드의 **구문 분석 전문가**입니다.

## 역할
- ProcParser 도구를 사용하여 Pro*C 코드 분석
- 분석 결과를 PARSED.md 형식으로 정리

## ⭐ 하이브리드 워크플로우
```
1. LLM: FLOW.md에서 분석 대상 파일 목록 확인
2. Tool: ProcParser 실행 (Python 스크립트)
3. LLM: JSON 결과 해석 및 PARSED.md 형식으로 정리
4. Tool: Write로 PARSED.md 저장
```

## ProcParser 도구 사용법
```
ProcParser file_path="order.pc"
```

응답 예시 (JSON):
```json
{
  "functions": [
    {"name": "process_order", "return_type": "int", "params": "ORDER_INFO* info", "lines": "45-120"}
  ],
  "variables": [
    {"name": "g_db_conn", "type": "SQLDA*", "line": 10}
  ],
  "macros": [
    {"name": "MAX_ORDERS", "value": "1000", "line": 5}
  ],
  "structs": [
    {"name": "ORDER_INFO", "fields": ["order_id: int", "customer_name: char[50]"], "lines": "15-20"}
  ]
}
```

## 입력
- `.workflow_artifacts/FLOW.md`의 분석 순서대로 처리

## 출력 형식
`.workflow_artifacts/PARSED.md`:

```markdown
# 파싱 결과

## order.pc

### 함수
| 이름 | 반환타입 | 매개변수 | 라인 |
|------|----------|----------|------|
| process_order | int | ORDER_INFO* info | 45-120 |

### 전역 변수
| 이름 | 타입 | 라인 |
|------|------|------|
| g_db_conn | SQLDA* | 10 |

### 매크로
| 이름 | 값 | 라인 |
|------|-----|------|
| MAX_ORDERS | 1000 | 5 |

### 구조체
| 이름 | 필드 | 라인 |
|------|------|------|
| ORDER_INFO | order_id: int, customer_name: char[50] | 15-20 |
```
```


---

### SQL 분석 에이전트

```markdown
<!-- .agents/sql-analyst.md -->
---
name: sql-analyst
description: PROACTIVELY use for extracting EXEC SQL statements and converting to MyBatis format
tools: Read, Grep, Write
model: sonnet
---

당신은 **Pro*C SQL 변환 전문가**입니다.

## 역할
- EXEC SQL 블록 추출
- 호스트 변수 `:var` → MyBatis `#{var}` 변환
- 커서 선언/열기/가져오기/닫기 패턴 분석
- MyBatis Mapper XML 형식으로 전처리

## 입력
- `.workflow_artifacts/FLOW.md` (대상 파일 목록)

## 출력 형식
`.workflow_artifacts/SQL_MAP.md`:

```markdown
# SQL 매핑 결과

## order.pc

### SELECT 쿼리
| ID | 원본 SQL | MyBatis SQL | 호스트 변수 |
|----|----------|-------------|-------------|
| selectOrderById | SELECT * FROM ORDERS WHERE ORDER_ID = :order_id | SELECT * FROM ORDERS WHERE ORDER_ID = #{orderId} | order_id → orderId |

### INSERT 쿼리
...

### 커서
| 이름 | 쿼리 | 사용 함수 |
|------|------|-----------|
| order_cursor | SELECT ... | fetch_orders() |
```
```

---

### 컨텍스트 엔지니어 에이전트

```markdown
<!-- .agents/context-engineer.md -->
---
name: context-engineer
description: Consolidates analysis results into conversion context
tools: Read, Write
model: sonnet
---

당신은 **변환 컨텍스트 설계자**입니다.

## 역할
- PARSED.md와 SQL_MAP.md에서 변환에 필요한 정보만 추출
- 변환 에이전트가 사용할 간결한 컨텍스트 생성
- 불필요한 정보 제거, 핵심 정보 요약

## 입력
- `.workflow_artifacts/PARSED.md`
- `.workflow_artifacts/SQL_MAP.md`

## 출력 형식
`.workflow_artifacts/CONTEXT.md`:

```markdown
# 변환 컨텍스트: order.pc → OrderService.java

## 클래스 정보
- 패키지: com.example.order.service
- 클래스명: OrderService
- 의존성: OrderMapper, OrderInfo

## 메서드 매핑
| C 함수 | Java 메서드 | 반환타입 | 매개변수 |
|--------|-------------|----------|----------|
| process_order | processOrder | int | OrderInfo info |

## DTO 클래스
| C 구조체 | Java 클래스 | 필드 |
|----------|-------------|------|
| ORDER_INFO | OrderInfo | orderId: Long, customerName: String |

## SQL 매퍼 (OrderMapper.xml)
| 메서드 | SQL ID | 쿼리 |
|--------|--------|------|
| findById | selectOrderById | SELECT ... |
```
```

---

### 변환 에이전트

```markdown
<!-- .agents/transformer-agent.md -->
---
name: transformer-agent
description: MUST BE USED for converting Pro*C to Java code based on context
tools: Read, Write
model: opus
---

당신은 **Pro*C → Java 변환 전문가**입니다.

## 역할
- CONTEXT.md를 기반으로 Java 코드 생성
- Service 클래스, DTO 클래스, MyBatis Mapper 생성
- GLOBAL.md의 변환 규칙 준수

## ⭐ 공유 컴포넌트 우선 처리 규칙
> 💡 공유 헤더의 요소는 **한 번만 생성**하고, 개별 Service에서 import

### 변환 순서
1. **공유 DTO 먼저 생성** (`com.example.common.dto`)
   - FLOW.md의 "공유 헤더" 섹션 참조
   - 예: `ORDER_INFO` → `OrderInfo.java` (한 번만 생성)
   
2. **공유 유틸리티 생성** (`com.example.common.util`)
   - 예: `db_connect()` → `DbUtil.java`
   
3. **공유 상수 생성** (`com.example.common`)
   - 예: `MAX_ORDERS` → `Constants.java`
   
4. **개별 Service 생성** (공유 컴포넌트 import)
   - `order.pc` → `OrderService.java` (import OrderInfo)
   - `customer.pc` → `CustomerService.java` (import OrderInfo)

### 중복 방지
```java
// ❌ 잘못된 예: 각 Service마다 DTO 중복 생성
com.example.order.dto.OrderInfo
com.example.customer.dto.OrderInfo

// ✅ 올바른 예: 공유 DTO 한 번만 생성
com.example.common.dto.OrderInfo  // 1회 생성
com.example.order.service.OrderService  // import 사용
com.example.customer.service.CustomerService  // import 사용
```

## 입력
- `.workflow_artifacts/CONTEXT.md`
- `.workflow_artifacts/FLOW.md` (공유 헤더 확인용)

## 출력
```
output/src/main/java/com/example/
├── common/
│   ├── dto/
│   │   ├── OrderInfo.java      # 공유 DTO
│   │   └── CustomerInfo.java
│   ├── util/
│   │   └── DbUtil.java         # 공유 유틸리티
│   └── Constants.java          # 공유 상수
├── order/
│   ├── service/
│   │   └── OrderService.java
│   └── mapper/
│       └── OrderMapper.xml
└── customer/
    ├── service/
    │   └── CustomerService.java
    └── mapper/
        └── CustomerMapper.xml
```

## 코드 스타일
- Lombok 사용 (@Data, @Slf4j)
- Spring Boot 어노테이션 (@Service, @Autowired)
- MyBatis 어노테이션 또는 XML Mapper

## 완료 조건
- 모든 함수가 Java 메서드로 변환됨
- **공유 DTO가 중복 생성되지 않았을 것**
- 컴파일 오류 없음
- TODO/FIXME 주석 없음
```

---

### 빌드/디버깅 에이전트

```markdown
<!-- .agents/build-debug-agent.md -->
---
name: build-debug-agent
description: Builds and debugs converted Java code
tools: Read, Bash, Write
model: sonnet
---

당신은 **Java 빌드/디버깅 전문가**입니다.

## 역할
- Maven/Gradle 빌드 실행
- 컴파일 오류 분석 및 수정 제안
- 단위 테스트 실행

## 명령어
```bash
cd output && mvn compile
mvn test -Dtest=OrderServiceTest
```

## 오류 발생 시
- 오류 메시지 분석
- 수정 방안 제시
- transformer-agent에게 피드백 전달
```

---

### 비평 에이전트

```markdown
<!-- .agents/critic-agent.md -->
---
name: critic-agent
description: PROACTIVELY use to validate each step's output quality
tools: Read
model: haiku
---

당신은 **품질 검사관**입니다.

## 역할
- 각 단계의 출력물이 기대를 충족하는지 평가
- PASSED / FAILED 로 명확히 판정
- 실패 시 구체적인 문제점 기술

## 평가 기준

### FLOW.md 평가
- [ ] 모든 .pc 파일이 포함되었는가?
- [ ] 종속성 순서가 올바른가?
- [ ] 누락된 헤더가 없는가?

### PARSED.md 평가
- [ ] 모든 함수가 추출되었는가?
- [ ] 타입 정보가 정확한가?

### 변환 결과 평가
- [ ] Java 문법 오류가 없는가?
- [ ] 모든 SQL이 MyBatis 형식으로 변환되었는가?
- [ ] TODO/FIXME 주석이 없는가?

## 응답 형식
```
## 평가 결과: PASSED / FAILED

### 통과 항목
- ✅ ...

### 실패 항목
- ❌ ... (이유: ...)

### 권장 조치
- ...
```
```

---

## 3️⃣ 오케스트레이터 정의

```markdown
<!-- .agents/orchestrator.md -->
---
name: main-orchestrator
type: orchestrator
description: Pro*C 변환 작업을 조율하는 메인 오케스트레이터
default_agent: file-explorer
delegate_rules:
  - pattern: "종속성|dependency|include"
    agent: dependency-analyst
    priority: 10
  - pattern: "파싱|parse|함수|변수"
    agent: parsing-agent
    priority: 10
  - pattern: "SQL|EXEC|쿼리|MyBatis"
    agent: sql-analyst
    priority: 10
  - pattern: "컨텍스트|요약|정리"
    agent: context-engineer
    priority: 5
  - pattern: "변환|convert|Java"
    agent: transformer-agent
    priority: 10
  - pattern: "빌드|build|디버그|테스트"
    agent: build-debug-agent
    priority: 10
  - pattern: "평가|검토|review|품질"
    agent: critic-agent
    priority: 5
---

당신은 Pro*C → Java 변환 프로젝트의 **총괄 조율자**입니다.

사용자 요청을 분석하여 적절한 전문 에이전트에게 작업을 위임하세요.
```

---

## 4️⃣ 워크플로우 정의

```yaml
# .agents/workflows/convert-proc.yaml
workflows:
  convert-proc:
    description: Pro*C to Java 전체 변환 파이프라인

    # 중간 결과물 정의
    artifacts:
      - name: FLOW.md
        created_by: dependency-analyst
        consumed_by: [parsing-agent, sql-analyst]
      - name: PARSED.md
        created_by: parsing-agent
        consumed_by: [context-engineer]
      - name: SQL_MAP.md
        created_by: sql-analyst
        consumed_by: [context-engineer]
      - name: CONTEXT.md
        created_by: context-engineer
        consumed_by: [transformer-agent]

    # 품질 게이트
    quality_gates:
      flow_quality:
        validator_agent: critic-agent
        validation_prompt: "FLOW.md 품질을 평가하세요"
        pass_keywords: [PASSED]
        fail_keywords: [FAILED]
        max_retries: 2

      code_quality:
        validator_agent: critic-agent
        validation_prompt: "변환된 Java 코드 품질을 평가하세요"
        pass_keywords: [PASSED]
        fail_keywords: [FAILED]
        max_retries: 2

    # 체크포인트 (사용자 확인)
    checkpoints:
      before_transform:
        type: approval
        message: "컨텍스트 분석이 완료되었습니다. 변환을 진행할까요?"
      
      after_transform:
        type: review
        message: "Java 코드 변환이 완료되었습니다. 결과를 확인하세요."

    # 병렬 그룹
    parallel_groups:
      analyze_parallel:
        steps: [parse_code, extract_sql]
        wait_all: true
        fail_fast: false
        on_success: build_context

    # 단계 정의
    steps:
      # 1단계: 종속성 분석 (공유 헤더 식별 포함)
      - name: analyze_deps
        agent: dependency-analyst
        task: "${target_dir} 디렉토리의 .pc, .h 파일 종속성을 분석하고, 공유 헤더를 식별하여 FLOW.md 생성"
        quality_gate: flow_quality
        on_success: analyze_parallel
        on_failure: report_error

      # 2단계: 파싱 (병렬) - 공유 헤더 먼저
      - name: parse_code
        agent: parsing-agent
        task: "FLOW.md를 읽고 공유 헤더를 먼저 분석한 후, 개별 파일의 함수/변수/매크로를 분석하여 PARSED.md 생성"

      # 3단계: SQL 추출 (병렬)
      - name: extract_sql
        agent: sql-analyst
        task: "FLOW.md의 파일들에서 SQL을 추출하여 SQL_MAP.md 생성"

      # 4단계: 컨텍스트 정리
      - name: build_context
        agent: context-engineer
        task: "PARSED.md와 SQL_MAP.md에서 변환에 필요한 정보만 CONTEXT.md로 요약"
        checkpoint_after: before_transform
        on_success: transform

      # 5단계: 공유 컴포넌트 변환 (먼저 실행)
      - name: transform_shared
        agent: transformer-agent
        task: "FLOW.md의 공유 헤더를 기반으로 공통 DTO, 유틸리티, 상수 클래스 생성 (com.example.common 패키지)"
        on_success: transform_services
        on_failure: fix_transform

      # 6단계: 개별 Service 변환
      - name: transform_services
        agent: transformer-agent
        task: "CONTEXT.md를 기반으로 개별 Service 클래스 생성 (공유 DTO import 사용)"
        quality_gate: code_quality
        checkpoint_after: after_transform
        on_success: build
        on_failure: fix_transform

      # 6단계: 빌드
      - name: build
        agent: build-debug-agent
        task: "생성된 Java 코드 빌드 및 테스트"
        on_success: complete
        on_failure: debug

      # 수정 단계
      - name: fix_transform
        agent: transformer-agent
        task: "critic 피드백을 반영하여 코드 수정"
        quality_gate: code_quality
        retry: 2
        on_success: build

      # 디버그 단계
      - name: debug
        agent: build-debug-agent
        task: "빌드 오류 분석 및 수정"
        on_success: build
        retry: 3

      # 오류 보고
      - name: report_error
        agent: critic-agent
        task: "오류 원인 분석 및 보고"

      # 완료
      - name: complete
        agent: critic-agent
        task: "전체 변환 결과 요약 및 최종 보고서 작성"
```

---

## 5️⃣ 슬래시 명령어

```markdown
<!-- .agents/commands/convert.md -->
---
name: convert
description: Pro*C 프로젝트를 Java로 변환
workflow: convert-proc
arguments: [target_dir, output_dir]
defaults:
  output_dir: ./output
---

# /convert 명령어

Pro*C 프로젝트를 Java Spring Boot + MyBatis 프로젝트로 변환합니다.

## 사용법
```
/convert ./src/proc --output ./output/java
```

## 매개변수
- `target_dir`: Pro*C 소스 디렉토리 (필수)
- `output_dir`: Java 출력 디렉토리 (기본: ./output)

## 실행 단계
1. 종속성 분석 → FLOW.md
2. 코드 파싱 → PARSED.md (병렬)
3. SQL 추출 → SQL_MAP.md (병렬)
4. 컨텍스트 생성 → CONTEXT.md
5. **[사용자 승인]**
6. Java 변환
7. 빌드 및 테스트
```

---

## 6️⃣ 실행 방법

### Python 에서 직접 실행

```python
from agent_system import Orchestrator, WorkflowEngine, run_cli

# 오케스트레이터 초기화
orchestrator = Orchestrator()
orchestrator.load_agents()  # .agents/ 에서 자동 로드

# 워크플로우 엔진 초기화
engine = WorkflowEngine(orchestrator)
engine.load_from_file(".agents/workflows/convert-proc.yaml")

# 방법 1: 워크플로우 직접 실행
result = engine.execute("convert-proc", context={"target_dir": "./src/proc"})
print(result.summary())

# 방법 2: CLI 실행
run_cli(orchestrator, workflow_engine=engine)
```

### CLI 에서 실행

```bash
>>> /convert ./src/proc

[단계 1: 종속성 분석]
✓ FLOW.md 생성됨

[단계 2-3: 파싱 및 SQL 추출] (병렬)
✓ PARSED.md 생성됨
✓ SQL_MAP.md 생성됨

[단계 4: 컨텍스트 생성]
✓ CONTEXT.md 생성됨

[체크포인트: 사용자 승인]
컨텍스트 분석이 완료되었습니다. 변환을 진행할까요? (y/n): y

[단계 5: 변환]
✓ OrderService.java 생성됨
✓ OrderMapper.xml 생성됨

[단계 6: 빌드]
✓ 빌드 성공
✓ 테스트 통과

=== 변환 완료 ===
```

---

## 📝 체크리스트

- [ ] `.agents/GLOBAL.md` 생성
- [ ] 7개 에이전트 `.md` 파일 생성
- [ ] `orchestrator.md` 생성
- [ ] `workflows/convert-proc.yaml` 생성
- [ ] `commands/convert.md` 생성
- [ ] 커스텀 도구 등록
- [ ] 테스트 실행

---

## 7️⃣ 커스텀 도구 등록 (하이브리드 에이전트용)

> 💡 **하이브리드 에이전트**는 LLM 추론과 Python 스크립트 실행을 결합합니다.

### 커스텀 도구 정의

```python
# custom_tools.py
from agent_system import Tool, ToolResult, ToolRegistry

class ProcParserTool(Tool):
    """Pro*C 파싱 전용 도구"""
    
    name = "ProcParser"
    description = "Pro*C 파일을 파싱하여 함수/변수/SQL 정보를 JSON으로 반환"
    
    def execute(self, file_path: str, **kwargs) -> ToolResult:
        # 실제 파싱 모듈 사용
        from proc_parser import parse_file
        
        try:
            result = parse_file(file_path)
            return ToolResult(
                success=True,
                output=json.dumps(result, ensure_ascii=False, indent=2)
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class SQLExtractorTool(Tool):
    """SQL 추출 전용 도구"""
    
    name = "SQLExtractor"
    description = "Pro*C 파일에서 EXEC SQL 구문을 추출하여 JSON으로 반환"
    
    def execute(self, file_path: str, **kwargs) -> ToolResult:
        from proc_parser.sql_extractor import extract_sql
        
        try:
            result = extract_sql(file_path)
            return ToolResult(
                success=True,
                output=json.dumps(result, ensure_ascii=False, indent=2)
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class MavenBuildTool(Tool):
    """Maven 빌드 전용 도구"""
    
    name = "MavenBuild"
    description = "Maven 프로젝트 빌드 및 테스트 실행"
    
    def execute(self, project_dir: str, goal: str = "compile", **kwargs) -> ToolResult:
        import subprocess
        
        cmd = f"cd {project_dir} && mvn {goal}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            return ToolResult(success=True, output=result.stdout)
        else:
            return ToolResult(success=False, error=result.stderr)
```

### 도구 레지스트리에 등록

```python
from agent_system import ToolRegistry, Orchestrator
from custom_tools import ProcParserTool, SQLExtractorTool, MavenBuildTool

# 커스텀 도구 등록
registry = ToolRegistry()
registry.register(ProcParserTool())
registry.register(SQLExtractorTool())
registry.register(MavenBuildTool())

# 오케스트레이터에 전달
orchestrator = Orchestrator(tool_registry=registry)
orchestrator.load_agents()
```

### 에이전트에서 사용

| 에이전트 | 커스텀 도구 | 용도 |
|----------|-------------|------|
| parsing-agent | `ProcParser` | Pro*C 파일 파싱 |
| sql-analyst | `SQLExtractor` | SQL 구문 추출 |
| build-debug-agent | `MavenBuild` | Java 빌드 |

---

## 8️⃣ 하이브리드 에이전트 패턴

### 패턴 1: 도구 결과 해석

```
┌─────────────────────────────────────────────────────────┐
│                    Parsing Agent                         │
├─────────────────────────────────────────────────────────┤
│  1. LLM: FLOW.md에서 대상 파일 목록 확인                   │
│  2. Tool: ProcParser 실행 (Python → JSON)               │
│  3. LLM: JSON 결과 해석 및 마크다운으로 정리              │
│  4. Tool: Write로 PARSED.md 저장                         │
└─────────────────────────────────────────────────────────┘
```

### 패턴 2: 조건부 도구 실행

```
┌─────────────────────────────────────────────────────────┐
│                  Build/Debug Agent                       │
├─────────────────────────────────────────────────────────┤
│  1. Tool: MavenBuild(goal="compile")                    │
│  2. LLM: 빌드 결과 분석                                   │
│     - 성공 → "빌드 완료" 보고                             │
│     - 실패 → 오류 분석 후 수정 제안                       │
│  3. Tool: 필요시 MavenBuild 재실행                        │
└─────────────────────────────────────────────────────────┘
```

### 패턴 3: 다중 도구 체이닝

```
┌─────────────────────────────────────────────────────────┐
│                 Context Engineer Agent                   │
├─────────────────────────────────────────────────────────┤
│  1. Tool: Read("PARSED.md")                              │
│  2. Tool: Read("SQL_MAP.md")                             │
│  3. LLM: 두 결과 통합 분석                                │
│  4. LLM: 변환에 필요한 정보만 추출                        │
│  5. Tool: Write("CONTEXT.md")                            │
└─────────────────────────────────────────────────────────┘
```

---

## 💡 Best Practices

### 도구 vs LLM 역할 분담

| 작업 | 도구 (Python) | LLM |
|------|---------------|-----|
| 파일 파싱 | ✅ 정확한 구문 분석 | ❌ |
| JSON 생성 | ✅ 구조화된 데이터 | ❌ |
| 패턴 매칭 | ✅ 정규식 기반 | ❌ |
| 결과 해석 | ❌ | ✅ 의미 분석 |
| 형식 변환 | ❌ | ✅ 마크다운 정리 |
| 오류 분석 | ❌ | ✅ 원인 추론 |
| 코드 생성 | ❌ | ✅ Java 코드 작성 |

### 하이브리드 에이전트 설계 원칙

1. **결정론적 작업 → 도구**: 파싱, 빌드, 파일 I/O
2. **추론 작업 → LLM**: 해석, 분석, 생성
3. **도구 출력은 JSON**: LLM이 해석하기 쉬움
4. **실패 처리는 LLM**: 오류 분석 및 재시도 결정

---

## 9️⃣ 자가개선 체크리스트 시스템

> 💡 반복 발생하는 실패를 자동으로 체크리스트로 변환하여 에이전트 프롬프트에 주입

### 에이전트 레벨 설정

```markdown
<!-- .agents/parsing-agent.md -->
---
name: parsing-agent
self_improve: true    # ⭐ 자가개선 활성화
tools: Read, ProcParser, Write
---
```

### 워크플로우 레벨 오버라이드

```yaml
# workflows/convert-proc.yaml
steps:
  - name: parse_code
    agent: parsing-agent
    self_improve: true       # 활성화

  - name: validate
    agent: critic-agent
    self_improve: false      # 비활성화 (정적 규칙만 사용)
```

### 우선순위

```
워크플로우 설정 > 에이전트 설정 > 기본값(false)
```

### Python에서 훅 통합

```python
from agent_system import (
    SelfImprovingChecklist, HookRegistry, AgentLoader, WorkflowEngine
)
from pathlib import Path

# 초기화
loader = AgentLoader([Path(".agents")])
loader.load_all()

hooks = HookRegistry()
si = SelfImprovingChecklist()

# 훅 등록 (자동 이슈 수집 + 체크리스트 주입)
si.setup_hooks(hooks, loader)

# 워크플로우 엔진에 훅 전달
engine = WorkflowEngine(orchestrator)
engine.hooks = hooks
```

### 자동 생성 체크리스트 예시

```markdown
## ⚠️ 자동 생성 체크리스트 (과거 실패 사례 기반)

> 다음 항목들은 과거 반복 발생한 이슈입니다. 작업 전에 확인하세요.

- [ ] **확인: 매크로 내부의 함수 호출을 놓침** (발생 5회)
      ```
      #define PROCESS(x) do_process(x)
      ```
- [ ] **확인: typedef struct 패턴에서 타입 이름 누락** (발생 3회)
```

### 수동 체크리스트 추가

```python
si.add_manual_check(
    agent="parsing-agent",
    check="EXEC SQL INCLUDE 구문도 #include처럼 처리",
    example="EXEC SQL INCLUDE sqlca;"
)
```

### 자가개선 권장 에이전트

| 에이전트 | self_improve | 이유 |
|----------|-------------|------|
| `parsing-agent` | ✅ true | 다양한 코드 패턴 |
| `sql-analyst` | ✅ true | SQL 패턴 학습 |
| `transformer-agent` | ✅ true | 변환 오류 패턴 |
| `build-debug-agent` | ✅ true | 빌드 오류 패턴 |
| `critic-agent` | ❌ false | 정적 평가 기준 |
| `dependency-analyst` | ❌ false | 결정론적 분석 |

