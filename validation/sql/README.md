# SQL Validator

Pro*C SQL에서 MyBatis SQL로의 변환을 검증하는 GUI 도구입니다.

## 개요

`sql_validator`는 Pro*C 애플리케이션을 MyBatis로 마이그레이션할 때, SQL 변환이 올바르게 수행되었는지 검증하는 도구입니다. YAML 파일에서 원본(sql)과 변환된(parsed_sql) SQL을 로드하여 시각적으로 비교하고, 정적 분석 및 LLM 기반 피드백을 제공합니다.

## 주요 기능

- **A/B Side-by-Side Diff 뷰**: 원본과 변환된 SQL을 나란히 비교하며 변경점을 하이라이트
- **정적 분석**: 규칙 기반으로 변환 품질을 자동 검증
- **LLM 피드백**: vLLM API를 통한 AI 기반 상세 분석
- **승인/거부 마킹**: 각 SQL 항목을 ✅ 승인 / ❌ 거부로 마킹
- **내보내기**: 승인된 항목을 YAML로 저장 (테스트 데이터로 재활용)
- **세션 저장**: 작업 상태를 저장하고 나중에 이어서 작업
- **대시보드**: 전체 검증 현황 및 통계 표시
- **일괄 처리**: 여러 YAML 파일 일괄 검증 및 리포트 생성
- **키보드 단축키**: 빠른 작업을 위한 단축키 지원

## 모듈 구조

```
sql_validator/
├── __init__.py           # 패키지 초기화 및 공개 API
├── __main__.py           # CLI 진입점
├── gui.py                # Tkinter GUI 애플리케이션
├── yaml_loader.py        # YAML 파일 로더
├── static_analyzer.py    # 정적 분석 검증기
├── diff_highlighter.py   # Diff 시각화 모듈
├── llm_client.py         # vLLM API 클라이언트
├── prompt.py             # LLM 프롬프트 관리
├── exporter.py           # 검증 결과 내보내기
├── session.py            # 세션 저장/복원
├── host_var_mapper.py    # 호스트 변수 매핑 분석
├── batch_processor.py    # 일괄 처리 및 리포트 생성
├── .env.example          # 환경 변수 예시
└── samples/
    └── sample.yaml       # 샘플 YAML 파일
```

## 설치

### 의존성

```bash
pip install pyyaml python-dotenv requests loguru
```

### 환경 설정

`.env.example`을 복사하여 `.env` 파일을 생성합니다:

```bash
cp .env.example .env
```

`.env` 파일을 편집하여 vLLM API 엔드포인트를 설정합니다:

```env
VLLM_API_ENDPOINT=http://localhost:8000/v1
```

## 사용법

### GUI 실행

```bash
# 모듈로 실행
python -m sql_validator

# 또는 직접 실행
python sql_validator/gui.py
```

### 키보드 단축키

| 단축키 | 기능 |
|--------|------|
| `←` / `→` | 이전/다음 항목 |
| `A` | 현재 항목 승인 |
| `R` | 현재 항목 거부 |
| `Ctrl+O` | YAML 열기 |
| `Ctrl+S` | 세션 저장 |
| `Ctrl+E` | 승인 내보내기 |

### 프로그래밍 API 사용

```python
from sql_validator import (
    load_yaml, StaticAnalyzer, DiffHighlighter, LLMClient,
    export_approved, SessionData, save_session, load_session,
    extract_variable_mapping, process_batch, generate_markdown_report
)

# YAML 로드
items = load_yaml("path/to/sql_data.yaml")

# 정적 분석
analyzer = StaticAnalyzer()
result = analyzer.analyze(items[0]['sql'], items[0]['parsed_sql'])
print(f"통과: {result.pass_count}, 실패: {result.fail_count}")

# 승인된 항목 내보내기
statuses = {0: 'approved', 1: 'rejected', 2: 'approved'}
export_approved(items, statuses, "approved_data.yaml")

# 세션 저장
session = SessionData(
    yaml_path="data.yaml",
    current_index=5,
    validation_statuses={0: 'approved'},
    comments={0: "확인 완료"}
)
save_session(session, "my_session.json")

# 일괄 처리
result = process_batch(["file1.yaml", "file2.yaml"])
print(generate_markdown_report(result))
```

## YAML 파일 형식

입력 YAML 파일은 다음 형식을 따라야 합니다:

```yaml
- sql: |
    EXEC SQL SELECT emp_id, emp_name
    INTO :emp_id, :emp_name
    FROM employees
    WHERE dept_id = :dept_id;
  parsed_sql: |
    SELECT emp_id, emp_name
    FROM employees
    WHERE dept_id = #{deptId}

- sql: |
    EXEC SQL INSERT INTO orders
    (order_id, customer_id)
    VALUES (:order_id, :customer_id);
  parsed_sql: |
    INSERT INTO orders
    (order_id, customer_id)
    VALUES (#{orderId}, #{customerId})
```

## 새로 추가된 기능

### 승인/거부 및 내보내기

```python
from sql_validator import export_approved, export_rejected

# 승인된 항목만 저장 (테스트 데이터용)
export_approved(items, statuses, "test_data.yaml")

# 거부된 항목 저장 (추가 검토용)
export_rejected(items, statuses, "review_needed.yaml")
```

### 세션 관리

```python
from sql_validator import SessionData, save_session, load_session

# 세션 저장
session = SessionData(
    yaml_path="data.yaml",
    current_index=10,
    validation_statuses={0: 'approved', 1: 'rejected'},
    comments={0: "LGTM"}
)
save_session(session, "session.json")

# 세션 복원
session = load_session("session.json")
```

### 호스트 변수 매핑

```python
from sql_validator import extract_variable_mapping

asis = "SELECT * FROM users WHERE id = :user_id AND status = :status"
tobe = "SELECT * FROM users WHERE id = #{userId} AND status = #{status}"

mappings = extract_variable_mapping(asis, tobe)
# [(':user_id', '#{userId}'), (':status', '#{status}')]
```

### 일괄 처리

```python
from sql_validator import process_batch, generate_markdown_report, generate_html_report

result = process_batch(["file1.yaml", "file2.yaml", "file3.yaml"])

# Markdown 리포트
md_report = generate_markdown_report(result)

# HTML 리포트
html_report = generate_html_report(result)
```

## GUI 사용 가이드

### 메인 화면

1. **YAML 열기**: 파일 대화상자에서 YAML 파일 선택
2. **세션 저장/로드**: 작업 상태 저장 및 복원
3. **네비게이션**: 이전/다음 버튼 또는 ← → 키로 이동
4. **승인/거부**: ✅ 승인 / ❌ 거부 버튼 또는 A / R 키
5. **코멘트**: 각 항목에 메모 작성
6. **내보내기**: 승인/거부된 항목 YAML로 저장

### 분석 탭

- **정적 분석**: 규칙 기반 검증 결과
- **LLM 피드백**: AI 분석 결과
- **대시보드**: 전체 현황 및 통계

### 색상 코드

| 색상 | 의미 |
|------|------|
| 🟡 노란색 | 변경된 부분 (REPLACE) |
| 🔴 빨간색 | 삭제된 부분 (DELETE) |
| 🟢 초록색 | 추가된 부분 (INSERT) |

## 라이선스

이 프로젝트는 proc_parser 프로젝트의 일부입니다.
