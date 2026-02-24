# SQL Validator 사용 가이드

Pro*C SQL에서 MyBatis SQL로의 변환 결과가 올바른지 검증하고 관리하는 도구입니다.

## 1. 환경 설정

`.env.example` 파일을 `.env`로 복사하고 vLLM API 엔드포인트를 설정합니다.

```bash
cp .env.example .env
```

```env
VLLM_API_ENDPOINT=http://localhost:8000/v1
```

---

## 2. GUI 도구 사용법

### 실행 방법
```bash
# 모듈로 실행 (권장)
python -m sql_validator

# 또는 직접 실행
python sql_validator/gui.py
```

### 주요 기능
- **YAML 로드**: 변환 데이터가 담긴 YAML 파일을 불러옵니다.
- **A/B 비교**: 원본 SQL과 변환된 SQL의 차이점을 시각적으로 확인합니다.
- **정적 분석**: 기본적인 변환 규칙(SELECT/INSERT 등) 준수 여부를 자동 확인합니다.
- **AI 피드백**: LLM을 통해 논리적 결함이나 개선 사항을 제안받습니다.
- **검증 마킹**: 각 항목에 대해 ✅ 승인(Approved) 또는 ❌ 거절(Rejected) 표시를 합니다.
- **세션 관리**: 작업 중인 상태를 저장하고 나중에 다시 불러올 수 있습니다.

### 키보드 단축키
| 단축키 | 기능 |
|--------|------|
| `←` / `→` | 이전/다음 항목으로 이동 |
| `A` | 현재 항목 승인 (Approved) |
| `R` | 현재 항목 거절 (Rejected) |
| `Ctrl+O` | YAML 파일 열기 |
| `Ctrl+S` | 현재 세션 저장 |
| `Ctrl+E` | 승인된 항목만 내보내기 |

---

## 3. 프로그래밍 API 사용법

### 기본 분석 및 로드
```python
from sql_validator import load_yaml, StaticAnalyzer

# YAML 파일 로드
items = load_yaml("data.yaml")

# 정적 분석기 실행
analyzer = StaticAnalyzer()
for item in items:
    result = analyzer.analyze(item['sql'], item['parsed_sql'])
    if not result.is_valid:
        print(f"Validation failed: {result.errors}")
```

### 세션 및 내보내기
```python
from sql_validator import SessionData, save_session, export_approved

# 세션 데이터 생성 및 저장
session = SessionData(
    yaml_path="data.yaml",
    current_index=10,
    validation_statuses={0: 'approved', 1: 'rejected'}
)
save_session(session, "work_session.json")

# 승인된 항목만 별도 YAML로 저장
statuses = {0: 'approved', 1: 'rejected'}
export_approved(items, statuses, "approved_output.yaml")
```

### 일괄 처리 (Batch Processing)
```python
from sql_validator import process_batch, generate_markdown_report

# 여러 파일을 한 번에 분석
results = process_batch(["file1.yaml", "file2.yaml"])

# 리포트 생성
report = generate_markdown_report(results)
with open("report.md", "w", encoding="utf-8") as f:
    f.write(report)
```

---

## 4. 데이터 형식 (YAML)

입력으로 사용되는 YAML 파일은 다음과 같은 구조를 가져야 합니다.

```yaml
- sql: |
    EXEC SQL SELECT name INTO :name FROM users WHERE id = :id;
  parsed_sql: |
    SELECT name FROM users WHERE id = #{id}
- sql: |
    EXEC SQL INSERT INTO logs (msg) VALUES (:msg);
  parsed_sql: |
    INSERT INTO logs (msg) VALUES (#{msg})
```

---

## 5. 색상 가이드 (Diff View)

| 색상 | 의미 |
|------|------|
| 🟡 노란색 (Yellow) | 수정됨 (Changed) |
| 🔴 빨간색 (Red) | 삭제됨 (Removed) |
| 🟢 초록색 (Green) | 추가됨 (Added) |
