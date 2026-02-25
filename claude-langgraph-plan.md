# Pro*C → Java 멀티에이전트 실제 구현 계획

## 배경

`run_multiagent_conversion.py`는 5단계 파이프라인 구조를 갖추고 있지만
모든 에이전트 호출이 더미 데이터를 반환하는 스켈레톤 상태.

실제 파싱/변환/생성 모듈(`parsing/`, `conversion/`, `generation/`)은 이미 구현되어 있으므로,
이를 연결해 **실제 동작하는 LangGraph 기반 멀티에이전트 시스템**을 구축한다.

---

## 목표 아키텍처

```
run_multiagent_conversion.py
        ↓ (ConversionGraph.invoke)
infra/agents/langchain/orchestration/conversion_graph.py  [NEW]
        ↓ LangGraph StateGraph
    ┌───────────────────────────────────────┐
    │           analysis_node               │
    │  IntegratedHeaderParser + ProCParser  │
    │         + SQLExtractor                │
    └────────────────┬──────────────────────┘
                     ↓
    ┌─────────────────────────────────────────────────┐
    │          parallel_conversion_node               │
    │              [ThreadPoolExecutor]               │
    │   ┌──────────────────┐  ┌──────────────────┐   │
    │   │ java_spring_node │  │  mybatis_node    │   │
    │   │ ProcToJavaConv.  │  │ DAO+OMM+DBIO Gen │   │
    │   │    (LLM 사용)    │  │   (규칙 기반)    │   │
    │   └──────────────────┘  └──────────────────┘   │
    └────────────────┬────────────────────────────────┘
                     ↓
    ┌───────────────────────────────────────┐
    │            report_node                │
    │    migration-report.md 생성           │
    └───────────────────────────────────────┘
                     ↓ END
```

---

## 생성/수정 파일 목록

### 새로 생성 (6개)

| 파일 | 역할 | 재사용 모듈 |
|------|------|------------|
| `agents/__init__.py` | 패키지 초기화 | - |
| `agents/analysis_agent.py` | 헤더+Pro*C 파싱, SQL 추출 | `parsing.header`, `parsing.core`, `parsing.sql` |
| `agents/java_spring_agent.py` | Java Service 클래스 생성 (LLM) | `conversion.core`, `conversion.plugins` |
| `agents/mybatis_agent.py` | MyBatis DTO/DAO/XML 생성 | `generation.artifacts` |
| `agents/report_agent.py` | 마크다운 리포트 생성 | - |
| `infra/agents/langchain/orchestration/conversion_graph.py` | 4-에이전트 LangGraph StateGraph | `langgraph` |

### 수정 (2개)

| 파일 | 변경 내용 |
|------|-----------|
| `infra/agents/langchain/state.py` | `ConversionState` TypedDict 추가 |
| `run_multiagent_conversion.py` | 더미 호출 → `ConversionGraph.invoke()` 교체 |

> **`migration_graph.py` (Parser→Critic→Draftsman→Specialist→Designer)는 유지** — BXM 전용 파이프라인과 분리

---

## ConversionState (LangGraph 상태)

```python
class ConversionState(TypedDict, total=False):
    # 입력
    header_paths: List[str]
    proc_paths:   List[str]
    output_dir:   str
    strategy:     str           # "preserve" | "refactor"
    knowledge_doc: Optional[str]

    # analysis_node 산출물
    analysis_result: Optional[Dict]
    # {type_map, files, sql_blocks, extern_list}

    # parallel_conversion_node 산출물
    java_result:    Optional[Dict]   # {java_files, stub_files}
    mybatis_result: Optional[Dict]   # {dto_files, dao_files, xml_files}

    # report_node 산출물
    report_path: Optional[str]

    # 제어
    errors:   List[str]
    messages: Annotated[List, add_messages]
```

---

## 에이전트별 구현 상세

### analysis_agent.py

```
입력: header_paths, proc_paths, config
흐름:
  1. IntegratedHeaderParser.parse_headers(header_paths) → type_map
  2. 각 proc_path:
     - LOC 계산
     - LOC > 5,000: chunk_by_function() 적용 (existing util)
     - ProCParser.parse_file() → functions
     - SQLExtractor.decompose_sql() → sql_blocks (커서 병합 포함)
  3. extern_list 추출 (미정의 외부 심볼)
출력: {type_map, files, sql_blocks, extern_list}
```

### java_spring_agent.py

