# SQL Extractor 사용 가이드

Pro*C/SQLC 코드에서 SQL을 추출하고 MyBatis 형식으로 변환하는 모듈입니다.

## 기본 사용법

### 1. SQL 추출 및 MyBatis 변환

```python
from sql_extractor import SQLExtractor

extractor = SQLExtractor()

# Pro*C 코드
code = """
void process_data() {
    EXEC SQL SELECT name, age INTO :out_name, :out_age 
             FROM users WHERE id = :in_id;
    EXEC SQL INSERT INTO logs VALUES (:log_msg);
}
"""

# MyBatis 변환 + 주석 삽입
result_code, mybatis_sqls = extractor.extract_with_mybatis_conversion(
    code=code,
    file_key="program"
)
```

### 2. 커스텀 포맷터 사용

```python
# 입력 변수 포맷 커스터마이징
def my_input_formatter(var_name: str) -> str:
    return f"${{param.{var_name}}}"

# 커스텀 주석 템플릿
result_code, sqls = extractor.extract_with_mybatis_conversion(
    code=code,
    file_key="prog",
    input_formatter=my_input_formatter,
    comment_template="/* @SQL: {sql_id} ({sql_type}) */"
)
```

### 3. 개별 컴포넌트 사용

```python
from sql_extractor import (
    MyBatisConverter,
    SQLIdGenerator,
    SQLCommentMarker,
    CursorMerger,
    DynamicSQLExtractor
)

# ID 생성기
id_gen = SQLIdGenerator()
print(id_gen.generate_id("select"))  # "select_0"
print(id_gen.generate_id("select"))  # "select_1"
print(id_gen.generate_id("insert"))  # "insert_0"

# 주석 마커
marker = SQLCommentMarker(format_template="/* SQL: {sql_id} */")
print(marker.mark("select_0", "select"))  # /* SQL: select_0 */

# MyBatis 변환기
converter = MyBatisConverter()
result = converter.convert_sql(
    sql="EXEC SQL SELECT name INTO :out_name FROM users WHERE id = :in_id",
    sql_type="select",
    sql_id="select_0",
    input_vars=[":in_id"],
    output_vars=[":out_name"]
)
```

---

## 출력 포맷

### 1. 변환된 코드 (주석 삽입)

원본 SQL이 주석으로 대체됩니다:

```c
// 원본
void process_data() {
    EXEC SQL SELECT name INTO :out_name FROM users WHERE id = :in_id;
}

// 변환 후
void process_data() {
    /* sql extracted: select_0 */
}
```

### 2. MyBatisSQL 객체

```python
@dataclass
class MyBatisSQL:
    id: str              # "select_0"
    mybatis_type: str    # "select", "insert", "update", "delete"
    sql: str             # 변환된 SQL (INTO 제거, #{var} 형식)
    original_sql: str    # 원본 Pro*C SQL
    input_params: List[str]   # ["in_id"]
    output_fields: List[str]  # ["out_name"]
```

**예시 출력:**
```python
MyBatisSQL(
    id="select_0",
    mybatis_type="select",
    sql="SELECT name FROM users WHERE id = #{in_id}",
    original_sql="EXEC SQL SELECT name INTO :out_name FROM users WHERE id = :in_id",
    input_params=["in_id"],
    output_fields=["out_name"]
)
```

### 3. YAML 출력 파일 (`sql_calls.yaml`)

`decompose_sql()` 메서드 사용 시 생성:

```yaml
- id: select_0
  name: select_0
  sql: |
    EXEC SQL SELECT name, age INTO :out_name, :out_age 
             FROM users WHERE id = :in_id;
  sql_type: select
  function_name: process_data
  line_start: 3
  line_end: 4
  input_vars:
    - ":in_id"
  output_vars:
    - ":out_name"
    - ":out_age"
```

---

## 기능 요약

| 기능 | 메서드/클래스 | 설명 |
|-----|-------------|------|
| MyBatis 변환 | `extract_with_mybatis_conversion()` | SQL 추출 + 변환 + 주석 삽입 |
| 기본 SQL 추출 | `decompose_sql()` | SQL 추출 + YAML 저장 |
| 커서 병합 | `CursorMerger` | DECLARE/FETCH → 단일 SELECT |
| 동적 SQL | `DynamicSQLExtractor` | strncpy/sprintf 재구성 |
| 포맷터 | `default_input_formatter` | `:var` → `#{var}` |
| 주석 | `SQLCommentMarker` | 커스텀 주석 생성 |
| **컬럼 Alias** | `ColumnAliasMapper` | SELECT 컬럼에 AS alias 추가 |

---

## Column Alias Mapper

SELECT 컬럼에 INTO 절 변수 기반 alias를 추가합니다.

### 지원 구문

