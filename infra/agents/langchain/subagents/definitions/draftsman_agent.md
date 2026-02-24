---
name: draftsman_agent
persona: 초안 작성자 (Draftsman)
description: SQL을 기계적으로 MyBatis XML로 1차 변환
skills:
  - convert_sql_draft
uses_llm: false
input_fields:
  - ast_data
output_fields:
  - draft_xmls
---

# Draftsman Agent

추출된 SQL을 MyBatis XML 포맷으로 1차 변환합니다.

## 역할
- Pro*C SQL을 MyBatis XML 형식으로 기계적 변환
- 호스트 변수 `:var` → `#{var}` 변환
- 변환 신뢰도 평가 (high/medium/low)

## 변환 규칙

### 호스트 변수 변환
```
:order_id  →  #{orderId}
:customer_name  →  #{customerName}
```

### SQL 타입별 태그
- SELECT → `<select>`
- INSERT → `<insert>`
- UPDATE → `<update>`
- DELETE → `<delete>`

### SELECT INTO 처리
```sql
-- Before
SELECT name, age INTO :v_name, :v_age FROM users

-- After (INTO 절 제거)
SELECT name, age FROM users
```

## 출력 형식
`draft_xmls` 필드에 초안 리스트 저장:
```json
[
  {
    "id": "select_0",
    "xml": "<select id=\"select_0\">...</select>",
    "confidence": "high",
    "original_sql": "SELECT..."
  }
]
```

## 신뢰도 기준
- **high**: 단순 CRUD
- **medium**: 커서 관련, 서브쿼리 포함
- **low**: DECODE, NVL, CONNECT BY 등 복잡한 구조
