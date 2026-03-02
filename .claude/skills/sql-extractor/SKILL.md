---
name: sql-extractor
description: |
  Pro*C 코드에서 EXEC SQL 블록을 추출하고 표준 SQL 형태로 정제.
  
  **When to use**: analysis-agent가 Pro*C 청크를 처리할 때 각 청크마다 호출.

inputs:
  - name: proc_chunk
    type: string
    required: true
    description: Pro*C 코드 조각
  
  - name: source_file
    type: string
    required: true
    description: 원본 파일명
  
  - name: function_name
    type: string
    required: false
    description: 함수명 (컨텍스트 제공용)

outputs:
  - name: sql_blocks
    type: json
    required: true
    description: 추출된 SQL 블록 배열
---

# SQL Extractor Skill

Pro*C에서 EXEC SQL 블록을 추출하고 표준 SQL로 정제합니다.

---

## 📋 What it does

1. **`EXEC SQL ... ;` 패턴 추출**
2. **커서 선언(`EXEC SQL DECLARE`)** → Open/Fetch/Close 시퀀스를 묶어 하나의 논리 단위로 처리
3. **Pro*C 전용 구문 정제**:
   - `:indicator` 제거
   - `VARCHAR` 제거
   - `SQLCA` 제거
4. **바인드 변수(`:var_name`) 목록 추출**

---

## 🔧 활용 기존 코드

| 모듈 | 파일 경로 | 용도 |
|------|----------|------|
| SQLExtractor | `parsing/sql/extractor.py` | SQL 추출 (Tree-sitter 기반) |
| CursorMerger | `parsing/sql/cursor_merger.py` | 커서 DECLARE/OPEN/FETCH/CLOSE 병합 |
| DynamicSQLExtractor | `parsing/sql/dynamic_sql_extractor.py` | 동적 SQL 탐지 |

---

## 💻 구현 예시

```python
from parsing.sql import SQLExtractor

def sql_extractor(proc_chunk: str, source_file: str, function_name: str = None) -> dict:
    """
    Pro*C 청크에서 SQL 추출 및 정제
    
    Returns:
        {
            "sql_blocks": [
                {
                    "id": "sql_001",
                    "source_file": "customer.pc",
                    "function": "get_customer_info",
                    "sql_type": "SELECT",
                    "raw_sql": "SELECT ID, NAME FROM CUSTOMER WHERE ID = :in_id",
                    "bind_vars": [":in_id"],
                    "output_vars": [":cust_id", ":cust_name"],
                    "is_cursor": false,
                    "is_dynamic": false
                }
            ]
        }
    """
    extractor = SQLExtractor()
    
    # Tree-sitter 기반 SQL 추출
    sql_blocks = extractor._extract_with_tree_sitter(proc_chunk)
    
    result_blocks = []
    for i, block in enumerate(sql_blocks):
        # SQL 타입 결정
        sql_type_result = extractor.sql_type_registry.determine_type(block.text)
        
        # 호스트 변수 추출
        input_vars, output_vars = extractor.host_var_registry.classify_by_direction(
            block.text, sql_type_result.value
        )
        
        result_blocks.append({
            "id": f"sql_{i}",
            "source_file": source_file,
            "function": function_name or block.containing_function,
            "sql_type": sql_type_result.value,
            "raw_sql": block.text.lstrip(),
            "bind_vars": [v.get('raw', '') for v in input_vars],
            "output_vars": [v.get('raw', '') for v in output_vars],
            "is_cursor": sql_type_result.metadata.get('is_cursor', False) if sql_type_result.metadata else False,
            "is_dynamic": False
        })
    
    return {"sql_blocks": result_blocks}
```

---

## 📊 I/O Contract

### Input Example

```json
{
  "proc_chunk": "EXEC SQL SELECT ID, NAME INTO :cust_id, :cust_name FROM CUSTOMER WHERE ID = :in_id;",
  "source_file": "customer.pc",
  "function_name": "get_customer_info"
}
```

### Output Example

```json
{
  "sql_blocks": [
    {
      "id": "sql_001",
      "source_file": "customer.pc",
      "function": "get_customer_info",
      "sql_type": "SELECT",
      "raw_sql": "SELECT ID, NAME FROM CUSTOMER WHERE ID = :in_id",
      "bind_vars": [":in_id"],
      "output_vars": [":cust_id", ":cust_name"],
      "is_cursor": false,
      "is_dynamic": false
    }
  ]
}
```

---

## ⚠️ Edge Cases

### 1. 동적 SQL (문자열 변수로 SQL 조합)

**증상**:
```c
char sql_query[256];
strcpy(sql_query, "SELECT * FROM ");
strcat(sql_query, table_name);
EXEC SQL EXECUTE IMMEDIATE :sql_query;
```

**처리**:
```json
{
  "id": "sql_002",
  "sql_type": "EXECUTE_IMMEDIATE",
  "is_dynamic": true,
  "raw_sql": "/* dynamic SQL - variable: sql_query */",
  "dynamic_var": "sql_query",
  "note": "Manual review required"
}
```

### 2. 커서 루프

**원본**:
```c
EXEC SQL DECLARE emp_cursor CURSOR FOR
    SELECT id, name FROM employees;
EXEC SQL OPEN emp_cursor;
EXEC SQL FETCH emp_cursor INTO :emp_id, :emp_name;
// ... loop ...
EXEC SQL CLOSE emp_cursor;
```

**처리**:
```json
{
  "id": "sql_003",
  "sql_type": "SELECT",
  "is_cursor": true,
  "cursor_name": "emp_cursor",
  "cursor_query": "SELECT id, name FROM employees",
  "fetch_vars": [":emp_id", ":emp_name"],
  "note": "Cursor-based loop - convert to List<T> in Java"
}
```

### 3. EXEC SQL EXECUTE IMMEDIATE

**처리**: `is_dynamic: true` 플래그 설정

---

## ✅ 검증 체크리스트

- [ ] 모든 EXEC SQL 블록이 추출되는가?
- [ ] 바인드 변수가 올바르게 분류되는가 (입력/출력)?
- [ ] 커서가 DECLARE/OPEN/FETCH/CLOSE로 병합되는가?
- [ ] 동적 SQL이 `is_dynamic: true`로 플래그되는가?
- [ ] Pro*C 전용 구문(INTO, INDICATOR)이 제거되는가?
