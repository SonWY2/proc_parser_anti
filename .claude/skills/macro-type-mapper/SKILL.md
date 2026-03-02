---
name: macro-type-mapper
description: |
  C 헤더 파일의 typedef, #define, struct를 파싱하여 Java 타입 매핑 테이블 생성.
  
  **When to use**: analysis-agent가 헤더 파일 분석 시 최초 1회 호출.

inputs:
  - name: header_paths
    type: list[string]
    required: true
    description: 헤더 파일 경로 리스트

outputs:
  - name: type_map
    type: json
    required: true
    description: C 타입 → Java 타입 매핑 테이블
---

# Macro Type Mapper Skill

C 헤더에서 typedef/macro/struct를 추출하여 Java 타입으로 매핑합니다.

---

## 📋 What it does

1. **`typedef` → Java 동등 타입 매핑**
   - `typedef char CHAR_100[100]` → `String`
   - `typedef int INT_T` → `int`

2. **`#define` 상수 → Java static final 또는 enum 후보 목록**
   - `#define MAX_RETRY 3` → `static final int MAX_RETRY = 3`

3. **`struct` → Java DTO 클래스 스캐폴딩 정보**
   - `struct CUSTOMER { ... }` → `CustomerDto.java`

---

## 🔧 활용 기존 코드

| 모듈 | 파일 경로 | 용도 |
|------|----------|------|
| IntegratedHeaderParser | `parsing/header/integrated_parser.py` | 헤더 파일 통합 분석 |
| MacroExtractor | `parsing/header/macro_extractor.py` | 매크로 추출 |
| type_mappings | `infra/config/type_mappings.py` | C → Java 타입 매핑 테이블 |

---

## 💻 구현 예시

```python
from parsing.header import IntegratedHeaderParser
from infra.config.type_mappings import C_TO_JAVA_TYPE_MAP

def macro_type_mapper(header_paths: list) -> dict:
    """
    C 헤더에서 typedef/struct/macro 추출 후 Java 타입으로 매핑
    
    Returns:
        {
            "type_map": {
                "CHAR_100": "String",
                "CUSTOMER": "CustomerDto"
            },
            "constants": [
                {
                    "c_name": "MAX_RETRY",
                    "value": "3",
                    "java_candidate": "static final int MAX_RETRY = 3"
                }
            ],
            "struct_candidates": [
                {
                    "c_struct": "CUSTOMER",
                    "fields": ["char id[10]", "char name[100]"],
                    "java_class": "CustomerDto"
                }
            ]
        }
    """
    parser = IntegratedHeaderParser()
    result = parser.parse_headers(header_paths)
    
    # 매크로 → Java 상수 변환
    constants = []
    for macro_name, macro_value in result.macros.items():
        java_type = infer_java_type(macro_value)
        constants.append({
            "c_name": macro_name,
            "value": str(macro_value),
            "java_candidate": f"static final {java_type} {macro_name} = {macro_value}"
        })
    
    # typedef → Java 타입 매핑
    type_map = {}
    for c_type, java_type in C_TO_JAVA_TYPE_MAP.items():
        type_map[c_type] = java_type
    
    # struct → DTO 후보 생성
    struct_candidates = []
    for struct_name, struct_info in result.db_vars_info.items():
        struct_candidates.append({
            "c_struct": struct_name,
            "fields": struct_info.get('fields', []),
            "java_class": f"{struct_name}Dto"
        })
    
    return {
        "type_map": type_map,
        "constants": constants,
        "struct_candidates": struct_candidates
    }
```

---

## 📊 I/O Contract

### Input Example

```json
{
  "header_paths": [
    "include/types.h",
    "include/customer.h"
  ]
}
```

### Output Example

```json
{
  "type_map": {
    "CHAR_100": "String",
    "INT_T": "int",
    "CUSTOMER": "CustomerDto"
  },
  "constants": [
    {
      "c_name": "MAX_RETRY",
      "value": "3",
      "java_candidate": "static final int MAX_RETRY = 3"
    },
    {
      "c_name": "SUCCESS",
      "value": "0",
      "java_candidate": "static final int SUCCESS = 0"
    }
  ],
  "struct_candidates": [
    {
      "c_struct": "CUSTOMER",
      "fields": [
        "char id[10]",
        "char name[100]",
        "int status"
      ],
      "java_class": "CustomerDto"
    }
  ]
}
```

---

## ⚠️ Edge Cases

### 1. 매핑 규칙 불명확한 타입

**증상**: 복잡한 포인터 또는 함수 포인터 타입
**처리**:
```json
{
  "c_type": "void (*callback)(int, char*)",
  "java_type": "Object /* 검토 필요 */",
  "requires_review": true
}
```

### 2. 중첩 struct

**증상**: struct 내부에 또 다른 struct 포함
**처리**: 재귀적으로 처리, 깊이 3 초과 시 플래그 설정
```json
{
  "c_struct": "ORDER",
  "nested_depth": 3,
  "nested_structs": ["CUSTOMER", "PRODUCT"],
  "requires_review": true
}
```

### 3. 조건부 컴파일 매크로

**증상**: `#ifdef`, `#ifndef`로 감싸진 타입 정의
**처리**: 모든 조건부 분기를 수집하고 플래그 설정
```json
{
  "c_type": "DB_HANDLE",
  "conditional": true,
  "conditions": ["DB2", "ORACLE"],
  "note": "Conditional compilation detected"
}
```

---

## ✅ 검증 체크리스트

- [ ] 모든 typedef가 type_map에 포함되는가?
- [ ] #define 상수가 Java static final로 변환되는가?
- [ ] struct 필드가 올바르게 추출되는가?
- [ ] 중첩 struct가 재귀적으로 처리되는가?
- [ ] 불명확한 타입이 "검토 필요" 플래그와 함께 반환되는가?
