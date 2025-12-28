# Pro*C → Java 변환을 위한 컨텍스트 메타데이터 관리

Pro*C 코드를 Java로 변환할 때 파싱한 정보를 효율적으로 관리하는 메타데이터 구조입니다.

---

## 📊 메타데이터 설계 원칙

### 핵심 요구사항

1. **헤더 정보 재사용**: 공유 타입/매크로가 여러 .pc에서 참조됨
2. **필요한 정보만 추출**: LLM 컨텍스트 윈도우 절약
3. **관계 추적**: 함수가 어떤 타입/SQL을 사용하는지

---

## 🗂️ 메타데이터 구조

### 1단계: 심볼 테이블 (전역 레지스트리)

```yaml
# metadata/symbol_table.yaml
types:
  ORDER_INFO:
    source: common/types.h
    kind: struct
    fields:
      - name: order_id
        c_type: int
        java_type: Long
      - name: customer_name
        c_type: char[50]
        java_type: String
    java_class: com.example.common.dto.OrderInfo
    used_by: [order.pc, invoice.pc]

  CUSTOMER_INFO:
    source: common/types.h
    kind: struct
    # ...

macros:
  MAX_ORDERS:
    source: common/constants.h
    value: "1000"
    c_type: int
    java_constant: com.example.common.Constants.MAX_ORDERS
    used_by: [order.pc, customer.pc]

  ERROR_DB_CONNECT:
    source: common/error_codes.h
    value: "-100"
    # ...

functions:
  db_connect:
    source: common/db_util.h
    return_type: int
    params: []
    java_method: com.example.common.util.DbUtil.connect()
    used_by: [order.pc, customer.pc, invoice.pc]
```

---

### 2단계: 파일별 메타데이터

```yaml
# metadata/files/order.pc.yaml
file: order.pc
imports:
  - common/types.h      # ORDER_INFO, CUSTOMER_INFO
  - common/db_util.h    # db_connect, db_close
  - common/constants.h  # MAX_ORDERS

functions:
  process_order:
    lines: 45-120
    return_type: int
    params:
      - name: info
        type: ORDER_INFO*
        java_type: OrderInfo
    
    # ⭐ 이 함수가 사용하는 심볼들 (LLM에 전달할 컨텍스트)
    uses:
      types: [ORDER_INFO]
      macros: [MAX_ORDERS]
      globals: [g_db_conn]
      functions: [db_connect, validate_order]
    
    # SQL 정보
    sql_statements:
      - id: select_order_1
        type: SELECT
        original: "SELECT * FROM ORDERS WHERE ORDER_ID = :order_id"
        mybatis: "SELECT * FROM ORDERS WHERE ORDER_ID = #{orderId}"
        host_variables:
          - c_name: order_id
            java_name: orderId
            type: int → Long

    # 변환 힌트
    java_target:
      class: OrderService
      method: processOrder
      package: com.example.order.service

  fetch_orders:
    lines: 125-180
    # ...

globals:
  g_db_conn:
    type: SQLDA*
    line: 10
    java_field: null  # Spring에서는 @Autowired로 대체
```

---

### 3단계: 함수별 컨텍스트 (LLM 전달용)

```yaml
# metadata/context/order.pc/process_order.yaml
# ⭐ LLM에 전달할 "필요한 정보만" 추린 컨텍스트

target:
  function: process_order
  file: order.pc

# 1. 원본 C 코드
source_code: |
  int process_order(ORDER_INFO* info) {
      EXEC SQL SELECT * FROM ORDERS WHERE ORDER_ID = :info->order_id;
      if (sqlca.sqlcode != 0) return ERROR_DB_CONNECT;
      // ...
  }

# 2. 필요한 타입 정의 (헤더에서 추출)
required_types:
  ORDER_INFO:
    c_definition: |
      typedef struct {
          int order_id;
          char customer_name[50];
      } ORDER_INFO;
    java_mapping:
      class: OrderInfo
      package: com.example.common.dto
      fields:
        - c: order_id (int) → java: orderId (Long)
        - c: customer_name (char[50]) → java: customerName (String)

# 3. 필요한 매크로
required_macros:
  ERROR_DB_CONNECT: -100

# 4. SQL 매핑
sql_mapping:
  - original: "SELECT * FROM ORDERS WHERE ORDER_ID = :info->order_id"
    mybatis_id: selectOrderById
    mybatis_sql: "SELECT * FROM ORDERS WHERE ORDER_ID = #{orderId}"

# 5. 변환 규칙 (GLOBAL.md에서 상속)
conversion_rules:
  - "EXEC SQL → MyBatis Mapper 호출"
  - "sqlca.sqlcode 체크 → try-catch 또는 예외 처리"
  - ":변수 → #{변수}"
```

---

## 🔄 메타데이터 생성 파이프라인

```
┌─────────────────────────────────────────────────────────────────┐
│                    메타데이터 생성 흐름                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 종속성 분석                                                  │
│     ├─ .pc/.h 파일 스캔                                         │
│     └─ #include 관계 추출                                        │
│              ↓                                                  │
│  2. 심볼 테이블 구축                                              │
│     ├─ 헤더 파싱 (types, macros, functions)                      │
│     ├─ 공유 심볼 식별 (2개 이상 파일에서 사용)                   │
│     └─ Java 매핑 정보 생성                                       │
│              ↓                                                  │
│  3. 파일별 메타데이터 생성                                        │
│     ├─ 함수별 uses 추적 (어떤 심볼을 참조하는지)                 │
│     ├─ SQL 추출 및 매핑                                          │
│     └─ 변환 대상 식별                                            │
│              ↓                                                  │
│  4. 함수별 컨텍스트 추출 (LLM용)                                  │
│     ├─ 원본 코드                                                 │
│     ├─ 필요한 타입 정의 (심볼 테이블에서 조회)                   │
│     ├─ SQL 매핑 정보                                             │
│     └─ 변환 규칙                                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 💡 핵심 아이디어: **uses 추적**

함수가 사용하는 심볼을 추적하면 **필요한 정보만** LLM에 전달 가능:

```python
def extract_context_for_function(func_name, file_meta, symbol_table):
    """함수 변환에 필요한 컨텍스트만 추출"""
    
    func = file_meta['functions'][func_name]
    context = {
        'source_code': func['code'],
        'sql_mapping': func['sql_statements'],
        'required_types': {},
        'required_macros': {},
    }
    
    # uses에서 필요한 타입만 심볼 테이블에서 조회
    for type_name in func['uses']['types']:
        context['required_types'][type_name] = symbol_table['types'][type_name]
    
    for macro_name in func['uses']['macros']:
        context['required_macros'][macro_name] = symbol_table['macros'][macro_name]
    
    return context
```

---

## 📁 디렉토리 구조

```
metadata/
├── symbol_table.yaml         # 전역 심볼 테이블
├── files/
│   ├── order.pc.yaml         # 파일별 메타데이터
│   ├── customer.pc.yaml
│   └── invoice.pc.yaml
└── context/                  # LLM 전달용 컨텍스트
    ├── order.pc/
    │   ├── process_order.yaml
    │   └── fetch_orders.yaml
    └── customer.pc/
        └── create_customer.yaml
```

---

## ❓ 결정이 필요한 사항

1. **메타데이터 포맷**: YAML vs JSON vs SQLite?
2. **uses 추적 방법**: 정적 분석 (AST) vs 정규식?
3. **컨텍스트 크기 제한**: 함수당 최대 몇 토큰?
