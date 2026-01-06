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

sql_extractor 패키지는 여러 독립적인 컴포넌트로 구성되어 있어 필요에 따라 개별적으로 사용할 수 있습니다.

---

## 모듈 개요

| 모듈 | 클래스/함수 | 역할 |
|------|------------|------|
| `extractor.py` | `SQLExtractor` | 메인 통합 클래스, 전체 워크플로우 관리 |
| `tree_sitter_extractor.py` | `TreeSitterSQLExtractor` | Tree-sitter로 EXEC SQL 블록 추출 |
| `pyparsing_parser.py` | `PyparsingProCParser` | SQL 타입 결정 및 호스트 변수 분류 |
| `mybatis_converter.py` | `MyBatisConverter` | Pro*C SQL → MyBatis 형식 변환 |
| `sql_id_generator.py` | `SQLIdGenerator` | 고유 SQL ID 생성 |
| `comment_marker.py` | `SQLCommentMarker` | SQL 주석 마커 생성 |
| `cursor_merger.py` | `CursorMerger` | 커서 SQL 병합 |
| `dynamic_sql_extractor.py` | `DynamicSQLExtractor` | strncpy/sprintf 기반 동적 SQL 재구성 |
| `column_alias_mapper.py` | `ColumnAliasMapper` | SELECT 컬럼에 AS alias 추가 |

---

## 1. SQL 블록 추출 (TreeSitterSQLExtractor)

**역할**: Pro*C 코드에서 `EXEC SQL ... ;` 블록을 추출합니다.

```python
from sql_extractor import TreeSitterSQLExtractor

# Tree-sitter 기반 추출기 생성
extractor = TreeSitterSQLExtractor()

code = """
void process_data() {
    EXEC SQL SELECT name, age INTO :out_name, :out_age 
             FROM users WHERE id = :in_id;
    EXEC SQL INSERT INTO logs VALUES (:log_msg);
}
"""

# SQL 블록 추출
sql_blocks = extractor.extract_sql_blocks(code)

for block in sql_blocks:
    print(f"SQL: {block.text}")
    print(f"  라인: {block.start_line}-{block.end_line}")
    print(f"  함수: {block.containing_function}")
```

**출력 결과:**
```
SQL: EXEC SQL SELECT name, age INTO :out_name, :out_age FROM users WHERE id = :in_id;
  라인: 3-4
  함수: process_data
SQL: EXEC SQL INSERT INTO logs VALUES (:log_msg);
  라인: 5-5
  함수: process_data
```

---

## 2. SQL 타입 결정 및 호스트 변수 분류 (PyparsingProCParser)

**역할**: SQL 구문의 타입(SELECT, INSERT 등)을 결정하고, 호스트 변수를 입력/출력으로 분류합니다.

```python
from sql_extractor.pyparsing_parser import get_sql_parser

parser = get_sql_parser()

sql = "EXEC SQL SELECT name, age INTO :out_name, :out_age FROM users WHERE id = :in_id"

# SQL 타입 결정
sql_type = parser.determine_sql_type(sql)
print(f"SQL 타입: {sql_type}")  # "select"

# 호스트 변수 분류
input_vars, output_vars = parser.classify_host_variables(sql, sql_type)
print(f"입력 변수: {input_vars}")   # [':in_id']
print(f"출력 변수: {output_vars}")  # [':out_name', ':out_age']
```

**지원하는 SQL 타입:**
- `select`, `insert`, `update`, `delete`
- `declare_cursor`, `open`, `fetch`, `close`
- `prepare`, `execute`, `connect`, `disconnect`
- `commit`, `rollback`, `savepoint`
- 기타: `include`, `whenever`, `begin_declare_section` 등

---

## 3. MyBatis 형식 변환 (MyBatisConverter)

**역할**: Pro*C SQL을 MyBatis XML에서 사용 가능한 형식으로 변환합니다.
- `EXEC SQL` 접두사 제거
- `INTO :var` 절 제거 (SELECT 문)
- 호스트 변수 `:var` → `#{var}` 변환
- 컬럼 alias 자동 추가

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

print(f"ID: {result.id}")                    # "select_0"
print(f"MyBatis 타입: {result.mybatis_type}")  # "select"
print(f"변환된 SQL: {result.sql}")
# SELECT name AS outName, age AS outAge FROM users WHERE id = #{inId}
print(f"입력 파라미터: {result.input_params}")  # ["inId"]
print(f"출력 필드: {result.output_fields}")     # ["outName", "outAge"]
```

### 커스텀 포맷터 사용

```python
# 입력 변수 포맷 커스터마이징 (예: ${param.변수명})
def my_input_formatter(var_name: str) -> str:
    return f"${{param.{var_name}}}"

