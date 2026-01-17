# proc_parser 모듈 사용 가이드

Pro*C/C 소스 파일을 파싱하여 SQL, 함수, 변수, 매크로 등의 요소를 추출하는 모듈입니다.

## 설치 요구사항

```bash
pip install tree-sitter tree-sitter-c
```

## 기본 사용법

### 단일 파일 파싱

```python
from proc_parser import ProCParser

parser = ProCParser()
elements = parser.parse_file("sample.pc")

# 추출된 요소 타입별 출력
for el in elements:
    print(f"{el['type']}: {el.get('name', el.get('sql_id', ''))}")
```

### 디렉토리 일괄 처리

```python
from proc_parser import process_directory

# input_dir 내의 모든 .pc, .h 파일을 파싱하여
# output_dir에 타입별 JSONL 파일로 저장
process_directory("input_dir", "output_dir")
```

### CLI 사용

```bash
python main.py <input_dir> <output_dir>
```

## 추출되는 요소 타입

| 타입 | 설명 |
|------|------|
| `sql` | EXEC SQL 블록 |
| `function` | C 함수 정의 |
| `variable` | 변수 선언 |
| `struct` | 구조체 정의 |
| `function_call` | 함수 호출 |
| `include` | #include 지시문 |
| `macro` | #define 매크로 |
| `comment` | 주석 |
| `bam_call` | BAMCALL 구문 |
| `unknown` | 미분류 요소 |

## SQL 관계 플러그인

SQL 요소 간의 논리적 관계를 감지합니다. **sql_extractor.plugins**에서 제공됩니다:

- **CursorRelationshipPlugin**: DECLARE → OPEN → FETCH → CLOSE 커서 패턴
- **DynamicSQLRelationshipPlugin**: PREPARE → EXECUTE 동적 SQL 패턴
- **TransactionRelationshipPlugin**: SQL문 → COMMIT/ROLLBACK 트랜잭션 경계
- **ArrayDMLRelationshipPlugin**: FOR 절 배열 DML 패턴

## 플러그인 딕셔너리 구조

ProCParser는 플러그인을 카테고리별 딕셔너리로 관리합니다:

```python
parser = ProCParser()
print(parser.plugins.keys())
# ['naming', 'code_element', 'sql_relationship', 'element_enricher', 'sql_transform']
```

| 카테고리 | 플러그인 | 위치 |
|---------|---------|------|
| `naming` | SnakeToCamelPlugin | proc_parser |
| `code_element` | BamCallPlugin | proc_parser |
| `sql_relationship` | Cursor, DynamicSQL, Transaction, ArrayDML | sql_extractor |
| `element_enricher` | DocstringEnricherPlugin | proc_parser |
| `sql_transform` | CommentRemovalPlugin | sql_extractor |

## 커스텀 플러그인 작성

### ParserPlugin (구문 파싱)

```python
from proc_parser import ParserPlugin
import re

class MyCustomPlugin(ParserPlugin):
    def __init__(self):
        self._pattern = re.compile(r'MY_SYNTAX\((.*?)\);', re.DOTALL)
    
    @property
    def pattern(self):
        return self._pattern
    
    @property
    def element_type(self):
        return "my_syntax"
    
    def parse(self, match, content):
        line_start, line_end = self.get_line_range(match, content)
        return {
            "type": self.element_type,
            "args": match.group(1).strip(),
            "line_start": line_start,
            "line_end": line_end,
            "raw_content": match.group(0),
            "function": None
        }
```

### SQLRelationshipPlugin (SQL 관계 감지)

```python
from proc_parser import SQLRelationshipPlugin
from typing import List, Dict

class MyRelationshipPlugin(SQLRelationshipPlugin):
    def can_handle(self, sql_elements: List[Dict]) -> bool:
        # 처리 가능 여부 반환
        return any(el.get('sql_type') == 'MY_TYPE' for el in sql_elements)
    
    def extract_relationships(self, sql_elements: List[Dict], 
                             all_elements: List[Dict] = None) -> List[Dict]:
        # 관계 추출 로직
        return [{
            'relationship_id': 'my_rel_001',
            'relationship_type': 'MY_RELATIONSHIP',
            'sql_ids': ['sql_001', 'sql_002'],
            'metadata': {}
        }]
```

