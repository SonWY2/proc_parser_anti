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

SQL 요소 간의 논리적 관계를 감지합니다:

- **CursorRelationshipPlugin**: DECLARE → OPEN → FETCH → CLOSE 커서 패턴
- **DynamicSQLRelationshipPlugin**: PREPARE → EXECUTE 동적 SQL 패턴
- **TransactionRelationshipPlugin**: SQL문 → COMMIT/ROLLBACK 트랜잭션 경계
- **ArrayDMLRelationshipPlugin**: FOR 절 배열 DML 패턴

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