converter = MyBatisConverter(input_formatter=my_input_formatter)
result = converter.convert_sql(
    sql="EXEC SQL UPDATE users SET name = :new_name WHERE id = :user_id",
    sql_type="update",
    sql_id="update_0",
    input_vars=[":new_name", ":user_id"]
)
print(result.sql)  # UPDATE users SET name = ${param.new_name} WHERE id = ${param.user_id}
```

---

## 4. SQL ID 생성 (SQLIdGenerator)

**역할**: SQL 타입별로 고유한 ID를 자동 생성합니다.

```python
from sql_extractor import SQLIdGenerator

id_gen = SQLIdGenerator()

print(id_gen.generate_id("select"))  # "select_0"
print(id_gen.generate_id("select"))  # "select_1"
print(id_gen.generate_id("insert"))  # "insert_0"
print(id_gen.generate_id("select"))  # "select_2"

# 카운터 초기화
id_gen.reset()
print(id_gen.generate_id("select"))  # "select_0"
```

---

## 5. 주석 마커 (SQLCommentMarker)

**역할**: 원본 SQL을 식별 가능한 주석으로 대체할 때 사용합니다.

```python
from sql_extractor import SQLCommentMarker

# 기본 템플릿
marker = SQLCommentMarker()
print(marker.mark("select_0", "select"))  
# /* sql extracted: select_0 */

# 커스텀 템플릿
marker = SQLCommentMarker(format_template="/* @SQL: {sql_id} ({sql_type}) */")
print(marker.mark("select_0", "select"))  
# /* @SQL: select_0 (select) */
```

---

## 6. 커서 병합 (CursorMerger)

**역할**: DECLARE CURSOR + OPEN + FETCH + CLOSE 패턴을 단일 SELECT 문으로 병합합니다.

```python
from sql_extractor import CursorMerger

merger = CursorMerger()

# SQL 블록 목록 (decompose_sql 등으로 추출된 결과)
sql_blocks = [
    {"sql_type": "declare_cursor", "sql": "EXEC SQL DECLARE emp_cur CURSOR FOR SELECT name, salary FROM employees WHERE dept = :dept_id"},
    {"sql_type": "open", "sql": "EXEC SQL OPEN emp_cur"},
    {"sql_type": "fetch", "sql": "EXEC SQL FETCH emp_cur INTO :emp_name, :emp_salary"},
    {"sql_type": "close", "sql": "EXEC SQL CLOSE emp_cur"},
]

# 커서 그룹 찾기
groups = merger.find_cursor_groups(sql_blocks)

for group in groups:
    # 병합
    merged = merger.merge(group)
    print(f"커서명: {merged.cursor_name}")
    print(f"병합된 SQL: {merged.merged_sql}")
    print(f"입력 변수: {merged.input_vars}")
    print(f"출력 변수: {merged.output_vars}")
```

**출력 결과:**
```
커서명: emp_cur
병합된 SQL: SELECT name, salary INTO :emp_name, :emp_salary FROM employees WHERE dept = :dept_id
입력 변수: ['dept_id']
출력 변수: ['emp_name', 'emp_salary']
```

---

## 7. 동적 SQL 추출 (DynamicSQLExtractor)

**역할**: strncpy, sprintf 등으로 조합된 동적 SQL을 재구성합니다.

```python
from sql_extractor import DynamicSQLExtractor

extractor = DynamicSQLExtractor()

# C 코드 요소 목록 (CParser 등으로 추출된 결과)
c_elements = [
    {"type": "function_call", "name": "strcpy", "raw_content": 'strcpy(sql_buf, "SELECT * FROM ")', "line_start": 10},
    {"type": "function_call", "name": "strcat", "raw_content": 'strcat(sql_buf, table_name)', "line_start": 11},
    {"type": "function_call", "name": "strcat", "raw_content": 'strcat(sql_buf, " WHERE id = ")', "line_start": 12},
]

result = extractor.extract_dynamic_sql(
    variable_name="sql_buf",
    c_elements=c_elements,
    before_line=20,
    function_name="process_query"
)

if result:
    print(f"변수명: {result.variable_name}")
    print(f"재구성된 SQL: {result.reconstructed_sql}")
    print(f"신뢰도: {result.confidence}")
```

---

## 8. 호스트 변수 추출만 수행하기

SQL에서 호스트 변수만 추출하려면 `PyparsingProCParser`를 사용합니다:

```python
from sql_extractor.pyparsing_parser import get_sql_parser

parser = get_sql_parser()

sql = "EXEC SQL SELECT a, b INTO :out_a, :out_b FROM t WHERE x = :in_x AND y = :in_y"

