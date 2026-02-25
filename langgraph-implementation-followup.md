# LangGraph 멀티 에이전트 전환 시스템 구현 팔로업 (실행 레벨)

`claude-langgraph-plan.md`의 상위 설계를 실제 구현으로 옮기기 위한 **작업 단위/함수 단위 실행 계획**이다.

## 0) 구현 범위 재정의 (In/Out)

### In Scope
- `run_multiagent_conversion.py`를 실제 LangGraph 실행 엔트리로 전환
- `analysis/java/mybatis/report` 4개 에이전트 + 그래프 오케스트레이션 구현
- 결과물 파일 생성 및 리포트 생성 자동화
- 최소 단위 테스트 + 통합 스모크 테스트 추가

### Out of Scope (이번 스프린트)
- 병렬 처리 고도화(프로세스 풀/분산 큐)
- 장문 Pro*C 파일에 대한 고급 청킹 최적화
- 리포트 UI/대시보드
- 리트라이 정책, 서킷브레이커 등 운영 기능

---

## 1) 파일별 작업 백로그 (체크리스트)

## 1-1. `infra/agents/langchain/state.py`
- [ ] `ConversionState` TypedDict 추가
- [ ] 필수/선택 필드 구분 (`total=False`)
- [ ] `errors`, `messages` 기본 누적 규약 문서화

**구현 포인트**
- 그래프 노드가 부분 업데이트(dict patch) 방식으로 상태를 반환하도록 설계
- `messages`는 LangGraph message aggregator(`add_messages`)와 호환

---

## 1-2. `agents/analysis_agent.py`
- [ ] `run_analysis(state: ConversionState) -> dict` 구현
- [ ] 헤더 파싱 + Pro*C 파싱 + SQL 추출 통합
- [ ] 파일별 메타데이터(LOC/함수수/SQL수) 집계
- [ ] extern 심볼 목록 산출

**권장 함수 시그니처**
```python
def run_analysis(state: ConversionState) -> dict:
    ...

def _parse_headers(header_paths: list[str]) -> dict:
    ...

def _parse_proc_file(proc_path: str, type_map: dict) -> dict:
    ...
```

**반환 예시**
```python
{
  "analysis_result": {
    "type_map": {...},
    "files": [
      {
        "path": "...",
        "loc": 123,
        "functions": [...],
        "sql_blocks": [...],
      }
    ],
    "sql_blocks": [...],
    "extern_list": [...],
    "stats": {"file_count": 1, "total_loc": 123, "sql_count": 5}
  }
}
```

**에러 규약**
- 파일 단위 실패는 `errors` 누적 후 다음 파일 계속 처리
- 전체 실패만 예외 재상승(그래프 중단 사유 명확화)

---

## 1-3. `agents/mybatis_agent.py`
- [ ] `run_mybatis_generation(state: ConversionState) -> dict` 구현
- [ ] SQL block 기반 DTO/DAO/XML 생성 루프 구현
- [ ] 산출 파일 경로 목록 수집

**권장 함수 시그니처**
```python
def run_mybatis_generation(state: ConversionState) -> dict:
    ...

def _ensure_output_dirs(output_dir: str) -> dict[str, str]:
    ...
```

**검증 포인트**
- sql block이 0개일 때도 정상 종료(빈 결과 반환)
- 파일 생성 실패 시 해당 block만 skip + error 기록

---

## 1-4. `agents/java_spring_agent.py`
- [ ] `run_java_conversion(state: ConversionState) -> dict` 구현
- [ ] strategy별 plugin 조합 분기
- [ ] LLM 미설정 환경 graceful degradation 처리

**전략 매핑**
- `preserve`: `SpringAnnotationPlugin`
- `refactor`: `SpringAnnotationPlugin + NamingConventionPlugin`

**운영 안전장치**
- `OPENAI_API_KEY` 없으면:
  - 옵션 A) 명시 에러 반환 + 나머지 노드 진행
  - 옵션 B) 템플릿 기반 스텁 Java 파일 생성

---

## 1-5. `agents/report_agent.py`
- [ ] `run_report(state: ConversionState) -> dict` 구현
- [ ] markdown 리포트 템플릿 작성
- [ ] 통계/매핑/체크리스트/오류 섹션 포함

**리포트 최소 섹션**
1. Summary
2. Input Files
3. Generated Artifacts
4. Pro*C → Java Mapping
5. Extern Stub TODO
6. Errors & Warnings

---