| SQL 타입 | 설명 |
|---------|------|
| SELECT ... INTO | 컬럼에 AS alias 추가 |
| DECLARE CURSOR FOR SELECT | 커서 쿼리 컬럼에 alias |
| INSERT/UPDATE/DELETE RETURNING | RETURNING 절 컬럼에 alias |

### 사용법

```python
from sql_extractor import ColumnAliasMapper, snake_to_camel

mapper = ColumnAliasMapper(alias_formatter=snake_to_camel)

result = mapper.add_aliases(
    sql="SELECT emp_name, emp_age FROM users",
    output_vars=[":out_emp_name", ":out_emp_age"]
)
# 결과: SELECT emp_name AS outEmpName, emp_age AS outEmpAge FROM users
```

### MyBatis 변환시 자동 적용

`MyBatisConverter.convert_sql()` 호출 시 자동으로 alias가 추가됩니다:

```python
from sql_extractor import MyBatisConverter

converter = MyBatisConverter()
result = converter.convert_sql(
    sql="EXEC SQL SELECT name, age INTO :out_name, :out_age FROM users WHERE id = :in_id",
    sql_type="select",
    sql_id="select_0",
    input_vars=[":in_id"],
    output_vars=[":out_name", ":out_age"]
)

print(result.sql)
# SELECT name AS outName, age AS outAge FROM users WHERE id = #{inId}
```

---

## CLI 도구 (legacy_input_test.py)

`.pc` 파일을 직접 분석하여 YAML로 저장하는 CLI 도구입니다.

### 사용법

```bash
# 명령행 모드
python legacy_input_test.py --input_file sample.pc --save_as output.yaml

# 단축 옵션
python legacy_input_test.py -i tests/samples/complex_test.pc -o result.yaml

# 대화형 모드 (인자 없이 실행)
python legacy_input_test.py
```

### 출력 파일

| 파일 | 설명 |
|-----|------|
| `{save_as}` | 분석 결과 YAML |
| `{save_as}_commented.txt` | 주석이 삽입된 변환 코드 |

### YAML 출력 예시

```yaml
source_file: sample.pc
total_sql_count: 3
sql_statements:
  - id: select_0
    mybatis_type: select
    converted_sql: |
      SELECT name FROM users WHERE id = #{in_id}
    original_sql: |
      EXEC SQL SELECT name INTO :out_name FROM users WHERE id = :in_id;
    input_params:
      - in_id
    output_fields:
      - out_name
  - id: insert_0
    mybatis_type: insert
    converted_sql: |
      INSERT INTO logs VALUES (#{log_msg})
    original_sql: |
      EXEC SQL INSERT INTO logs VALUES (:log_msg);
    input_params:
      - log_msg
    output_fields: []
```

---

## Transform Plugin System

SQL 변환 플러그인 시스템으로 페이징, DB 방언 변환 등을 지원합니다.

### 기본 사용법

```python
from sql_extractor import (
    TransformPipeline,
    MySQLPaginationPlugin,
    OracleToMySQLPlugin
)

# 파이프라인 생성 및 플러그인 등록
pipeline = TransformPipeline()
pipeline.register(OracleToMySQLPlugin())  # Oracle→MySQL 변환
pipeline.register(MySQLPaginationPlugin())  # 페이징 추가

# SQL 변환
result = pipeline.transform(
    sql="SELECT NVL(name, 'unknown') FROM users",
    sql_type="select",
    metadata={"is_cursor_based": True}
)

print(result.sql)
# SELECT IFNULL(name, 'unknown') FROM users LIMIT #{limit} OFFSET #{offset}
```

### 지원 플러그인

| 플러그인 | 설명 |
|---------|------|
| `MySQLPaginationPlugin` | MySQL LIMIT/OFFSET 추가 |
| `OraclePaginationPlugin` | Oracle ROWNUM 또는 12c OFFSET/FETCH |
| `PostgreSQLPaginationPlugin` | PostgreSQL LIMIT/OFFSET |
| `DB2PaginationPlugin` | DB2 FETCH FIRST / ROW_NUMBER |
| `OracleToMySQLPlugin` | Oracle→MySQL 함수 변환 (NVL→IFNULL 등) |
| `DB2ToMySQLPlugin` | DB2→MySQL 함수 변환 |

### 커스텀 플러그인

```python
from sql_extractor import SQLTransformPlugin

class MyPlugin(SQLTransformPlugin):
    name = "my_plugin"
    priority = 50  # 낮을수록 먼저 실행
    
    def can_transform(self, sql, sql_type, metadata):
        return sql_type == "select"
    
    def transform(self, sql, sql_type, metadata):
        return sql.replace("OLD_TABLE", "NEW_TABLE")

pipeline.register(MyPlugin())
```