# 모든 호스트 변수 추출
all_vars = parser.extract_all_host_variables(sql)
print(all_vars)  # [':out_a', ':out_b', ':in_x', ':in_y']

# 개별 호스트 변수 파싱
var_info = parser.parse_host_variable(":arr[10]")
print(var_info)  # {'name': 'arr', 'index': '10', 'indicator': None}

var_info = parser.parse_host_variable(":struct.field:indicator")
print(var_info)  # {'name': 'struct', 'member': 'field', 'indicator': 'indicator'}
```

---

## 9. 전체 워크플로우 예제

SQL 추출 → 호스트 변수 분류 → MyBatis 변환의 전체 과정:

```python
from sql_extractor import (
    TreeSitterSQLExtractor,
    MyBatisConverter,
    SQLIdGenerator
)
from sql_extractor.pyparsing_parser import get_sql_parser

# 초기화
ts_extractor = TreeSitterSQLExtractor()
parser = get_sql_parser()
converter = MyBatisConverter()
id_gen = SQLIdGenerator()

# Pro*C 소스 코드
code = """
void process_data() {
    EXEC SQL SELECT name INTO :out_name FROM users WHERE id = :in_id;
}
"""

# 1단계: SQL 블록 추출
sql_blocks = ts_extractor.extract_sql_blocks(code)

for block in sql_blocks:
    # 2단계: SQL 타입 결정
    sql_type = parser.determine_sql_type(block.text)
    
    # 3단계: 호스트 변수 분류
    input_vars, output_vars = parser.classify_host_variables(block.text, sql_type)
    
    # 4단계: ID 생성
    sql_id = id_gen.generate_id(sql_type)
    
    # 5단계: MyBatis 변환
    result = converter.convert_sql(
        sql=block.text,
        sql_type=sql_type,
        sql_id=sql_id,
        input_vars=input_vars,
        output_vars=output_vars
    )
    
    print(f"=== {sql_id} ===")
    print(f"원본: {block.text}")
    print(f"변환: {result.sql}")
    print(f"입력: {result.input_params}")
    print(f"출력: {result.output_fields}")
```

**출력 결과:**
```
=== select_0 ===
원본: EXEC SQL SELECT name INTO :out_name FROM users WHERE id = :in_id;
변환: SELECT name AS outName FROM users WHERE id = #{inId}
입력: ['inId']
출력: ['outName']
```

---

## 10. 호스트 변수 블랙리스트 설정

호스트 변수 추출 시 시간 포맷(`:MI`, `:SS`) 등이 잘못 추출되는 것을 방지하기 위해 블랙리스트를 설정할 수 있습니다.

### 기본 블랙리스트

기본적으로 다음 키워드들은 호스트 변수로 인식되지 않습니다:

| 카테고리 | 키워드 예시 | 설명 |
|---------|-----------|------|
| 시간 포맷 | `HH`, `HH12`, `HH24`, `MI`, `SS` | Oracle/DB2 시간 형식 |
| 날짜 포맷 | `DD`, `MM`, `YY`, `YYYY`, `MON` | Oracle/DB2 날짜 형식 |
| 기타 포맷 | `TZH`, `TZM`, `AM`, `PM` | 타임존, 오전/오후 |

### Config를 통한 블랙리스트 설정

```python
from sql_extractor import SQLExtractorConfig
from sql_extractor.pyparsing_parser import PyparsingProCParser

# Config로 블랙리스트 설정
config = SQLExtractorConfig(
    # 커스텀 블랙리스트 (사용자 정의)
    CUSTOM_HOST_VAR_BLACKLIST={'MY_CONSTANT', 'STATUS_ACTIVE', 'TYPE_NORMAL'},
    
    # DB2 특수 레지스터 블랙리스트 활성화
    USE_DB2_SPECIAL_REGISTERS_BLACKLIST=True,
    
    # 단일 문자 상수 (Y, N) 블랙리스트 활성화
    USE_SINGLE_CHAR_BLACKLIST=True,
    
    # 문자열 리터럴 내 호스트 변수 무시 (기본: True)
    IGNORE_VARS_IN_STRING_LITERALS=True,
)

# Config를 파서에 전달
parser = PyparsingProCParser(config=config)

sql = "SELECT * FROM users WHERE status = :ACTIVE AND type = :user_type"
vars = parser.extract_all_host_variables(sql)
print(vars)  # [':user_type'] - :ACTIVE는 제외됨
```

### DBMS 방언별 자동 블랙리스트

```python
# DB2 방언 설정 시 DB2 특수 레지스터 자동 블랙리스트
config = SQLExtractorConfig(DBMS_DIALECT='db2')