## 출력 예시

`sql.jsonl` 파일 내용:

```json
{"type": "sql", "sql_id": "sql_001", "sql_type": "SELECT", "normalized_sql": "SELECT * FROM users WHERE id = ?", "input_host_vars": [":user_id"], "output_host_vars": [":name", ":email"], "function": "get_user", "line_start": 45, "line_end": 48}
```

---

## Header Parser 모듈

C 헤더 파일을 파싱하여 구조체/STP 정보를 추출합니다.

### 기본 사용법

```python
from header_parser import HeaderParser

parser = HeaderParser(
    external_macros={"MAX_SIZE": 30},      # 매크로 값 주입
    count_field_mapping={"outrec1": "total"}  # count 필드 수동 매핑
)

# 파일에서 파싱
db_vars_info = parser.parse_file("sample.h")

# 또는 내용 직접 파싱
db_vars_info = parser.parse(header_content)
```

### 출력 구조

```python
{
    "spaa010p_inrec1": {
        "rfrnStrtDate": {
            "dtype": "String",
            "size": 9,
            "decimal": 0,
            "name": "rfrn_strt_date",
            "description": "조회시작일자"
        },
        # ...
    }
}
```

---

## OMM Generator 모듈

db_vars_info를 OMM 파일로 변환합니다.

```python
from omm_generator import OMMGenerator

generator = OMMGenerator(
    base_package="com.example.dao.dto",
    output_dir="./output/omm"
)

# 단일 생성
content = generator.generate(db_vars_info["spaa010p_inrec1"], "spaa010p_inrec1")

# 파일로 저장
generator.write(content, "spaa010p_inrec1")

# 전체 저장
generator.write_all(db_vars_info)
```

### 출력 포맷

```
OMM com.example.dao.dto.Spaa010pInrec1
< logicalName= "Spaa010pInrec1" description="Spaa010pInrec1" >
{
    String rfrnStrtDate < length = 9 description = "조회시작일자" > ;
    BigDecimal aNxtSqno < length = 11 description = "다음일련번호" > ;
}
```

---

## DBIO Generator 모듈

SQL 정보를 MyBatis XML로 변환합니다.

```python
from dbio_generator import DBIOGenerator

generator = DBIOGenerator(
    base_package="com.example.dao",
    datasource="MainDS",
    output_dir="./output/dbio"
)

sql_calls = [
    {
        "name": "selectAcntId",
        "sql_type": "select",
        "parsed_sql": "SELECT ACNT_ID FROM ...",
        "input_vars": ["acntNoCryp"],
        "output_vars": ["acntId"]
    }
]

id_to_path_map = {
    "selectAcntIdIn": "com.example.dto.SelectAcntIdIn",
    "selectAcntIdOut": "com.example.dto.SelectAcntIdOut"
}

content = generator.generate(sql_calls, id_to_path_map, "SPAA0010Dao")
generator.write(content, "SPAA0010Dao")
```

---

## 공통 설정 (shared_config)

타입 매핑을 중앙에서 관리합니다. 새 타입 추가 시 해당 파일만 수정:

| 파일 | 내용 |
|------|------|
| `shared_config/type_mappings.py` | C→Java, STP 타입 매핑 |
| `shared_config/sql_mappings.py` | SQL→MyBatis 태그 매핑 |
| `shared_config/naming_rules.py` | 네이밍 규칙, count 패턴 |
| `shared_config/logger.py` | Loguru 기반 로깅 설정 |

### 타입 매핑 수정 예시

```python
# shared_config/type_mappings.py

C_TO_JAVA_TYPE_MAP = {
    "int": ("Integer", "INTEGER"),
    "char": ("String", "VARCHAR"),
    "long": ("BigDecimal", "NUMERIC"),
    "double": ("BigDecimal", "DECIMAL"),
    # 새 타입 추가
    "my_type": ("MyJavaType", "MY_JDBC_TYPE"),
}
```

