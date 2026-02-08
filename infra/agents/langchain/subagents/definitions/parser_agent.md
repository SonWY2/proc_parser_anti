---
name: parser_agent
persona: 분해자 (Decomposer)
description: Pro*C 소스를 해체하여 정형 데이터로 변환
skills:
  - parse_proc_code
uses_llm: false
input_fields:
  - source_code
output_fields:
  - ast_data
---

# Parser Agent

Pro*C 파일을 읽어 헤더, 변수, SQL 블록으로 분해합니다.

## 역할
- `.pc` 파일을 읽어 구조화된 AST로 변환
- 호스트 변수, SQL 블록, 함수 정보 추출
- 매크로 및 구조체 정보 수집

## 처리 흐름
1. 소스 코드 입력 (`source_code` 필드)
2. ProCParser를 통한 파싱
3. 결과를 `ast_data` 필드에 저장

## 출력 형식
`ast_data` 필드에 다음 구조의 딕셔너리 저장:
```json
{
  "headers": [{"name": "sqlca.h", "is_system": true}],
  "host_vars": [{"name": "order_id", "dtype": "int"}],
  "sql_blocks": [{"id": "select_0", "content": "SELECT...", "sql_type": "select"}],
  "functions": [{"name": "process_order", "return_type": "int"}]
}
```

## 완료 조건
- 모든 SQL 블록이 추출됨
- 호스트 변수가 식별됨
- 함수 경계가 정확히 파악됨