# PostgreSQL 방언 설정 시 타입명 자동 블랙리스트
config = SQLExtractorConfig(DBMS_DIALECT='postgresql')
```

### 런타임에 동적으로 블랙리스트 관리

```python
from sql_extractor.pyparsing_parser import get_sql_parser

parser = get_sql_parser()

# 블랙리스트에 키워드 추가
parser.add_to_blacklist({'MY_KEYWORD', 'ANOTHER_CONSTANT'})

# 블랙리스트에서 키워드 제거 (기본 키워드도 제거 가능)
parser.remove_from_blacklist({'HH'})

# 현재 블랙리스트 확인
print(parser.get_blacklist())
```

### 사용 예제: 시간 포맷 오인 방지

```python
from sql_extractor.pyparsing_parser import get_sql_parser

parser = get_sql_parser()

# HH12:MI:SS 형태의 시간 포맷이 있는 SQL
sql = "EXEC SQL SELECT name, TO_CHAR(created_at, 'HH24:MI:SS') INTO :out_name FROM users WHERE id = :in_id"

# 블랙리스트 덕분에 :MI, :SS는 추출되지 않음
all_vars = parser.extract_all_host_variables(sql)
print(all_vars)  # [':out_name', ':in_id']

input_vars, output_vars = parser.classify_host_variables(sql, 'select')
print(f"입력: {input_vars}")   # [':in_id']
print(f"출력: {output_vars}")  # [':out_name']
```

---

## 11. 파싱 모드 설정 (PARSER_MODE)

호스트 변수 추출 시 사용하는 파서를 선택할 수 있습니다.

### 파싱 모드 옵션

| 모드 | 설명 |
|------|------|
| `auto` (기본) | pyparsing 라이브러리가 설치되어 있으면 pyparsing 사용, 없으면 regex 사용 |
| `pyparsing` | pyparsing 강제 사용 (미설치 시 에러 발생) |
| `regex` | 정규식만 사용 (pyparsing 무시) |

### 사용법

```python
from sql_extractor import SQLExtractor, SQLExtractorConfig

# 1. 기본값 (auto): pyparsing 있으면 사용, 없으면 regex
extractor = SQLExtractor()
print(extractor.host_var_registry.use_pyparsing)  # True 또는 False

# 2. pyparsing 강제 사용 (없으면 RuntimeError 발생)
config = SQLExtractorConfig(PARSER_MODE="pyparsing")
extractor = SQLExtractor(config=config)

# 3. 정규식만 사용 (pyparsing 무시)
config = SQLExtractorConfig(PARSER_MODE="regex")
extractor = SQLExtractor(config=config)
```

### pyparsing vs regex 비교

| 항목 | pyparsing | regex |
|------|-----------|-------|
| 정확도 | ✅ 높음 (문법 기반) | ⚠️ 보통 (패턴 기반) |
| 블랙리스트 처리 | ✅ 정밀 (문자열 리터럴 인식) | ⚠️ 기본 (위치 기반) |
| 성능 | ⚠️ 약간 느림 | ✅ 빠름 |
| 의존성 | pyparsing 라이브러리 필요 | 없음 |
| 확장성 | ✅ 문법 규칙 추가 용이 | ⚠️ 정규식 패턴 추가 |

### pyparsing 설치

pyparsing 모드를 사용하려면 라이브러리를 설치해야 합니다:

```bash
pip install pyparsing
```

### 모드 확인

```python
from sql_extractor import SQLExtractor, SQLExtractorConfig

extractor = SQLExtractor()

# 현재 파서 모드 확인
print(f"설정된 모드: {extractor.config.PARSER_MODE}")
print(f"pyparsing 사용 여부: {extractor.host_var_registry.use_pyparsing}")
```

### HostVariableRegistry 직접 사용

```python
from sql_extractor import SQLExtractorConfig
from sql_extractor.registry import HostVariableRegistry

# pyparsing 모드로 직접 생성
config = SQLExtractorConfig(PARSER_MODE="auto")
registry = HostVariableRegistry(config=config)
registry.load_defaults()

# 호스트 변수 추출 (pyparsing 또는 regex 자동 선택)
sql = "SELECT name, age INTO :out_name, :out_age FROM users WHERE id = :in_id"
vars = registry.extract_all(sql)
print([v['raw'] for v in vars])  # [':out_name', ':out_age', ':in_id']

# 입출력 분류
input_vars, output_vars = registry.classify_by_direction(sql, 'select')
print(f"입력: {[v['raw'] for v in input_vars]}")   # [':in_id']
print(f"출력: {[v['raw'] for v in output_vars]}")  # [':out_name', ':out_age']
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
