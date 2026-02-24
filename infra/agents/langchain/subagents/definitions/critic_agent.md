---
name: critic_agent
persona: 검증자 (Validator)
description: 분해된 데이터의 무결성 검증
skills:
  - validate_ast
uses_llm: false
input_fields:
  - ast_data
output_fields:
  - validation_errors
---

# Critic Agent

파싱된 AST 데이터의 무결성을 검증합니다.

## 역할
- 필수 헤더 파일 존재 여부 확인
- 미정의 호스트 변수 탐지
- SQL 블록 완전성 검증
- 문제 발생 시 파이프라인 중단 요청

## 검증 항목

### 1. 헤더 검증
- `sqlca.h` 필수 포함 확인
- 누락된 헤더 파일 경고

### 2. 변수 검증
- SQL에서 사용하는 호스트 변수가 선언되었는지 확인
- 타입 불일치 경고

### 3. SQL 검증
- 빈 SQL 블록 탐지
- SQL 타입 미정의 탐지

## 출력 형식
`validation_errors` 필드에 에러 목록 저장:
```json
["필수 헤더 누락: sqlca.h", "빈 SQL 블록: sql_3"]
```

빈 리스트(`[]`)면 검증 통과, 항목이 있으면 파이프라인 중단.

## 중단 조건
- `validation_errors`가 비어있지 않으면 후속 에이전트로 진행하지 않음
- 사용자 개입 필요 (Human-in-the-Loop)