## 1-6. `infra/agents/langchain/orchestration/conversion_graph.py`
- [ ] StateGraph 정의
- [ ] `analysis -> conversion -> report -> END` 연결
- [ ] `parallel_conversion_node` 내 병렬 실행 구현

**노드 책임 분리**
- `analysis_node`: 분석 결과 생성
- `parallel_conversion_node`: java/mybatis 병렬 생성 후 merge
- `report_node`: 최종 결과 문서화

**병렬 노드 머지 규약**
- 충돌 키 금지(`java_result`, `mybatis_result` 분리)
- 에러는 리스트 concatenate

---

## 1-7. `run_multiagent_conversion.py`
- [ ] CLI 인자 → `ConversionState` 초기 입력 변환
- [ ] `build_conversion_graph().invoke(initial_state)` 호출
- [ ] 종료 코드 규칙 정의

**종료 코드 제안**
- `0`: 산출물 정상 생성(에러 0)
- `2`: 산출물 생성됐으나 warning/error 존재
- `1`: 그래프 실행 자체 실패

---

## 2) 구현 순서 (D+N 기준)

### Day 1
1. `state.py` + `analysis_agent.py`
2. 분석 결과 JSON dump로 단독 검증

### Day 2
1. `mybatis_agent.py` 구현
2. fixture 대상으로 산출물 생성 확인

### Day 3
1. `java_spring_agent.py` 구현
2. API key 유무 2가지 경로 검증

### Day 4
1. `report_agent.py`
2. `conversion_graph.py` 연결 + 병렬 실행

### Day 5
1. `run_multiagent_conversion.py` 교체
2. 테스트/문서/예제 커맨드 정리

---

## 3) 테스트 전략 (필수)

## 3-1. 단위 테스트
- [ ] analysis: 입력 fixture → stats/sql_count 검증
- [ ] mybatis: sql block 1개 입력 → dto/dao/xml 파일 생성 검증
- [ ] report: markdown 주요 헤더 포함 검증

## 3-2. 통합 테스트
- [ ] small fixture 1개로 end-to-end 실행
- [ ] LLM key 없는 환경에서 degrade 경로 검증
- [ ] 오류 포함 fixture에서 `errors` 누적 검증

## 3-3. 회귀 테스트 포인트
- 기존 `migration_graph.py` 관련 테스트 불변 확인
- `run_multiagent_conversion.py` CLI 옵션 호환성 확인

---

## 4) 완료 기준 (Definition of Done)

- [ ] `python run_multiagent_conversion.py ...`로 실제 java/mybatis/report 파일 생성
- [ ] 결과 디렉토리 구조가 계획 문서와 일치
- [ ] 최소 1개 통합 테스트 green
- [ ] README 또는 usage 문서에 실행 예제 갱신
- [ ] 실패/경고 시 로그와 종료 코드가 명확

---

## 5) 리스크 및 즉시 대응

1. **LLM 의존성 리스크**
   - 대응: no-key fallback 경로를 먼저 구현
2. **파서 입력 다양성 리스크**
   - 대응: 파일 단위 예외 격리 + 부분 성공 허용
3. **병렬 병합 충돌 리스크**
   - 대응: 상태 키 네임스페이스 강제(`java_*`, `mybatis_*`)
4. **산출물 네이밍 불일치**
   - 대응: 공통 filename helper 도입

---

## 6) 바로 착수 가능한 첫 커밋 단위

### Commit A
- `state.py`: `ConversionState` 추가
- `agents/analysis_agent.py`: skeleton + 기본 파싱 연결
- 테스트: analysis smoke test

### Commit B
- `agents/mybatis_agent.py` + 출력 경로 생성 유틸
- 테스트: mybatis artifact 생성 테스트

### Commit C
- `agents/java_spring_agent.py` + fallback 처리
- 테스트: key 없음 케이스

### Commit D
- `report_agent.py` + `conversion_graph.py` + CLI 교체
- 통합 테스트 + 문서 업데이트

---

## 7) 실행 커맨드 템플릿

```bash
python run_multiagent_conversion.py \
  --headers tests/fixtures/sample_input_data/sample.h \
  --procs tests/fixtures/sample_input_data/cursor_sample.pc \
  --output output/langgraph_demo \
  --strategy preserve
```

검증:
```bash
test -f output/langgraph_demo/report/migration-report.md
test -d output/langgraph_demo/mybatis/mapper
test -d output/langgraph_demo/java/service
```

---

이 문서는 설계 설명서가 아니라 **구현용 체크리스트**이므로,
작업 진행 시 각 항목을 PR 단위로 바로 닫는 방식으로 운영한다.
