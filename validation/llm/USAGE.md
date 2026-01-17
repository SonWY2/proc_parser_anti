# llm_verifier 모듈 사용 가이드

Pro*C 파싱 결과의 정확성을 LLM을 활용하여 검증하는 모듈입니다.

## 설치 요구사항

```bash
pip install requests python-dotenv pyyaml loguru
```

## 환경 설정

프로젝트 루트에 `.env` 파일을 생성하고 OpenAI API를 설정합니다:

```bash
# OpenAI API 설정
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=o1-mini

# 또는 다른 OpenAI 호환 서버 사용 시
# VLLM_API_ENDPOINT=http://your-llm-server:8000/v1
```

### 지원 모델

| 모델 | 특징 |
|------|------|
| `o1-mini` | 빠른 추론, 비용 효율적 (기본값) |
| `o1-preview` | 더 정확한 추론 |
| `gpt-4o` | 범용 모델 |
| `gpt-4o-mini` | 빠른 범용 모델 |

## 기본 사용법

### 단일 검증

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

# 에러가 있는 경우
if result.has_errors():
    for err in result.get_errors():
        print(f"Error: {err.message}")
```

### 배치 검증

```python
items = [
    {"source": source1, "result": result1},
    {"source": source2, "result": result2},
]

results = verifier.verify_batch(
    stage="sql_extraction",
    items=items
)
```

## 검증 단계 (Stages)

| Stage | 설명 |
|-------|------|
| `sql_extraction` | Pro*C → SQL 추출 검증 |
| `function_parsing` | Pro*C → 함수 파싱 검증 |
| `header_parsing` | .h → 구조체 파싱 검증 |
| `translation_merge` | Java 코드 병합 검증 |

## 플러그인 시스템

### 플러그인 구조

```
PRE_VERIFY ──→ VERIFY ──→ POST_VERIFY
    │             │            │
    ├─ static_precheck    │    └─ report_generator
    └─ sampler            │
                          └─ sql_extraction_verify
                          └─ (다른 검증 플러그인들)
```

### 커스텀 플러그인 작성

```python
from llm_verifier.plugins import VerifierPlugin, PluginPhase, register_plugin

@register_plugin
class MyCustomPlugin(VerifierPlugin):
    name = "my_custom"
    stage = "sql_extraction"  # 또는 "all"
    phase = PluginPhase.VERIFY
    priority = 50
    description = "나만의 검증 로직"
    
    def process(self, context):
        # 검증 로직
        return context
```

### 플러그인 선택 실행

```python
# 특정 플러그인만 활성화
verifier = LLMVerifier(enabled_plugins=["static_precheck", "report_generator"])
```

## 체크리스트

### YAML 체크리스트 구조

```yaml
name: SQL Extraction Verification

static_checks:
  - id: count_match
    description: SQL 수량 일치
    severity: error

llm_checks:
  - id: all_exec_sql_found
    question: "모든 EXEC SQL이 추출되었나요?"
    severity: error
```

### 커스텀 체크리스트 사용

```python
result = verifier.verify(
    stage="sql_extraction",
    source=source,
    result=result,
    checklist_path="my_checklist.yaml"
)
```

## 리포트 출력

```python
# Markdown 리포트
print(result.report_markdown)

# JSON 리포트
import json
print(json.dumps(result.report_json, indent=2, ensure_ascii=False))
```

## LLM 없이 정적 체크만 실행

LLM API가 설정되지 않아도 정적 체크는 실행됩니다:

```python
verifier = LLMVerifier()
result = verifier.verify(
    stage="sql_extraction",
    source=source,
    result=result
)

# 정적 체크 결과만 확인
for check in result.static_checks:
    print(f"{check.name}: {check.status.value}")
```
