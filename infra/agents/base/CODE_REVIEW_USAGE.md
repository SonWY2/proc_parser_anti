# Code Review Agent System 사용 가이드

LLM 추론만으로 동작하는 코드 분석/리뷰 시스템입니다.

## 📋 에이전트 구성

| 에이전트 | 역할 |
|----------|------|
| `code-review-orchestrator` | 리뷰 조율, 결과 통합 |
| `structure-analyzer` | 구조, 모듈화, 결합도 분석 |
| `bug-detector` | 버그, 에지케이스, 리소스 누수 탐지 |
| `performance-reviewer` | 성능 이슈, N+1 문제 탐지 |
| `security-scanner` | 보안 취약점, SQL 인젝션 탐지 |

## 🚀 사용 방법

### CLI 사용

```bash
cd d:\workspace\proc_parser_antigravity\proc_parser

# 전체 리뷰 (오케스트레이터)
python -m agent_system run code-review-orchestrator "다음 코드를 리뷰해주세요: [코드]"

# 개별 분석
python -m agent_system run bug-detector "버그 탐지: [코드]"
python -m agent_system run security-scanner "보안 점검: [코드]"
python -m agent_system run performance-reviewer "성능 리뷰: [코드]"
python -m agent_system run structure-analyzer "구조 분석: [코드]"
```

### Python API 사용

```python
from agent_system import Orchestrator

# 오케스트레이터 생성
orchestrator = Orchestrator()
orchestrator.load_agents()

# 리뷰할 코드
code = '''
void process_data() {
    EXEC SQL SELECT * FROM users;
    for (int i = 0; i < count; i++) {
        EXEC SQL SELECT * FROM orders WHERE user_id = :user_ids[i];
    }
}
'''

# 전체 리뷰
result = orchestrator.delegate(
    "code-review-orchestrator", 
    f"다음 코드를 종합적으로 리뷰해주세요:\n\n```c\n{code}\n```"
)
print(result.output)

# 또는 개별 분석
bug_result = orchestrator.delegate("bug-detector", f"버그 탐지:\n{code}")
security_result = orchestrator.delegate("security-scanner", f"보안 점검:\n{code}")
```

### 병렬 분석

모든 관점에서 동시에 분석:

```python
tasks = [
    {"agent": "structure-analyzer", "task": f"구조 분석:\n{code}"},
    {"agent": "bug-detector", "task": f"버그 탐지:\n{code}"},
    {"agent": "performance-reviewer", "task": f"성능 리뷰:\n{code}"},
    {"agent": "security-scanner", "task": f"보안 점검:\n{code}"}
]

results = orchestrator.delegate_parallel(tasks)
for r in results:
    print(f"=== {r.agent_name} ===")
    print(r.output)
```

---

## 📊 분석 관점

### 구조 분석 (structure-analyzer)
- 함수 크기 및 단일 책임
- 모듈화 수준
- 의존성/결합도

### 버그 탐지 (bug-detector)  
- 널 체크 누락
- 리소스 누수
- 경계 조건 오류
- Pro*C: SQLCA 미체크

### 성능 리뷰 (performance-reviewer)
- N+1 쿼리 문제
- O(n²) 루프
- 불필요한 SELECT *
- Pro*C: ARRAY FETCH 미사용

### 보안 점검 (security-scanner)
- SQL 인젝션
- 하드코딩된 비밀번호
- 민감 데이터 노출
- Pro*C: 동적 SQL 위험

---

## 📝 출력 예시

```markdown
## 🐛 버그 탐지 결과

### 요약
- Critical: 1개, High: 2개, Medium: 1개

### 🔴 Critical: 리소스 누수

**[BUG-001] 커서 미해제**
- 위치: process_data(), 라인 15
- 문제: 커서를 열었으나 닫지 않음
- 수정: EXEC SQL CLOSE cursor_name 추가

### 🟠 High: 널 체크 누락
...
```

---

## ⚠️ 주의사항

1. **LLM 기반 분석**: 확률적 결과, 오탐 가능
2. **컨텍스트 제한**: 긴 코드는 청크로 분할 권장
3. **보완적 사용**: 정적 분석 도구와 함께 사용 권장