```
입력: analysis_result, strategy, output_dir, llm
흐름:
  - preserve: [SpringAnnotationPlugin]
  - refactor: [SpringAnnotationPlugin, NamingConventionPlugin]
  - ProcToJavaConverter(strategy, plugins, llm).convert()
  - output_dir/java/service/{ClassName}Service.java 저장
  - extern → output_dir/java/stub/{ExternClass}Stub.java 저장
출력: {java_files, stub_files}
```

### mybatis_agent.py

```
입력: analysis_result, output_dir
흐름: 각 sql_block별:
  - ArtifactConfig 생성
  - OMMGenerator → dto/{ClassName}Dto.java
  - DAOGenerator  → mapper/{ClassName}Dao.java
  - DBIOGenerator → mapper/{ClassName}Mapper.xml
출력: {dto_files, dao_files, xml_files}
```

### report_agent.py

```
입력: analysis_result, java_result, mybatis_result, strategy, output_dir
내용:
  - 변환 통계 (파일/SQL/LOC 수)
  - Pro*C → Java 파일 매핑 테이블
  - Extern Stub 목록 (수동 구현 필요 항목)
  - 검증 체크리스트
출력: output_dir/report/migration-report.md
```

---

## LangGraph 그래프 구조

```python
def build_conversion_graph() -> CompiledGraph:
    workflow = StateGraph(ConversionState)
    workflow.add_node("analysis",   analysis_node)
    workflow.add_node("conversion", parallel_conversion_node)
    workflow.add_node("report",     report_node)

    workflow.set_entry_point("analysis")
    workflow.add_edge("analysis",   "conversion")
    workflow.add_edge("conversion", "report")
    workflow.add_edge("report",     END)
    return workflow.compile()
```

`parallel_conversion_node` 내부에서 `ThreadPoolExecutor(max_workers=2)`로
`java_spring_node`와 `mybatis_node`를 병렬 실행.

---

## 출력 디렉토리 구조

```
output_dir/
├── java/
│   ├── service/{ClassName}Service.java
│   └── stub/{ExternClass}Stub.java
├── mybatis/
│   ├── dto/{ClassName}Dto.java         (OMM 포맷)
│   └── mapper/
│       ├── {ClassName}Dao.java          (Mapper interface)
│       └── {ClassName}Mapper.xml        (MyBatis XML)
└── report/
    └── migration-report.md
```

---

## 구현 우선순위

| 순서 | 파일 | 이유 |
|------|------|------|
| 1 | `agents/analysis_agent.py` | 모든 에이전트가 이 결과에 의존 |
| 2 | `agents/mybatis_agent.py` | LLM 없이 테스트 가능 |
| 3 | `agents/java_spring_agent.py` | LLM API 키 필요 |
| 4 | `agents/report_agent.py` | 템플릿 기반, 단순 |
| 5 | `state.py` + `conversion_graph.py` | LangGraph 연결 |
| 6 | `run_multiagent_conversion.py` | 진입점 업그레이드 |

---

## 검증 방법

```bash
# 시나리오 1: 소규모 파일 (LOC < 5,000)
python run_multiagent_conversion.py \
  --headers tests/fixtures/sample_input_data/sample.h \
  --procs tests/fixtures/sample_input_data/cursor_sample.pc \
  --output output/test1/ \
  --strategy preserve

# 시나리오 3: Extern 포함
python run_multiagent_conversion.py \
  --headers tests/fixtures/sample_input_data/sample.h \
  --procs original_source.sqc \
  --output output/test3/ \
  --strategy preserve
```

### 검증 체크리스트

- [ ] `output/java/service/` 에 `.java` 파일 존재
- [ ] `output/mybatis/mapper/` 에 `.xml` 파일 존재
- [ ] `output/report/migration-report.md` 존재
- [ ] 리포트에 파일 매핑 테이블 존재
- [ ] Extern 파일에 Stub 생성 확인
- [ ] LOC > 5,000 파일 시 청킹 동작 확인

---

## 주요 고려사항

1. **LLM 연결**: `LLMConfig.from_env()`로 `ChatOpenAI` 초기화. `.env`에 `OPENAI_API_KEY` 필요
2. **에러 처리**: 각 노드는 `try/except` 처리 + `state["errors"]`에 기록. 에러가 있어도 파이프라인 계속 진행
3. **기존 `migration_graph.py` 보존**: 새 `conversion_graph.py`와 독립적으로 유지
4. **청킹**: `infra/agents/langchain/utils/chunking.py`의 `chunk_by_function()` 재사용

---

*작성일: 2026-02-25*


## 후속 문서

- 구현 체크리스트: `langgraph-implementation-followup.md`
